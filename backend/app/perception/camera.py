"""
Camera and input source abstractions.

Provides a unified interface for ingesting images from different sources:
single image files, video files, USB/webcam, and (future) ROS2 topics.

Each source implements ``read_frame()`` which returns a BGR numpy array,
and ``release()`` for cleanup.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class CameraSource(ABC):
    """
    Abstract base class for all camera/input sources.

    Subclasses implement frame acquisition from their specific medium.
    """

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read the next frame.

        Returns:
            BGR image as numpy array, or None if no frame available.
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Release underlying resources (file handles, camera devices)."""
        ...

    @abstractmethod
    def is_opened(self) -> bool:
        """Check whether the source is open and readable."""
        ...

    @property
    def source_type(self) -> str:
        """Human-readable source type identifier."""
        return self.__class__.__name__


class ImageSource(CameraSource):
    """
    Single image file source.

    Reads one image from disk. After the first ``read_frame()`` call,
    subsequent calls return None (the image has been consumed).
    """

    def __init__(self, image_path: str | Path):
        self._path = Path(image_path)
        self._consumed = False
        self._image: Optional[np.ndarray] = None

        if not self._path.exists():
            raise FileNotFoundError(f"Image not found: {self._path}")

        logger.info("ImageSource initialized: %s", self._path.name)

    def read_frame(self) -> Optional[np.ndarray]:
        if self._consumed:
            return None

        self._image = cv2.imread(str(self._path))
        if self._image is None:
            logger.error("Failed to read image: %s", self._path)
            return None

        self._consumed = True
        h, w = self._image.shape[:2]
        logger.info("Image loaded: %dx%d — %s", w, h, self._path.name)
        return self._image

    def release(self) -> None:
        self._image = None
        self._consumed = True

    def is_opened(self) -> bool:
        return not self._consumed


class VideoSource(CameraSource):
    """
    Video file source with configurable frame skipping.

    Processes every Nth frame (configured via ``PROCESS_EVERY_N_FRAMES``)
    to avoid unnecessary inference on redundant frames.
    """

    def __init__(self, video_path: str | Path, process_every_n: Optional[int] = None):
        self._path = Path(video_path)
        settings = get_settings()
        self._process_every_n = process_every_n or settings.process_every_n_frames
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0

        if not self._path.exists():
            raise FileNotFoundError(f"Video not found: {self._path}")

        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video: {self._path}")

        total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        logger.info(
            "VideoSource initialized: %s (%.0f fps, %d frames, processing every %d)",
            self._path.name, fps, total_frames, self._process_every_n,
        )

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None

        while True:
            ret, frame = self._cap.read()
            if not ret:
                return None

            self._frame_count += 1
            if self._frame_count % self._process_every_n == 0:
                logger.debug("Processing frame %d", self._frame_count)
                return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("VideoSource released: %s", self._path.name)

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def frame_count(self) -> int:
        return self._frame_count


class WebcamSource(CameraSource):
    """
    USB/webcam camera source.

    Opens a live camera device by index (default 0).
    """

    def __init__(self, device_index: int = 0):
        self._device_index = device_index
        self._cap: Optional[cv2.VideoCapture] = None

        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open webcam device {device_index}")

        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("WebcamSource initialized: device %d (%dx%d)", device_index, w, h)

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        return frame if ret else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("WebcamSource released: device %d", self._device_index)

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()


# --- Future Extension Point ---
# class ROS2CameraSource(CameraSource):
#     """
#     ROS2 camera topic subscriber.
#
#     Subscribes to a sensor_msgs/Image topic and converts frames
#     via cv_bridge. Requires rclpy and cv_bridge packages.
#
#     Planned for Phase 12 — ROS2 Jazzy integration.
#     """
#     pass
