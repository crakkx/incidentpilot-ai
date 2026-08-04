"""add remediation proposal column

Revision ID: 20260803_0006
Revises: 20260721_0005
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260803_0006"
down_revision = "20260721_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "remediation_proposal",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "analysis_runs",
        "remediation_proposal",
    )
