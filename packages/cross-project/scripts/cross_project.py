#!/usr/bin/env python3
"""A local, dependency-free cross-project coordination harness."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping


CONFIG_NAME = "harness.config.json"
LOCK_NAME = ".cross-project.lock"
SCHEMA_VERSION = 1
HARNESS_ID = "cross-project"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
START = "<!-- cross-project:start -->"
END = "<!-- cross-project:end -->"
MANAGED_FILES = ("AGENTS.md", "FRONTS.md", "NEXT.md")
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class HarnessError(ValueError):
    """A safe user-facing contract failure."""


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _metadata_is_link_like(metadata: os.stat_result) -> bool:
    """Recognize symbolic links and reported Windows reparse metadata."""

    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _is_link_like(path: Path) -> bool:
    """Inspect one existing path without following it; missing paths are plain."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise HarnessError("path metadata must be readable") from exc
    return _metadata_is_link_like(metadata)


def _lexical_absolute(path: Path) -> Path:
    """Make a native path absolute without resolving or erasing link components."""

    if path.drive and not path.is_absolute():
        raise HarnessError("root must not use a drive-relative path")
    return path if path.is_absolute() else Path.cwd() / path


def _assert_link_free_existing_root(path: Path) -> None:
    """Reject every link-like component in an existing lexical root path."""

    anchor = Path(path.anchor)
    try:
        anchor_metadata = anchor.lstat()
    except OSError as exc:
        raise HarnessError("root must be an existing directory") from exc
    if _metadata_is_link_like(anchor_metadata):
        raise HarnessError("root path components must not be link-like")

    cursor = anchor
    anchor_parts = len(anchor.parts)
    remaining = path.parts[anchor_parts:]
    for index, part in enumerate(remaining):
        if part in {"", "."}:
            continue
        if part == "..":
            cursor = cursor.parent
            continue
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            raise HarnessError("root must be an existing directory") from exc
        if _metadata_is_link_like(metadata):
            raise HarnessError("root path components must not be link-like")
        if index < len(remaining) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise HarnessError("root must be an existing directory")

    try:
        final_metadata = cursor.lstat()
    except OSError as exc:
        raise HarnessError("root must be an existing directory") from exc
    if _metadata_is_link_like(final_metadata):
        raise HarnessError("root path components must not be link-like")
    if not stat.S_ISDIR(final_metadata.st_mode):
        raise HarnessError("root must be an existing directory")


def _root(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError("root must be an existing directory")
    raw = _lexical_absolute(Path(value))
    _assert_link_free_existing_root(raw)
    try:
        resolved = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HarnessError("root must be an existing directory") from exc
    if not resolved.is_dir():
        raise HarnessError("root must be an existing directory")
    if resolved.parent == resolved:
        raise HarnessError("filesystem root must not be a harness root")
    try:
        home = Path.home().resolve(strict=True)
    except OSError:
        home = None
    if home is not None and resolved == home:
        raise HarnessError("home directory must not be a harness root")
    if any(part.casefold() == ".git" for part in resolved.parts):
        raise HarnessError("Git metadata must not be a harness root")
    return resolved


def _assert_plain_target(path: Path, root: Path, *, allow_missing: bool = False) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HarnessError("target escapes the selected root") from exc

    cursor = root
    relative = path.relative_to(root)
    for part in relative.parts:
        cursor = cursor / part
        if _is_link_like(cursor):
            raise HarnessError("link-like paths are not allowed in managed paths")
        if not cursor.exists():
            if allow_missing:
                return
            raise HarnessError("target must already exist")


def _child_parts(value: str) -> tuple[str, ...]:
    pure = PurePosixPath(value)
    if not value or value in {".", ".."}:
        raise HarnessError("child path must name a directory below the root")
    if any(
        ord(character) < 32
        or ord(character) == 127
        or character in '<>:"|?*' + chr(92)
        for character in value
    ):
        raise HarnessError("child path contains a non-portable character")
    if (
        pure.is_absolute()
        or value != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise HarnessError("child path must be normalized and root-relative")
    for part in pure.parts:
        if part.casefold() == ".git":
            raise HarnessError("Git metadata must not be a managed child path")
        if part.endswith((" ", ".")) or part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise HarnessError("child path contains a non-portable segment")
    return pure.parts


def _project_path_syntax(value: str) -> Path | None:
    """Validate one stored project-root spelling without touching the filesystem.

    Relative POSIX paths are the v0.1/v0.2.1 compatibility form and remain
    contained by the coordination root. New independent project roots may use
    normalized native absolute paths.
    """

    candidate = Path(value)
    if candidate.drive and not candidate.is_absolute():
        raise HarnessError("project root must not use a drive-relative path")
    if not candidate.is_absolute():
        _child_parts(value)
        return None

    native = os.fspath(candidate)
    if (
        value != native
        or any(part in {".", ".."} for part in candidate.parts)
        or (os.name != "nt" and value.startswith("//"))
    ):
        raise HarnessError("absolute project root must be normalized")
    if any(part.casefold() == ".git" for part in candidate.parts):
        raise HarnessError("Git metadata must not be a project root")
    return candidate


def _project_path(root: Path, value: str) -> tuple[str, Path]:
    candidate = _project_path_syntax(value)
    if candidate is None:
        parts = _child_parts(value)
        contained = root.joinpath(*parts)
        _assert_plain_target(contained, root)
        resolved = contained.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise HarnessError(
                "relative project root resolves outside the coordination root"
            ) from exc
        if not resolved.is_dir():
            raise HarnessError("project root must be an existing directory")
        return resolved.relative_to(root).as_posix(), resolved

    _assert_link_free_existing_root(candidate)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HarnessError("project root must be an existing directory") from exc
    if not resolved.is_dir():
        raise HarnessError("project root must be an existing directory")
    if resolved.parent == resolved:
        raise HarnessError("filesystem root must not be a project root")
    try:
        home = Path.home().resolve(strict=True)
    except OSError:
        home = None
    if home is not None and _same_path(resolved, home):
        raise HarnessError("home directory must not be a project root")
    if any(part.casefold() == ".git" for part in resolved.parts):
        raise HarnessError("Git metadata must not be a project root")
    if _same_path(resolved, root):
        raise HarnessError(
            "project root must be distinct from the coordination root"
        )
    return os.fspath(resolved), resolved


def _same_path(first: Path, second: Path) -> bool:
    try:
        return first.samefile(second)
    except OSError as exc:
        raise HarnessError("project root changed during validation; retry") from exc


def _read_text(path: Path) -> str:
    if _is_link_like(path):
        raise HarnessError(f"{path.name} must not be link-like")
    if not path.exists():
        return ""
    if not path.is_file():
        raise HarnessError(f"{path.name} must be a regular file")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise HarnessError(f"{path.name} must be readable UTF-8 text") from exc


def _managed(existing: str, body: str) -> str:
    start_count = existing.count(START)
    end_count = existing.count(END)
    block = f"{START}\n{body.rstrip()}\n{END}"
    if start_count == 0 and end_count == 0:
        if not existing:
            return f"{block}\n"
        separator = "\n" if existing.endswith("\n") else "\n\n"
        return f"{existing}{separator}{block}\n"
    if start_count != 1 or end_count != 1:
        raise HarnessError("managed block markers are malformed or duplicated")
    if existing.index(END) < existing.index(START):
        raise HarnessError("managed block markers are out of order")
    before, remainder = existing.split(START, 1)
    _, after = remainder.split(END, 1)
    return f"{before}{block}{after}"


def _validate_front(front_id: str, front: Any) -> None:
    if not ID_PATTERN.fullmatch(front_id):
        raise HarnessError("front id has an invalid format")
    if not isinstance(front, dict):
        raise HarnessError("front state must be an object")
    required = {
        "name": str,
        "path": str,
        "role": str,
        "state": str,
        "next": str,
        "blocker": str,
        "coordinationPending": bool,
        "lastReflection": str,
        "reflectWhen": str,
    }
    if set(front) != set(required):
        raise HarnessError("front state fields do not match the schema")
    for key, expected in required.items():
        if not isinstance(front[key], expected):
            raise HarnessError(f"front field {key} has an invalid type")
    if not front["name"] or not front["path"] or not front["role"] or not front["next"]:
        raise HarnessError("front name, path, role, and next must not be empty")
    for key, value in front.items():
        if isinstance(value, str):
            _safe_string(value, key, allow_empty=key in {
                "blocker",
                "lastReflection",
                "reflectWhen",
            })
    _project_path_syntax(front["path"])
    if front["coordinationPending"]:
        if front["lastReflection"] or front["reflectWhen"]:
            raise HarnessError("pending front must not contain a completed reflection")
    elif not front["lastReflection"] or not front["reflectWhen"]:
        raise HarnessError("reflected front must contain summary and reflection trigger")


def _safe_string(value: str, label: str, *, allow_empty: bool = False) -> str:
    if not allow_empty and not value.strip():
        raise HarnessError(f"{label} must not be empty")
    if len(value) > 1_000:
        raise HarnessError(f"{label} is longer than allowed")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise HarnessError(f"{label} must be a single line of text")
    if START in value or END in value:
        raise HarnessError(f"{label} contains a reserved managed-block marker")
    return value


def _validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "harness",
        "master",
        "fronts",
    }:
        raise HarnessError("configuration fields do not match the schema")
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != SCHEMA_VERSION
        or value["harness"] != HARNESS_ID
    ):
        raise HarnessError("configuration version or harness id is unsupported")
    if not isinstance(value["master"], dict) or set(value["master"]) != {"name"}:
        raise HarnessError("master state is invalid")
    if not isinstance(value["master"]["name"], str) or not value["master"]["name"]:
        raise HarnessError("master name must not be empty")
    _safe_string(value["master"]["name"], "master name")
    if not isinstance(value["fronts"], dict):
        raise HarnessError("fronts must be an object")
    for front_id, front in value["fronts"].items():
        _validate_front(front_id, front)
    return value


def _decode_state(raw: bytes) -> dict[str, Any]:
    if len(raw) > 1_000_000:
        raise HarnessError("configuration must be a small regular file")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise HarnessError("configuration contains a duplicate object key")
            value[key] = item
        return value

    def reject_constant(_: str) -> None:
        raise HarnessError("configuration must use standard JSON values")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except HarnessError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise HarnessError("configuration must be readable UTF-8 JSON") from exc
    return _validate_state(value)


def _load(root: Path, *, required: bool = True) -> dict[str, Any] | None:
    path = root / CONFIG_NAME
    if _is_link_like(path):
        raise HarnessError("configuration must not be link-like")
    if not path.exists():
        if required:
            raise HarnessError("root is not initialized")
        return None
    if not path.is_file():
        raise HarnessError("configuration must be a small regular file")
    try:
        if path.stat().st_size > 1_000_000:
            raise HarnessError("configuration must be a small regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise HarnessError("configuration must be readable UTF-8 JSON") from exc
    return _decode_state(raw)


def _state_bytes(state: Mapping[str, Any]) -> bytes:
    return (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _agents_body() -> str:
    return """# Cross-project protocol

Use `harness.config.json` as machine authority and `FRONTS.md` as the compact
human panel. Keep dense implementation history in each registered project.
Run `hq-sync` after a registration or reflection. Never repair a divergence
silently."""


def _fronts_body(state: Mapping[str, Any]) -> str:
    lines = [
        "# Fronts",
        "",
        "| ID | Name | Role | State | Next | Blocker |",
        "|---|---|---|---|---|---|",
    ]
    active = [
        (front_id, front)
        for front_id, front in sorted(state["fronts"].items())
        if not front["coordinationPending"]
    ]
    if not active:
        lines.append("| — | No reflected fronts yet | — | — | — | — |")
    for front_id, front in active:
        fields = [
            front_id,
            front["name"],
            front["role"],
            front["state"],
            front["next"],
            front["blocker"] or "—",
        ]
        safe = [str(field).replace("|", "&#124;").replace("\n", " ") for field in fields]
        lines.append("| " + " | ".join(safe) + " |")
        lines.append(
            f"\nResumption `{front_id}`: {front['next']} "
            f"(reflect again when: {front['reflectWhen']})"
        )
    return "\n".join(lines)


def _next_body(state: Mapping[str, Any]) -> str:
    lines = ["# Master open loops", "", "## Pending coordination"]
    pending = [
        (front_id, front)
        for front_id, front in sorted(state["fronts"].items())
        if front["coordinationPending"]
    ]
    if not pending:
        lines.append("- None.")
    else:
        for front_id, front in pending:
            lines.append(f"- `{front_id}` — first complete reflection is pending.")
    return "\n".join(lines)


def _render(root: Path, state: Mapping[str, Any]) -> dict[Path, bytes]:
    bodies = {
        "AGENTS.md": _agents_body(),
        "FRONTS.md": _fronts_body(state),
        "NEXT.md": _next_body(state),
    }
    rendered: dict[Path, bytes] = {}
    for name, body in bodies.items():
        rendered[root / name] = _managed(_read_text(root / name), body).encode("utf-8")
    # The manifest is the commit marker and machine authority, so replace it last.
    rendered[root / CONFIG_NAME] = _state_bytes(state)
    return rendered


def _capture_managed(root: Path) -> dict[Path, bytes | None]:
    captured: dict[Path, bytes | None] = {}
    for name in (CONFIG_NAME, *MANAGED_FILES):
        path = root / name
        if _is_link_like(path):
            raise HarnessError(f"{name} must not be link-like")
        if path.exists() and not path.is_file():
            raise HarnessError(f"{name} must be a regular file")
        try:
            captured[path] = path.read_bytes() if path.exists() else None
        except OSError as exc:
            raise HarnessError(f"{name} is not readable") from exc
    return captured


def _state_from_capture(
    captured: Mapping[Path, bytes | None],
    root: Path,
    *,
    required: bool,
) -> dict[str, Any] | None:
    raw = captured[root / CONFIG_NAME]
    if raw is None:
        if required:
            raise HarnessError("root is not initialized")
        return None
    return _decode_state(raw)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    lock = root / LOCK_NAME
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise HarnessError("another cross-project mutation holds the root lock") from exc
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except OSError as exc:
            raise HarnessError("could not release the root lock") from exc


def _replace(source: Path, target: Path) -> None:
    os.replace(source, target)


def _stage(root: Path, target: Path, content: bytes) -> Path:
    _assert_plain_target(target, root, allow_missing=True)
    if target.parent != root:
        raise HarnessError("managed files must live directly in the selected root")
    if _is_link_like(target):
        raise HarnessError(f"{target.name} must not be link-like")
    descriptor, temporary = tempfile.mkstemp(prefix=".cross-project-", dir=root)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            os.chmod(temp_path, stat.S_IMODE(target.stat().st_mode))
        return temp_path
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _restore(root: Path, target: Path, content: bytes | None) -> None:
    if content is None:
        target.unlink(missing_ok=True)
        return
    staged = _stage(root, target, content)
    _replace(staged, target)


def _apply(
    root: Path,
    rendered: Mapping[Path, bytes],
    *,
    expected: Mapping[Path, bytes | None] | None = None,
) -> list[str]:
    with _lock(root):
        current: dict[Path, bytes | None] = {}
        changes: dict[Path, bytes] = {}
        for target, content in rendered.items():
            if _is_link_like(target):
                raise HarnessError(f"{target.name} must not be link-like")
            old = target.read_bytes() if target.exists() else None
            if expected is not None and old != expected.get(target):
                raise HarnessError("managed state changed during the mutation; retry")
            current[target] = old
            if old != content:
                changes[target] = content
        if not changes:
            return []

        staged: dict[Path, Path] = {}
        applied: list[Path] = []
        try:
            for target, content in changes.items():
                staged[target] = _stage(root, target, content)
            for target, temporary in staged.items():
                _replace(temporary, target)
                applied.append(target)
            _fsync_directory(root)
        except BaseException as exc:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)
            rollback_error: BaseException | None = None
            for target in reversed(applied):
                try:
                    _restore(root, target, current[target])
                except BaseException as restore_exc:
                    rollback_error = restore_exc
            _fsync_directory(root)
            if rollback_error is not None:
                raise HarnessError("mutation failed and rollback was incomplete") from rollback_error
            if isinstance(exc, HarnessError):
                raise
            raise HarnessError("mutation failed; prior files were restored") from exc
    return sorted(path.name for path in changes)


def _snapshot(root: Path) -> dict[str, tuple[int, int, int, int, int] | None]:
    snapshot: dict[str, tuple[int, int, int, int, int] | None] = {}
    for name in (CONFIG_NAME, *MANAGED_FILES):
        path = root / name
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            snapshot[name] = None
            continue
        snapshot[name] = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_mode,
        )
    return snapshot


def _lock_exists(root: Path) -> bool:
    return os.path.lexists(root / LOCK_NAME)


def _ensure_unlocked(root: Path) -> None:
    if _lock_exists(root):
        raise HarnessError("another cross-project mutation holds the root lock")


@contextmanager
def _stable_read(root: Path) -> Iterator[None]:
    _ensure_unlocked(root)
    before = _snapshot(root)
    _ensure_unlocked(root)
    try:
        yield
    finally:
        after = _snapshot(root)
        if _lock_exists(root) or before != after:
            raise HarnessError("managed state changed during the read; retry")


def _require_front(state: Mapping[str, Any], front_id: str) -> dict[str, Any]:
    front = state["fronts"].get(front_id)
    if not isinstance(front, dict):
        raise HarnessError("front id is not registered")
    return front


def _assert_registered_paths(root: Path, state: Mapping[str, Any]) -> None:
    seen: list[tuple[str, Path]] = []
    for front_id, front in state["fronts"].items():
        _, path = _project_path(root, front["path"])
        for other_id, other_path in seen:
            if _same_path(path, other_path):
                raise HarnessError(f"front path aliases {other_id}")
        seen.append((front_id, path))


def command_bom_dia(args: argparse.Namespace) -> int:
    root = _root(args.root)
    with _stable_read(root):
        state = _load(root, required=False)
        if state is None:
            payload = {
                "command": "bom-dia",
                "initialized": False,
                "next": "run hq-init --dry-run",
            }
        elif args.front:
            front = _require_front(state, args.front)
            _project_path(root, front["path"])
            payload = {
                "command": "bom-dia",
                "front": args.front,
                "pending": front["coordinationPending"],
                "state": front["state"],
                "next": front["next"],
                "blocker": front["blocker"],
                "reflectWhen": front["reflectWhen"],
            }
        else:
            now = [
                {"id": front_id, "state": front["state"], "next": front["next"]}
                for front_id, front in sorted(state["fronts"].items())
                if not front["coordinationPending"]
            ]
            pending = sorted(
                front_id
                for front_id, front in state["fronts"].items()
                if front["coordinationPending"]
            )
            payload = {
                "command": "bom-dia",
                "initialized": True,
                "now": now,
                "pending": pending,
            }
    _emit(payload)
    return 0


def command_hq_init(args: argparse.Namespace) -> int:
    root = _root(args.root)
    _ensure_unlocked(root)
    read_snapshot = _snapshot(root)
    if not ID_PATTERN.fullmatch(args.front):
        raise HarnessError("front id has an invalid format")
    stored_path, resolved = _project_path(root, args.path)
    captured = _capture_managed(root)
    state = _state_from_capture(captured, root, required=False) or {
        "schemaVersion": SCHEMA_VERSION,
        "harness": HARNESS_ID,
        "master": {"name": args.master_name},
        "fronts": {},
    }
    existing = state["fronts"].get(args.front)
    proposed = {
        "name": args.name,
        "path": stored_path,
        "role": args.role,
        "state": "registered",
        "next": args.next,
        "blocker": "",
        "coordinationPending": True,
        "lastReflection": "",
        "reflectWhen": "",
    }
    if existing is not None and existing != proposed:
        raise HarnessError("front id is already registered with different facts")
    for other_id, other in state["fronts"].items():
        if other_id == args.front:
            continue
        _, other_path = _project_path(root, other["path"])
        if _same_path(other_path, resolved):
            raise HarnessError("another front id already owns this path")
    state["fronts"][args.front] = proposed
    rendered = _render(root, _validate_state(state))
    changed = sorted(
        path.name
        for path, content in rendered.items()
        if not path.exists() or path.read_bytes() != content
    )
    if args.dry_run:
        if _snapshot(root) != read_snapshot or _lock_exists(root):
            raise HarnessError("managed state changed during the read; retry")
        _emit({"command": "hq-init", "dryRun": True, "changed": changed})
        return 0
    applied = _apply(root, rendered, expected=captured)
    _emit({"command": "hq-init", "dryRun": False, "changed": applied})
    return 0


def command_hq_sync(args: argparse.Namespace) -> int:
    root = _root(args.root)
    with _stable_read(root):
        state = _load(root)
        issues: list[str] = []
        seen: list[tuple[str, Path]] = []
        for front_id, front in state["fronts"].items():
            try:
                _, path = _project_path(root, front["path"])
            except HarnessError as exc:
                issues.append(f"{front_id}: {exc}")
                continue
            for other_id, other_path in seen:
                if _same_path(path, other_path):
                    issues.append(f"{front_id}: path aliases {other_id}")
                    break
            seen.append((front_id, path))
        try:
            expected = _render(root, state)
        except HarnessError as exc:
            issues.append(str(exc))
            expected = {}
        for path, content in expected.items():
            if not path.exists() or path.read_bytes() != content:
                issues.append(f"{path.name}: rendered state diverges")
    _emit({"command": "hq-sync", "consistent": not issues, "issues": issues})
    return 0 if not issues else 1


def command_digere(args: argparse.Namespace) -> int:
    root = _root(args.root)
    with _stable_read(root):
        state = _load(root)
        front = _require_front(state, args.front)
        stored_path, _ = _project_path(root, front["path"])
        if args.scope == "local":
            owner = stored_path
            durable = True
        elif args.scope == "coordination":
            owner = CONFIG_NAME
            durable = True
        else:
            owner = ""
            durable = False
    _emit(
        {
            "command": "digere",
            "front": args.front,
            "scope": args.scope,
            "durable": durable,
            "owner": owner,
        }
    )
    return 0


def command_registra(args: argparse.Namespace) -> int:
    root = _root(args.root)
    _ensure_unlocked(root)
    captured = _capture_managed(root)
    state = _state_from_capture(captured, root, required=True)
    assert state is not None
    _assert_registered_paths(root, state)
    front = _require_front(state, args.front)
    front["state"] = args.state
    front["next"] = args.next
    if args.blocker is not None:
        front["blocker"] = args.blocker
    applied = _apply(
        root, _render(root, _validate_state(state)), expected=captured
    )
    _emit(
        {
            "command": "registra",
            "changed": applied,
            "coordinationPending": front["coordinationPending"],
        }
    )
    return 0


def command_encerra(args: argparse.Namespace) -> int:
    root = _root(args.root)
    _ensure_unlocked(root)
    captured = _capture_managed(root)
    state = _state_from_capture(captured, root, required=True)
    assert state is not None
    _assert_registered_paths(root, state)
    front = _require_front(state, args.front)
    front.update(
        {
            "role": args.role,
            "state": args.state,
            "next": args.next,
            "blocker": args.blocker,
            "coordinationPending": False,
            "lastReflection": args.summary,
            "reflectWhen": args.reflect_when,
        }
    )
    applied = _apply(
        root, _render(root, _validate_state(state)), expected=captured
    )
    _emit({"command": "encerra", "changed": applied, "coordinationPending": False})
    return 0


def _non_empty(parser: argparse.ArgumentParser, value: str, label: str) -> str:
    try:
        return _safe_string(value, label)
    except HarnessError as exc:
        parser.error(str(exc))
        raise AssertionError("argparse.error exits") from exc


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__)
    commands = top.add_subparsers(dest="command", required=True)

    bom = commands.add_parser("bom-dia", help="read-only orientation")
    bom.add_argument("--root", required=True)
    bom.add_argument("--front")
    bom.set_defaults(handler=command_bom_dia)

    init = commands.add_parser("hq-init", help="preview or register a project")
    init.add_argument("--root", required=True)
    init.add_argument("--master-name", default="Cross-project root")
    init.add_argument("--front", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--path", required=True)
    init.add_argument("--role", required=True)
    init.add_argument("--next", required=True)
    init.add_argument("--dry-run", action="store_true")
    init.set_defaults(handler=command_hq_init)

    sync = commands.add_parser("hq-sync", help="read-only structural validation")
    sync.add_argument("--root", required=True)
    sync.set_defaults(handler=command_hq_sync)

    digest = commands.add_parser("digere", help="read-only ownership routing")
    digest.add_argument("--root", required=True)
    digest.add_argument("--front", required=True)
    digest.add_argument(
        "--scope", required=True, choices=("local", "coordination", "ephemeral")
    )
    digest.set_defaults(handler=command_digere)

    register = commands.add_parser("registra", help="write a minimal checkpoint")
    register.add_argument("--root", required=True)
    register.add_argument("--front", required=True)
    register.add_argument("--state", required=True)
    register.add_argument("--next", required=True)
    register.add_argument("--blocker")
    register.set_defaults(handler=command_registra)

    close = commands.add_parser("encerra", help="write a complete reflection")
    close.add_argument("--root", required=True)
    close.add_argument("--front", required=True)
    close.add_argument("--role", required=True)
    close.add_argument("--state", required=True)
    close.add_argument("--next", required=True)
    close.add_argument("--summary", required=True)
    close.add_argument("--reflect-when", required=True)
    close.add_argument("--blocker", default="")
    close.set_defaults(handler=command_encerra)
    return top


def main(argv: list[str] | None = None) -> int:
    command_parser = parser()
    args = command_parser.parse_args(argv)
    for name in (
        "master_name",
        "name",
        "role",
        "next",
        "state",
        "summary",
        "reflect_when",
    ):
        if hasattr(args, name):
            setattr(args, name, _non_empty(command_parser, getattr(args, name), name))
    try:
        return int(args.handler(args))
    except HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
