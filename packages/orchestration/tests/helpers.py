"""Synthetic fixture helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import _bootstrap

from orchestration_harness.service import ControlPlane


def initialize(root: Path, *, fault_hook: Any = None) -> ControlPlane:
    control = ControlPlane(root, fault_hook=fault_hook)
    control.init(
        front_id="sample-front",
        display_name="Sample Front",
        path="fronts/sample-front",
        aliases=("sample",),
    )
    return control


def snapshot(root: Path) -> dict[str, tuple[Any, ...]]:
    values: dict[str, tuple[Any, ...]] = {
        ".": ("directory", root.stat().st_mode & 0o777, root.stat().st_mtime_ns)
    }
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in sorted(directories):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                values[relative] = ("symlink", os.readlink(path))
            else:
                stat = path.stat()
                values[relative] = (
                    "directory",
                    stat.st_mode & 0o777,
                    stat.st_mtime_ns,
                )
        for name in sorted(files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                values[relative] = ("symlink", os.readlink(path))
            else:
                stat = path.stat()
                values[relative] = (
                    "file",
                    stat.st_mode & 0o777,
                    stat.st_mtime_ns,
                    path.read_bytes(),
                )
    return values
