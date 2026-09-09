"""
Observation ORM model.

Each observation records a single sighting of an object within a scene.
Observations link objects to scenes and capture per-frame detection
details (bounding box, position, confidence).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ObservationRecord(Base):
    """A single observation of an object within a scene."""

    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(String(64), ForeignKey("objects.object_id"), nullable=False, index=True)
    scene_id = Column(String(64), ForeignKey("scenes.scene_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    bbox_x = Column(Float, nullable=False, doc="Bounding box top-left x")
    bbox_y = Column(Float, nullable=False, doc="Bounding box top-left y")
    bbox_w = Column(Float, nullable=False, doc="Bounding box width")
    bbox_h = Column(Float, nullable=False, doc="Bounding box height")
    position_x = Column(Float, nullable=False, doc="Object center x (image coordinates)")
    position_y = Column(Float, nullable=False, doc="Object center y (image coordinates)")
    position_z = Column(Float, nullable=True, doc="Depth (requires depth camera)")
    confidence = Column(Float, nullable=False)
    class_name = Column(String(128), nullable=False)
    visibility = Column(
        String(32),
        default="VISIBLE",
        nullable=False,
        doc="VISIBLE | OCCLUDED | OUT_OF_VIEW | MISSING | REMOVED | UNKNOWN",
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    object = relationship("ObjectRecord", back_populates="observations")
    scene = relationship("SceneRecord", back_populates="observations")

    def __repr__(self) -> str:
        return (
            f"<ObservationRecord(object_id={self.object_id!r}, "
            f"scene_id={self.scene_id!r}, class={self.class_name!r})>"
        )
