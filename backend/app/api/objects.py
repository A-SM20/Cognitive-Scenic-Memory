"""
Object API endpoints.

GET /api/objects              — List all persistent objects in memory.
GET /api/objects/{object_id}  — Get details of a specific object.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import ObjectResponse
from app.models.object import ObjectRecord

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["objects"])


@router.get(
    "/objects",
    response_model=list[ObjectResponse],
    summary="List all persistent objects in memory",
)
async def list_objects(
    status: str | None = None,
    class_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[ObjectResponse]:
    """
    Returns all objects tracked in persistent memory.

    Optionally filter by status (ACTIVE, POSSIBLY_MISSING, MISSING, REMOVED)
    or class_name.
    """
    stmt = select(ObjectRecord).order_by(ObjectRecord.last_seen.desc())

    if status:
        stmt = stmt.where(ObjectRecord.status == status.upper())
    if class_name:
        stmt = stmt.where(ObjectRecord.class_name == class_name)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    objects = result.scalars().all()

    return [
        ObjectResponse(
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
        )
        for o in objects
    ]


@router.get(
    "/objects/{object_id}",
    response_model=ObjectResponse,
    summary="Get a specific object by persistent ID",
)
async def get_object(
    object_id: str,
    db: AsyncSession = Depends(get_db),
) -> ObjectResponse:
    """Returns the details of a specific persistent object."""
    stmt = select(ObjectRecord).where(ObjectRecord.object_id == object_id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()

    if obj is None:
        raise HTTPException(status_code=404, detail=f"Object not found: {object_id}")

    return ObjectResponse(
        object_id=obj.object_id,
        class_name=obj.class_name,
        display_name=obj.display_name,
        first_seen=obj.first_seen,
        last_seen=obj.last_seen,
        last_position_x=obj.last_position_x,
        last_position_y=obj.last_position_y,
        observation_count=obj.observation_count,
        current_confidence=obj.current_confidence,
        identity_confidence=obj.identity_confidence,
        status=obj.status,
    )
