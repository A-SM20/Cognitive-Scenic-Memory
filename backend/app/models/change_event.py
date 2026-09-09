"""
Change Event ORM model.

Each record captures a detected change between two scenes — for example,
an object that was ADDED, REMOVED, MOVED, or REPLACED. Change events
are computed by the ChangeDetectionService when comparing scene pairs.

Change types:
  ADDED, REMOVED, MOVED, REPLACED, STATUS_CHANGED, CONFIDENCE_CHANGED
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ChangeEventRecord(Base):
    """A detected change between two scenes."""

    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_before_id = Column(
        String(64),
        ForeignKey("scenes.scene_id"),
        nullable=False,
        index=True,
        doc="Scene before the change",
    )
    scene_after_id = Column(
        String(64),
        ForeignKey("scenes.scene_id"),
        nullable=False,
        index=True,
        doc="Scene after the change",
    )
    object_id = Column(
        String(64),
        ForeignKey("objects.object_id"),
        nullable=True,
        index=True,
        doc="The object involved (NULL for newly ADDED objects not yet tracked)",
    )
    change_type = Column(
        String(32),
        nullable=False,
        index=True,
        doc="ADDED | REMOVED | MOVED | REPLACED | STATUS_CHANGED | CONFIDENCE_CHANGED",
    )
    description = Column(
        Text,
        nullable=False,
        doc="Human-readable change description",
    )
    magnitude = Column(
        Float,
        nullable=True,
        doc="Quantified change magnitude (px for MOVED, delta for confidence)",
    )
    old_value_json = Column(
        Text,
        nullable=True,
        doc="JSON-serialized state before the change",
    )
    new_value_json = Column(
        Text,
        nullable=True,
        doc="JSON-serialized state after the change",
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    scene_before = relationship(
        "SceneRecord",
        foreign_keys=[scene_before_id],
        backref="changes_as_before",
    )
    scene_after = relationship(
        "SceneRecord",
        foreign_keys=[scene_after_id],
        backref="changes_as_after",
    )
    object = relationship(
        "ObjectRecord",
        backref="change_events",
    )

    def __repr__(self) -> str:
        return (
            f"<ChangeEvent({self.change_type} "
            f"object={self.object_id!r} "
            f"{self.scene_before_id!r}→{self.scene_after_id!r})>"
        )
