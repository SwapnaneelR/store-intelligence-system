"""
Parse Brigade Road store layout Excel and seed zones + cameras into the DB.

Usage:
    python scripts/parse_layout.py --api http://localhost:8000

Sends HTTP requests to the running API to create Camera + Zone records.
Falls back to direct DB seed if --db-url provided.
"""

import argparse
import sys
import uuid
from pathlib import Path

LAYOUT_PATH = Path(__file__).parent.parent / "dataset" / "Brigade Road - Store layoutc5f5d56.xlsx"

# Derived from Excel shape analysis — two floor plans (revised / current).
# Brand zones extracted from TextBox positions relative to the two floor-plan images.
# Image 1 (top layout): y ∈ [43, 267] — "Revised" layout
# Image 2 (bottom layout): y ∈ [317, 541] — "Current" layout (use this one)

CAMERAS = [
    # IDs must match what the tracker emits: camera_id = f"cam_{i+1}"
    {"id": "cam_1", "name": "CAM 1", "location": "Entrance / Front",  "file": "CAM 1.mp4"},
    {"id": "cam_2", "name": "CAM 2", "location": "Centre Aisle",      "file": "CAM 2.mp4"},
    {"id": "cam_3", "name": "CAM 3", "location": "Rear / Skin Zone",  "file": "CAM 3.mp4"},
    {"id": "cam_4", "name": "CAM 4", "location": "Makeup Zone",       "file": "CAM 4.mp4"},
    {"id": "cam_5", "name": "CAM 5", "location": "Checkout / Exit",   "file": "CAM 5.mp4"},
]

# Zones derived from the "Current" layout (Image 2) textbox labels.
# Polygon coords are normalised [0,1] fractions of the store footprint.
# Origin: top-left corner of the store floor plan image.
# Image dims used for normalisation: W≈470, H≈224 pts.
ZONES = [
    # ── Tracker-compatible coarse zones (IDs must match tracker/_DEFAULT_ZONES) ──
    # These are used by the CV tracker for event generation.
    {
        "id": "zone_entrance",
        "name": "Entrance",
        "zone_type": "ENTRANCE",
        "polygon": [[0.0, 0.85], [0.18, 0.85], [0.18, 1.0], [0.0, 1.0]],
        "color": "#22c55e",
    },
    {
        "id": "zone_exit",
        "name": "Exit / Checkout",
        "zone_type": "EXIT",
        "polygon": [[0.82, 0.85], [1.0, 0.85], [1.0, 1.0], [0.82, 1.0]],
        "color": "#ef4444",
    },
    {
        "id": "zone_skincare_row",
        "name": "Skincare Row",
        "zone_type": "PRODUCT",
        "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.3], [0.0, 0.3]],
        "color": "#3b82f6",
    },
    {
        "id": "zone_makeup_row",
        "name": "Makeup Row",
        "zone_type": "PRODUCT",
        "polygon": [[0.0, 0.5], [1.0, 0.5], [1.0, 0.85], [0.0, 0.85]],
        "color": "#ec4899",
    },
    {
        "id": "zone_aisle",
        "name": "Centre Aisle",
        "zone_type": "WALKWAY",
        "polygon": [[0.0, 0.3], [1.0, 0.3], [1.0, 0.5], [0.0, 0.5]],
        "color": "#94a3b8",
    },
    # ── Fine-grained brand zones from store layout Excel ──────────────────────
    # Skin-care brand row (top shelf — positions from TextBox 30-35)
    {
        "name": "EB / Exclusive Brands",
        "zone_type": "PRODUCT",
        "polygon": [[0.0, 0.0], [0.1, 0.0], [0.1, 0.3], [0.0, 0.3]],
        "color": "#a855f7",
    },
    {
        "name": "TFS",
        "zone_type": "PRODUCT",
        "polygon": [[0.1, 0.0], [0.22, 0.0], [0.22, 0.3], [0.1, 0.3]],
        "color": "#8b5cf6",
    },
    {
        "name": "Good Vibes (GV)",
        "zone_type": "PRODUCT",
        "polygon": [[0.22, 0.0], [0.34, 0.0], [0.34, 0.3], [0.22, 0.3]],
        "color": "#6366f1",
    },
    {
        "name": "DermDoc",
        "zone_type": "PRODUCT",
        "polygon": [[0.34, 0.0], [0.48, 0.0], [0.48, 0.3], [0.34, 0.3]],
        "color": "#3b82f6",
    },
    {
        "name": "Minimalist",
        "zone_type": "PRODUCT",
        "polygon": [[0.48, 0.0], [0.62, 0.0], [0.62, 0.3], [0.48, 0.3]],
        "color": "#06b6d4",
    },
    {
        "name": "Aqualogica",
        "zone_type": "PRODUCT",
        "polygon": [[0.62, 0.0], [0.76, 0.0], [0.76, 0.3], [0.62, 0.3]],
        "color": "#10b981",
    },
    {
        "name": "Pilgrim",
        "zone_type": "PRODUCT",
        "polygon": [[0.76, 0.0], [0.88, 0.0], [0.88, 0.3], [0.76, 0.3]],
        "color": "#84cc16",
    },
    {
        "name": "D&K",
        "zone_type": "PRODUCT",
        "polygon": [[0.88, 0.0], [1.0, 0.0], [1.0, 0.3], [0.88, 0.3]],
        "color": "#eab308",
    },
    # Makeup brand row (bottom shelf — positions from TextBox 19-26)
    {
        "name": "Maybelline",
        "zone_type": "PRODUCT",
        "polygon": [[0.0, 0.5], [0.14, 0.5], [0.14, 0.85], [0.0, 0.85]],
        "color": "#f97316",
    },
    {
        "name": "Faces Canada",
        "zone_type": "PRODUCT",
        "polygon": [[0.14, 0.5], [0.28, 0.5], [0.28, 0.85], [0.14, 0.85]],
        "color": "#ec4899",
    },
    {
        "name": "Lakme",
        "zone_type": "PRODUCT",
        "polygon": [[0.28, 0.5], [0.42, 0.5], [0.42, 0.85], [0.28, 0.85]],
        "color": "#f43f5e",
    },
    {
        "name": "Swiss Beauty / Renee",
        "zone_type": "PRODUCT",
        "polygon": [[0.42, 0.5], [0.54, 0.5], [0.54, 0.85], [0.42, 0.85]],
        "color": "#c084fc",
    },
    {
        "name": "Mars / Nybae",
        "zone_type": "PRODUCT",
        "polygon": [[0.54, 0.5], [0.66, 0.5], [0.66, 0.85], [0.54, 0.85]],
        "color": "#fb7185",
    },
    {
        "name": "Alps Goodness",
        "zone_type": "PRODUCT",
        "polygon": [[0.66, 0.5], [0.76, 0.5], [0.76, 0.85], [0.66, 0.85]],
        "color": "#4ade80",
    },
    {
        "name": "L'Oreal",
        "zone_type": "PRODUCT",
        "polygon": [[0.76, 0.5], [0.86, 0.5], [0.86, 0.85], [0.76, 0.85]],
        "color": "#fbbf24",
    },
    {
        "name": "Beauty Essentials",
        "zone_type": "PRODUCT",
        "polygon": [[0.86, 0.5], [0.94, 0.5], [0.94, 0.85], [0.86, 0.85]],
        "color": "#a3e635",
    },
    {
        "name": "Accessories",
        "zone_type": "PRODUCT",
        "polygon": [[0.94, 0.3], [1.0, 0.3], [1.0, 0.85], [0.94, 0.85]],
        "color": "#67e8f9",
    },
    # Centre aisle
    {
        "name": "Centre Aisle",
        "zone_type": "WALKWAY",
        "polygon": [[0.0, 0.3], [1.0, 0.3], [1.0, 0.5], [0.0, 0.5]],
        "color": "#94a3b8",
    },
]


def seed_via_api(api_base: str) -> None:
    import json
    import urllib.request

    headers = {"Content-Type": "application/json"}

    def post(path: str, data: dict) -> dict:
        body = json.dumps(data).encode()
        req = urllib.request.Request(f"{api_base}{path}", data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    print("Seeding cameras...")
    cam_ids: dict[str, str] = {}
    for cam in CAMERAS:
        resp = post("/api/v1/ingest/camera", {"name": cam["name"], "location": cam["location"]})
        cam_ids[cam["name"]] = resp["id"]
        print(f"  {cam['name']} → {resp['id']}")

    print("Seeding zones...")
    for zone in ZONES:
        resp = post("/api/v1/ingest/zone", zone)
        print(f"  {zone['name']} → {resp['id']}")


def seed_direct(db_url: str) -> None:
    """Seed directly via SQLAlchemy (synchronous, for offline use)."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.models import Camera, Zone

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def _run():
        async with async_session() as session:
            for cam in CAMERAS:
                c = Camera(
                    id=cam.get("id", uuid.uuid4().hex),
                    name=cam["name"],
                    location=cam["location"],
                    status="active",
                )
                session.add(c)

            for zone in ZONES:
                z = Zone(
                    id=zone.get("id", uuid.uuid4().hex),
                    name=zone["name"],
                    zone_type=zone["zone_type"],
                    polygon=zone["polygon"],
                    color=zone.get("color"),
                )
                session.add(z)

            await session.commit()
            print(f"Seeded {len(CAMERAS)} cameras, {len(ZONES)} zones.")

    asyncio.run(_run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed store layout (cameras + zones)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--api", help="API base URL, e.g. http://localhost:8000")
    group.add_argument("--db-url", help="Async DB URL for direct seeding")
    args = parser.parse_args()

    if args.db_url:
        sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))
        seed_direct(args.db_url)
    else:
        seed_via_api(args.api)
