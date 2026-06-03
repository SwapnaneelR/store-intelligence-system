from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_base_url: str = Field("http://api:8000", env="API_BASE_URL")
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL")

    # YOLO model — yolo11n.pt auto-downloads; override with local path for offline
    yolo_model: str = Field("yolo11n.pt", env="YOLO_MODEL")
    yolo_conf: float = Field(0.35, env="YOLO_CONF")
    yolo_iou: float = Field(0.45, env="YOLO_IOU")

    # Tracker
    process_every_n_frames: int = Field(3, env="PROCESS_EVERY_N_FRAMES")
    tracker_max_age: int = Field(30, env="TRACKER_MAX_AGE")

    # Dwell threshold seconds before firing DWELL_STARTED
    dwell_threshold_s: float = Field(20.0, env="DWELL_THRESHOLD_S")
    # Long-stay anomaly threshold
    long_stay_threshold_s: float = Field(1800.0, env="LONG_STAY_THRESHOLD_S")
    # Crowd surge: occupancy spike vs rolling mean
    crowd_surge_ratio: float = Field(2.0, env="CROWD_SURGE_RATIO")
    # Excess re-entry count
    excess_reentry_count: int = Field(3, env="EXCESS_REENTRY_COUNT")
    # Camera freeze detection: seconds without new detections
    camera_freeze_threshold_s: float = Field(30.0, env="CAMERA_FREEZE_THRESHOLD_S")

    video_dir: str = Field("/videos", env="VIDEO_DIR")

    # Zone layout JSON path (optional — seeded separately)
    zone_layout_path: str | None = Field(None, env="ZONE_LAYOUT_PATH")

    class Config:
        env_file = ".env"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
