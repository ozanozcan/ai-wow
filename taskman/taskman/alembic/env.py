"""Alembic env for taskman_* schema.

URL comes from taskman.config.database_url() (DATABASE_URL / docker default),
not from alembic.ini's placeholder sqlalchemy.url.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from taskman.config import database_url
from taskman.models import Base

config = context.config
# Only configure logging for standalone CLI runs. In-process callers (taskman.db.upgrade_head,
# used by `taskman init-db`) set configure_logger=False: fileConfig would otherwise replace the
# host process's root handlers and drop its level to WARN, silencing app loggers for good.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", database_url())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def _include_name(name, type_, parent_names):
    """Only manage taskman_* tables — leave the rest of the application DB alone."""
    if type_ == "table":
        return name is not None and name.startswith("taskman_")
    return True


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
