"""Decision/Capture tags + Decision.task_id (d#852, d#865).

Revision ID: 0009_decision_capture_tags
Revises: 0008_capture_task_link
Create Date: 2026-08-10

Schema only — moving machinery decisions into the ``workflow`` project is a CLI
command (``decision move``), not this migration (d#859 / d#856).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009_decision_capture_tags"
down_revision: Union[str, Sequence[str], None] = "0008_capture_task_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE taskman_decision "
        "ADD COLUMN IF NOT EXISTS tags VARCHAR[] NOT NULL DEFAULT '{}'"
    )
    op.execute(
        "ALTER TABLE taskman_capture "
        "ADD COLUMN IF NOT EXISTS tags VARCHAR[] NOT NULL DEFAULT '{}'"
    )
    op.execute(
        "ALTER TABLE taskman_decision ADD COLUMN IF NOT EXISTS task_id INTEGER"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_taskman_decision_task_id'
            ) THEN
                ALTER TABLE taskman_decision
                ADD CONSTRAINT fk_taskman_decision_task_id
                FOREIGN KEY (task_id) REFERENCES taskman_task(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_decision_task_id "
        "ON taskman_decision (task_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_taskman_decision_task_id")
    op.execute(
        "ALTER TABLE taskman_decision DROP CONSTRAINT IF EXISTS fk_taskman_decision_task_id"
    )
    op.execute("ALTER TABLE taskman_decision DROP COLUMN IF EXISTS task_id")
    op.execute("ALTER TABLE taskman_decision DROP COLUMN IF EXISTS tags")
    op.execute("ALTER TABLE taskman_capture DROP COLUMN IF EXISTS tags")
