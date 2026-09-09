"""
Memory API endpoints (Phase 4-5).

GET  /api/memory/summary   — Object memory status breakdown.
GET  /api/memory/objects    — All objects with confidence and lifecycle state.
POST /api/memory/decay      — Manually trigger confidence decay cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import MemorySummaryResponse, MemoryObjectResponse
from app.services.memory_service import MemoryService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get(
    "/summary",
    response_model=MemorySummaryResponse,
    summary="Get cognitive memory status breakdown",
)
async def memory_summary(
    db: AsyncSession = Depends(get_db),
) -> MemorySummaryResponse:
    """
    Returns a summary of the system's persistent object memory:
    counts by status (ACTIVE, POSSIBLY_MISSING, MISSING, REMOVED),
    total scenes processed, and average confidence.
    """
    svc = MemoryService(db)
    summary = await svc.get_memory_summary()

    return MemorySummaryResponse(
        **summary,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/objects",
    response_model=list[MemoryObjectResponse],
    summary="List all objects with confidence and lifecycle state",
)
async def memory_objects(
    db: AsyncSession = Depends(get_db),
) -> list[MemoryObjectResponse]:
    """
    Returns all tracked objects with their current confidence,
    lifecycle status, and observation history — sorted by
    status priority then confidence.
    """
    svc = MemoryService(db)
    objects = await svc.get_memory_objects()

    return [
        MemoryObjectResponse(
            object_id=o.object_id,
            class_name=o.class_name,
            display_name=o.display_name,
            first_seen=o.first_seen,
            last_seen=o.last_seen,
            last_position_x=o.last_position_x,
            last_position_y=o.last_position_y,
            observation_count=o.observation_count,
            current_confidence=o.current_confidence,
            identity_confidence=o.identity_confidence,
            status=o.status,
            scenes_since_last_seen=0,  # TODO: compute from scene count
        )
        for o in objects
    ]


@router.post(
    "/decay",
    summary="Manually trigger confidence decay cycle",
)
async def trigger_decay(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Manually triggers a confidence decay cycle for all objects not
    observed in the most recent scene. Useful for testing and debugging
    the cognitive memory model.
    """
    from sqlalchemy import select
    from app.models.scene import SceneRecord

    # Get most recent scene
    stmt = (
        select(SceneRecord.scene_id)
        .order_by(SceneRecord.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        return {"message": "No scenes found", "decayed": 0, "transitions": {}}

    scene_id = row[0]
    svc = MemoryService(db)
    decayed = await svc.decay_unseen_objects(scene_id)
    transitions = await svc.update_object_lifecycle()

    return {
        "message": f"Decay cycle complete for scene {scene_id}",
        "decayed": decayed,
        "transitions": transitions,
    }


@router.post(
    "/clear",
    summary="Clear all persistent cognitive memory and scene history",
)
async def clear_memory(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Clears all stored memory, including:
    - Object records & lifecycle states
    - Observations
    - Spatial relationships (scene graphs)
    - Change events
    - Scenes
    """
    from sqlalchemy import delete
    from app.models.change_event import ChangeEventRecord
    from app.models.spatial_relationship import SpatialRelationshipRecord
    from app.models.observation import ObservationRecord
    from app.models.object import ObjectRecord
    from app.models.scene import SceneRecord

    c_changes = (await db.execute(delete(ChangeEventRecord))).rowcount
    c_rels = (await db.execute(delete(SpatialRelationshipRecord))).rowcount
    c_obs = (await db.execute(delete(ObservationRecord))).rowcount
    c_objs = (await db.execute(delete(ObjectRecord))).rowcount
    c_scenes = (await db.execute(delete(SceneRecord))).rowcount

    logger.info(
        "Cognitive memory cleared: %d changes, %d rels, %d obs, %d objs, %d scenes",
        c_changes, c_rels, c_obs, c_objs, c_scenes,
    )

    return {
        "message": "Cognitive memory cleared successfully",
        "cleared": {
            "change_events": c_changes,
            "spatial_relationships": c_rels,
            "observations": c_obs,
            "objects": c_objs,
            "scenes": c_scenes,
        },
    }
