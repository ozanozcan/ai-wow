"""Add taskman_task.claimed_by/claimed_at for atomic checkout locks.

Budget and ancestry-warning need no schema change (budget lives in the
existing `brief` JSONB column; ancestry is a CLI-only warning).

Revision ID: 0007_claim_budget_ancestry
Revises: 0006_task_lens
Create Date: 2026-07-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007_claim_budget_ancestry"
down_revision: Union[str, Sequence[str], None] = "0006_task_lens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS claimed_by VARCHAR")
    op.execute(
        "ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS claimed_at")
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS claimed_by")
