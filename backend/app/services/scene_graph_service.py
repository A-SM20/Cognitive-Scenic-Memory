"""
Scene Graph service — Semantic Scene Graph (Phase 6).

Builds a directed graph of spatial relationships between objects using
NetworkX. Relationships are inferred from bounding-box geometry:

  ON, UNDER, LEFT_OF, RIGHT_OF, NEAR, CONTAINS, INSIDE,
  ABOVE, BELOW, ADJACENT

The graph is persisted to the ``spatial_relationships`` table and can
be queried per-scene or compared between scenes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from itertools import combinations

import networkx as nx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.object import ObjectRecord
from app.models.observation import ObservationRecord
from app.models.spatial_relationship import SpatialRelationshipRecord

logger = get_logger(__name__)

# ── Spatial heuristic thresholds ────────────────────────────────────

# Maximum pixel distance to qualify as NEAR
NEAR_THRESHOLD_PX = 150.0

# Maximum edge gap to qualify as ADJACENT
ADJACENT_GAP_PX = 20.0

# Vertical proximity for ON/UNDER (bottom-to-top distance)
ON_VERTICAL_PROXIMITY_PX = 25.0

# Minimum horizontal overlap ratio for ON/UNDER
ON_HORIZONTAL_OVERLAP_RATIO = 0.40

# Minimum area overlap ratio for CONTAINS/INSIDE
CONTAINMENT_AREA_RATIO = 0.65


def _bbox_overlap_x(a: dict, b: dict) -> float:
    """Compute horizontal overlap ratio of bbox A within B."""
    a_left, a_right = a["x"], a["x"] + a["w"]
    b_left, b_right = b["x"], b["x"] + b["w"]
    overlap = max(0.0, min(a_right, b_right) - max(a_left, b_left))
    return overlap / max(a["w"], 1.0)


def _bbox_overlap_y(a: dict, b: dict) -> float:
    """Compute vertical overlap ratio of bbox A within B."""
    a_top, a_bottom = a["y"], a["y"] + a["h"]
    b_top, b_bottom = b["y"], b["y"] + b["h"]
    overlap = max(0.0, min(a_bottom, b_bottom) - max(a_top, b_top))
    return overlap / max(a["h"], 1.0)


def _area_containment(inner: dict, outer: dict) -> float:
    """What fraction of 'inner' bbox is contained within 'outer'."""
    i_left, i_right = inner["x"], inner["x"] + inner["w"]
    i_top, i_bottom = inner["y"], inner["y"] + inner["h"]
    o_left, o_right = outer["x"], outer["x"] + outer["w"]
    o_top, o_bottom = outer["y"], outer["y"] + outer["h"]

    overlap_w = max(0.0, min(i_right, o_right) - max(i_left, o_left))
    overlap_h = max(0.0, min(i_bottom, o_bottom) - max(i_top, o_top))
    overlap_area = overlap_w * overlap_h
    inner_area = max(inner["w"] * inner["h"], 1.0)
    return overlap_area / inner_area


def _edge_gap(a: dict, b: dict) -> float:
    """Minimum pixel gap between bbox edges (0 if overlapping)."""
    a_left, a_right = a["x"], a["x"] + a["w"]
    a_top, a_bottom = a["y"], a["y"] + a["h"]
    b_left, b_right = b["x"], b["x"] + b["w"]
    b_top, b_bottom = b["y"], b["y"] + b["h"]

    gap_x = max(0.0, max(a_left - b_right, b_left - a_right))
    gap_y = max(0.0, max(a_top - b_bottom, b_top - a_bottom))
    return math.hypot(gap_x, gap_y)


def compute_relationships(obs_a: dict, obs_b: dict) -> list[dict]:
    """
    Compute all applicable spatial relationships from obs_a to obs_b.

    Each observation dict must have:
      object_id, class_name, center_x, center_y,
      bbox_x, bbox_y, bbox_w, bbox_h

    Returns list of {relationship_type, confidence, distance_px}.
    """
    relationships = []

    bbox_a = {"x": obs_a["bbox_x"], "y": obs_a["bbox_y"],
              "w": obs_a["bbox_w"], "h": obs_a["bbox_h"]}
    bbox_b = {"x": obs_b["bbox_x"], "y": obs_b["bbox_y"],
              "w": obs_b["bbox_w"], "h": obs_b["bbox_h"]}

    dist = math.hypot(
        obs_a["center_x"] - obs_b["center_x"],
        obs_a["center_y"] - obs_b["center_y"],
    )

    a_bottom = bbox_a["y"] + bbox_a["h"]
    b_top = bbox_b["y"]
    b_bottom = bbox_b["y"] + bbox_b["h"]
    a_top = bbox_a["y"]

    h_overlap = _bbox_overlap_x(bbox_a, bbox_b)

    # ── ON: A is on top of B (A's bottom near B's top, horizontal overlap) ──
    vertical_gap_on = abs(a_bottom - b_top)
    if (vertical_gap_on <= ON_VERTICAL_PROXIMITY_PX
            and h_overlap >= ON_HORIZONTAL_OVERLAP_RATIO
            and obs_a["center_y"] < obs_b["center_y"]):
        conf = max(0.3, 1.0 - vertical_gap_on / ON_VERTICAL_PROXIMITY_PX)
        relationships.append({
            "relationship_type": "ON",
            "confidence": round(conf, 3),
            "distance_px": round(dist, 1),
        })

    # ── UNDER: A is under B (inverse of ON) ──
    vertical_gap_under = abs(b_bottom - a_top)
    if (vertical_gap_under <= ON_VERTICAL_PROXIMITY_PX
            and h_overlap >= ON_HORIZONTAL_OVERLAP_RATIO
            and obs_a["center_y"] > obs_b["center_y"]):
        conf = max(0.3, 1.0 - vertical_gap_under / ON_VERTICAL_PROXIMITY_PX)
        relationships.append({
            "relationship_type": "UNDER",
            "confidence": round(conf, 3),
            "distance_px": round(dist, 1),
        })

    has_on = any(r["relationship_type"] == "ON" for r in relationships)
    has_under = any(r["relationship_type"] == "UNDER" for r in relationships)

    # ── LEFT_OF / RIGHT_OF (requires vertical overlap and local proximity) ──
    if dist <= 500:
        if obs_a["center_x"] < obs_b["center_x"]:
            x_diff = obs_b["center_x"] - obs_a["center_x"]
            if x_diff > 20:  # minimum separation to be meaningful
                v_overlap = _bbox_overlap_y(bbox_a, bbox_b)
                if v_overlap > 0.2:  # some vertical alignment
                    conf = min(1.0, 0.5 + v_overlap * 0.5)
                    relationships.append({
                        "relationship_type": "LEFT_OF",
                        "confidence": round(conf, 3),
                        "distance_px": round(dist, 1),
                    })
        elif obs_a["center_x"] > obs_b["center_x"]:
            x_diff = obs_a["center_x"] - obs_b["center_x"]
            if x_diff > 20:
                v_overlap = _bbox_overlap_y(bbox_a, bbox_b)
                if v_overlap > 0.2:
                    conf = min(1.0, 0.5 + v_overlap * 0.5)
                    relationships.append({
                        "relationship_type": "RIGHT_OF",
                        "confidence": round(conf, 3),
                        "distance_px": round(dist, 1),
                    })

    # ── ABOVE / BELOW (requires horizontal alignment, not already ON/UNDER, local proximity) ──
    if dist <= 500 and h_overlap > 0.15:
        if obs_a["center_y"] < obs_b["center_y"] and not has_on:
            y_diff = obs_b["center_y"] - obs_a["center_y"]
            if y_diff > 30:
                conf = min(1.0, 0.4 + h_overlap * 0.6)
                relationships.append({
                    "relationship_type": "ABOVE",
                    "confidence": round(conf, 3),
                    "distance_px": round(dist, 1),
                })
        elif obs_a["center_y"] > obs_b["center_y"] and not has_under:
            y_diff = obs_a["center_y"] - obs_b["center_y"]
            if y_diff > 30:
                conf = min(1.0, 0.4 + h_overlap * 0.6)
                relationships.append({
                    "relationship_type": "BELOW",
                    "confidence": round(conf, 3),
                    "distance_px": round(dist, 1),
                })

    # ── CONTAINS / INSIDE ──
    containment_ab = _area_containment(bbox_b, bbox_a)  # B inside A
    containment_ba = _area_containment(bbox_a, bbox_b)  # A inside B

    if containment_ab >= CONTAINMENT_AREA_RATIO and bbox_a["w"] * bbox_a["h"] > bbox_b["w"] * bbox_b["h"]:
        relationships.append({
            "relationship_type": "CONTAINS",
            "confidence": round(containment_ab, 3),
            "distance_px": round(dist, 1),
        })
    elif containment_ba >= CONTAINMENT_AREA_RATIO and bbox_b["w"] * bbox_b["h"] > bbox_a["w"] * bbox_a["h"]:
        relationships.append({
            "relationship_type": "INSIDE",
            "confidence": round(containment_ba, 3),
            "distance_px": round(dist, 1),
        })

    # ── NEAR ──
    if dist <= NEAR_THRESHOLD_PX:
        conf = max(0.3, 1.0 - dist / NEAR_THRESHOLD_PX)
        relationships.append({
            "relationship_type": "NEAR",
            "confidence": round(conf, 3),
            "distance_px": round(dist, 1),
        })

    # ── ADJACENT (edges very close but not overlapping significantly) ──
    gap = _edge_gap(bbox_a, bbox_b)
    if 0 < gap <= ADJACENT_GAP_PX:
        conf = max(0.5, 1.0 - gap / ADJACENT_GAP_PX)
        relationships.append({
            "relationship_type": "ADJACENT",
            "confidence": round(conf, 3),
            "distance_px": round(dist, 1),
        })

    return relationships


class SceneGraphService:
    """
    Builds and queries semantic scene graphs using NetworkX.

    Each scene gets a directed graph where nodes are observed objects
    and edges are inferred spatial relationships.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def build_scene_graph(self, scene_id: str) -> nx.DiGraph:
        """
        Build the scene graph for a given scene from its observations.

        1. Load all observations for the scene
        2. Compute pairwise spatial relationships
        3. Persist relationships to DB
        4. Return the NetworkX DiGraph

        Args:
            scene_id: The scene to build the graph for.

        Returns:
            NetworkX DiGraph with object nodes and relationship edges.
        """
        # Load observations
        stmt = select(ObservationRecord).where(
            ObservationRecord.scene_id == scene_id
        )
        result = await self._db.execute(stmt)
        observations = result.scalars().all()

        if not observations:
            logger.info("No observations for scene %s, empty graph", scene_id)
            return nx.DiGraph()

        # Load object records for status/display info
        obj_ids = [obs.object_id for obs in observations]
        obj_stmt = select(ObjectRecord).where(
            ObjectRecord.object_id.in_(obj_ids)
        )
        obj_result = await self._db.execute(obj_stmt)
        objects_by_id = {
            obj.object_id: obj
            for obj in obj_result.scalars().all()
        }

        # Build observation dicts
        obs_dicts = []
        for obs in observations:
            obj = objects_by_id.get(obs.object_id)
            obs_dicts.append({
                "object_id": obs.object_id,
                "class_name": obs.class_name,
                "center_x": obs.position_x,
                "center_y": obs.position_y,
                "bbox_x": obs.bbox_x,
                "bbox_y": obs.bbox_y,
                "bbox_w": obs.bbox_w,
                "bbox_h": obs.bbox_h,
                "confidence": obs.confidence,
                "status": obj.status if obj else "UNKNOWN",
                "display_name": obj.display_name if obj else obs.class_name,
            })

        # Build graph
        graph = nx.DiGraph()

        # Add nodes
        for od in obs_dicts:
            graph.add_node(od["object_id"], **od)

        # Compute pairwise relationships
        all_relationships = []
        for od_a, od_b in combinations(obs_dicts, 2):
            # A → B relationships
            rels_ab = compute_relationships(od_a, od_b)
            for rel in rels_ab:
                graph.add_edge(
                    od_a["object_id"],
                    od_b["object_id"],
                    key=rel["relationship_type"],
                    **rel,
                )
                all_relationships.append({
                    "source_object_id": od_a["object_id"],
                    "target_object_id": od_b["object_id"],
                    **rel,
                })

            # B → A relationships (for non-symmetric relations)
            rels_ba = compute_relationships(od_b, od_a)
            for rel in rels_ba:
                graph.add_edge(
                    od_b["object_id"],
                    od_a["object_id"],
                    key=rel["relationship_type"],
                    **rel,
                )
                all_relationships.append({
                    "source_object_id": od_b["object_id"],
                    "target_object_id": od_a["object_id"],
                    **rel,
                })

        # Persist to database (replace existing)
        await self._persist_relationships(scene_id, all_relationships)

        logger.info(
            "Scene graph built for %s: %d nodes, %d edges",
            scene_id, graph.number_of_nodes(), len(all_relationships),
        )

        return graph

    async def _persist_relationships(
        self,
        scene_id: str,
        relationships: list[dict],
    ) -> None:
        """Save spatial relationships to the database, replacing any existing ones."""
        # Delete existing relationships for this scene
        del_stmt = delete(SpatialRelationshipRecord).where(
            SpatialRelationshipRecord.scene_id == scene_id
        )
        await self._db.execute(del_stmt)

        # Insert new relationships
        for rel in relationships:
            record = SpatialRelationshipRecord(
                scene_id=scene_id,
                source_object_id=rel["source_object_id"],
                target_object_id=rel["target_object_id"],
                relationship_type=rel["relationship_type"],
                confidence=rel["confidence"],
                distance_px=rel.get("distance_px"),
            )
            self._db.add(record)

        await self._db.flush()

    async def get_scene_graph(self, scene_id: str) -> dict:
        """
        Load the persisted scene graph for a scene.

        Returns a dict with nodes and edges suitable for API response.
        """
        # Load observations for nodes
        obs_stmt = select(ObservationRecord).where(
            ObservationRecord.scene_id == scene_id
        )
        obs_result = await self._db.execute(obs_stmt)
        observations = obs_result.scalars().all()

        obj_ids = [obs.object_id for obs in observations]
        objects_by_id = {}
        if obj_ids:
            obj_stmt = select(ObjectRecord).where(
                ObjectRecord.object_id.in_(obj_ids)
            )
            obj_result = await self._db.execute(obj_stmt)
            objects_by_id = {
                obj.object_id: obj
                for obj in obj_result.scalars().all()
            }

        nodes = []
        for obs in observations:
            obj = objects_by_id.get(obs.object_id)
            nodes.append({
                "object_id": obs.object_id,
                "class_name": obs.class_name,
                "display_name": obj.display_name if obj else obs.class_name,
                "center_x": obs.position_x,
                "center_y": obs.position_y,
                "bbox_x": obs.bbox_x,
                "bbox_y": obs.bbox_y,
                "bbox_w": obs.bbox_w,
                "bbox_h": obs.bbox_h,
                "confidence": obs.confidence,
                "status": obj.status if obj else "UNKNOWN",
            })

        # Load relationships for edges
        rel_stmt = select(SpatialRelationshipRecord).where(
            SpatialRelationshipRecord.scene_id == scene_id
        )
        rel_result = await self._db.execute(rel_stmt)
        rels = rel_result.scalars().all()

        edges = []
        for rel in rels:
            src_obj = objects_by_id.get(rel.source_object_id)
            tgt_obj = objects_by_id.get(rel.target_object_id)
            edges.append({
                "source_object_id": rel.source_object_id,
                "target_object_id": rel.target_object_id,
                "source_class": src_obj.class_name if src_obj else None,
                "target_class": tgt_obj.class_name if tgt_obj else None,
                "relationship_type": rel.relationship_type,
                "confidence": rel.confidence,
                "distance_px": rel.distance_px,
            })

        return {
            "scene_id": scene_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    async def get_relationships(self, scene_id: str) -> list[SpatialRelationshipRecord]:
        """Load all spatial relationships for a scene."""
        stmt = select(SpatialRelationshipRecord).where(
            SpatialRelationshipRecord.scene_id == scene_id
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
