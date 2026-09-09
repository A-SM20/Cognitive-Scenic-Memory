"""
Scene ORM model.

Each scene represents a single perception cycle — one snapshot of the
environment captured at a specific timestamp. Scenes persist the image
path, detected object count, and optional metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.orm import relationship

from app.database import Base


class SceneRecord(Base):
    """Persistent record of a captured scene."""

    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(String(64), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    environment_id = Column(String(64), default="default", nullable=False)
    image_path = Column(String(512), nullable=True)
    annotated_image_path = Column(String(512), nullable=True)
    object_count = Column(Integer, default=0)
    processing_time_ms = Column(Float, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    observations = relationship("ObservationRecord", back_populates="scene", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SceneRecord(scene_id={self.scene_id!r}, objects={self.object_count})>"
