"""add analysis version and configuration fields

Revision ID: 20260719_0004
Revises: 20260704_0003
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_0004"
down_revision = "20260704_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "pipeline_version",
            sa.String(length=50),
            nullable=False,
            server_default="v0.1.0",
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "schema_version",
            sa.String(length=80),
            nullable=False,
            server_default="legacy-unversioned",
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "prompt_version",
            sa.String(length=80),
            nullable=False,
            server_default="legacy-unversioned",
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "run_config",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "analysis_runs",
        "run_config",
    )

    op.drop_column(
        "analysis_runs",
        "prompt_version",
    )

    op.drop_column(
        "analysis_runs",
        "schema_version",
    )

    op.drop_column(
        "analysis_runs",
        "pipeline_version",
    )