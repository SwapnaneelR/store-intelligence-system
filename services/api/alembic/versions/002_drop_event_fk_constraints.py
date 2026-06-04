"""drop FK constraints on events/sessions so tracker IDs don't have to match DB UUIDs

Revision ID: 002
Revises: 001
Create Date: 2026-06-04 00:00:00.000000

Rationale: the tracker service uses logical IDs (cam_1, zone_entrance) that may
not match the UUIDs inserted by seed scripts. The events table is an append-only
audit log — events must always be stored regardless of whether the referenced
camera or zone ID exists in the lookup tables.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FK constraints on events table
    op.drop_constraint("events_camera_id_fkey", "events", type_="foreignkey")
    op.drop_constraint("events_session_id_fkey", "events", type_="foreignkey")
    op.drop_constraint("events_zone_id_fkey", "events", type_="foreignkey")

    # Drop FK constraints on sessions table
    op.drop_constraint("sessions_camera_id_fkey", "sessions", type_="foreignkey")
    op.drop_constraint("sessions_entry_zone_id_fkey", "sessions", type_="foreignkey")
    op.drop_constraint("sessions_exit_zone_id_fkey", "sessions", type_="foreignkey")

    # Drop FK on anomalies (event_id) — keep it as audit trail still references events
    # Leave anomalies_event_id_fkey intact

    # Drop FK on zones (layout_id, camera_id) — zones may exist without a layout
    op.drop_constraint("zones_layout_id_fkey", "zones", type_="foreignkey")
    op.drop_constraint("zones_camera_id_fkey", "zones", type_="foreignkey")


def downgrade() -> None:
    # Restore FKs (best-effort — data may violate constraints after drop)
    op.create_foreign_key("events_camera_id_fkey", "events", "cameras", ["camera_id"], ["id"])
    op.create_foreign_key("events_session_id_fkey", "events", "sessions", ["session_id"], ["id"])
    op.create_foreign_key("events_zone_id_fkey", "events", "zones", ["zone_id"], ["id"])
    op.create_foreign_key("sessions_camera_id_fkey", "sessions", "cameras", ["camera_id"], ["id"])
    op.create_foreign_key("sessions_entry_zone_id_fkey", "sessions", "zones", ["entry_zone_id"], ["id"])
    op.create_foreign_key("sessions_exit_zone_id_fkey", "sessions", "zones", ["exit_zone_id"], ["id"])
    op.create_foreign_key("zones_layout_id_fkey", "zones", "store_layouts", ["layout_id"], ["id"])
    op.create_foreign_key("zones_camera_id_fkey", "zones", "cameras", ["camera_id"], ["id"])
