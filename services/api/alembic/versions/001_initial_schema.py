"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("rtsp_url", sa.Text()),
        sa.Column("resolution_w", sa.Integer()),
        sa.Column("resolution_h", sa.Integer()),
        sa.Column("fps", sa.Integer(), server_default="30"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "store_layouts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("floor_plan", JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "zones",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("layout_id", UUID(as_uuid=False), sa.ForeignKey("store_layouts.id"), nullable=True),
        sa.Column("camera_id", UUID(as_uuid=False), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("zone_type", sa.String(100), nullable=False),
        sa.Column("polygon", JSONB(), nullable=False),
        sa.Column("color", sa.String(50)),
        sa.Column("metadata", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("track_id", sa.String(255), nullable=False),
        sa.Column("camera_id", UUID(as_uuid=False), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("person_class", sa.String(50), server_default="customer"),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True)),
        sa.Column("entry_zone_id", UUID(as_uuid=False), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("exit_zone_id", UUID(as_uuid=False), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("metadata", JSONB()),
    )
    op.create_index("idx_sessions_track_id", "sessions", ["track_id"])

    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("camera_id", UUID(as_uuid=False), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("track_id", sa.String(255)),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("zone_id", UUID(as_uuid=False), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("group_id", sa.String(255)),
        sa.Column("person_class", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("bbox", JSONB()),
        sa.Column("metadata", JSONB()),
    )
    op.create_index("idx_events_type_ts", "events", ["event_type", "timestamp"])
    op.create_index("idx_events_camera_ts", "events", ["camera_id", "timestamp"])
    op.create_index("idx_events_zone", "events", ["zone_id", "timestamp"])
    op.create_index("idx_events_session", "events", ["session_id"])

    op.create_table(
        "anomalies",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("anomaly_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(255)),
        sa.Column("notes", sa.Text()),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_anomalies_resolved_detected", "anomalies", ["resolved", "detected_at"])
    op.create_index("idx_anomalies_severity", "anomalies", ["severity", "detected_at"])


def downgrade() -> None:
    op.drop_table("anomalies")
    op.drop_table("events")
    op.drop_table("sessions")
    op.drop_table("zones")
    op.drop_table("store_layouts")
    op.drop_table("cameras")
