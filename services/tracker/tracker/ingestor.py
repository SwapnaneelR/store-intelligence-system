"""
Video ingestor — reads MP4 files or RTSP streams, yields frames.

For file-based mode (assessment): loops through all MP4 files in VIDEO_DIR.
For live mode: reads RTSP URLs from camera config.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class VideoIngestor:
    def __init__(self, video_dir: str, process_every_n: int = 3) -> None:
        self._video_dir = Path(video_dir)
        self._process_every_n = process_every_n

    def video_files(self) -> list[Path]:
        files = sorted(self._video_dir.glob("*.mp4"))
        if not files:
            logger.warning("no_mp4_files", dir=str(self._video_dir))
        return files

    def frames(self, video_path: Path) -> Generator[tuple[np.ndarray, int, int, int], None, None]:
        """
        Yields (frame, frame_w, frame_h, frame_number).
        Only yields every N-th frame.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error("cannot_open_video", path=str(video_path))
            return

        frame_num = 0
        logger.info("processing_video", path=video_path.name)

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_num += 1
                if frame_num % self._process_every_n != 0:
                    continue
                h, w = frame.shape[:2]
                yield frame, w, h, frame_num
        finally:
            cap.release()
            logger.info("video_done", path=video_path.name, frames=frame_num)

    def rtsp_frames(self, rtsp_url: str) -> Generator[tuple[np.ndarray, int, int, int], None, None]:
        cap = cv2.VideoCapture(rtsp_url)
        frame_num = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.warning("rtsp_read_failed", url=rtsp_url)
                time.sleep(0.5)
                continue
            frame_num += 1
            if frame_num % self._process_every_n != 0:
                continue
            h, w = frame.shape[:2]
            yield frame, w, h, frame_num
