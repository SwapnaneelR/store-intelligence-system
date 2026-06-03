"""
Seed synthetic demo data — fast way to populate the dashboard without running CV.

Generates realistic footfall patterns for the day of the CSV (2026-04-10).

Usage:
    python scripts/seed_demo.py --db-url postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence
"""

import argparse
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))

STORE_OPEN = 10   # 10:00
STORE_CLOSE = 21  # 21:00
TARGET_DATE = datetime(2026, 4, 10, tzinfo=timezone.utc)

# Footfall pattern: visitors per hour (realistic retail bell curve)
HOURLY_VISITORS = {
    10: 8,  11: 15, 12: 22, 13: 30,
    14: 28, 15: 25, 16: 35, 17: 40,
    18: 45, 19: 38, 20: 20,
}

ZONE_IDS = [
    "zone_entrance", "zone_exit", "zone_skincare_row",
    "zone_makeup_row", "zone_aisle", "zone_checkout",
]
BRAND_ZONES = [
    "zone_maybelline", "zone_lakme", "zone_faces",
    "zone_dermdoc", "zone_minimalist", "zone_goodvibes",
    "zone_loreal", "zone_aqualogica",
]


def rand_dt(base: datetime, spread_minutes: int = 10) -> datetime:
    return base + timedelta(seconds=random.randint(0, spread_minutes * 60))


async def seed(db_url: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.db.models import Anomaly, Event, Session as VisitSession  # noqa: PLC0415

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        total_events = 0

        for hour, visitor_count in HOURLY_VISITORS.items():
            hour_base = TARGET_DATE.replace(hour=hour, minute=0, second=0, microsecond=0)

            for _ in range(visitor_count):
                entered_at = rand_dt(hour_base, 50)
                dwell_min = random.randint(5, 45)
                exited_at = entered_at + timedelta(minutes=dwell_min)
                if exited_at.hour >= STORE_CLOSE:
                    exited_at = exited_at.replace(hour=STORE_CLOSE - 1, minute=55)

                track_id = f"demo_{uuid.uuid4().hex[:8]}"
                is_staff = random.random() < 0.05
                person_class = "staff" if is_staff else "customer"

                sess = VisitSession(
                    id=uuid.uuid4().hex,
                    track_id=track_id,
                    person_class=person_class,
                    entered_at=entered_at,
                    exited_at=exited_at,
                )
                session.add(sess)

                # ENTRY
                session.add(Event(
                    id=uuid.uuid4().hex, event_type="ENTRY",
                    timestamp=entered_at, track_id=track_id,
                    session_id=sess.id, person_class=person_class,
                    confidence=round(random.uniform(0.82, 0.99), 2),
                ))
                total_events += 1

                # Zone visits — 1 to 4 zones
                visit_time = entered_at + timedelta(minutes=2)
                for zone_id in random.sample(BRAND_ZONES, k=random.randint(1, 4)):
                    session.add(Event(
                        id=uuid.uuid4().hex, event_type="ZONE_ENTER",
                        timestamp=rand_dt(visit_time, 5),
                        track_id=track_id, session_id=sess.id,
                        zone_id=zone_id, person_class=person_class,
                        confidence=round(random.uniform(0.75, 0.99), 2),
                    ))
                    total_events += 1

                # DWELL (30% chance)
                if random.random() < 0.3:
                    dwell_start = visit_time + timedelta(minutes=random.randint(2, 8))
                    session.add(Event(
                        id=uuid.uuid4().hex, event_type="DWELL_STARTED",
                        timestamp=dwell_start, track_id=track_id,
                        session_id=sess.id, person_class=person_class,
                        confidence=0.9,
                    ))
                    total_events += 1

                # GROUP_ENTRY (8% chance)
                if random.random() < 0.08:
                    session.add(Event(
                        id=uuid.uuid4().hex, event_type="GROUP_ENTRY",
                        timestamp=entered_at + timedelta(seconds=5),
                        track_id=track_id, session_id=sess.id,
                        group_id=uuid.uuid4().hex[:8], person_class="customer",
                        confidence=0.85,
                    ))
                    total_events += 1

                # EXIT
                session.add(Event(
                    id=uuid.uuid4().hex, event_type="EXIT",
                    timestamp=exited_at, track_id=track_id,
                    session_id=sess.id, person_class=person_class,
                    confidence=round(random.uniform(0.80, 0.99), 2),
                ))
                total_events += 1

        # Synthetic anomalies
        anomaly_specs = [
            ("CROWD_SURGE",  "HIGH",     TARGET_DATE.replace(hour=17, minute=30)),
            ("LONG_STAY",    "MEDIUM",   TARGET_DATE.replace(hour=14, minute=15)),
            ("EXCESS_REENTRY", "MEDIUM", TARGET_DATE.replace(hour=12, minute=45)),
            ("CAMERA_FAILURE", "HIGH",   TARGET_DATE.replace(hour=11, minute=0)),
            ("LOITERING",    "LOW",      TARGET_DATE.replace(hour=19, minute=20)),
        ]
        for atype, severity, detected_at in anomaly_specs:
            session.add(Anomaly(
                id=uuid.uuid4().hex,
                anomaly_type=atype,
                severity=severity,
                resolved=False,
                detected_at=detected_at,
            ))

        await session.commit()
        print(f"Seeded {total_events} demo events + {len(anomaly_specs)} anomalies.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed synthetic demo data")
    parser.add_argument(
        "--db-url",
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.db_url))
