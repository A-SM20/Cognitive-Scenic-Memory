"""
Detection API endpoints.

POST /api/process/image — Upload an image for real YOLO detection.
GET  /api/health        — System health and readiness check.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
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
