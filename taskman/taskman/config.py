from __future__ import annotations

import os
import pathlib
import tomllib

from dotenv import load_dotenv

# Reuses this project's existing Postgres. Prefer TASKMAN_DATABASE_URL; else
# rewrite asyncpg DATABASE_URL to psycopg; else DATABASE_URL; else this default.
DEFAULT_DATABASE_URL = "postgresql+psycopg://taskman:taskman@localhost:5432/taskman"


# Load .env.local / .env from the nearest .taskman.toml ancestor of cwd.
# Import-time load covers entry points that never call cli.main(); main()
# reloads with override so chdir-into-project (and the env-loading tests) work.
_DOTENV_LOADED = False


def load_dotenv_from_cwd(*, force: bool = False) -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED and not force:
        return
    _DOTENV_LOADED = True
    here = pathlib.Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".taskman.toml").exists():
            local = d / ".env.local"
            env = d / ".env"
            if local.exists():
                load_dotenv(local, override=force)
            elif env.exists():
                load_dotenv(env, override=force)
            break


load_dotenv_from_cwd()

def database_url() -> str:
    taskman_url = os.environ.get("TASKMAN_DATABASE_URL")
    if taskman_url:
        return taskman_url

    url = os.environ.get("DATABASE_URL")
    if url is None:
        return DEFAULT_DATABASE_URL
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg", 1)
    return url


def find_project() -> tuple[str, str]:
    """Project identity from the nearest .taskman.toml. Never guess.

    Walks up from the cwd. If no marker (or no slug) is found, the operation
    stops rather than risk mixing projects.
    """
    here = pathlib.Path.cwd().resolve()
    for d in (here, *here.parents):
        marker = d / ".taskman.toml"
        if marker.exists():
            data = tomllib.loads(marker.read_text())
            proj = data.get("project", data)
            slug = proj.get("slug")
            if not slug:
                raise SystemExit(f"taskman: {marker} has no project.slug — refusing to guess.")
            return slug, proj.get("name", slug)
    raise SystemExit("taskman: no .taskman.toml found above cwd — refusing to guess the project.")


def find_toolkit() -> dict[str, list[str]]:
    """Tag → recommended skills/agents from the nearest .taskman.toml [toolkit].

    Missing marker or missing table means no recommendations ({}), never an error —
    the toolkit line is advisory rendering only.
    """
    here = pathlib.Path.cwd().resolve()
    for d in (here, *here.parents):
        marker = d / ".taskman.toml"
        if marker.exists():
            data = tomllib.loads(marker.read_text())
            raw = data.get("toolkit", {})
            if not isinstance(raw, dict):
                return {}
            return {
                str(tag): [str(rec) for rec in recs]
                for tag, recs in raw.items()
                if isinstance(recs, list)
            }
    return {}
