"""
Memory service — Cognitive Confidence Model (Phase 5).

Implements Bayesian confidence decay and reinforcement for persistent
object memory. Objects that are not observed decay in confidence over
time and transition through lifecycle states:

  ACTIVE → POSSIBLY_MISSING → MISSING → REMOVED

Objects that are re-observed get confidence reinforcement.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models.object import ObjectRecord
from app.models.observation import ObservationRecord
from app.models.scene import SceneRecord

logger = get_logger(__name__)


class MemoryService:
    """
    Manages cognitive confidence for persistent object memory.

    After each perception cycle, objects not observed in the latest
    scene have their confidence decayed. Objects re-observed get
    Bayesian reinforcement. Lifecycle transitions are triggered
    when confidence crosses thresholds.
    """

    # Status transition thresholds
    THRESHOLD_POSSIBLY_MISSING = 0.50
    THRESHOLD_MISSING = 0.20
    THRESHOLD_REMOVED = 0.05

    def __init__(self, db: AsyncSession):
        self._db = db
        self._settings = get_settings()

    async def decay_unseen_objects(self, scene_id: str) -> int:
        """
        Decay confidence of all ACTIVE/POSSIBLY_MISSING objects NOT
        observed in the given scene.

        Args:
            scene_id: The scene that was just processed.

        Returns:
            Number of objects whose confidence was decayed.
        """
        # Get object_ids observed in this scene
        obs_stmt = (
            select(ObservationRecord.object_id)
            .where(ObservationRecord.scene_id == scene_id)
        )
        result = await self._db.execute(obs_stmt)
        observed_ids = {row[0] for row in result.all()}

        # Fetch objects that should decay (ACTIVE or POSSIBLY_MISSING, not observed)
        decay_stmt = select(ObjectRecord).where(
            ObjectRecord.status.in_(["ACTIVE", "POSSIBLY_MISSING"])
        )
        result = await self._db.execute(decay_stmt)
        candidates = result.scalars().all()

        decay_rate = self._settings.confidence_decay
        decayed_count = 0

        for obj in candidates:
            if obj.object_id not in observed_ids:
                old_conf = obj.current_confidence
                # Multiplicative decay: conf *= (1 - decay_rate)
                obj.current_confidence = max(0.0, old_conf * (1.0 - decay_rate))
                decayed_count += 1
                logger.debug(
                    "Decayed %s: %.3f → %.3f",
                    obj.object_id, old_conf, obj.current_confidence,
                )

        if decayed_count > 0:
            await self._db.flush()
            logger.info(
                "Confidence decay applied: %d objects decayed (rate=%.2f)",
                decayed_count, decay_rate,
            )

        return decayed_count

    async def reinforce_object(
        self,
        object_id: str,
        observation_confidence: float,
    ) -> float:
        """
        Bayesian reinforcement: blend current confidence with new
        observation confidence.

        Uses weighted average: new_conf = 0.7 * obs_conf + 0.3 * current_conf
        This gives more weight to fresh observations.

        Args:
            object_id: The object to reinforce.
            observation_confidence: Confidence from the new detection.

        Returns:
            Updated confidence value.
        """
        stmt = select(ObjectRecord).where(ObjectRecord.object_id == object_id)
        result = await self._db.execute(stmt)
        obj = result.scalar_one_or_none()

        if obj is None:
            logger.warning("Cannot reinforce unknown object: %s", object_id)
            return 0.0

        old_conf = obj.current_confidence
        # Weighted Bayesian blend
        new_conf = min(1.0, 0.7 * observation_confidence + 0.3 * old_conf)
        obj.current_confidence = new_conf

        # Restore status if previously degraded
        if new_conf >= self.THRESHOLD_POSSIBLY_MISSING and obj.status != "ACTIVE":
            logger.info(
                "Object %s restored to ACTIVE (conf=%.3f)",
                object_id, new_conf,
            )
            obj.status = "ACTIVE"

        await self._db.flush()
        return new_conf

    async def update_object_lifecycle(self) -> dict[str, int]:
        """
        Transition objects through status states based on confidence.

        Returns:
            Dict with counts of transitions: {"to_possibly_missing": n, ...}
        """
        stmt = select(ObjectRecord).where(
            ObjectRecord.status.in_(["ACTIVE", "POSSIBLY_MISSING", "MISSING"])
        )
        result = await self._db.execute(stmt)
        objects = result.scalars().all()

        transitions = {
            "to_possibly_missing": 0,
            "to_missing": 0,
            "to_removed": 0,
        }

        for obj in objects:
            old_status = obj.status
            conf = obj.current_confidence

            if conf < self.THRESHOLD_REMOVED:
                obj.status = "REMOVED"
                if old_status != "REMOVED":
                    transitions["to_removed"] += 1
            elif conf < self.THRESHOLD_MISSING:
                obj.status = "MISSING"
                if old_status != "MISSING":
                    transitions["to_missing"] += 1
            elif conf < self.THRESHOLD_POSSIBLY_MISSING:
                obj.status = "POSSIBLY_MISSING"
                if old_status != "POSSIBLY_MISSING":
                    transitions["to_possibly_missing"] += 1

        total = sum(transitions.values())
        if total > 0:
            await self._db.flush()
            logger.info("Lifecycle transitions: %s", transitions)

        return transitions

    async def get_memory_summary(self) -> dict:
        """
        Returns a summary of the cognitive memory state:
        counts by status, total scenes, average confidence.
        """
        # Count objects by status
        status_stmt = (
            select(ObjectRecord.status, func.count(ObjectRecord.id))
            .group_by(ObjectRecord.status)
        )
        result = await self._db.execute(status_stmt)
        status_counts = {row[0]: row[1] for row in result.all()}

        # Total scenes
        scene_count_stmt = select(func.count(SceneRecord.id))
        result = await self._db.execute(scene_count_stmt)
        total_scenes = result.scalar() or 0

        # Average confidence of non-REMOVED objects
        avg_stmt = select(func.avg(ObjectRecord.current_confidence)).where(
            ObjectRecord.status != "REMOVED"
        )
        result = await self._db.execute(avg_stmt)
        avg_confidence = result.scalar() or 0.0

        return {
            "total_objects": sum(status_counts.values()),
            "active": status_counts.get("ACTIVE", 0),
            "possibly_missing": status_counts.get("POSSIBLY_MISSING", 0),
            "missing": status_counts.get("MISSING", 0),
            "removed": status_counts.get("REMOVED", 0),
            "unknown": status_counts.get("UNKNOWN", 0),
            "total_scenes": total_scenes,
            "average_confidence": round(float(avg_confidence), 4),
        }

    async def get_memory_objects(self) -> list[ObjectRecord]:
        """
        Returns all objects with their current confidence and lifecycle state,
        ordered by status priority then confidence descending.
        """
        status_order = {
            "ACTIVE": 0,
            "POSSIBLY_MISSING": 1,
            "MISSING": 2,
            "UNKNOWN": 3,
            "REMOVED": 4,
        }

        stmt = select(ObjectRecord).order_by(
            ObjectRecord.last_seen.desc()
        )
        result = await self._db.execute(stmt)
        objects = result.scalars().all()

        # Sort by status priority, then confidence descending
        objects.sort(
            key=lambda o: (
                status_order.get(o.status, 99),
                -o.current_confidence,
            )
        )

        return objects
