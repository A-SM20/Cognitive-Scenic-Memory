"""
Settings API endpoint.

GET   /api/settings — Retrieve current runtime configuration.
PATCH /api/settings — Dynamically update thresholds and feature flags.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    """Current system settings."""
    project_name: str
    project_version: str
    model_name: str
    confidence_threshold: float
    iou_threshold: float
    process_every_n_frames: int
    confidence_decay: float
    movement_threshold: float
    enable_segmentation: bool
    enable_feature_matching: bool
    enable_depth: bool
    enable_llm: bool
    database_url: str
    upload_dir: str


class SettingsUpdateRequest(BaseModel):
    """Configurable fields for runtime update."""
    confidence_threshold: Optional[float] = Field(None, ge=0.05, le=0.95)
    iou_threshold: Optional[float] = Field(None, ge=0.1, le=0.9)
    confidence_decay: Optional[float] = Field(None, ge=0.01, le=0.5)
    movement_threshold: Optional[float] = Field(None, ge=5.0, le=500.0)
    enable_segmentation: Optional[bool] = None
    enable_feature_matching: Optional[bool] = None
    enable_depth: Optional[bool] = None
    enable_llm: Optional[bool] = None


@router.get("", response_model=SettingsResponse, summary="Get system settings")
async def get_system_settings() -> SettingsResponse:
    """Returns all current configurable thresholds and feature flags."""
    settings = get_settings()
    return SettingsResponse(
        project_name=settings.project_name,
        project_version=settings.project_version,
        model_name=settings.model_name,
        confidence_threshold=settings.confidence_threshold,
        iou_threshold=settings.iou_threshold,
        process_every_n_frames=settings.process_every_n_frames,
        confidence_decay=settings.confidence_decay,
        movement_threshold=settings.movement_threshold,
        enable_segmentation=settings.enable_segmentation,
        enable_feature_matching=settings.enable_feature_matching,
        enable_depth=settings.enable_depth,
        enable_llm=settings.enable_llm,
        database_url=settings.database_url,
        upload_dir=settings.upload_dir,
    )


@router.patch("", response_model=SettingsResponse, summary="Update system settings")
async def update_system_settings(req: SettingsUpdateRequest) -> SettingsResponse:
    """Dynamically update thresholds and feature flags without server restart."""
    settings = get_settings()

    if req.confidence_threshold is not None:
        settings.confidence_threshold = req.confidence_threshold
    if req.iou_threshold is not None:
        settings.iou_threshold = req.iou_threshold
    if req.confidence_decay is not None:
        settings.confidence_decay = req.confidence_decay
    if req.movement_threshold is not None:
        settings.movement_threshold = req.movement_threshold
    if req.enable_segmentation is not None:
        settings.enable_segmentation = req.enable_segmentation
    if req.enable_feature_matching is not None:
        settings.enable_feature_matching = req.enable_feature_matching
    if req.enable_depth is not None:
        settings.enable_depth = req.enable_depth
    if req.enable_llm is not None:
        settings.enable_llm = req.enable_llm

    logger.info("Updated runtime settings: confidence=%.2f, decay=%.2f, movement=%.1f",
                settings.confidence_threshold, settings.confidence_decay, settings.movement_threshold)

    return await get_system_settings()
