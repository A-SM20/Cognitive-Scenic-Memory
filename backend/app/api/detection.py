"""
Detection API endpoints.

POST /api/process/image — Upload an image for real YOLO detection.
GET  /api/health        — System health and readiness check.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.logging_config import get_logger
from app.models.detection import DetectionResult, HealthResponse
from app.services.detection_service import DetectionService, get_detector

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["detection"])


@router.post(
    "/process/image",
    response_model=DetectionResult,
    summary="Process an image through the YOLO detection pipeline",
)
async def process_image(
    file: UploadFile = File(..., description="Image file to process"),
    track: bool = Query(False, description="Apply ByteTrack across frames"),
    db: AsyncSession = Depends(get_db),
) -> DetectionResult:
    """
    Upload an image and run real YOLO object detection.

    Returns structured detection results including:
    - List of detected objects with class names, confidence, and bounding boxes
    - URL to the annotated image with bounding box overlays
    - Processing time and model metadata

    The image and annotated result are saved to the uploads directory.
    """
    # Validate file type
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Expected an image file.",
        )

    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty image file")

        service = DetectionService(db=db)
        result = await service.process_image_bytes(
            image_bytes=image_bytes,
            filename=file.filename or "upload.jpg",
            track=track,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Detection model error: {e}")
    except Exception as e:
        logger.error("Image processing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


@router.get(
    "/detection/latest",
    response_model=Optional[DetectionResult],
    summary="Get the most recent detection result from any source (including robot)",
)
async def get_latest_detection(
    db: AsyncSession = Depends(get_db),
) -> Optional[DetectionResult]:
    """Returns the most recent detection result with annotated image and bounding boxes."""
    from app.models.scene import SceneRecord
    from app.models.observation import ObservationRecord
    from app.models.detection import BoundingBox, Detection
    from pathlib import Path

    stmt = select(SceneRecord).order_by(SceneRecord.timestamp.desc()).limit(1)
    res = await db.execute(stmt)
    scene = res.scalar_one_or_none()
    if not scene:
        return None

    obs_stmt = select(ObservationRecord).where(ObservationRecord.scene_id == scene.scene_id)
    obs_res = await db.execute(obs_stmt)
    observations = obs_res.scalars().all()

    detections = []
    for o in observations:
        detections.append(
            Detection(
                class_name=o.class_name,
                confidence=o.confidence,
                bbox=BoundingBox(x=o.bbox_x, y=o.bbox_y, w=o.bbox_w, h=o.bbox_h),
                center_x=o.position_x,
                center_y=o.position_y,
                width=o.bbox_w,
                height=o.bbox_h,
                timestamp=o.timestamp,
                frame_id=0,
            )
        )

    annotated_url = ""
    if scene.annotated_image_path:
        filename = Path(scene.annotated_image_path).name
        annotated_url = f"/api/uploads/{filename}"

    settings = get_settings()
    return DetectionResult(
        scene_id=scene.scene_id,
        image_path=scene.image_path or "",
        annotated_image_path=scene.annotated_image_path or "",
        annotated_image_url=annotated_url,
        detections=detections,
        total_objects=scene.object_count or len(detections),
        processing_time_ms=scene.processing_time_ms or 0.0,
        model_name=settings.model_name,
        image_width=1280,
        image_height=720,
        timestamp=scene.timestamp,
    )



@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health and readiness check",
)
async def health_check() -> HealthResponse:
    """
    Returns the current system status including model availability,
    database connectivity, and enabled features.
    """
    settings = get_settings()

    # Check if model is loaded
    try:
        detector = get_detector()
        model_loaded = detector.is_loaded()
    except Exception:
        model_loaded = False

    # Check database connectivity
    db_connected = False
    try:
        from app.database import engine
        if engine is not None:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
                db_connected = True
    except Exception:
        db_connected = False

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        project_name=settings.project_name,
        version=settings.project_version,
        model_name=settings.model_name,
        model_loaded=model_loaded,
        database_connected=db_connected,
        features={
            "segmentation": settings.enable_segmentation,
            "feature_matching": settings.enable_feature_matching,
            "depth": settings.enable_depth,
            "llm": settings.enable_llm,
        },
        timestamp=datetime.now(timezone.utc),
    )
