"""
Zone intersection engine using Shapely polygons.
Zones are defined in normalised [0,1] coordinates relative to camera frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from shapely.geometry import Point, Polygon


@dataclass
class Zone:
    id: str
    name: str
    zone_type: str                 # ENTRANCE | EXIT | PRODUCT | WALKWAY
    polygon: Polygon
    camera_id: str | None = None


class ZoneEngine:
    def __init__(self, zones: list[Zone]) -> None:
        self._zones = zones

    @classmethod
    def from_config(cls, zone_configs: list[dict]) -> "ZoneEngine":
        zones = []
        for cfg in zone_configs:
            poly = Polygon(cfg["polygon"])
            zones.append(Zone(
                id=cfg["id"],
                name=cfg["name"],
                zone_type=cfg["zone_type"],
                polygon=poly,
                camera_id=cfg.get("camera_id"),
            ))
        return cls(zones)

    def zones_for_point(self, nx: float, ny: float) -> list[Zone]:
        """Return all zones containing normalised point (nx, ny)."""
        pt = Point(nx, ny)
        return [z for z in self._zones if z.polygon.contains(pt)]

    def is_entrance(self, nx: float, ny: float) -> bool:
        return any(z.zone_type == "ENTRANCE" for z in self.zones_for_point(nx, ny))

    def is_exit(self, nx: float, ny: float) -> bool:
        return any(z.zone_type == "EXIT" for z in self.zones_for_point(nx, ny))

    def product_zones(self, nx: float, ny: float) -> list[Zone]:
        return [z for z in self.zones_for_point(nx, ny) if z.zone_type == "PRODUCT"]

    @staticmethod
    def bbox_centre(bbox: dict, frame_w: int, frame_h: int) -> tuple[float, float]:
        """Convert pixel bbox to normalised frame coordinates."""
        cx = (bbox["x"] + bbox["w"] / 2) / frame_w
        cy = (bbox["y"] + bbox["h"]) / frame_h   # use bottom-centre (feet)
        return cx, cy
