from __future__ import annotations

import pathlib
import tomllib


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
