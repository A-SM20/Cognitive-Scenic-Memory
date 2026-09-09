"""
Spatial Relationship ORM model.

Each record represents a directed spatial relationship between two objects
within a specific scene. These edges form the scene graph, computed by
the SceneGraphService using bounding-box heuristics.

Relationship types:
  ON, UNDER, LEFT_OF, RIGHT_OF, NEAR, CONTAINS, INSIDE,
  ABOVE, BELOW, ADJACENT
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SpatialRelationshipRecord(Base):
    """A directed spatial relationship between two objects in a scene."""

    __tablename__ = "spatial_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(
        String(64),
        ForeignKey("scenes.scene_id"),
        nullable=False,
        index=True,
        doc="Scene where this relationship was computed",
    )
    source_object_id = Column(
        String(64),
        ForeignKey("objects.object_id"),
        nullable=False,
        index=True,
        doc="Subject object (e.g., 'the laptop')",
    )
    target_object_id = Column(
        String(64),
        ForeignKey("objects.object_id"),
        nullable=False,
        index=True,
        doc="Reference object (e.g., 'the desk')",
    )
    relationship_type = Column(
        String(32),
        nullable=False,
        index=True,
        doc="ON | UNDER | LEFT_OF | RIGHT_OF | NEAR | CONTAINS | INSIDE | ABOVE | BELOW | ADJACENT",
    )
    confidence = Column(
        Float,
        default=1.0,
        nullable=False,
        doc="Confidence of this spatial inference [0, 1]",
    )
    distance_px = Column(
        Float,
        nullable=True,
        doc="Euclidean distance between object centers in pixels",
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    scene = relationship("SceneRecord", backref="spatial_relationships")
    source_object = relationship(
        "ObjectRecord",
        foreign_keys=[source_object_id],
        backref="relationships_as_source",
    )
    target_object = relationship(
        "ObjectRecord",
        foreign_keys=[target_object_id],
        backref="relationships_as_target",
    )

    def __repr__(self) -> str:
        return (
            f"<SpatialRelationship({self.source_object_id!r} "
            f"{self.relationship_type} {self.target_object_id!r})>"
        )
