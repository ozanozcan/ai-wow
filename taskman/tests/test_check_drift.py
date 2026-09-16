"""Tests for taskman.mow.check_drift (exit codes + drift reporting)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path



def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_identical_temp_dirs_exit_zero(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    files = {"cli.py": "print('ok')\n", "pkg/mod.py": "x = 1\n"}
    _write_tree(left, files)
    _write_tree(right, files)

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "taskman.mow.check_drift",
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_content_diff_exits_one_and_names_file(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    _write_tree(left, {"cli.py": "print('left')\n", "shared.py": "same\n"})
    _write_tree(right, {"cli.py": "print('right')\n", "shared.py": "same\n"})

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "taskman.mow.check_drift",
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    combined = result.stderr + result.stdout
    assert "cli.py" in combined
    # Only the differing file should be listed as a drift path line.
    drift_lines = [
        line.strip()
        for line in combined.splitlines()
        if line.strip().startswith("- ")
    ]
    assert drift_lines == ["- cli.py"]


def test_file_only_on_one_side_exits_one(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    _write_tree(left, {"cli.py": "same\n", "only_left.py": "extra\n"})
    _write_tree(right, {"cli.py": "same\n"})

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "taskman.mow.check_drift",
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    combined = result.stderr + result.stdout
    assert "only_left.py" in combined


def test_pycache_and_pyc_excluded(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    _write_tree(left, {"cli.py": "same\n"})
    _write_tree(right, {"cli.py": "same\n"})
    (left / "__pycache__").mkdir()
    (left / "__pycache__" / "cli.cpython-314.pyc").write_bytes(b"\x00\x01")
    (right / "orphan.pyc").write_bytes(b"\x00\x02")

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "taskman.mow.check_drift",
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
