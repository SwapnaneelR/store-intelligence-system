"""
Person detector + ByteTracker wrapper using Ultralytics YOLOv11.

Returns per-frame list of tracked detections:
  {"track_id": int, "bbox": {x,y,w,h}, "confidence": float, "person_class": str}

Staff vs customer classification: heuristic based on bounding-box aspect ratio
and a configurable colour range (purple apron) — defaults to "customer" until
fine-tuned model is available.
"""

from __future__ import annotations

import numpy as np
import structlog
from ultralytics import YOLO

logger = structlog.get_logger(__name__)

# COCO class index for "person"
_PERSON_CLASS = 0


class Detector:
    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        conf: float = 0.35,
        iou: float = 0.45,
        device: str = "cpu",
    ) -> None:
        logger.info("loading_yolo_model", path=model_path, device=device)
        self._model = YOLO(model_path)
        self._conf = conf
        self._iou = iou
        self._device = device

    def detect_and_track(self, frame: np.ndarray) -> list[dict]:
        """
        Run YOLO detection + ByteTrack on one frame.
        Returns list of dicts with keys: track_id, bbox, confidence, person_class.
        """
        results = self._model.track(
            source=frame,
            classes=[_PERSON_CLASS],
            conf=self._conf,
            iou=self._iou,
            tracker="bytetrack.yaml",
            device=self._device,
            persist=True,
            verbose=False,
        )

        detections: list[dict] = []
        if not results or results[0].boxes is None:
            return detections

        boxes = results[0].boxes
        if boxes.id is None:
            return detections

        for i, track_id in enumerate(boxes.id.int().tolist()):
            xyxy = boxes.xyxy[i].tolist()
            x1, y1, x2, y2 = xyxy
            x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)
            conf = float(boxes.conf[i])

            # Simple staff heuristic: tall narrow boxes (staff stand still behind counters)
            aspect = h / max(w, 1)
            person_class = "staff" if aspect > 3.0 else "customer"

            detections.append({
                "track_id": track_id,
                "bbox": {"x": x, "y": y, "w": w, "h": h},
                "confidence": conf,
                "person_class": person_class,
            })

        return detections
