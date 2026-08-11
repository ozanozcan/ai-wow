"""Initial taskman schema (idempotent for v1 DBs).

Revision ID: 0001_taskman_brain
Revises:
Create Date: 2026-07-09

Strategy: CREATE TABLE IF NOT EXISTS for every taskman_* table, then ADD COLUMN
IF NOT EXISTS for Task.pbi_id. Safe on:
  - fresh DB (creates everything)
  - existing v1 DB from create_all() (Project/Task/task_dep/session already present)
Does not drop or rewrite Task rows.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001_taskman_brain"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- core (may already exist from create_all) ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_project (
            id SERIAL PRIMARY KEY,
            slug VARCHAR NOT NULL,
            name VARCHAR NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_taskman_project_slug ON taskman_project (slug)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_task (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            title VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'backlog',
            priority INTEGER NOT NULL DEFAULT 3,
            tags VARCHAR[] NOT NULL DEFAULT '{}',
            source_ref VARCHAR,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_task_project_id ON taskman_task (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_task_status ON taskman_task (status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_task_dep (
            task_id INTEGER NOT NULL REFERENCES taskman_task(id) ON DELETE CASCADE,
            blocked_by_id INTEGER NOT NULL REFERENCES taskman_task(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, blocked_by_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_session (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            session_id VARCHAR NOT NULL,
            source VARCHAR NOT NULL DEFAULT 'unknown',
            transcript_path VARCHAR NOT NULL,
            tokens_status VARCHAR NOT NULL DEFAULT 'unknown',
            input_tokens BIGINT NOT NULL DEFAULT 0,
            output_tokens BIGINT NOT NULL DEFAULT 0,
            cache_read_tokens BIGINT NOT NULL DEFAULT 0,
            cache_creation_tokens BIGINT NOT NULL DEFAULT 0,
            api_calls INTEGER NOT NULL DEFAULT 0,
            models JSONB NOT NULL DEFAULT '{}',
            effort JSONB NOT NULL DEFAULT '{}',
            recorded_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            CONSTRAINT uq_taskman_session_path
                UNIQUE (project_id, session_id, transcript_path)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_session_project_id ON taskman_session (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_session_session_id ON taskman_session (session_id)"
    )

    # --- Wave 2 entities ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_tag (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL,
            CONSTRAINT uq_taskman_tag_project_name UNIQUE (project_id, name)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_tag_project_id ON taskman_tag (project_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_feature (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            title VARCHAR NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status VARCHAR NOT NULL DEFAULT 'backlog',
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_feature_project_id ON taskman_feature (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_feature_status ON taskman_feature (status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_pbi (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES taskman_feature(id) ON DELETE CASCADE,
            title VARCHAR NOT NULL,
            acceptance_criteria TEXT NOT NULL DEFAULT '',
            status VARCHAR NOT NULL DEFAULT 'backlog',
            priority INTEGER NOT NULL DEFAULT 3,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_pbi_project_id ON taskman_pbi (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_pbi_feature_id ON taskman_pbi (feature_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_pbi_status ON taskman_pbi (status)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_feature_tag (
            feature_id INTEGER NOT NULL REFERENCES taskman_feature(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES taskman_tag(id) ON DELETE CASCADE,
            PRIMARY KEY (feature_id, tag_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_pbi_tag (
            pbi_id INTEGER NOT NULL REFERENCES taskman_pbi(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES taskman_tag(id) ON DELETE CASCADE,
            PRIMARY KEY (pbi_id, tag_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_decision (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            title VARCHAR NOT NULL,
            why TEXT NOT NULL DEFAULT '',
            alternatives TEXT NOT NULL DEFAULT '',
            implications TEXT NOT NULL DEFAULT '',
            source_ref VARCHAR,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_decision_project_id ON taskman_decision (project_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taskman_capture (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES taskman_project(id) ON DELETE CASCADE,
            kind VARCHAR NOT NULL,
            summary VARCHAR NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            source_ref VARCHAR,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_capture_project_id ON taskman_capture (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_capture_kind ON taskman_capture (kind)"
    )

    # Legacy Task rows get pbi_id = NULL until manually linked.
    op.execute(
        """
        ALTER TABLE taskman_task
            ADD COLUMN IF NOT EXISTS pbi_id INTEGER
            REFERENCES taskman_pbi(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_taskman_task_pbi_id ON taskman_task (pbi_id)"
    )


def downgrade() -> None:
    # Destructive — only for fresh installs / tests. Does not restore dropped data.
    op.execute("ALTER TABLE taskman_task DROP COLUMN IF EXISTS pbi_id")
    op.execute("DROP TABLE IF EXISTS taskman_capture")
    op.execute("DROP TABLE IF EXISTS taskman_decision")
    op.execute("DROP TABLE IF EXISTS taskman_pbi_tag")
    op.execute("DROP TABLE IF EXISTS taskman_feature_tag")
    op.execute("DROP TABLE IF EXISTS taskman_pbi")
    op.execute("DROP TABLE IF EXISTS taskman_feature")
    op.execute("DROP TABLE IF EXISTS taskman_tag")
    # Do not drop project/task/session/dep — those predate this revision on v1 DBs.
