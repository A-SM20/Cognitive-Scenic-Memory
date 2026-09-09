"""
Detection service — orchestrates the image processing pipeline.

Responsibilities:
1. Accept an image (file upload bytes or filesystem path).
2. Decode the image via OpenCV.
3. Run real YOLO inference through the detector abstraction.
4. Generate an annotated image with bounding boxes.
5. Save both original and annotated images to the uploads directory.
6. Persist the scene and observations to the database.
7. Return a structured DetectionResult.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models.detection import Detection, DetectionResult
from app.models.scene import SceneRecord
from app.models.object import ObjectRecord
from app.models.observation import ObservationRecord
from app.perception.detector import BaseDetector, YOLODetector

logger = get_logger(__name__)

# Module-level singleton detector (lazy loaded)
_detector: Optional[BaseDetector] = None


def get_detector() -> BaseDetector:
    """Get or create the singleton YOLO detector."""
    global _detector
    if _detector is None:
        _detector = YOLODetector()
    return _detector


class DetectionService:
    """
    High-level service that runs the full detection pipeline.

    This service is the primary entry point for the ``POST /api/process/image``
    endpoint. It coordinates perception, annotation, persistence, and
    response formatting.
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self._db = db
        self._settings = get_settings()
        self._detector = get_detector()

    async def process_image_bytes(
        self,
        image_bytes: bytes,
        filename: str = "upload.jpg",
        track: bool = False,
    ) -> DetectionResult:
        """
        Process raw image bytes through the detection pipeline.

        Args:
            image_bytes: Raw image file content.
            filename: Original filename for saving.

        Returns:
            DetectionResult with detections, annotated image URL, and metadata.

        Raises:
            ValueError: If the image cannot be decoded.
        """
        # Decode image from bytes
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError(f"Failed to decode image: {filename}")

        h, w = image.shape[:2]
        logger.info("Processing image: %s (%dx%d)", filename, w, h)

        return await self._run_pipeline(image, filename, w, h, track)

    async def process_image_path(self, image_path: str | Path, track: bool = False) -> DetectionResult:
        """
        Process an image from a filesystem path.

        Args:
            image_path: Path to the image file.
            track: Whether to apply ByteTrack tracking to the frame.

        Returns:
            DetectionResult with detections and metadata.

        Raises:
            FileNotFoundError: If the image file does not exist.
            ValueError: If the image cannot be read.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Failed to read image: {path}")

        h, w = image.shape[:2]
        logger.info("Processing image from path: %s (%dx%d)", path.name, w, h)

        return await self._run_pipeline(image, path.name, w, h, track)

    async def _run_pipeline(
        self,
        image: np.ndarray,
        filename: str,
        width: int,
        height: int,
        track: bool = False,
    ) -> DetectionResult:
        """
        Core pipeline: detect → annotate → save → persist → respond.
        """
        scene_id = f"SCENE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        start = time.perf_counter()

        # 1. Run real YOLO detection
        detections = self._detector.detect(image, frame_id=0, track=track)

        processing_time_ms = (time.perf_counter() - start) * 1000

        # 2. Annotate image with bounding boxes
        annotated = self._detector.annotate_image(image, detections)

        # 3. Save images
        upload_dir = Path(self._settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(filename).stem
        ext = Path(filename).suffix or ".jpg"
        ts_suffix = now.strftime("%Y%m%d_%H%M%S")

        original_name = f"{stem}_{ts_suffix}_original{ext}"
        annotated_name = f"{stem}_{ts_suffix}_annotated{ext}"

        original_path = upload_dir / original_name
        annotated_path = upload_dir / annotated_name

        cv2.imwrite(str(original_path), image)
        cv2.imwrite(str(annotated_path), annotated)

        logger.info("Saved original: %s", original_name)
        logger.info("Saved annotated: %s", annotated_name)

        # 4. Persist to database
        if self._db is not None:
            previous_scene_id = await self._get_previous_scene_id()

            await self._persist_scene(
                scene_id, now, str(original_path), str(annotated_path),
                len(detections), processing_time_ms, detections,
            )

            # 5. Cognitive processing (Phase 4-7)
            await self._run_cognitive_pipeline(scene_id, previous_scene_id)

        # 6. Build response
        annotated_url = f"/api/uploads/{annotated_name}"

        result = DetectionResult(
            scene_id=scene_id,
            image_path=str(original_path),
            annotated_image_path=str(annotated_path),
            annotated_image_url=annotated_url,
            detections=detections,
            total_objects=len(detections),
            processing_time_ms=round(processing_time_ms, 1),
            model_name=self._settings.model_name,
            image_width=width,
            image_height=height,
            timestamp=now,
        )

        logger.info(
            "Detection complete: scene=%s, objects=%d, time=%.1fms",
            scene_id, len(detections), processing_time_ms,
        )

        return result

    async def _persist_scene(
        self,
        scene_id: str,
        timestamp: datetime,
        original_path: str,
        annotated_path: str,
        object_count: int,
        processing_time_ms: float,
        detections: list[Detection],
    ) -> None:
        """Save the scene and all observations to the database."""
        try:
            # Create scene record
            scene = SceneRecord(
                scene_id=scene_id,
                timestamp=timestamp,
                image_path=original_path,
                annotated_image_path=annotated_path,
                object_count=object_count,
                processing_time_ms=processing_time_ms,
            )
            self._db.add(scene)

            # 1. Fetch ACTIVE objects to match against
            stmt = select(ObjectRecord).where(ObjectRecord.status == "ACTIVE")
            result = await self._db.execute(stmt)
            active_objects = result.scalars().all()

            # Group by class name for faster matching
            active_by_class = {}
            for obj in active_objects:
                active_by_class.setdefault(obj.class_name, []).append(obj)

            dets_by_class = {}
            for i, det in enumerate(detections):
                dets_by_class.setdefault(det.class_name, []).append((i, det))

            matched_indices = set()

            # 2. Match detections to existing objects using spatial distance (Hungarian algorithm)
            for class_name, class_dets in dets_by_class.items():
                if class_name not in active_by_class:
                    continue

                class_objs = active_by_class[class_name]
                cost_matrix = np.zeros((len(class_dets), len(class_objs)))

                for r, (det_idx, det) in enumerate(class_dets):
                    for c, obj in enumerate(class_objs):
                        dist = math.hypot(
                            det.center_x - (obj.last_position_x or 0.0),
                            det.center_y - (obj.last_position_y or 0.0)
                        )
                        cost_matrix[r, c] = dist

                row_ind, col_ind = linear_sum_assignment(cost_matrix)

                for r, c in zip(row_ind, col_ind):
                    dist = cost_matrix[r, c]
                    if dist <= self._settings.movement_threshold:
                        # Match found!
                        det_idx, det = class_dets[r]
                        matched_obj = class_objs[c]

                        # Update object
                        matched_obj.last_position_x = det.center_x
                        matched_obj.last_position_y = det.center_y
                        matched_obj.last_seen = timestamp
                        matched_obj.observation_count += 1

                        # Create observation
                        obs = ObservationRecord(
                            object_id=matched_obj.object_id,
                            scene_id=scene_id,
                            timestamp=timestamp,
                            bbox_x=det.bbox.x,
                            bbox_y=det.bbox.y,
                            bbox_w=det.bbox.w,
                            bbox_h=det.bbox.h,
                            position_x=det.center_x,
                            position_y=det.center_y,
                            confidence=det.confidence,
                            class_name=det.class_name,
                            visibility="VISIBLE",
                        )
                        self._db.add(obs)
                        matched_indices.add(det_idx)

            # 3. Create new objects for unmatched detections
            for i, det in enumerate(detections):
                if i not in matched_indices:
                    obj_id = f"OBJ-{uuid.uuid4().hex[:8].upper()}"

                    obj = ObjectRecord(
                        object_id=obj_id,
                        class_name=det.class_name,
                        display_name=f"{det.class_name}",
                        first_seen=timestamp,
                        last_seen=timestamp,
                        last_position_x=det.center_x,
                        last_position_y=det.center_y,
                        observation_count=1,
                        current_confidence=det.confidence,
                        identity_confidence=1.0,
                        status="ACTIVE",
                    )
                    self._db.add(obj)

                    obs = ObservationRecord(
                        object_id=obj_id,
                        scene_id=scene_id,
                        timestamp=timestamp,
                        bbox_x=det.bbox.x,
                        bbox_y=det.bbox.y,
                        bbox_w=det.bbox.w,
                        bbox_h=det.bbox.h,
                        position_x=det.center_x,
                        position_y=det.center_y,
                        confidence=det.confidence,
                        class_name=det.class_name,
                        visibility="VISIBLE",
                    )
                    self._db.add(obs)

            await self._db.flush()
            logger.info("Scene %s persisted: %d new objects, %d updated existing objects", 
                        scene_id, len(detections) - len(matched_indices), len(matched_indices))

        except Exception as e:
            logger.error("Failed to persist scene %s: %s", scene_id, e)
            # Don't fail the whole request if DB persistence fails
            # The detection result is still valid

    async def _get_previous_scene_id(self) -> str | None:
        """Get the scene_id of the most recent scene before the current one."""
        from app.models.scene import SceneRecord as SR
        stmt = (
            select(SR.scene_id)
            .order_by(SR.timestamp.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.first()
        return row[0] if row else None

    async def _run_cognitive_pipeline(
        self,
        scene_id: str,
        previous_scene_id: str | None,
    ) -> None:
        """
        Run Phase 4-7 cognitive services after scene persistence.

        1. Memory decay for unseen objects
        2. Object lifecycle transitions
        3. Scene graph construction
        4. Change detection (vs previous scene)
        """
        try:
            from app.services.memory_service import MemoryService
            from app.services.scene_graph_service import SceneGraphService
            from app.services.change_detection_service import ChangeDetectionService

            # Phase 5: Cognitive confidence model
            memory_svc = MemoryService(self._db)
            decayed = await memory_svc.decay_unseen_objects(scene_id)
            transitions = await memory_svc.update_object_lifecycle()

            # Phase 6: Semantic scene graph
            graph_svc = SceneGraphService(self._db)
            graph = await graph_svc.build_scene_graph(scene_id)

            # Phase 7: Change detection (compare vs previous scene)
            if previous_scene_id:
                change_svc = ChangeDetectionService(self._db)
                changes = await change_svc.compare_scenes(
                    previous_scene_id, scene_id
                )
                logger.info(
                    "Cognitive pipeline: decayed=%d, transitions=%s, "
                    "graph_nodes=%d, changes=%d",
                    decayed, transitions,
                    graph.number_of_nodes(), len(changes),
                )
            else:
                logger.info(
                    "Cognitive pipeline: decayed=%d, transitions=%s, "
                    "graph_nodes=%d (no previous scene for change detection)",
                    decayed, transitions, graph.number_of_nodes(),
                )

        except Exception as e:
            logger.error("Cognitive pipeline error: %s", e, exc_info=True)
            # Non-fatal: detection result is still valid

