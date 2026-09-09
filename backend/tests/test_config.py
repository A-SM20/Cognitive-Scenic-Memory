"""
Tests for the centralized configuration system.

Validates that settings load correctly from defaults and that
all critical parameters have sensible values.
"""

import os

import pytest


def test_settings_defaults():
    """Settings should have sensible defaults without any env file."""
    # Clear any env vars that might interfere
    from app.config import Settings

    settings = Settings()

    assert settings.model_name == "yolov8n.pt"
    assert settings.confidence_threshold == 0.40
    assert settings.iou_threshold == 0.50
    assert settings.process_every_n_frames == 10
    assert settings.enable_segmentation is False
    assert settings.enable_feature_matching is True
    assert settings.enable_depth is False
    assert settings.enable_llm is False
    assert settings.confidence_decay == 0.15
    assert settings.movement_threshold == 50.0
    assert settings.log_level == "INFO"


def test_confidence_threshold_bounds():
    """Confidence threshold must be between 0 and 1."""
    from app.config import Settings

    settings = Settings(confidence_threshold=0.0)
    assert settings.confidence_threshold == 0.0

    settings = Settings(confidence_threshold=1.0)
    assert settings.confidence_threshold == 1.0

    with pytest.raises(Exception):
        Settings(confidence_threshold=1.5)

    with pytest.raises(Exception):
        Settings(confidence_threshold=-0.1)


def test_process_every_n_frames_minimum():
    """Process every N frames must be at least 1."""
    from app.config import Settings

    settings = Settings(process_every_n_frames=1)
    assert settings.process_every_n_frames == 1

    with pytest.raises(Exception):
        Settings(process_every_n_frames=0)


def test_settings_from_env(monkeypatch):
    """Settings should pick up values from environment variables."""
    monkeypatch.setenv("MODEL_NAME", "yolov8s.pt")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.65")
    monkeypatch.setenv("ENABLE_SEGMENTATION", "true")

    from app.config import Settings

    settings = Settings()
    assert settings.model_name == "yolov8s.pt"
    assert settings.confidence_threshold == 0.65
    assert settings.enable_segmentation is True


def test_project_identity():
    """Project name and version should be set."""
    from app.config import Settings

    settings = Settings()
    assert settings.project_name == "Cognitive Scene Memory"
    assert settings.project_version == "0.1.0"
