"""Add taskman_requirement: Feature-scoped living spec (SHALL + scenarios).

Revision ID: 0005_requirement
Revises: 0004_task_brief
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_requirement"
down_revision: Union[str, Sequence[str], None] = "0004_task_brief"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_requirement (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES taskman_feature(id) ON DELETE CASCADE,
            title VARCHAR NOT NULL,
            statement TEXT NOT NULL DEFAULT '',
            scenarios JSONB NOT NULL DEFAULT '[]',
            status VARCHAR NOT NULL DEFAULT 'active',
            source_pbi_id INTEGER REFERENCES taskman_pbi(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_requirement_project_id "
        "ON taskman_requirement (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_requirement_feature_id "
        "ON taskman_requirement (feature_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_requirement_status "
        "ON taskman_requirement (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_requirement_source_pbi_id "
        "ON taskman_requirement (source_pbi_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS taskman_requirement")
