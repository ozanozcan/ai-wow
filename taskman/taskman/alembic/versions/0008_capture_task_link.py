"""Link taskman_capture rows to taskman_task (optional FK).

Revision ID: 0008_capture_task_link
Revises: 0007_claim_budget_ancestry
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008_capture_task_link"
down_revision: Union[str, Sequence[str], None] = "0007_claim_budget_ancestry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE taskman_capture ADD COLUMN IF NOT EXISTS task_id INTEGER"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_taskman_capture_task_id'
            ) THEN
                ALTER TABLE taskman_capture
                ADD CONSTRAINT fk_taskman_capture_task_id
                FOREIGN KEY (task_id) REFERENCES taskman_task(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_capture_task_id ON taskman_capture (task_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_taskman_capture_task_id")
    op.execute(
        "ALTER TABLE taskman_capture DROP CONSTRAINT IF EXISTS fk_taskman_capture_task_id"
    )
    op.execute("ALTER TABLE taskman_capture DROP COLUMN IF EXISTS task_id")
