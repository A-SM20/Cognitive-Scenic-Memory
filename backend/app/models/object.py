"""
Persistent Object ORM model.

Represents a unique object that the system has identified and remembered
across observations. Each object has a persistent identity, confidence
state, and observation history.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ObjectRecord(Base):
    """Persistent memory record of a recognized object."""

    __tablename__ = "objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(String(64), unique=True, nullable=False, index=True)
    class_name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(256), nullable=True)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_position_x = Column(Float, nullable=True)
    last_position_y = Column(Float, nullable=True)
    last_position_z = Column(Float, nullable=True)
    observation_count = Column(Integer, default=1)
    current_confidence = Column(Float, default=1.0)
    identity_confidence = Column(Float, default=1.0)
    status = Column(
        String(32),
        default="ACTIVE",
        nullable=False,
        doc="ACTIVE | POSSIBLY_MISSING | MISSING | REMOVED | UNKNOWN",
    )
    feature_data = Column(Text, nullable=True, doc="Serialized feature descriptors (JSON)")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    observations = relationship("ObservationRecord", back_populates="object", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<ObjectRecord(object_id={self.object_id!r}, "
            f"class={self.class_name!r}, status={self.status!r})>"
        )
