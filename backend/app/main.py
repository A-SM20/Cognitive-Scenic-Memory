"""
Cognitive Scene Memory — FastAPI Application Entry Point.

Registers CORS middleware, API routers, static file serving,
and manages the database lifecycle (init on startup, close on shutdown).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, close_db
from app.logging_config import setup_logging, get_logger

# Import routers
from app.api.detection import router as detection_router
from app.api.scenes import router as scenes_router
from app.api.objects import router as objects_router
from app.api.memory import router as memory_router
from app.api.scene_graph import router as scene_graph_router
from app.api.changes import router as changes_router

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB on startup, close on shutdown."""
    logger.info("=" * 60)
    logger.info("  Cognitive Scene Memory v%s", settings.project_version)
    logger.info("  Semantic World Modeling & Change Detection")
    logger.info("=" * 60)
    logger.info("Model: %s | Confidence: %.2f | IOU: %.2f",
                settings.model_name, settings.confidence_threshold, settings.iou_threshold)
    logger.info("Features — Segmentation: %s | Feature Matching: %s | Depth: %s | LLM: %s",
                settings.enable_segmentation, settings.enable_feature_matching,
                settings.enable_depth, settings.enable_llm)

    # Initialize database
    await init_db()

    # Ensure upload directory exists
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Backend ready — http://%s:%d", settings.backend_host, settings.backend_port)
    logger.info("API docs — http://%s:%d/docs", settings.backend_host, settings.backend_port)

    yield

    # Shutdown
    logger.info("Shutting down Cognitive Scene Memory...")
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Cognitive Scene Memory",
    description=(
        "Semantic World Modeling and Long-Term Environment Change Detection "
        "for Indoor Robots. Provides real-time object detection, persistent "
        "memory, scene graph construction, and natural-language querying."
    ),
    version=settings.project_version,
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(detection_router)
app.include_router(scenes_router)
app.include_router(objects_router)
app.include_router(memory_router)
app.include_router(scene_graph_router)
app.include_router(changes_router)

# Mount static file serving for uploaded/annotated images
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


@app.get("/", tags=["root"])
async def root():
    """Root endpoint — redirects to API documentation."""
    return {
        "project": settings.project_name,
        "version": settings.project_version,
        "docs": "/docs",
        "health": "/api/health",
    }
