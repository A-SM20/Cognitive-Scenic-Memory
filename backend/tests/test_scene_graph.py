"""
Tests for the Scene Graph Service (Phase 6 — Semantic Scene Graph).

Tests spatial relationship computation from bounding-box heuristics.
"""

import pytest
from app.services.scene_graph_service import compute_relationships


def _make_obs(object_id, class_name, cx, cy, bx, by, bw, bh):
    """Helper to create observation dicts for testing."""
    return {
        "object_id": object_id,
        "class_name": class_name,
        "center_x": cx,
        "center_y": cy,
        "bbox_x": bx,
        "bbox_y": by,
        "bbox_w": bw,
        "bbox_h": bh,
    }


def test_near_relationship():
    """Two objects close together should have a NEAR relationship."""
    obs_a = _make_obs("OBJ-A", "cup", 100, 100, 80, 80, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 150, 120, 130, 100, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "NEAR" in rel_types


def test_not_near_far_apart():
    """Two objects far apart should NOT have a NEAR relationship."""
    obs_a = _make_obs("OBJ-A", "cup", 100, 100, 80, 80, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 500, 500, 480, 480, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "NEAR" not in rel_types


def test_left_of_relationship():
    """Object A to the left of Object B should have LEFT_OF."""
    obs_a = _make_obs("OBJ-A", "cup", 100, 200, 80, 180, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 250, 200, 230, 180, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "LEFT_OF" in rel_types


def test_right_of_relationship():
    """Object A to the right of Object B should have RIGHT_OF."""
    obs_a = _make_obs("OBJ-A", "cup", 300, 200, 280, 180, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 100, 200, 80, 180, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "RIGHT_OF" in rel_types


def test_above_relationship():
    """Object A above Object B should have ABOVE."""
    obs_a = _make_obs("OBJ-A", "cup", 200, 100, 180, 80, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 200, 250, 180, 230, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "ABOVE" in rel_types


def test_below_relationship():
    """Object A below Object B should have BELOW."""
    obs_a = _make_obs("OBJ-A", "cup", 200, 300, 180, 280, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 200, 100, 180, 80, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "BELOW" in rel_types


def test_on_relationship():
    """Object A sitting on top of Object B (bottom of A near top of B)."""
    # A: laptop sitting ON B: desk
    # A's bottom edge (y + h = 200) is near B's top edge (y = 205)
    obs_a = _make_obs("OBJ-A", "laptop", 200, 170, 120, 140, 160, 60)
    obs_b = _make_obs("OBJ-B", "desk", 200, 260, 100, 205, 200, 110)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "ON" in rel_types


def test_contains_relationship():
    """Large object containing a small object."""
    # Large box
    obs_a = _make_obs("OBJ-A", "desk", 200, 200, 100, 100, 200, 200)
    # Small object inside
    obs_b = _make_obs("OBJ-B", "cup", 200, 200, 170, 170, 60, 60)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    assert "CONTAINS" in rel_types


def test_confidence_values():
    """All relationship confidences should be in [0, 1]."""
    obs_a = _make_obs("OBJ-A", "cup", 100, 100, 80, 80, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 130, 110, 110, 90, 40, 40)

    rels = compute_relationships(obs_a, obs_b)

    for rel in rels:
        assert 0.0 <= rel["confidence"] <= 1.0, f"Bad confidence: {rel}"
        assert rel["distance_px"] >= 0, f"Bad distance: {rel}"


def test_empty_when_identical_position():
    """Objects at the same position shouldn't produce LEFT_OF/RIGHT_OF with small overlap."""
    obs_a = _make_obs("OBJ-A", "cup", 200, 200, 180, 180, 40, 40)
    obs_b = _make_obs("OBJ-B", "book", 200, 200, 180, 180, 40, 40)

    rels = compute_relationships(obs_a, obs_b)
    rel_types = [r["relationship_type"] for r in rels]

    # Should still be NEAR (distance = 0) but NOT LEFT_OF or RIGHT_OF
    assert "LEFT_OF" not in rel_types
    assert "RIGHT_OF" not in rel_types
