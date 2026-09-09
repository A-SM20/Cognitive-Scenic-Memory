"""
Pydantic schemas for detection API requests and responses.

These schemas define the wire format between the backend API and
the frontend. They are intentionally decoupled from the ORM models
so that the API surface can evolve independently of the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box in pixel coordinates."""
    x: float = Field(description="Top-left x coordinate")
    y: float = Field(description="Top-left y coordinate")
    w: float = Field(description="Width in pixels")
    h: float = Field(description="Height in pixels")


class Detection(BaseModel):
    """A single object detection from the perception pipeline."""
    class_name: str = Field(description="Detected object class (e.g., 'person', 'laptop')")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence score")
    bbox: BoundingBox = Field(description="Bounding box in pixel coordinates")
    center_x: float = Field(description="Object center x coordinate")
    center_y: float = Field(description="Object center y coordinate")
    width: float = Field(description="Bounding box width")
    height: float = Field(description="Bounding box height")
    timestamp: datetime = Field(description="Detection timestamp")
    frame_id: int = Field(default=0, description="Frame index (0 for single images)")
    track_id: Optional[int] = Field(default=None, description="Unique track ID for the object")


class DetectionResult(BaseModel):
    """Complete result of processing a single image/frame."""
    scene_id: str = Field(description="Unique scene identifier")
    image_path: str = Field(description="Path to the original uploaded image")
    annotated_image_path: str = Field(description="Path to the annotated output image")
    annotated_image_url: str = Field(description="URL to access the annotated image")
    detections: list[Detection] = Field(default_factory=list, description="List of detections")
    total_objects: int = Field(description="Number of objects detected")
    processing_time_ms: float = Field(description="Inference time in milliseconds")
    model_name: str = Field(description="Model used for detection")
    image_width: int = Field(description="Original image width")
    image_height: int = Field(description="Original image height")
    timestamp: datetime = Field(description="Processing timestamp")


class SceneResponse(BaseModel):
    """API response for a scene record."""
    scene_id: str
    timestamp: datetime
    environment_id: str
    image_path: Optional[str] = None
    annotated_image_path: Optional[str] = None
    object_count: int = 0
    processing_time_ms: Optional[float] = None
    created_at: datetime


class ObjectResponse(BaseModel):
    """API response for a persistent object record."""
    object_id: str
    class_name: str
    display_name: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    last_position_x: Optional[float] = None
    last_position_y: Optional[float] = None
    observation_count: int = 0
    current_confidence: float = 1.0
    identity_confidence: float = 1.0
    status: str = "ACTIVE"


class HealthResponse(BaseModel):
    """API response for system health check."""
    status: str = "ok"
    project_name: str
    version: str
    model_name: str
    model_loaded: bool
    database_connected: bool
    features: dict
    timestamp: datetime


class QueryRequest(BaseModel):
    """Natural language query request."""
    query: str = Field(min_length=1, description="Natural language question")


class QueryResponse(BaseModel):
    """Structured response to a natural language query."""
    query: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    timestamp: datetime


# ── Phase 4-7 Schemas ──────────────────────────────────────────────


class SpatialRelationshipResponse(BaseModel):
    """A directed spatial relationship between two objects."""
    source_object_id: str
    target_object_id: str
    source_class: Optional[str] = None
    target_class: Optional[str] = None
    relationship_type: str
    confidence: float = 1.0
    distance_px: Optional[float] = None


class SceneGraphNodeResponse(BaseModel):
    """A node in the scene graph representing an observed object."""
    object_id: str
    class_name: str
    display_name: Optional[str] = None
    center_x: float
    center_y: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    confidence: float
    status: str = "ACTIVE"


class SceneGraphResponse(BaseModel):
    """Complete scene graph with nodes (objects) and edges (relationships)."""
    scene_id: str
    node_count: int
    edge_count: int
    nodes: list[SceneGraphNodeResponse] = Field(default_factory=list)
    edges: list[SpatialRelationshipResponse] = Field(default_factory=list)
    timestamp: datetime


class ChangeEventResponse(BaseModel):
    """A detected change between two scenes."""
    id: int
    scene_before_id: str
    scene_after_id: str
    object_id: Optional[str] = None
    change_type: str
    description: str
    magnitude: Optional[float] = None
    old_value_json: Optional[str] = None
    new_value_json: Optional[str] = None
    created_at: datetime


class SceneComparisonResponse(BaseModel):
    """Full comparison result between two scenes."""
    scene_before_id: str
    scene_after_id: str
    total_changes: int
    changes: list[ChangeEventResponse] = Field(default_factory=list)
    summary: dict = Field(
        default_factory=dict,
        description="Breakdown by change type: {ADDED: n, REMOVED: n, MOVED: n, ...}",
    )
    timestamp: datetime


class MemoryObjectResponse(BaseModel):
    """Object with full confidence and lifecycle state for the memory dashboard."""
    object_id: str
    class_name: str
    display_name: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    last_position_x: Optional[float] = None
    last_position_y: Optional[float] = None
    observation_count: int = 0
    current_confidence: float = 1.0
    identity_confidence: float = 1.0
    status: str = "ACTIVE"
    scenes_since_last_seen: int = 0


class MemorySummaryResponse(BaseModel):
    """Summary of the cognitive memory state."""
    total_objects: int = 0
    active: int = 0
    possibly_missing: int = 0
    missing: int = 0
    removed: int = 0
    unknown: int = 0
    total_scenes: int = 0
    average_confidence: float = 0.0
    timestamp: datetime

