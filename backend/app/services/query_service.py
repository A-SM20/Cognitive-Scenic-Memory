"""
Cognitive Query & Chatbot Service.

Provides natural language understanding and structured reasoning over:
1. Detected objects and persistent memory (locations, confidences, lifecycle states).
2. Spatial relationships in semantic scene graphs (ON, NEAR, LEFT_OF, RIGHT_OF, etc.).
3. Environment changes when comparing two scenes (ADDED, REMOVED, MOVED, REPLACED).
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.scene import SceneRecord
from app.models.object import ObjectRecord
from app.models.observation import ObservationRecord
from app.models.spatial_relationship import SpatialRelationshipRecord
from app.models.change_event import ChangeEventRecord
from app.services.change_detection_service import ChangeDetectionService
from app.services.scene_graph_service import SceneGraphService

logger = get_logger(__name__)

RELATION_PHRASES = {
    "LEFT_OF": "to the left of the",
    "RIGHT_OF": "to the right of the",
    "ON": "on top of the",
    "UNDER": "under the",
    "ABOVE": "above the",
    "BELOW": "below the",
    "NEAR": "near the",
    "ADJACENT": "next to the",
    "CONTAINS": "contains the",
    "INSIDE": "inside the",
    "BEHIND": "behind the",
    "IN_FRONT_OF": "in front of the",
}


def _extract_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """Extract (X, Y) coordinates from text like '(172, 357)', 'at 172, 357', '172, 357'."""
    patterns = [
        r"\(\s*(?:x\s*[:=]\s*)?(-?\d+(?:\.\d+)?)\s*,\s*(?:y\s*[:=]\s*)?(-?\d+(?:\.\d+)?)\s*\)",
        r"(?:at|position|coord|coordinates|near|around)\s+(?:x\s*[:=]\s*)?(-?\d+(?:\.\d+)?)\s*,\s*(?:y\s*[:=]\s*)?(-?\d+(?:\.\d+)?)",
        r"(?:^|\s)(-?\d{2,4}(?:\.\d+)?)\s*,\s*(-?\d{2,4}(?:\.\d+)?)(?:\s|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
    return None


def _extract_object_id(text: str) -> Optional[str]:
    """Extract object IDs like OBJ-1234ABCD from query text."""
    m = re.search(r"\bOBJ-[A-Za-z0-9]+\b", text, re.IGNORECASE)
    return m.group(0).upper() if m else None


def _direction_from_offset(dx: float, dy: float) -> str:
    """Computes human-friendly relative direction from source (0,0) to target (dx, dy)."""
    dir_parts = []
    # In camera/image coordinates, Y increases downwards:
    # dy < -30 => target is higher in image (behind / above)
    # dy > 30 => target is lower in image (in front / below)
    if dy < -30:
        dir_parts.append("behind / above")
    elif dy > 30:
        dir_parts.append("in front / below")

    if dx < -30:
        dir_parts.append("to the left")
    elif dx > 30:
        dir_parts.append("to the right")

    return " and ".join(dir_parts) if dir_parts else "adjacent"



def _join_natural_list(items: list[str]) -> str:
    """Joins a list of phrases into natural English: 'A and B' or 'A, B, and C'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _fuzzy_match_token(token: str, candidates: list[str]) -> Optional[str]:
    """Matches a token to candidate class names with typo tolerance (e.g. 'char' -> 'chair')."""
    t = token.lower().strip()
    if not t or len(t) < 3:
        return None

    # Exact or substring match
    for cand in candidates:
        c_low = cand.lower()
        if t == c_low or t in c_low or c_low in t:
            return cand

    # Character set similarity for common typos
    for cand in candidates:
        c_low = cand.lower()
        overlap = len(set(t) & set(c_low))
        if overlap >= max(len(t) - 1, 3) and abs(len(t) - len(c_low)) <= 2:
            return cand

    return None


class QueryService:
    """Answers user questions regarding objects, spatial relations, and scene changes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def answer_query(
        self,
        query: str,
        scene_id: Optional[str] = None,
        scene_before_id: Optional[str] = None,
        scene_after_id: Optional[str] = None,
    ) -> dict:
        """
        Processes a natural language query and returns an intelligent response with evidence.
        """
        q = query.strip()
        q_lower = q.lower()

        # 1. Check for coordinate-based query or specific object ID query
        coords = _extract_coordinates(q)
        obj_id = _extract_object_id(q)
        if coords or obj_id:
            return await self._handle_coordinate_or_id_query(
                q, coords=coords, target_object_id=obj_id, scene_id=scene_id
            )

        # 2. Check for spatial relationship / location query intent
        # (e.g. "what's next to the chair", "what is near the person", "is cup on table")
        if self._is_relationship_intent(q_lower):
            return await self._handle_relationship_query(q_lower, scene_id)

        # 3. Check for explicit scene comparison intent
        if self._is_comparison_intent(q_lower, scene_before_id, scene_after_id):
            return await self._handle_comparison_query(q, scene_before_id, scene_after_id)

        # 4. Check for object location / count / inventory intent
        if self._is_object_query_intent(q_lower):
            return await self._handle_object_query(q_lower, scene_id)

        # 5. Check for system overview / summary intent
        if any(w in q_lower for w in ["summary", "overview", "what do you know", "status", "report", "health"]):
            return await self._handle_overview_query()

        # 6. Default fallback search across all memory
        return await self._handle_general_search(q, scene_id)

    def _is_comparison_intent(self, q: str, before: Optional[str], after: Optional[str]) -> bool:
        """Check if query is asking to compare scenes or ask about changes."""
        keywords = ["compare", "comparison", "what changed", "changes between", "difference between", "diff between", "what was added", "what was removed"]
        if any(k in q for k in keywords):
            return True
        if before and after and q.startswith("compare"):
            return True
        if "between" in q and ("scene" in q or "scan" in q):
            return True
        return False

    def _is_relationship_intent(self, q: str) -> bool:
        """Check if query asks about spatial relationships or layout."""
        keywords = ["near", "next to", "beside", "on top", "under", "left of", "right of", "relationship", "relation", "layout", "relative to", "close to", "around", "behind", "in front"]
        return any(k in q for k in keywords)

    def _is_object_query_intent(self, q: str) -> bool:
        """Check if query asks where an object is or counts items."""
        keywords = ["where", "how many", "count", "find", "locate", "seen", "detected", "which objects", "what objects", "list objects"]
        return any(k in q for k in keywords)

    async def _extract_scene_ids(self, q: str) -> tuple[Optional[str], Optional[str]]:
        """Extract scene IDs mentioned in the query text (e.g. SCENE-1234)."""
        pattern = r"SCENE-[A-Za-z0-9]+"
        matches = re.findall(pattern, q, re.IGNORECASE)
        # Normalize uppercase
        matches = [m.upper() for m in matches]
        if len(matches) >= 2:
            return matches[0], matches[1]
        elif len(matches) == 1:
            return matches[0], None
        return None, None

    async def _get_latest_two_scenes(self) -> tuple[Optional[str], Optional[str]]:
        """Fetch the two most recent scene IDs from the database."""
        stmt = select(SceneRecord.scene_id).order_by(desc(SceneRecord.timestamp)).limit(2)
        res = await self.db.execute(stmt)
        rows = res.scalars().all()
        if len(rows) >= 2:
            # Earlier scene is second, latest scene is first
            return rows[1], rows[0]
        elif len(rows) == 1:
            return rows[0], None
        return None, None

    async def _handle_comparison_query(
        self,
        q: str,
        scene_before_id: Optional[str],
        scene_after_id: Optional[str],
    ) -> dict:
        """Handles comparisons between two scenes or recent change queries."""
        before_id = scene_before_id
        after_id = scene_after_id

        # Try extracting from text if not provided
        if not before_id or not after_id:
            extracted_before, extracted_after = await self._extract_scene_ids(q)
            if extracted_before and extracted_after:
                before_id, after_id = extracted_before, extracted_after
            elif extracted_before and not before_id:
                before_id = extracted_before

        # If still missing, default to the two most recent scenes
        if not before_id or not after_id:
            recent_before, recent_after = await self._get_latest_two_scenes()
            before_id = before_id or recent_before
            after_id = after_id or recent_after

        if not before_id or not after_id or before_id == after_id:
            return {
                "query": q,
                "answer": "To compare scenes, at least two distinct scenes are needed. I currently only have one or zero scenes recorded in memory. Capture another view or specify two valid Scene IDs (e.g., 'Compare SCENE-A and SCENE-B').",
                "confidence": 0.85,
                "supporting_evidence": ["Insufficient scenes for pairwise comparison."],
                "context": {"type": "comparison_failed"},
                "timestamp": datetime.now(timezone.utc),
            }

        # Run comparison service
        change_svc = ChangeDetectionService(self.db)
        changes = await change_svc.compare_scenes(before_id, after_id)

        # Categorize changes
        added = [c for c in changes if c.change_type == "ADDED"]
        removed = [c for c in changes if c.change_type == "REMOVED"]
        moved = [c for c in changes if c.change_type == "MOVED"]
        replaced = [c for c in changes if c.change_type == "REPLACED"]
        confidence_changed = [c for c in changes if c.change_type == "CONFIDENCE_CHANGED"]

        evidence = [
            f"Comparing Earlier Scene: {before_id} vs Later Scene: {after_id}",
            f"Total Changes Detected: {len(changes)}",
        ]

        if not changes:
            answer = (
                f"When comparing scene **{before_id}** and **{after_id}**, I found that nothing changed. "
                f"All detected objects remained in their exact positions across both scans."
            )
        else:
            # Build conversational summary sentences
            narrative_items = []
            if added:
                added_names = [f"a new **{c.description.replace('Added ', '')}**" for c in added]
                narrative_items.append(f"{_join_natural_list(added_names)} was added to the room")
            if moved:
                moved_items = []
                for c in moved:
                    clean = c.description.replace("Moved ", "").replace(" pixels", "px")
                    moved_items.append(f"the **{clean}**")
                narrative_items.append(f"{_join_natural_list(moved_items)} moved")
            if removed:
                rem_names = [f"the **{c.description.replace('Removed ', '')}**" for c in removed]
                narrative_items.append(f"{_join_natural_list(rem_names)} was removed")
            if replaced:
                rep_names = [c.description for c in replaced]
                narrative_items.append(f"{_join_natural_list(rep_names)}")

            lead_sentence = f"When comparing **{before_id}** and **{after_id}**, {', while '.join(narrative_items)}."

            # Append concise breakdown list
            bullet_list = [f"- {c.description}" for c in changes]
            answer = f"{lead_sentence}\n\n**Detailed Changes ({len(changes)}):**\n" + "\n".join(bullet_list)

        return {
            "query": q,
            "answer": answer,
            "confidence": 0.95,
            "supporting_evidence": evidence,
            "context": {
                "type": "scene_comparison",
                "scene_before_id": before_id,
                "scene_after_id": after_id,
                "total_changes": len(changes),
                "summary": {
                    "added": len(added),
                    "removed": len(removed),
                    "moved": len(moved),
                    "replaced": len(replaced),
                },
            },
            "timestamp": datetime.now(timezone.utc),
        }

    async def _handle_coordinate_or_id_query(
        self,
        q: str,
        coords: Optional[Tuple[float, float]] = None,
        target_object_id: Optional[str] = None,
        scene_id: Optional[str] = None,
    ) -> dict:
        """
        Handles queries asking about what is located at or near specific (X, Y) coordinates
        or around a specific object ID (e.g. 'what all was near the person at (172,357)').
        """
        target_scene_id = scene_id
        if not target_scene_id:
            extracted_scene, _ = await self._extract_scene_ids(q)
            target_scene_id = extracted_scene

        # Default to latest scene if not explicitly specified
        if not target_scene_id:
            stmt = select(SceneRecord.scene_id).order_by(desc(SceneRecord.timestamp)).limit(1)
            res = await self.db.execute(stmt)
            target_scene_id = res.scalar_one_or_none()

        if not target_scene_id:
            return {
                "query": q,
                "answer": "I don't have any scenes stored in memory yet to query coordinates against. Please capture a scan or process an image first.",
                "confidence": 0.5,
                "supporting_evidence": [],
                "context": {"type": "no_scenes"},
                "timestamp": datetime.now(timezone.utc),
            }

        # Fetch all observations for this scene
        obs_stmt = select(ObservationRecord).where(ObservationRecord.scene_id == target_scene_id)
        obs_res = await self.db.execute(obs_stmt)
        observations = obs_res.scalars().all()

        if not observations:
            return {
                "query": q,
                "answer": f"In scene **{target_scene_id}**, no object observations were recorded.",
                "confidence": 0.6,
                "supporting_evidence": [f"Scene: {target_scene_id}"],
                "context": {"type": "no_observations", "scene_id": target_scene_id},
                "timestamp": datetime.now(timezone.utc),
            }

        # Fetch spatial relationships for this scene
        rel_stmt = select(SpatialRelationshipRecord).where(SpatialRelationshipRecord.scene_id == target_scene_id)
        rel_res = await self.db.execute(rel_stmt)
        all_rels = rel_res.scalars().all()

        # Resolve target observation
        target_obs = None
        min_target_dist = float("inf")

        if target_object_id:
            target_obs = next((o for o in observations if o.object_id.upper() == target_object_id.upper()), None)

        if not target_obs and coords:
            qx, qy = coords
            # Check if user mentioned an object class (e.g. "person" in "near the person at (172,357)")
            unique_classes = set(o.class_name.lower() for o in observations if o.class_name)
            class_candidates = [cls for cls in unique_classes if cls in q.lower()]

            search_pool = observations
            if class_candidates:
                search_pool = [o for o in observations if o.class_name and o.class_name.lower() in class_candidates]

            for o in search_pool:
                d = math.hypot(o.position_x - qx, o.position_y - qy)
                if d < min_target_dist:
                    min_target_dist = d
                    target_obs = o

            # If closest in filtered pool is very far, fall back to overall closest
            if min_target_dist > 300.0 and search_pool != observations:
                for o in observations:
                    d = math.hypot(o.position_x - qx, o.position_y - qy)
                    if d < min_target_dist:
                        min_target_dist = d
                        target_obs = o

        ref_x = target_obs.position_x if target_obs else (coords[0] if coords else 0.0)
        ref_y = target_obs.position_y if target_obs else (coords[1] if coords else 0.0)

        if target_obs:
            ref_label = f"the **{target_obs.class_name} at ({target_obs.position_x:.0f}, {target_obs.position_y:.0f})**"
        elif coords:
            ref_label = f"coordinates **({coords[0]:.0f}, {coords[1]:.0f})**"
        else:
            ref_label = f"object `{target_object_id}`"

        # Compute neighbors relative to reference point
        neighbors = []
        for o in observations:
            if target_obs and o.object_id == target_obs.object_id:
                continue

            dx = o.position_x - ref_x
            dy = o.position_y - ref_y
            dist = math.hypot(dx, dy)
            direction_phrase = _direction_from_offset(dx, dy)

            # Check explicit spatial relationships
            explicit_rels = []
            if target_obs:
                for r in all_rels:
                    if r.source_object_id == target_obs.object_id and r.target_object_id == o.object_id:
                        explicit_rels.append(r.relationship_type)
                    elif r.source_object_id == o.object_id and r.target_object_id == target_obs.object_id:
                        # Inverse
                        pass

            neighbors.append({
                "object_id": o.object_id,
                "class_name": o.class_name,
                "x": o.position_x,
                "y": o.position_y,
                "dist": dist,
                "dir": direction_phrase,
                "relations": explicit_rels,
                "confidence": o.confidence,
            })

        # Sort by distance
        neighbors.sort(key=lambda n: n["dist"])

        evidence = [f"Scene: {target_scene_id}"]
        if target_obs:
            evidence.append(
                f"Target: {target_obs.class_name} ({target_obs.object_id}) at "
                f"({target_obs.position_x:.1f}, {target_obs.position_y:.1f}), conf: {target_obs.confidence:.2f}"
            )
        elif coords:
            evidence.append(f"Coordinates: ({coords[0]:.1f}, {coords[1]:.1f})")

        # Build natural human-sounding sentences
        lines = []
        lines.append(f"In scene **{target_scene_id}**, near {ref_label}, I found the following surrounding objects:\n")

        for n in neighbors[:6]:
            rel_note = ""
            if "NEAR" in n["relations"] or n["dist"] < 120.0:
                rel_note = " (close nearby)"
            elif "ADJACENT" in n["relations"]:
                rel_note = " (directly adjacent)"

            lines.append(
                f"- A **{n['class_name']} at ({n['x']:.0f}, {n['y']:.0f})** is about {n['dist']:.0f}px {n['dir']}{rel_note}."
            )
            evidence.append(
                f"Neighbor: {n['class_name']} ({n['object_id']}) at ({n['x']:.1f}, {n['y']:.1f}) - {n['dist']:.1f}px {n['dir']}"
            )

        # Contextual summary sentence
        immediate = [n for n in neighbors if n["dist"] < 180.0]
        if len(immediate) >= 2:
            left_objs = [n for n in immediate if "left" in n["dir"]]
            right_objs = [n for n in immediate if "right" in n["dir"]]
            if left_objs and right_objs:
                l = left_objs[0]
                r = right_objs[0]
                lines.append(
                    f"\nIt is centrally positioned between the **{l['class_name']} at ({l['x']:.0f}, {l['y']:.0f})** to its left and the **{r['class_name']} at ({r['x']:.0f}, {r['y']:.0f})** to its right."
                )
        elif immediate:
            first = immediate[0]
            lines.append(
                f"\nIts nearest neighbor is the **{first['class_name']} at ({first['x']:.0f}, {first['y']:.0f})**, located {first['dist']:.0f}px away {first['dir']}."
            )

        answer = "\n".join(lines)

        return {
            "query": q,
            "answer": answer,
            "confidence": 0.95,
            "supporting_evidence": evidence[:10],
            "context": {
                "type": "coordinate_spatial_query",
                "scene_id": target_scene_id,
                "target_object_id": target_obs.object_id if target_obs else None,
                "target_class": target_obs.class_name if target_obs else None,
                "coords": [ref_x, ref_y],
                "nearby_count": len(neighbors),
            },
            "timestamp": datetime.now(timezone.utc),
        }

    async def _handle_relationship_query(self, q: str, scene_id: Optional[str]) -> dict:
        """Answers spatial relationship questions in natural, human conversational English."""
        target_scene_id = scene_id
        if not target_scene_id:
            extracted_scene, _ = await self._extract_scene_ids(q)
            target_scene_id = extracted_scene

        # If still no scene specified, grab the latest scene
        if not target_scene_id:
            stmt = select(SceneRecord.scene_id).order_by(desc(SceneRecord.timestamp)).limit(1)
            res = await self.db.execute(stmt)
            target_scene_id = res.scalar_one_or_none()

        if not target_scene_id:
            return {
                "query": q,
                "answer": "I don't have any scenes stored in memory yet. Please run a scan or upload an image first.",
                "confidence": 0.5,
                "supporting_evidence": [],
                "context": {"type": "no_scenes"},
                "timestamp": datetime.now(timezone.utc),
            }

        # Fetch observations and spatial relationships for this scene
        obs_stmt = select(ObservationRecord).where(ObservationRecord.scene_id == target_scene_id)
        obs_res = await self.db.execute(obs_stmt)
        observations = obs_res.scalars().all()

        stmt = (
            select(
                SpatialRelationshipRecord,
                ObjectRecord.class_name.label("source_class"),
            )
            .join(ObjectRecord, SpatialRelationshipRecord.source_object_id == ObjectRecord.object_id)
            .where(SpatialRelationshipRecord.scene_id == target_scene_id)
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        # Target object classes map
        target_ids = [r[0].target_object_id for r in rows]
        target_class_map = {}
        if target_ids:
            t_stmt = select(ObjectRecord.object_id, ObjectRecord.class_name).where(ObjectRecord.object_id.in_(target_ids))
            t_res = await self.db.execute(t_stmt)
            target_class_map = dict(t_res.all())

        # Collect all unique class names present in this scene
        all_scene_classes = set(o.class_name.lower() for o in observations if o.class_name)
        for r in rows:
            if r.source_class:
                all_scene_classes.add(r.source_class.lower())
            t_cls = target_class_map.get(r[0].target_object_id)
            if t_cls:
                all_scene_classes.add(t_cls.lower())

        # Match subject from query tokens, filtering out stopwords
        stopwords = {
            "what", "whats", "near", "next", "beside", "left", "right", "where", "find",
            "tell", "show", "from", "with", "scene", "scenes", "between", "have", "been",
            "there", "about", "the", "this", "that", "are", "and", "is", "any", "look"
        }
        tokens = [t for t in re.findall(r"\b[a-z]{3,}\b", q) if t not in stopwords]

        matched_class = None
        for t in tokens:
            match = _fuzzy_match_token(t, list(all_scene_classes))
            if match:
                matched_class = match
                break

        evidence = [f"Scene Analyzed: {target_scene_id}"]

        if matched_class:
            # Check observations of matched class in this scene
            matching_obs = [o for o in observations if o.class_name and o.class_name.lower() == matched_class]

            # If there's exactly 1 observation of that class, provide detailed surrounding neighborhood
            if len(matching_obs) == 1:
                target = matching_obs[0]
                neighbors = []
                for other in observations:
                    if other.object_id == target.object_id:
                        continue
                    dx = other.position_x - target.position_x
                    dy = other.position_y - target.position_y
                    dist = math.hypot(dx, dy)
                    neighbors.append({
                        "class_name": other.class_name,
                        "x": other.position_x,
                        "y": other.position_y,
                        "dist": dist,
                        "dir": _direction_from_offset(dx, dy),
                    })
                neighbors.sort(key=lambda n: n["dist"])

                neighbor_descriptions = []
                for n in neighbors[:4]:
                    neighbor_descriptions.append(f"{n['dir']} the **{n['class_name']}** ({n['dist']:.0f}px away)")
                    evidence.append(f"{matched_class} -> {n['class_name']} ({n['dir']}, {n['dist']:.0f}px)")

                if neighbor_descriptions:
                    answer = (
                        f"In scene **{target_scene_id}**, the **{matched_class}** at coordinates "
                        f"**({target.position_x:.0f}, {target.position_y:.0f})** is situated "
                        f"{_join_natural_list(neighbor_descriptions)}."
                    )
                else:
                    answer = f"In scene **{target_scene_id}**, the **{matched_class}** is isolated with no other objects nearby."

            elif len(matching_obs) > 1:
                # Multiple instances of that class (e.g. multiple persons or chairs)
                lines = [f"In scene **{target_scene_id}**, there are {len(matching_obs)} **{matched_class}** instances:\n"]
                for i, target in enumerate(matching_obs[:4], start=1):
                    # Find closest other object
                    closest_other = None
                    min_d = float("inf")
                    for other in observations:
                        if other.object_id == target.object_id:
                            continue
                        d = math.hypot(other.position_x - target.position_x, other.position_y - target.position_y)
                        if d < min_d:
                            min_d = d
                            closest_other = other

                    if closest_other:
                        dx = closest_other.position_x - target.position_x
                        dy = closest_other.position_y - target.position_y
                        dir_phrase = _direction_from_offset(dx, dy)
                        lines.append(
                            f"- **{matched_class.capitalize()} #{i} at ({target.position_x:.0f}, {target.position_y:.0f})**: "
                            f"situated {min_d:.0f}px away, {dir_phrase} a **{closest_other.class_name} at ({closest_other.position_x:.0f}, {closest_other.position_y:.0f})**."
                        )
                    else:
                        lines.append(f"- **{matched_class.capitalize()} #{i} at ({target.position_x:.0f}, {target.position_y:.0f})**.")
                    evidence.append(f"Instance #{i}: {matched_class} at ({target.position_x:.0f}, {target.position_y:.0f})")

                lines.append("\nYou can ask about a specific one by mentioning its coordinates, e.g. *'what is near the person at (172, 357)'*!")
                answer = "\n".join(lines)

            else:
                answer = (
                    f"In scene **{target_scene_id}**, I could not find any active detections for **{matched_class}**."
                )

        else:
            # General query: Group relationships by subject into natural conversational sentences
            by_subject = {}
            for rel, s_class in rows:
                if not s_class:
                    continue
                t_class = target_class_map.get(rel.target_object_id, "object")
                phrase_prep = RELATION_PHRASES.get(rel.relationship_type, f"{rel.relationship_type.replace('_', ' ').lower()} the")
                by_subject.setdefault(s_class, []).append(f"{phrase_prep} **{t_class}**")
                evidence.append(f"{s_class} {rel.relationship_type} {t_class}")

            if by_subject:
                sentences = []
                for subj, phrases in list(by_subject.items())[:4]:
                    deduped = list(dict.fromkeys(phrases))[:3]
                    sentences.append(f"the **{subj}** is {_join_natural_list(deduped)}")

                answer = f"In scene **{target_scene_id}**, {'. '.join([s.capitalize() for s in sentences])}."
            elif observations:
                # Describe overall room layout from observations
                items = [f"**{o.class_name}** at ({o.position_x:.0f}, {o.position_y:.0f})" for o in observations[:5]]
                answer = f"In scene **{target_scene_id}**, I detected {len(observations)} objects: {', '.join(items)}."
            else:
                answer = f"In scene **{target_scene_id}**, no spatial relationships were found between detected objects."

        return {
            "query": q,
            "answer": answer,
            "confidence": 0.95 if (rows or observations) else 0.60,
            "supporting_evidence": evidence[:10],
            "context": {
                "type": "spatial_relationships",
                "scene_id": target_scene_id,
                "matched_class": matched_class,
                "count": len(rows),
            },
            "timestamp": datetime.now(timezone.utc),
        }

    async def _handle_object_query(self, q: str, scene_id: Optional[str]) -> dict:
        """Answers where an object is or counts of objects."""
        # Find active objects in memory
        stmt = select(ObjectRecord).where(ObjectRecord.status == "ACTIVE").order_by(ObjectRecord.last_seen.desc())
        res = await self.db.execute(stmt)
        active_objects = res.scalars().all()

        # Find matching class names
        tokens = re.findall(r"\b[a-z]{3,}\b", q)
        matched = []
        for obj in active_objects:
            cname = (obj.class_name or "").lower()
            dname = (obj.display_name or "").lower()
            if any(t in cname or t in dname for t in tokens if t not in ["where", "many", "count", "find", "locate", "what", "seen"]):
                matched.append(obj)

        evidence = [f"Total Active Objects in Room: {len(active_objects)}"]

        if "how many" in q or "count" in q:
            if matched:
                cname = matched[0].class_name
                count = len(matched)
                answer = f"There are currently **{count} {cname}(s)** active in the room's persistent memory."
                for o in matched:
                    evidence.append(f"{o.object_id}: {o.class_name} at ({o.last_position_x:.0f}, {o.last_position_y:.0f})")
            else:
                # Group by class
                class_counts = {}
                for o in active_objects:
                    class_counts[o.class_name] = class_counts.get(o.class_name, 0) + 1
                breakdown = ", ".join([f"**{count} {cls}**" for cls, count in class_counts.items()])
                answer = f"The robot currently tracks **{len(active_objects)} total objects** in the room:\n{breakdown or 'No objects currently detected.'}"
        elif matched:
            target = matched[0]
            # Fetch latest observation for bbox & scene
            obs_stmt = (
                select(ObservationRecord)
                .where(ObservationRecord.object_id == target.object_id)
                .order_by(ObservationRecord.timestamp.desc())
                .limit(1)
            )
            obs_res = await self.db.execute(obs_stmt)
            latest_obs = obs_res.scalar_one_or_none()

            scene_ref = f"scene **{latest_obs.scene_id}**" if latest_obs else "the latest scan"
            pos_x = target.last_position_x or (latest_obs.position_x if latest_obs else 0.0)
            pos_y = target.last_position_y or (latest_obs.position_y if latest_obs else 0.0)

            # Check if it has any spatial relationships to describe context
            rel_stmt = (
                select(SpatialRelationshipRecord.relationship_type, ObjectRecord.class_name)
                .join(ObjectRecord, SpatialRelationshipRecord.target_object_id == ObjectRecord.object_id)
                .where(SpatialRelationshipRecord.source_object_id == target.object_id)
                .limit(2)
            )
            rel_res = await self.db.execute(rel_stmt)
            relations = rel_res.all()

            rel_text = ""
            if relations:
                phrases = []
                for r in relations:
                    prep = RELATION_PHRASES.get(r[0], f"{r[0].replace('_', ' ').lower()} the")
                    phrases.append(f"{prep} **{r[1]}**")
                deduped_phrases = list(dict.fromkeys(phrases))
                rel_text = f", situated {_join_natural_list(deduped_phrases)}"

            answer = (
                f"The **{target.class_name}** (`{target.object_id}`) was last observed in {scene_ref} "
                f"at coordinates **(X: {pos_x:.0f}, Y: {pos_y:.0f})**{rel_text}. "
                f"Current cognitive confidence is **{target.current_confidence * 100:.1f}%** "
                f"with {target.observation_count} total observation(s)."
            )
            evidence.append(f"Object ID: {target.object_id}")
            evidence.append(f"Confidence: {target.current_confidence:.2f}")
            if latest_obs:
                evidence.append(f"Bounding Box: [{latest_obs.bbox_x:.0f}, {latest_obs.bbox_y:.0f}, {latest_obs.bbox_w:.0f}, {latest_obs.bbox_h:.0f}]")
        else:
            # If no specific object matched, list all active
            items = [f"- **{o.class_name}** (`{o.object_id}`) at ({o.last_position_x:.0f}, {o.last_position_y:.0f})" for o in active_objects[:8]]
            answer = (
                f"I could not pinpoint the specific object you requested. "
                f"Here are the active objects currently tracked in the room:\n"
                + ("\n".join(items) if items else "No active objects currently tracked.")
            )

        return {
            "query": q,
            "answer": answer,
            "confidence": 0.92 if matched else 0.70,
            "supporting_evidence": evidence,
            "context": {"type": "object_location", "matched_count": len(matched)},
            "timestamp": datetime.now(timezone.utc),
        }

    async def _handle_overview_query(self) -> dict:
        """Answers high-level overview questions about the environment."""
        scene_count_res = await self.db.execute(select(func.count(SceneRecord.id)))
        scene_count = scene_count_res.scalar_one() or 0

        obj_count_res = await self.db.execute(
            select(func.count(ObjectRecord.id)).where(ObjectRecord.status == "ACTIVE")
        )
        active_count = obj_count_res.scalar_one() or 0

        change_count_res = await self.db.execute(select(func.count(ChangeEventRecord.id)))
        change_count = change_count_res.scalar_one() or 0

        # Latest scene
        stmt = select(SceneRecord).order_by(desc(SceneRecord.timestamp)).limit(1)
        res = await self.db.execute(stmt)
        latest_scene = res.scalar_one_or_none()

        answer = (
            f"### Cognitive Scene Memory Status:\n"
            f"- **Scenes Captured**: {scene_count} environment views\n"
            f"- **Active Tracked Objects**: {active_count} unique items\n"
            f"- **Historical Changes Detected**: {change_count} event(s)\n"
            f"- **Latest Scene**: {latest_scene.scene_id if latest_scene else 'None'} "
            f"({latest_scene.object_count if latest_scene else 0} objects observed)\n\n"
            f"The environment model is active and updating memory decay on unseen items. "
            f"You can ask me to **compare two scenes**, **locate any object**, or **describe spatial relationships**!"
        )

        return {
            "query": "overview",
            "answer": answer,
            "confidence": 0.98,
            "supporting_evidence": [
                f"Scenes: {scene_count}",
                f"Active Objects: {active_count}",
                f"Changes: {change_count}",
            ],
            "context": {"type": "overview"},
            "timestamp": datetime.now(timezone.utc),
        }

    async def _handle_general_search(self, q: str, scene_id: Optional[str]) -> dict:
        """Fallback search across recent change events, objects, and scenes."""
        # Search objects
        stmt = select(ObjectRecord).where(ObjectRecord.status == "ACTIVE").limit(10)
        res = await self.db.execute(stmt)
        objects = res.scalars().all()

        # Search changes
        c_stmt = select(ChangeEventRecord).order_by(desc(ChangeEventRecord.created_at)).limit(3)
        c_res = await self.db.execute(c_stmt)
        changes = c_res.scalars().all()

        answer = (
            f"I analyzed your question: *\"{q}\"*\n\n"
            f"Here is what I currently know from the environment:\n"
            f"- **Active Objects**: {len(objects)} tracked (e.g. {', '.join([o.class_name for o in objects[:4]]) or 'None'})\n"
            f"- **Recent Changes**: {len(changes)} recorded\n\n"
            f"💡 **Tip**: Try asking:\n"
            f"- *'Compare the latest two scenes'*\n"
            f"- *'Where is the [object]?'*\n"
            f"- *'What is near the [object]?'*\n"
            f"- *'What changed in the room?'*"
        )

        return {
            "query": q,
            "answer": answer,
            "confidence": 0.75,
            "supporting_evidence": [f"Active tracked items: {len(objects)}"],
            "context": {"type": "general_fallback"},
            "timestamp": datetime.now(timezone.utc),
        }
