"""
Object detection abstraction with YOLO implementation.

Provides a ``BaseDetector`` interface and a concrete ``YOLODetector``
that uses Ultralytics for real inference. The architecture allows
future detector backends (e.g., DETR, custom models) by implementing
the same interface.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np

from app.config import get_settings
from app.logging_config import get_logger
from app.models.detection import BoundingBox, Detection

logger = get_logger(__name__)


class BaseDetector(ABC):
    """
    Abstract base class for object detectors.

    Subclasses must implement ``detect()`` which takes a BGR image
    (numpy array) and returns a list of structured ``Detection`` objects.
    """

    @abstractmethod
    def detect(self, image: np.ndarray, frame_id: int = 0, track: bool = False) -> list[Detection]:
        """
        Run object detection on an image.

        Args:
            image: BGR image as a numpy array (H, W, C).
            frame_id: Frame index for video streams (0 for single images).

        Returns:
            List of Detection objects with class, confidence, and bbox.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check whether the detection model is loaded and ready."""
        ...

    def annotate_image(
        self,
        image: np.ndarray,
        detections: list[Detection],
    ) -> np.ndarray:
        """
        Draw detection bounding boxes and labels on an image copy.

        Args:
            image: Original BGR image (not modified).
            detections: List of detections to draw.

        Returns:
            Annotated image copy.
        """
        annotated = image.copy()

        for det in detections:
            x, y = int(det.bbox.x), int(det.bbox.y)
            w, h = int(det.bbox.w), int(det.bbox.h)

            # Color based on confidence: green (high) → yellow → red (low)
            conf = det.confidence
            if conf >= 0.7:
                color = (0, 230, 118)     # emerald green
            elif conf >= 0.5:
                color = (0, 215, 255)     # amber
            else:
                color = (80, 120, 255)    # soft red

            # Draw bounding box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

            # Label background
            label = f"{det.class_name} {conf:.0%}"
            if det.track_id is not None:
                label = f"[{det.track_id}] {label}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
            )
            cv2.rectangle(
                annotated,
                (x, y - label_h - baseline - 6),
                (x + label_w + 6, y),
                color,
                cv2.FILLED,
            )

            # Label text
            cv2.putText(
                annotated,
                label,
                (x + 3, y - baseline - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        return annotated


class YOLODetector(BaseDetector):
    """
    Object detector using Ultralytics YOLO.

    Performs real inference — no fake or random detections. The model
    weights are downloaded automatically on first use.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
    ):
        settings = get_settings()
        self._model_name = model_name or settings.model_name
        self._conf_threshold = confidence_threshold or settings.confidence_threshold
        self._iou_threshold = iou_threshold or settings.iou_threshold
        self._model = None

    def _load_model(self) -> None:
        """Lazy-load the YOLO model on first detection call."""
        if self._model is not None:
            return

        logger.info("Loading YOLO model: %s", self._model_name)
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_name)
            logger.info("YOLO model loaded successfully: %s", self._model_name)
        except Exception as e:
            logger.error("Failed to load YOLO model '%s': %s", self._model_name, e)
            raise RuntimeError(f"Failed to load YOLO model: {e}") from e

    def is_loaded(self) -> bool:
        """Check if the YOLO model is loaded."""
        return self._model is not None

    def detect(self, image: np.ndarray, frame_id: int = 0, track: bool = False) -> list[Detection]:
        """
        Run YOLO inference or tracking on a BGR image.

        Args:
            image: BGR image as numpy array.
            frame_id: Frame index (0 for single images).
            track: If True, run object tracking (ByteTrack/BoT-SORT) to assign track IDs.

        Returns:
            List of Detection objects from real YOLO inference.
        """
        self._load_model()

        now = datetime.now(timezone.utc)

        logger.info("Running YOLO inference (frame=%d, conf≥%.2f, iou≥%.2f)",
                     frame_id, self._conf_threshold, self._iou_threshold)

        start = time.perf_counter()

        if track:
            results = self._model.track(
                image,
                persist=True,
                tracker="botsort.yaml",
                conf=self._conf_threshold,
                iou=self._iou_threshold,
                verbose=False,
            )
        else:
            results = self._model(
                image,
                conf=self._conf_threshold,
                iou=self._iou_threshold,
                verbose=False,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        detections: list[Detection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                # xyxy format: [x1, y1, x2, y2]
                xyxy = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                class_name = result.names[cls_id]

                track_id = None
                if boxes.id is not None:
                    track_id = int(boxes.id[i].cpu().numpy())

                bbox_w = x2 - x1
                bbox_h = y2 - y1
                center_x = x1 + bbox_w / 2
                center_y = y1 + bbox_h / 2

                detection = Detection(
                    class_name=class_name,
                    confidence=round(conf, 4),
                    bbox=BoundingBox(x=round(x1, 1), y=round(y1, 1),
                                     w=round(bbox_w, 1), h=round(bbox_h, 1)),
                    center_x=round(center_x, 1),
                    center_y=round(center_y, 1),
                    width=round(bbox_w, 1),
                    height=round(bbox_h, 1),
                    timestamp=now,
                    frame_id=frame_id,
                    track_id=track_id,
                )
                detections.append(detection)

        logger.info(
            "%d objects detected in %.1f ms",
            len(detections), elapsed_ms,
        )

        return detections
