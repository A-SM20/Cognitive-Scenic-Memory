"""
Timeline API endpoint (Phase 8).

GET /api/timeline — Unified chronological event stream of scenes,
object detections, and environmental changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.scene import SceneRecord
from app.models.change_event import ChangeEventRecord
from app.models.object import ObjectRecord

logger = get_logger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


class TimelineEvent(BaseModel):
    """An individual event in the environment history."""
    id: str
    event_type: str  # SCENE_CAPTURED | OBJECT_ADDED | OBJECT_REMOVED | OBJECT_MOVED | OBJECT_REPLACED
    title: str
    description: str
    timestamp: datetime
    scene_id: Optional[str] = None
    object_id: Optional[str] = None
    image_url: Optional[str] = None
    metadata: Optional[dict] = None


class TimelineResponse(BaseModel):
    """Paginated timeline response."""
    total_events: int
    events: List[TimelineEvent]


@router.get(
    "",
    response_model=TimelineResponse,
    summary="Get unified chronological event timeline",
)
async def get_timeline(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """
    Returns an aggregated, chronological timeline of all robot observations,
    including new scene captures, object lifecycle events, and change detections.
    """
    events: List[TimelineEvent] = []

    # 1. Fetch scenes
    scenes_stmt = select(SceneRecord).order_by(desc(SceneRecord.timestamp)).limit(limit)
    scenes_res = await db.execute(scenes_stmt)
    scenes = scenes_res.scalars().all()

    for s in scenes:
        img_url = None
        if s.annotated_image_path:
            import os
            fname = os.path.basename(s.annotated_image_path)
            img_url = f"/api/uploads/{fname}"

        events.append(
            TimelineEvent(
                id=f"scene-{s.scene_id}",
                event_type="SCENE_CAPTURED",
                title=f"Scene Captured: {s.scene_id}",
                description=f"Robot observed {s.object_count} objects in environment {s.environment_id}.",
                timestamp=s.timestamp,
                scene_id=s.scene_id,
                image_url=img_url,
                metadata={"object_count": s.object_count, "processing_time_ms": s.processing_time_ms},
            )
        )

    # 2. Fetch change events
    changes_stmt = select(ChangeEventRecord).order_by(desc(ChangeEventRecord.created_at)).limit(limit)
    changes_res = await db.execute(changes_stmt)
    changes = changes_res.scalars().all()

    for c in changes:
        events.append(
            TimelineEvent(
                id=f"change-{c.id}",
                event_type=f"OBJECT_{c.change_type}",
                title=f"Environment Change: {c.change_type}",
                description=c.description,
                timestamp=c.created_at,
                scene_id=c.scene_after_id,
                object_id=c.object_id,
                metadata={
                    "magnitude": c.magnitude,
                    "scene_before_id": c.scene_before_id,
                    "scene_after_id": c.scene_after_id,
                },
            )
        )

    # Sort all events chronologically descending
    events.sort(key=lambda x: x.timestamp, reverse=True)

    # Apply event_type filter if provided
    if event_type:
        events = [e for e in events if event_type.lower() in e.event_type.lower()]

    total_count = len(events)
    paginated_events = events[offset : offset + limit]

    return TimelineResponse(
        total_events=total_count,
        events=paginated_events,
    )
