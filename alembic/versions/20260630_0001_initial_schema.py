"""initial schema with metrics and indexes

Revision ID: 20260630_0001
Revises:
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260630_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "services",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_team", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_services_name", "services", ["name"], unique=True)

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service_id", sa.String(length=36), nullable=True),
        sa.Column("service_name", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index(
        "ix_incidents_service_name_started_at",
        "incidents",
        ["service_name", "started_at"],
    )

    op.create_table(
        "deployments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("environment", sa.String(length=80), nullable=False),
        sa.Column("commit_sha", sa.String(length=120), nullable=True),
        sa.Column("deployed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
    )
    op.create_index(
        "ix_deployments_service_name_deployed_at",
        "deployments",
        ["service_name", "deployed_at"],
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("level", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
    )
    op.create_index(
        "ix_logs_service_name_timestamp",
        "logs",
        ["service_name", "timestamp"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
    )

    op.create_table(
        "metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_metrics_service_name_timestamp",
        "metrics",
        ["service_name", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_metrics_service_name_timestamp", table_name="metrics")
    op.drop_table("metrics")

    op.drop_table("analysis_runs")

    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_logs_service_name_timestamp", table_name="logs")
    op.drop_table("logs")

    op.drop_table("documents")

    op.drop_index(
        "ix_deployments_service_name_deployed_at",
        table_name="deployments",
    )
    op.drop_table("deployments")

    op.drop_index("ix_incidents_service_name_started_at", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_services_name", table_name="services")
    op.drop_table("services")

    op.execute("DROP EXTENSION IF EXISTS vector")
