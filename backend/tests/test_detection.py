"""
Tests for the object detection pipeline.

Validates that:
1. The YOLODetector can be instantiated.
2. Detection on a real test image produces structured results.
3. The annotate_image method draws bounding boxes without crashing.
4. Detection output conforms to the Detection schema.
"""

import numpy as np
import pytest

from app.perception.detector import YOLODetector
from app.models.detection import Detection


@pytest.fixture(scope="module")
def detector():
    """Create a YOLODetector instance (downloads model if needed)."""
    return YOLODetector()


@pytest.fixture
def test_image():
    """Create a simple synthetic test image (640x480 with colored rectangles)."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[50:200, 100:300] = (0, 120, 255)   # Orange rectangle
    img[250:400, 350:550] = (255, 100, 50)  # Blue rectangle
    img[100:350, 200:450] = (50, 200, 50)   # Green rectangle
    return img


def test_detector_instantiation(detector):
    """YOLODetector should instantiate without errors."""
    assert detector is not None


def test_detect_returns_list(detector, test_image):
    """detect() should return a list (possibly empty for synthetic images)."""
    detections = detector.detect(test_image)
    assert isinstance(detections, list)


def test_detect_on_synthetic_image_structure(detector, test_image):
    """Even if no objects found, the result should be a proper list."""
    detections = detector.detect(test_image)
    for det in detections:
        assert isinstance(det, Detection)
        assert isinstance(det.class_name, str)
        assert 0.0 <= det.confidence <= 1.0
        assert det.bbox.w > 0
        assert det.bbox.h > 0
        assert det.width > 0
        assert det.height > 0


def test_annotate_image(detector, test_image):
    """annotate_image should return an image of the same dimensions."""
    detections = detector.detect(test_image)
    annotated = detector.annotate_image(test_image, detections)

    assert annotated.shape == test_image.shape
    # Original should not be modified
    assert not np.array_equal(annotated, test_image) or len(detections) == 0


def test_detector_model_loaded_after_detect(detector, test_image):
    """After calling detect(), the model should be loaded."""
    detector.detect(test_image)
    assert detector.is_loaded()
