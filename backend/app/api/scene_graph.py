"""
Scene Graph API endpoints (Phase 6).

GET  /api/scene-graph/{scene_id}                — Get the scene graph.
POST /api/scene-graph/{scene_id}/build          — Rebuild the scene graph.
GET  /api/scene-graph/{scene_id}/relationships  — List spatial relationships.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import (
    SceneGraphResponse,
    SpatialRelationshipResponse,
)
from app.models.scene import SceneRecord
from app.services.scene_graph_service import SceneGraphService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/scene-graph", tags=["scene-graph"])


async def _verify_scene_exists(scene_id: str, db: AsyncSession) -> None:
    """Raise 404 if scene doesn't exist."""
    stmt = select(SceneRecord).where(SceneRecord.scene_id == scene_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")


@router.get(
    "/{scene_id}",
    response_model=SceneGraphResponse,
    summary="Get the scene graph for a scene",
)
async def get_scene_graph(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
) -> SceneGraphResponse:
    """
    Returns the semantic scene graph for a specific scene, including
    all object nodes and spatial relationship edges.
    """
    await _verify_scene_exists(scene_id, db)

    svc = SceneGraphService(db)
    graph_data = await svc.get_scene_graph(scene_id)

    return SceneGraphResponse(
        **graph_data,
        timestamp=datetime.now(timezone.utc),
    )


@router.post(
    "/{scene_id}/build",
    response_model=SceneGraphResponse,
    summary="Rebuild the scene graph for a scene",
)
async def build_scene_graph(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
) -> SceneGraphResponse:
    """
    Rebuilds the semantic scene graph from scratch for a specific scene.
    Replaces any existing relationships.
    """
    await _verify_scene_exists(scene_id, db)

    svc = SceneGraphService(db)
    await svc.build_scene_graph(scene_id)
    graph_data = await svc.get_scene_graph(scene_id)

    return SceneGraphResponse(
        **graph_data,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/{scene_id}/relationships",
    response_model=list[SpatialRelationshipResponse],
    summary="List spatial relationships for a scene",
)
async def list_relationships(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SpatialRelationshipResponse]:
    """Returns all spatial relationships in the scene graph."""
    await _verify_scene_exists(scene_id, db)

    svc = SceneGraphService(db)
    rels = await svc.get_relationships(scene_id)

    return [
        SpatialRelationshipResponse(
            source_object_id=r.source_object_id,
            target_object_id=r.target_object_id,
            relationship_type=r.relationship_type,
            confidence=r.confidence,
            distance_px=r.distance_px,
        )
        for r in rels
    ]
