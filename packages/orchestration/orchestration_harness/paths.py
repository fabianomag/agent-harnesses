"""Root-bound path resolution without following symlink escapes."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath

from .errors import ValidationError
from .model import validate_relative_path


MAX_STATE_BYTES = 1_000_000


def _metadata_is_link_like(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and attributes & reparse)


def is_link_like(path: Path) -> bool:
    """Detect symlinks and Windows reparse points without following them."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ValidationError("managed path metadata is unreadable") from error
    return _metadata_is_link_like(metadata)


def _reject_link_like_root_components(candidate: Path) -> None:
    lexical = candidate if candidate.is_absolute() else Path.cwd() / candidate
    current = Path(lexical.anchor)
    for part in lexical.parts:
        if part in {"", ".", lexical.anchor}:
            continue
        if part == "..":
            current = current.parent
            continue
        current = current / part
        try:
            metadata = current.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return
        except OSError as error:
            raise ValidationError("workspace root metadata is unreadable") from error
        if _metadata_is_link_like(metadata):
            raise ValidationError(
                "workspace root path must not contain a link-like component"
            )


def canonical_root(root: Path) -> Path:
    candidate = Path(root)
    _reject_link_like_root_components(candidate)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValidationError("workspace root must already exist") from error
    if not resolved.is_dir():
        raise ValidationError("workspace root must be a directory")
    return resolved


def safe_path(root: Path, relative: str) -> Path:
    """Resolve one validated relative path and reject every existing symlink."""

    validated = validate_relative_path(relative, allow_reserved=True)
    boundary = canonical_root(root)
    current = boundary
    parts = PurePosixPath(validated).parts
    for index, part in enumerate(parts):
        current = current / part
        if is_link_like(current):
            raise ValidationError("managed path crosses a symbolic link")
        if current.exists() and index < len(parts) - 1 and not current.is_dir():
            raise ValidationError("managed path crosses a non-directory")
    try:
        resolved = current.resolve(strict=False)
        resolved.relative_to(boundary)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValidationError("managed path escapes the workspace root") from error
    try:
        common = os.path.commonpath((str(boundary), str(resolved)))
    except ValueError as error:
        raise ValidationError("managed path escapes the workspace root") from error
    if common != str(boundary):
        raise ValidationError("managed path escapes the workspace root")
    return current


def read_owned_text(root: Path, relative: str) -> str:
    path = safe_path(root, relative)
    if is_link_like(path) or not path.is_file():
        raise ValidationError("required managed file is missing")
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise ValidationError("managed file exceeds the size limit")
        return path.read_text(encoding="utf-8")
    except ValidationError:
        raise
    except (OSError, UnicodeError) as error:
        raise ValidationError("managed file is not readable UTF-8 text") from error
