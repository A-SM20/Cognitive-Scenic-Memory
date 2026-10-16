"""
Centralized configuration for Cognitive Scene Memory.

All configurable parameters are defined here and loaded from environment
variables or a .env file. No important thresholds should be scattered
throughout the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # --- Project Identity ---
    project_name: str = "Cognitive Scene Memory"
    project_version: str = "0.1.0"

    # --- Object Detection ---
    model_name: str = Field(default="yolov8n.pt", description="YOLO model file name")
    confidence_threshold: float = Field(
        default=0.40, ge=0.0, le=1.0,
        description="Minimum detection confidence"
    )
    iou_threshold: float = Field(
        default=0.50, ge=0.0, le=1.0,
        description="IOU threshold for non-max suppression"
    )

    # --- Processing ---
    process_every_n_frames: int = Field(
        default=10, ge=1,
        description="Process every Nth frame in video streams"
    )

    # --- Feature Flags ---
    enable_segmentation: bool = Field(default=False, description="Enable semantic segmentation")
    enable_feature_matching: bool = Field(default=True, description="Enable ORB/SIFT feature matching")
    enable_depth: bool = Field(default=False, description="Enable depth/3D positioning")
    enable_llm: bool = Field(default=False, description="Enable LLM-based query responses")

    # --- Memory ---
    confidence_decay: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="Confidence decay per missed observation cycle"
    )
    movement_threshold: float = Field(
        default=50.0, ge=0.0,
        description="Minimum pixel displacement to classify as MOVED"
    )

    # --- Database ---
    database_url: str = Field(
        default="sqlite:///./data/scene_memory.db",
        description="SQLAlchemy database URL"
    )

    # --- Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8001
    frontend_url: str = "http://localhost:5173"

    # --- Paths ---
    upload_dir: str = Field(default="./data/uploads", description="Directory for uploaded images")
    base_dir: str = Field(default="", description="Auto-resolved project base directory")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    def resolve_paths(self) -> None:
        """Resolve relative paths to absolute paths based on project root."""
        if not self.base_dir:
            # Resolve from backend/ directory up to project root
            self.base_dir = str(Path(__file__).resolve().parent.parent.parent)

        base = Path(self.base_dir)

        # Ensure upload directory exists
        upload_path = base / self.upload_dir if not os.path.isabs(self.upload_dir) else Path(self.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
        self.upload_dir = str(upload_path)

        # Resolve database URL path
        if self.database_url.startswith("sqlite:///./"):
            relative_db_path = self.database_url.replace("sqlite:///./", "")
            abs_db_path = base / relative_db_path
            abs_db_path.parent.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite:///{abs_db_path}"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns a singleton Settings instance. The lru_cache ensures
    settings are only loaded once from disk.
    """
    settings = Settings()
    settings.resolve_paths()
    return settings
