"""
Tests for the Memory Service (Phase 5 — Cognitive Confidence Model).

Tests confidence decay, Bayesian reinforcement, and object lifecycle
transitions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.memory_service import MemoryService


class FakeObjectRecord:
    """Minimal fake for ObjectRecord used in tests."""
    def __init__(self, object_id, class_name, status="ACTIVE",
                 current_confidence=1.0, last_position_x=100.0,
                 last_position_y=100.0):
        self.id = hash(object_id) % 10000
        self.object_id = object_id
        self.class_name = class_name
        self.display_name = class_name
        self.status = status
        self.current_confidence = current_confidence
        self.identity_confidence = 1.0
        self.last_position_x = last_position_x
        self.last_position_y = last_position_y
        self.first_seen = datetime.now(timezone.utc)
        self.last_seen = datetime.now(timezone.utc)
        self.observation_count = 1


def _make_sync_result(rows=None, scalars_list=None, scalar_value=None,
                      scalar_one=None):
    """Create a mock result object that mimics SQLAlchemy's sync-style result access.
    
    SQLAlchemy async execute() returns a regular result object (not coroutines)
    for .all(), .scalars(), .scalar(), etc.
    """
    result = MagicMock()
    
    if rows is not None:
        result.all = MagicMock(return_value=rows)
    
    if scalars_list is not None:
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=scalars_list)
        result.scalars = MagicMock(return_value=scalars_mock)
    
    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    
    if scalar_one is not None:
        result.scalar_one_or_none = MagicMock(return_value=scalar_one)
    
    return result


def test_lifecycle_thresholds():
    """Verify the lifecycle threshold constants are properly ordered."""
    assert MemoryService.THRESHOLD_POSSIBLY_MISSING > MemoryService.THRESHOLD_MISSING
    assert MemoryService.THRESHOLD_MISSING > MemoryService.THRESHOLD_REMOVED
    assert MemoryService.THRESHOLD_REMOVED > 0.0


def test_lifecycle_threshold_values():
    """Verify specific threshold values."""
    assert MemoryService.THRESHOLD_POSSIBLY_MISSING == 0.50
    assert MemoryService.THRESHOLD_MISSING == 0.20
    assert MemoryService.THRESHOLD_REMOVED == 0.05


@pytest.mark.asyncio
async def test_decay_unseen_objects():
    """Test that objects not seen in a scene get confidence decayed."""
    db = AsyncMock()
    
    # Object observed in scene
    observed_obj = FakeObjectRecord("OBJ-001", "laptop", current_confidence=1.0)
    # Object NOT observed in scene
    unseen_obj = FakeObjectRecord("OBJ-002", "cup", current_confidence=0.8)

    # First call: observed object IDs in this scene
    obs_result = _make_sync_result(rows=[("OBJ-001",)])
    # Second call: candidates for decay
    candidates_result = _make_sync_result(scalars_list=[observed_obj, unseen_obj])

    db.execute = AsyncMock(side_effect=[obs_result, candidates_result])
    db.flush = AsyncMock()

    svc = MemoryService(db)
    decayed = await svc.decay_unseen_objects("SCENE-TEST")

    assert decayed == 1
    # OBJ-001 should not be decayed (it was observed)
    assert observed_obj.current_confidence == 1.0
    # OBJ-002 should be decayed: 0.8 * (1 - 0.15) = 0.68
    assert abs(unseen_obj.current_confidence - 0.68) < 0.01


@pytest.mark.asyncio
async def test_reinforce_object():
    """Test Bayesian reinforcement blends observation with current confidence."""
    db = AsyncMock()
    
    obj = FakeObjectRecord("OBJ-001", "laptop", current_confidence=0.5, status="POSSIBLY_MISSING")
    
    result = _make_sync_result(scalar_one=obj)
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    svc = MemoryService(db)
    new_conf = await svc.reinforce_object("OBJ-001", 0.9)

    # Expected: 0.7 * 0.9 + 0.3 * 0.5 = 0.63 + 0.15 = 0.78
    assert abs(new_conf - 0.78) < 0.01
    assert obj.status == "ACTIVE"  # Should be restored


@pytest.mark.asyncio
async def test_lifecycle_transitions():
    """Test that objects transition through status states based on confidence."""
    db = AsyncMock()
    
    active_obj = FakeObjectRecord("OBJ-001", "laptop", status="ACTIVE", current_confidence=0.45)
    missing_candidate = FakeObjectRecord("OBJ-002", "cup", status="ACTIVE", current_confidence=0.15)
    remove_candidate = FakeObjectRecord("OBJ-003", "book", status="MISSING", current_confidence=0.03)

    result = _make_sync_result(scalars_list=[active_obj, missing_candidate, remove_candidate])
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    svc = MemoryService(db)
    transitions = await svc.update_object_lifecycle()

    assert active_obj.status == "POSSIBLY_MISSING"
    assert missing_candidate.status == "MISSING"
    assert remove_candidate.status == "REMOVED"
    assert transitions["to_possibly_missing"] == 1
    assert transitions["to_missing"] == 1
    assert transitions["to_removed"] == 1
