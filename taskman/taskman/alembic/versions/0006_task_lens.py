"""Add lane/surface/afk/notes to taskman_task (web-app strategic-lens fields, flat-task level).

Revision ID: 0006_task_lens
Revises: 0005_requirement
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006_task_lens"
down_revision: Union[str, Sequence[str], None] = "0005_requirement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS lane VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS surface VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS afk VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE taskman_task ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT ''"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS notes")
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS afk")
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS surface")
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS lane")
