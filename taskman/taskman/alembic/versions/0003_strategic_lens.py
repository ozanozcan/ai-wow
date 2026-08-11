"""Carry over the legacy web-app strategic lens: feature lane/surface + enum priority.

Adds taskman_feature.lane / .surface, and converts the bare-int priority on
taskman_pbi and taskman_task to the keystone|high|med|low scheme.

Revision ID: 0003_strategic_lens
Revises: 0002_last_harvest_at
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_strategic_lens"
down_revision: Union[str, Sequence[str], None] = "0002_last_harvest_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# int → enum bucket (legacy CSV used 1=keystone..4=low; default 3=med).
_INT_TO_ENUM = "CASE {c} WHEN 1 THEN 'keystone' WHEN 2 THEN 'high' WHEN 3 THEN 'med' WHEN 4 THEN 'low' ELSE 'med' END"
_ENUM_TO_INT = "CASE {c} WHEN 'keystone' THEN 1 WHEN 'high' THEN 2 WHEN 'med' THEN 3 WHEN 'low' THEN 4 ELSE 3 END"


def _int_to_enum(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ALTER COLUMN priority DROP DEFAULT")
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN priority TYPE VARCHAR "
        f"USING ({_INT_TO_ENUM.format(c='priority')})"
    )
    op.execute(f"ALTER TABLE {table} ALTER COLUMN priority SET DEFAULT 'med'")
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_priority ON {table} (priority)")


def _enum_to_int(table: str) -> None:
    op.execute(f"DROP INDEX IF EXISTS ix_{table}_priority")
    op.execute(f"ALTER TABLE {table} ALTER COLUMN priority DROP DEFAULT")
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN priority TYPE INTEGER "
        f"USING ({_ENUM_TO_INT.format(c='priority')})"
    )
    op.execute(f"ALTER TABLE {table} ALTER COLUMN priority SET DEFAULT 3")


def upgrade() -> None:
    op.execute("ALTER TABLE taskman_feature ADD COLUMN IF NOT EXISTS lane VARCHAR NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE taskman_feature ADD COLUMN IF NOT EXISTS surface VARCHAR NOT NULL DEFAULT ''")
    op.execute("CREATE INDEX IF NOT EXISTS ix_taskman_feature_lane ON taskman_feature (lane)")
    _int_to_enum("taskman_pbi")
    _int_to_enum("taskman_task")


def downgrade() -> None:
    _enum_to_int("taskman_task")
    _enum_to_int("taskman_pbi")
    op.execute("DROP INDEX IF EXISTS ix_taskman_feature_lane")
    op.execute("ALTER TABLE taskman_feature DROP COLUMN IF EXISTS surface")
    op.execute("ALTER TABLE taskman_feature DROP COLUMN IF EXISTS lane")
