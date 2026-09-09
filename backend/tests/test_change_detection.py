"""
Tests for the Change Detection Service (Phase 7).

Tests ADDED, REMOVED, MOVED, REPLACED detection and description generation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.change_detection_service import (
    ChangeDetectionService,
    CONFIDENCE_CHANGE_THRESHOLD,
    SAME_LOCATION_THRESHOLD_PX,
)


class FakeObservation:
    """Minimal fake for ObservationRecord."""
    def __init__(self, object_id, class_name, cx, cy, bx, by, bw, bh,
                 confidence=0.9, visibility="VISIBLE"):
        self.object_id = object_id
        self.class_name = class_name
        self.position_x = cx
        self.position_y = cy
        self.bbox_x = bx
        self.bbox_y = by
        self.bbox_w = bw
        self.bbox_h = bh
        self.confidence = confidence
        self.visibility = visibility


def _make_db_with_observations(before_obs, after_obs):
    """Create a mock db that returns before/after observations.
    
    SQLAlchemy's execute() is async, but the returned result's
    .scalars().all() are synchronous methods.
    """
    db = AsyncMock()
    
    call_count = 0
    
    async def mock_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        scalars_mock = MagicMock()
        
        if call_count == 0:
            scalars_mock.all.return_value = before_obs
        else:
            scalars_mock.all.return_value = after_obs
        
        result.scalars.return_value = scalars_mock
        call_count += 1
        return result
    
    db.execute = mock_execute
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def test_threshold_constants():
    """Verify threshold constants exist and are reasonable."""
    assert CONFIDENCE_CHANGE_THRESHOLD > 0
    assert SAME_LOCATION_THRESHOLD_PX > 0


@pytest.mark.asyncio
async def test_detect_added():
    """New objects in scene_after should be detected as ADDED."""
    before = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
    ]
    after = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
        FakeObservation("OBJ-002", "cup", 300, 300, 280, 280, 40, 40),
    ]

    db = _make_db_with_observations(before, after)
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    added = [c for c in changes if c.change_type == "ADDED"]
    assert len(added) == 1
    assert added[0].object_id == "OBJ-002"
    assert "cup" in added[0].description


@pytest.mark.asyncio
async def test_detect_removed():
    """Objects in scene_before but not scene_after should be REMOVED."""
    before = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
        FakeObservation("OBJ-002", "cup", 300, 300, 280, 280, 40, 40),
    ]
    after = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
    ]

    db = _make_db_with_observations(before, after)
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    removed = [c for c in changes if c.change_type == "REMOVED"]
    assert len(removed) == 1
    assert removed[0].object_id == "OBJ-002"
    assert "cup" in removed[0].description


@pytest.mark.asyncio
async def test_detect_moved():
    """Same object with position change > threshold should be MOVED."""
    before = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
    ]
    after = [
        FakeObservation("OBJ-001", "laptop", 300, 100, 280, 80, 40, 40),  # moved 200px right
    ]

    db = _make_db_with_observations(before, after)
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    moved = [c for c in changes if c.change_type == "MOVED"]
    assert len(moved) == 1
    assert moved[0].magnitude > 50.0
    assert "right" in moved[0].description.lower()


@pytest.mark.asyncio
async def test_no_change_when_stationary():
    """Objects at the same position should NOT generate MOVED events."""
    before = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40),
    ]
    after = [
        FakeObservation("OBJ-001", "laptop", 110, 105, 90, 85, 40, 40),  # minor shift
    ]

    db = _make_db_with_observations(before, after)
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    moved = [c for c in changes if c.change_type == "MOVED"]
    assert len(moved) == 0  # below movement threshold


@pytest.mark.asyncio
async def test_empty_scenes():
    """Comparing two empty scenes should produce no changes."""
    db = _make_db_with_observations([], [])
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    assert len(changes) == 0


@pytest.mark.asyncio
async def test_detect_confidence_changed():
    """Significant confidence shift should be detected."""
    before = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40, confidence=0.9),
    ]
    after = [
        FakeObservation("OBJ-001", "laptop", 100, 100, 80, 80, 40, 40, confidence=0.5),
    ]

    db = _make_db_with_observations(before, after)
    svc = ChangeDetectionService(db)
    changes = await svc.compare_scenes("SCENE-A", "SCENE-B")

    conf_changes = [c for c in changes if c.change_type == "CONFIDENCE_CHANGED"]
    assert len(conf_changes) == 1
    assert "decreased" in conf_changes[0].description
