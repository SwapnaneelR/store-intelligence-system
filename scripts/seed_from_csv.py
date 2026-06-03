"""
Seed transaction events from the Brigade Bangalore POS CSV.

Each unique order_id with a valid order_time → CHECKOUT_VISIT event.
Unique customer_number per day → proxy for store visitor (ENTRY + EXIT).

Usage:
    python scripts/seed_from_csv.py --db-url postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence
"""

import argparse
import asyncio
import csv
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "dataset" / "Brigade_Bangalore_10_April_26 (1)bc6219c.csv"


def parse_rows() -> list[dict]:
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def order_datetime(row: dict) -> datetime | None:
    try:
        date_str = row["order_date"].strip()  # 10-04-2026
        time_str = row["order_time"].strip()  # 16:55:36
        dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def seed(db_url: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))
    from app.db.models import Event, Session as VisitSession  # noqa: PLC0415

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    rows = parse_rows()
    print(f"Loaded {len(rows)} CSV rows from {CSV_PATH.name}")

    # Collect unique orders (deduplicate by order_id)
    orders: dict[str, dict] = {}
    for row in rows:
        oid = row.get("order_id", "").strip()
        if oid and oid not in orders:
            orders[oid] = row

    # Collect unique customers → proxy visitor sessions
    customers: dict[str, datetime] = {}
    for row in rows:
        cnum = row.get("customer_number", "").strip()
        dt = order_datetime(row)
        if cnum and dt and cnum not in customers:
            customers[cnum] = dt

    async with async_session() as session:
        event_count = 0

        for cnum, entry_dt in customers.items():
            # Simulate: visitor entered 15 min before first purchase
            from datetime import timedelta
            entered_at = entry_dt - timedelta(minutes=15)
            exited_at = entry_dt + timedelta(minutes=20)

            sess = VisitSession(
                id=uuid.uuid4().hex,
                track_id=f"csv_{cnum}",
                person_class="customer",
                entered_at=entered_at,
                exited_at=exited_at,
            )
            session.add(sess)

            # ENTRY event
            entry_ev = Event(
                id=uuid.uuid4().hex,
                event_type="ENTRY",
                timestamp=entered_at,
                track_id=f"csv_{cnum}",
                session_id=sess.id,
                person_class="customer",
                confidence=1.0,
                metadata_={"source": "csv_seed"},
            )
            session.add(entry_ev)
            event_count += 1

            # EXIT event
            exit_ev = Event(
                id=uuid.uuid4().hex,
                event_type="EXIT",
                timestamp=exited_at,
                track_id=f"csv_{cnum}",
                session_id=sess.id,
                person_class="customer",
                confidence=1.0,
                metadata_={"source": "csv_seed"},
            )
            session.add(exit_ev)
            event_count += 1

        # CHECKOUT_VISIT events per order
        for oid, row in orders.items():
            dt = order_datetime(row)
            if not dt:
                continue
            gmv = float(row.get("GMV") or 0)
            ev = Event(
                id=uuid.uuid4().hex,
                event_type="ZONE_ENTER",
                timestamp=dt,
                track_id=f"csv_{row.get('customer_number', '').strip()}",
                zone_id=None,
                person_class="customer",
                confidence=1.0,
                metadata_={
                    "source": "csv_seed",
                    "order_id": oid,
                    "product": row.get("product_name", "")[:80],
                    "brand": row.get("brand_name", ""),
                    "category": row.get("dep_name", ""),
                    "gmv": gmv,
                    "salesperson": row.get("salesperson_name", ""),
                    "zone_hint": row.get("sub_category", ""),
                },
            )
            session.add(ev)
            event_count += 1

        await session.commit()
        print(f"Seeded {len(customers)} visitor sessions, {event_count} events.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed POS CSV data as events")
    parser.add_argument(
        "--db-url",
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.db_url))
