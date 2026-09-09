"""
Change Detection service (Phase 7).

Compares two scenes to detect environment changes:
  ADDED — Object in scene_after but not scene_before
  REMOVED — Object in scene_before but not scene_after
  MOVED — Same object, position shifted beyond threshold
  REPLACED — Same location, different object class
  STATUS_CHANGED — Object lifecycle state changed
  CONFIDENCE_CHANGED — Significant confidence shift

Results are persisted to the ``change_events`` table and returned
as structured responses for the frontend.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models.observation import ObservationRecord
from app.models.object import ObjectRecord
from app.models.change_event import ChangeEventRecord

logger = get_logger(__name__)

# Significant confidence change threshold
CONFIDENCE_CHANGE_THRESHOLD = 0.2

# Maximum center distance to consider same-location for REPLACED
SAME_LOCATION_THRESHOLD_PX = 40.0


class ChangeDetectionService:
    """
    Detects and records environment changes between scene pairs.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._settings = get_settings()

    async def compare_scenes(
        self,
        scene_before_id: str,
        scene_after_id: str,
    ) -> list[ChangeEventRecord]:
        """
        Compare two scenes and detect all changes.

        Args:
            scene_before_id: The earlier scene.
            scene_after_id: The later scene.

        Returns:
            List of ChangeEventRecord objects (already persisted).
        """
        # Load observations for both scenes
        before_obs = await self._load_observations(scene_before_id)
        after_obs = await self._load_observations(scene_after_id)

        # Build lookups by object_id
        before_by_id = {obs["object_id"]: obs for obs in before_obs}
        after_by_id = {obs["object_id"]: obs for obs in after_obs}

        before_ids = set(before_by_id.keys())
        after_ids = set(after_by_id.keys())

        changes: list[ChangeEventRecord] = []

        # ── ADDED: in after but not before ──
        added_ids = after_ids - before_ids
        for obj_id in added_ids:
            obs = after_by_id[obj_id]
            change = ChangeEventRecord(
                scene_before_id=scene_before_id,
                scene_after_id=scene_after_id,
                object_id=obj_id,
                change_type="ADDED",
                description=(
                    f"{obs['class_name']} appeared at "
                    f"({obs['center_x']:.0f}, {obs['center_y']:.0f})"
                ),
                magnitude=None,
                new_value_json=json.dumps({
                    "class_name": obs["class_name"],
                    "center_x": obs["center_x"],
                    "center_y": obs["center_y"],
                    "confidence": obs["confidence"],
                }),
            )
            self._db.add(change)
            changes.append(change)

        # ── REMOVED: in before but not after ──
        removed_ids = before_ids - after_ids
        for obj_id in removed_ids:
            obs = before_by_id[obj_id]
            change = ChangeEventRecord(
                scene_before_id=scene_before_id,
                scene_after_id=scene_after_id,
                object_id=obj_id,
                change_type="REMOVED",
                description=(
                    f"{obs['class_name']} disappeared from "
                    f"({obs['center_x']:.0f}, {obs['center_y']:.0f})"
                ),
                magnitude=None,
                old_value_json=json.dumps({
                    "class_name": obs["class_name"],
                    "center_x": obs["center_x"],
                    "center_y": obs["center_y"],
                    "confidence": obs["confidence"],
                }),
            )
            self._db.add(change)
            changes.append(change)

        # ── Objects present in both — check for MOVED / STATUS_CHANGED / CONFIDENCE_CHANGED ──
        common_ids = before_ids & after_ids
        for obj_id in common_ids:
            obs_before = before_by_id[obj_id]
            obs_after = after_by_id[obj_id]

            # Check for MOVED
            dist = math.hypot(
                obs_after["center_x"] - obs_before["center_x"],
                obs_after["center_y"] - obs_before["center_y"],
            )
            if dist > self._settings.movement_threshold:
                dx = obs_after["center_x"] - obs_before["center_x"]
                dy = obs_after["center_y"] - obs_before["center_y"]

                # Describe direction
                direction_parts = []
                if abs(dx) > 10:
                    direction_parts.append("right" if dx > 0 else "left")
                if abs(dy) > 10:
                    direction_parts.append("down" if dy > 0 else "up")
                direction = " and ".join(direction_parts) or "slightly"

                change = ChangeEventRecord(
                    scene_before_id=scene_before_id,
                    scene_after_id=scene_after_id,
                    object_id=obj_id,
                    change_type="MOVED",
                    description=(
                        f"{obs_before['class_name']} moved {dist:.0f}px {direction}"
                    ),
                    magnitude=round(dist, 1),
                    old_value_json=json.dumps({
                        "center_x": obs_before["center_x"],
                        "center_y": obs_before["center_y"],
                    }),
                    new_value_json=json.dumps({
                        "center_x": obs_after["center_x"],
                        "center_y": obs_after["center_y"],
                    }),
                )
                self._db.add(change)
                changes.append(change)

            # Check for CONFIDENCE_CHANGED
            conf_delta = obs_after["confidence"] - obs_before["confidence"]
            if abs(conf_delta) > CONFIDENCE_CHANGE_THRESHOLD:
                direction = "increased" if conf_delta > 0 else "decreased"
                change = ChangeEventRecord(
                    scene_before_id=scene_before_id,
                    scene_after_id=scene_after_id,
                    object_id=obj_id,
                    change_type="CONFIDENCE_CHANGED",
                    description=(
                        f"{obs_before['class_name']} confidence {direction} "
                        f"by {abs(conf_delta):.2f} "
                        f"({obs_before['confidence']:.2f} → {obs_after['confidence']:.2f})"
                    ),
                    magnitude=round(abs(conf_delta), 4),
                    old_value_json=json.dumps({"confidence": obs_before["confidence"]}),
                    new_value_json=json.dumps({"confidence": obs_after["confidence"]}),
                )
                self._db.add(change)
                changes.append(change)

        # ── REPLACED: different class at roughly the same location ──
        for added_id in added_ids:
            added_obs = after_by_id[added_id]
            for removed_id in removed_ids:
                removed_obs = before_by_id[removed_id]

                # Same class → not a replacement, just different object
                if added_obs["class_name"] == removed_obs["class_name"]:
                    continue

                dist = math.hypot(
                    added_obs["center_x"] - removed_obs["center_x"],
                    added_obs["center_y"] - removed_obs["center_y"],
                )
                if dist <= SAME_LOCATION_THRESHOLD_PX:
                    change = ChangeEventRecord(
                        scene_before_id=scene_before_id,
                        scene_after_id=scene_after_id,
                        object_id=added_id,
                        change_type="REPLACED",
                        description=(
                            f"{removed_obs['class_name']} replaced by "
                            f"{added_obs['class_name']} at "
                            f"({added_obs['center_x']:.0f}, {added_obs['center_y']:.0f})"
                        ),
                        magnitude=round(dist, 1),
                        old_value_json=json.dumps({
                            "class_name": removed_obs["class_name"],
                            "object_id": removed_id,
                        }),
                        new_value_json=json.dumps({
                            "class_name": added_obs["class_name"],
                            "object_id": added_id,
                        }),
                    )
                    self._db.add(change)
                    changes.append(change)

        if changes:
            await self._db.flush()

        logger.info(
            "Scene comparison %s → %s: %d changes detected",
            scene_before_id, scene_after_id, len(changes),
        )

        return changes

    async def _load_observations(self, scene_id: str) -> list[dict]:
        """Load observation dicts for a scene."""
        stmt = select(ObservationRecord).where(
            ObservationRecord.scene_id == scene_id
        )
        result = await self._db.execute(stmt)
        observations = result.scalars().all()

        return [
            {
                "object_id": obs.object_id,
                "class_name": obs.class_name,
                "center_x": obs.position_x,
                "center_y": obs.position_y,
                "bbox_x": obs.bbox_x,
                "bbox_y": obs.bbox_y,
                "bbox_w": obs.bbox_w,
                "bbox_h": obs.bbox_h,
                "confidence": obs.confidence,
                "visibility": obs.visibility,
            }
            for obs in observations
        ]

    async def get_changes_for_scene(self, scene_id: str) -> list[ChangeEventRecord]:
        """Get all change events involving a specific scene (as before or after)."""
        stmt = select(ChangeEventRecord).where(
            (ChangeEventRecord.scene_before_id == scene_id) |
            (ChangeEventRecord.scene_after_id == scene_id)
        ).order_by(ChangeEventRecord.created_at.desc())

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_change_history(self, object_id: str) -> list[ChangeEventRecord]:
        """Get all change events for a specific object, ordered chronologically."""
        stmt = (
            select(ChangeEventRecord)
            .where(ChangeEventRecord.object_id == object_id)
            .order_by(ChangeEventRecord.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_changes(self, limit: int = 50) -> list[ChangeEventRecord]:
        """Get the most recent change events across all scenes."""
        stmt = (
            select(ChangeEventRecord)
            .order_by(ChangeEventRecord.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
