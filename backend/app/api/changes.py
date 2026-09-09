"""
Change Detection API endpoints (Phase 7).

POST /api/changes/compare               — Compare two scenes.
GET  /api/changes/scene/{scene_id}      — Changes involving a scene.
GET  /api/changes/object/{object_id}    — Change history for an object.
GET  /api/changes/recent                — Recent changes across all scenes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import (
    ChangeEventResponse,
    SceneComparisonResponse,
)
from app.models.scene import SceneRecord
from app.services.change_detection_service import ChangeDetectionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/changes", tags=["changes"])


class CompareRequest(BaseModel):
    """Request body for scene comparison."""
    scene_before_id: str = Field(description="Scene ID for the earlier scene")
    scene_after_id: str = Field(description="Scene ID for the later scene")


def _change_to_response(c) -> ChangeEventResponse:
    """Convert a ChangeEventRecord to a response."""
    return ChangeEventResponse(
        id=c.id,
        scene_before_id=c.scene_before_id,
        scene_after_id=c.scene_after_id,
        object_id=c.object_id,
        change_type=c.change_type,
        description=c.description,
        magnitude=c.magnitude,
        old_value_json=c.old_value_json,
        new_value_json=c.new_value_json,
        created_at=c.created_at,
    )


@router.post(
    "/compare",
    response_model=SceneComparisonResponse,
    summary="Compare two scenes for changes",
)
async def compare_scenes(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
) -> SceneComparisonResponse:
    """
    Compares two scenes and detects all environment changes:
    ADDED, REMOVED, MOVED, REPLACED, CONFIDENCE_CHANGED.
    """
    # Verify both scenes exist
    for sid in [request.scene_before_id, request.scene_after_id]:
        stmt = select(SceneRecord).where(SceneRecord.scene_id == sid)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Scene not found: {sid}")

    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes(
        request.scene_before_id, request.scene_after_id,
    )

    # Build summary
    summary: dict[str, int] = {}
    for c in changes:
        summary[c.change_type] = summary.get(c.change_type, 0) + 1

    return SceneComparisonResponse(
        scene_before_id=request.scene_before_id,
        scene_after_id=request.scene_after_id,
        total_changes=len(changes),
        changes=[_change_to_response(c) for c in changes],
        summary=summary,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/scene/{scene_id}",
    response_model=list[ChangeEventResponse],
    summary="Get all changes involving a scene",
)
async def changes_for_scene(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ChangeEventResponse]:
    """Returns all change events where this scene is either the before or after."""
    svc = ChangeDetectionService(db)
    changes = await svc.get_changes_for_scene(scene_id)
    return [_change_to_response(c) for c in changes]


@router.get(
    "/object/{object_id}",
    response_model=list[ChangeEventResponse],
    summary="Get change history for an object",
)
async def changes_for_object(
    object_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ChangeEventResponse]:
    """Returns the chronological change history for a specific object."""
    svc = ChangeDetectionService(db)
    changes = await svc.get_change_history(object_id)
    return [_change_to_response(c) for c in changes]


@router.get(
    "/recent",
    response_model=list[ChangeEventResponse],
    summary="Get recent change events",
)
async def recent_changes(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[ChangeEventResponse]:
    """Returns the most recent change events across all scenes."""
    svc = ChangeDetectionService(db)
    changes = await svc.get_recent_changes(limit=limit)
    return [_change_to_response(c) for c in changes]
