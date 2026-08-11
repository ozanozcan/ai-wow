"""Add taskman_project.last_harvest_at for harvest cursor.

Revision ID: 0002_last_harvest_at
Revises: 0001_taskman_brain
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_last_harvest_at"
down_revision: Union[str, Sequence[str], None] = "0001_taskman_brain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE taskman_project
            ADD COLUMN IF NOT EXISTS last_harvest_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE taskman_project DROP COLUMN IF EXISTS last_harvest_at")
