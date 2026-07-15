"""add structured RCA reports to analysis runs

Revision ID: 20260704_0003
Revises: 20260702_0002
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0003"
down_revision = "20260702_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "report",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "evidence_snapshot",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "analysis_runs",
        "error_message",
    )

    op.drop_column(
        "analysis_runs",
        "evidence_snapshot",
    )

    op.drop_column(
        "analysis_runs",
        "report",
    )
