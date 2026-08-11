"""Add taskman_task.brief JSONB for dispatch brief round-trip.

Revision ID: 0004_task_brief
Revises: 0003_strategic_lens
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004_task_brief"
down_revision: Union[str, Sequence[str], None] = "0003_strategic_lens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS brief JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS brief")
