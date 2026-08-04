"""add analysis progress and debugging fields

Revision ID: 20260721_0005
Revises: 20260719_0004
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0005"
down_revision = "20260719_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "progress_stage",
            sa.String(length=80),
            nullable=False,
            server_default="queued",
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "progress_message",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "failure_type",
            sa.String(length=80),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "raw_model_output",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "validation_errors",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "generation_metadata",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "generation_attempts",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "analysis_runs",
        sa.Column(
            "retrieval_diagnostics",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "analysis_runs",
        "retrieval_diagnostics",
    )
    op.drop_column(
        "analysis_runs",
        "generation_attempts",
    )
    op.drop_column(
        "analysis_runs",
        "generation_metadata",
    )
    op.drop_column(
        "analysis_runs",
        "validation_errors",
    )
    op.drop_column(
        "analysis_runs",
        "raw_model_output",
    )
    op.drop_column(
        "analysis_runs",
        "failure_type",
    )
    op.drop_column(
        "analysis_runs",
        "progress_percent",
    )
    op.drop_column(
        "analysis_runs",
        "progress_message",
    )
    op.drop_column(
        "analysis_runs",
        "progress_stage",
    )