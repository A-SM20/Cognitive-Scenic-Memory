"""
Scene API endpoints.

GET /api/scenes             — List all captured scenes.
GET /api/scenes/{scene_id}  — Get details of a specific scene.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import SceneResponse
from app.models.scene import SceneRecord

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["scenes"])


@router.get(
    "/scenes",
    response_model=list[SceneResponse],
    summary="List all captured scenes",
)
async def list_scenes(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[SceneResponse]:
    """
    Returns a paginated list of all captured scenes, ordered by
    timestamp descending (most recent first).
    """
    stmt = (
        select(SceneRecord)
        .order_by(SceneRecord.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    scenes = result.scalars().all()

    return [
        SceneResponse(
            scene_id=s.scene_id,
            timestamp=s.timestamp,
            environment_id=s.environment_id,
            image_path=s.image_path,
            annotated_image_path=s.annotated_image_path,
            object_count=s.object_count,
            processing_time_ms=s.processing_time_ms,
            created_at=s.created_at,
        )
        for s in scenes
    ]


@router.get(
    "/scenes/{scene_id}",
    response_model=SceneResponse,
    summary="Get a specific scene by ID",
)
async def get_scene(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
) -> SceneResponse:
    """Returns the details of a specific scene including its observations."""
    stmt = select(SceneRecord).where(SceneRecord.scene_id == scene_id)
    result = await db.execute(stmt)
    scene = result.scalar_one_or_none()

    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")

    return SceneResponse(
        scene_id=scene.scene_id,
        timestamp=scene.timestamp,
        environment_id=scene.environment_id,
        image_path=scene.image_path,
        annotated_image_path=scene.annotated_image_path,
        object_count=scene.object_count,
        processing_time_ms=scene.processing_time_ms,
        created_at=scene.created_at,
    )
