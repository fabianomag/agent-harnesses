"""A clean-room, project-local harness implemented with the Python standard library."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence


HARNESS_VERSION = "0.2.2"
READABLE_HARNESS_VERSIONS = frozenset(
    ("0.1.0", "0.2.0", "0.2.1", HARNESS_VERSION)
)
STATE_SCHEMA_VERSION = 1
STATE_DIRECTORY = PurePosixPath(".project-harness")
STATE_PATH = STATE_DIRECTORY / "state.json"
REQUIRED_DIRECTORIES = (
    STATE_DIRECTORY,
    PurePosixPath("docs"),
    PurePosixPath("generated"),
    PurePosixPath("plans"),
    PurePosixPath("references"),
)
RESERVED_MARKER = "<!-- project-harness:"
MAX_SUMMARY_LENGTH = 10_000
MAX_ITEM_LENGTH = 2_000
MAX_ITEMS = 100
MAX_CONTEXT_BYTES = 256_000
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RECORD_ID_PATTERN = re.compile(r"^R[0-9]{4,}$")
TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class HarnessError(RuntimeError):
    """A safe, user-facing harness error."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message

    def render(self) -> str:
        return f"ERROR [{self.code}] {self.path}: {self.message}"


class CollisionError(HarnessError):
    """Raised when an existing path cannot be reconciled safely."""


class TransactionError(HarnessError):
    """Raised when a write transaction fails."""


@dataclass(frozen=True, order=True)
class VerificationIssue:
    """A verification finding that does not include project content."""

    path: str
    code: str
    message: str

    def render(self) -> str:
        return f"ERROR [{self.code}] {self.path}: {self.message}"


@dataclass(frozen=True)
class ManagedFile:
    """A managed Markdown projection and its stable marker key."""

    path: PurePosixPath
    key: str
    title: str

    @property
    def begin_marker(self) -> bytes:
        return (
            f"<!-- project-harness:managed:{self.key}:begin -->".encode("ascii")
        )

    @property
    def end_marker(self) -> bytes:
        return f"<!-- project-harness:managed:{self.key}:end -->".encode("ascii")

    @property
    def marker_token(self) -> bytes:
        return f"project-harness:managed:{self.key}".encode("ascii")


MANAGED_FILES = (
    ManagedFile(PurePosixPath("AGENTS.md"), "agents", "# Project Agent Instructions"),
    ManagedFile(PurePosixPath("ARCHITECTURE.md"), "architecture", "# Architecture"),
    ManagedFile(
        PurePosixPath("docs/project-context.md"),
        "project-context",
        "# Project Context",
    ),
    ManagedFile(
        PurePosixPath("docs/decisions.md"),
        "decisions",
        "# Decisions",
    ),
    ManagedFile(
        PurePosixPath("docs/next-actions.md"),
        "next-actions",
        "# Next Actions",
    ),
    ManagedFile(
        PurePosixPath("docs/session-log.md"),
        "session-log",
        "# Session Log",
    ),
)
MANAGED_BY_PATH = {spec.path: spec for spec in MANAGED_FILES}
DATA_PROJECTION_KEYS = {"decisions", "next-actions", "session-log"}


@dataclass(frozen=True)
class FileMutation:
    """One preflighted file replacement."""

    path: PurePosixPath
    before: bytes | None
    after: bytes
    mode: int

    @property
    def action(self) -> str:
        return "create-file" if self.before is None else "update-file"


@dataclass(frozen=True)
class ChangePlan:
    """A complete, deterministic write plan."""

    directories: tuple[PurePosixPath, ...]
    files: tuple[FileMutation, ...]

    @property
    def is_noop(self) -> bool:
        return not self.directories and not self.files

    def rendered_changes(self) -> list[dict[str, str]]:
        changes = [
            {"action": "create-directory", "path": path.as_posix()}
            for path in self.directories
        ]
        changes.extend(
            {"action": mutation.action, "path": mutation.path.as_posix()}
            for mutation in self.files
        )
        return changes


def _empty_state() -> dict[str, Any]:
    return {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "harnessVersion": HARNESS_VERSION,
        "nextRecord": 1,
        "records": [],
    }


def _state_bytes(state: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _normalize_text(
    value: str,
    *,
    field: str,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise HarnessError("INPUT_TYPE", ".", f"{field} must be text")
    if "\x00" in value or RESERVED_MARKER in value:
        raise HarnessError(
            "INPUT_RESERVED",
            ".",
            f"{field} contains reserved content",
        )
    normalized = " ".join(value.split())
    if not normalized and not allow_empty:
        raise HarnessError("INPUT_EMPTY", ".", f"{field} must not be empty")
    if len(normalized) > maximum:
        raise HarnessError("INPUT_LIMIT", ".", f"{field} exceeds its size limit")
    return normalized


def _normalize_items(values: Sequence[str], *, field: str) -> list[str]:
    if len(values) > MAX_ITEMS:
        raise HarnessError("INPUT_LIMIT", ".", f"{field} contains too many items")
    return [
        _normalize_text(value, field=field, maximum=MAX_ITEM_LENGTH)
        for value in values
    ]


def _validate_state_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CollisionError("STATE_INVALID", STATE_PATH.as_posix(), "state must be an object")
    required_keys = {
        "schemaVersion",
        "harnessVersion",
        "nextRecord",
        "records",
    }
    if set(value) != required_keys:
        raise CollisionError(
            "STATE_INVALID",
            STATE_PATH.as_posix(),
            "state has unsupported or missing fields",
        )
    if value["schemaVersion"] != STATE_SCHEMA_VERSION:
        raise CollisionError(
            "STATE_VERSION",
            STATE_PATH.as_posix(),
            "state schema version is not supported",
        )
    if value["harnessVersion"] not in READABLE_HARNESS_VERSIONS:
        raise CollisionError(
            "STATE_VERSION",
            STATE_PATH.as_posix(),
            "state harness version is not supported",
        )
    next_record = value["nextRecord"]
    records = value["records"]
    if (
        not isinstance(next_record, int)
        or isinstance(next_record, bool)
        or next_record < 1
        or not isinstance(records, list)
    ):
        raise CollisionError(
            "STATE_INVALID",
            STATE_PATH.as_posix(),
            "state record metadata is invalid",
        )
    expected_record_keys = {
        "id",
        "kind",
        "at",
        "session",
        "summary",
        "decisions",
        "tasks",
        "nextStep",
    }
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or set(record) != expected_record_keys:
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state contains an invalid record",
            )
        expected_id = f"R{index:04d}"
        if (
            record["id"] != expected_id
            or not isinstance(record["id"], str)
            or RECORD_ID_PATTERN.fullmatch(record["id"]) is None
        ):
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state record sequence is invalid",
            )
        if record["kind"] not in {"checkpoint", "close"}:
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state contains an unsupported record kind",
            )
        if (
            not isinstance(record["at"], str)
            or TIMESTAMP_PATTERN.fullmatch(record["at"]) is None
            or not isinstance(record["session"], str)
            or SESSION_ID_PATTERN.fullmatch(record["session"]) is None
        ):
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state record identity is invalid",
            )
        _normalize_text(
            record["summary"],
            field="record summary",
            maximum=MAX_SUMMARY_LENGTH,
        )
        _normalize_text(
            record["nextStep"],
            field="record next step",
            maximum=MAX_ITEM_LENGTH,
        )
        if not isinstance(record["decisions"], list) or not all(
            isinstance(item, str) for item in record["decisions"]
        ):
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state decisions are invalid",
            )
        if not isinstance(record["tasks"], list) or not all(
            isinstance(item, str) for item in record["tasks"]
        ):
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state tasks are invalid",
            )
        try:
            _normalize_items(record["decisions"], field="record decisions")
            _normalize_items(record["tasks"], field="record tasks")
        except HarnessError as error:
            raise CollisionError(
                "STATE_INVALID",
                STATE_PATH.as_posix(),
                "state record content is invalid",
            ) from error
    if next_record != len(records) + 1:
        raise CollisionError(
            "STATE_INVALID",
            STATE_PATH.as_posix(),
            "state next record counter is invalid",
        )
    return value


def _decode_state(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        value = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CollisionError(
            "STATE_INVALID",
            STATE_PATH.as_posix(),
            "state is not readable UTF-8 JSON",
        ) from error
    return _validate_state_value(value)


def _assert_relative_path(relative: PurePosixPath | str) -> PurePosixPath:
    candidate = (
        relative if isinstance(relative, PurePosixPath) else PurePosixPath(relative)
    )
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or "\\" in candidate.as_posix()
    ):
        raise HarnessError(
            "PATH_BOUNDARY",
            ".",
            "managed path must remain relative to the selected root",
        )
    return candidate


def _root_path(root_argument: str | os.PathLike[str] | Path) -> Path:
    raw_argument = os.fspath(root_argument)
    if isinstance(raw_argument, str) and not raw_argument.strip():
        raise HarnessError(
            "ROOT_INVALID",
            ".",
            "selected root must not be empty",
        )
    requested = Path(root_argument)
    lexical = requested if requested.is_absolute() else Path.cwd() / requested
    current = Path(lexical.anchor)
    try:
        metadata = current.lstat()
    except OSError as error:
        raise HarnessError(
            "ROOT_INVALID",
            ".",
            "selected root must already exist",
        ) from error
    if _is_link_like(metadata):
        raise HarnessError(
            "ROOT_SYMLINK",
            ".",
            "selected root path must not contain symbolic links",
        )

    for component in lexical.parts[1:]:
        current = current.parent if component == ".." else current / component
        try:
            metadata = current.lstat()
        except OSError as error:
            raise HarnessError(
                "ROOT_INVALID",
                ".",
                "selected root must already exist",
            ) from error
        if _is_link_like(metadata):
            raise HarnessError(
                "ROOT_SYMLINK",
                ".",
                "selected root path must not contain symbolic links",
            )

    if not stat.S_ISDIR(metadata.st_mode):
        raise HarnessError(
            "ROOT_INVALID",
            ".",
            "selected root must be a directory",
        )
    try:
        return current.resolve(strict=True)
    except OSError as error:
        raise HarnessError(
            "ROOT_INVALID",
            ".",
            "selected root cannot be resolved",
        ) from error


def _target(root: Path, relative: PurePosixPath | str) -> Path:
    safe_relative = _assert_relative_path(relative)
    candidate = root.joinpath(*safe_relative.parts)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise HarnessError(
            "PATH_BOUNDARY",
            safe_relative.as_posix(),
            "managed path escapes the selected root",
        ) from error

    current = root
    for index, part in enumerate(safe_relative.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError as error:
            raise CollisionError(
                "PATH_UNREADABLE",
                safe_relative.as_posix(),
                "managed path metadata is not readable",
            ) from error
        if _is_link_like(metadata):
            raise CollisionError(
                "PATH_SYMLINK",
                safe_relative.as_posix(),
                "managed paths must not contain symbolic links",
            )
        if index < len(safe_relative.parts) - 1 and not stat.S_ISDIR(
            metadata.st_mode
        ):
            raise CollisionError(
                "PATH_COLLISION",
                safe_relative.as_posix(),
                "a managed parent path is not a directory",
            )
    return candidate


def _is_link_like(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _read_regular_file(root: Path, relative: PurePosixPath) -> tuple[bytes, int] | None:
    path = _target(root, relative)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise CollisionError(
            "PATH_UNREADABLE",
            relative.as_posix(),
            "managed file metadata is not readable",
        ) from error
    if not stat.S_ISREG(metadata.st_mode):
        raise CollisionError(
            "PATH_COLLISION",
            relative.as_posix(),
            "managed file path is not a regular file",
        )
    try:
        return path.read_bytes(), stat.S_IMODE(metadata.st_mode)
    except OSError as error:
        raise CollisionError(
            "PATH_UNREADABLE",
            relative.as_posix(),
            "managed file is not readable",
        ) from error


def _ensure_directory_shape(root: Path, relative: PurePosixPath) -> bool:
    path = _target(root, relative)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CollisionError(
            "PATH_UNREADABLE",
            relative.as_posix(),
            "managed directory metadata is not readable",
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise CollisionError(
            "PATH_COLLISION",
            relative.as_posix(),
            "managed directory path is not a directory",
        )
    return True


def _newline_style(data: bytes) -> bytes:
    without_crlf = data.replace(b"\r\n", b"")
    if b"\r\n" in data and b"\n" not in without_crlf:
        return b"\r\n"
    return b"\n"


def _line_marker_is_exact(data: bytes, start: int, marker: bytes) -> bool:
    before_ok = start == 0 or data[start - 1 : start] == b"\n"
    end = start + len(marker)
    after_ok = end == len(data) or data[end : end + 1] in {b"\r", b"\n"}
    return before_ok and after_ok


def _locate_managed_block(
    data: bytes,
    spec: ManagedFile,
) -> tuple[int, int] | None:
    begin_count = data.count(spec.begin_marker)
    end_count = data.count(spec.end_marker)
    if begin_count == 0 and end_count == 0:
        if spec.marker_token in data:
            raise CollisionError(
                "MARKER_COLLISION",
                spec.path.as_posix(),
                "managed marker is malformed",
            )
        return None
    if begin_count != 1 or end_count != 1:
        raise CollisionError(
            "MARKER_COLLISION",
            spec.path.as_posix(),
            "managed marker pair is missing or duplicated",
        )
    begin = data.find(spec.begin_marker)
    end_start = data.find(spec.end_marker)
    end = end_start + len(spec.end_marker)
    if (
        end_start <= begin
        or not _line_marker_is_exact(data, begin, spec.begin_marker)
        or not _line_marker_is_exact(data, end_start, spec.end_marker)
    ):
        raise CollisionError(
            "MARKER_COLLISION",
            spec.path.as_posix(),
            "managed marker pair is malformed or out of order",
        )
    return begin, end


def _managed_block(spec: ManagedFile, body: str, newline: bytes) -> bytes:
    normalized_body = body.strip("\n")
    block = (
        spec.begin_marker.decode("ascii")
        + "\n"
        + normalized_body
        + "\n"
        + spec.end_marker.decode("ascii")
    )
    return block.encode("utf-8").replace(b"\n", newline)


def _merge_managed_block(
    existing: bytes | None,
    spec: ManagedFile,
    body: str,
) -> tuple[bytes, bool]:
    if existing is None or existing == b"":
        newline = b"\n"
        block = _managed_block(spec, body, newline)
        return spec.title.encode("utf-8") + newline * 2 + block + newline, False
    try:
        existing.decode("utf-8")
    except UnicodeError as error:
        raise CollisionError(
            "UTF8_INVALID",
            spec.path.as_posix(),
            "managed Markdown file is not valid UTF-8",
        ) from error
    newline = _newline_style(existing)
    block = _managed_block(spec, body, newline)
    location = _locate_managed_block(existing, spec)
    if location is None:
        if existing.endswith(newline * 2):
            separator = b""
        elif existing.endswith(newline):
            separator = newline
        else:
            separator = newline * 2
        return existing + separator + block + newline, False
    begin, end = location
    return existing[:begin] + block + existing[end:], True


def _static_body(key: str) -> str:
    bodies = {
        "agents": """
## Project Harness

This harness coordinates context and durable work for this project only.
It does not coordinate sibling projects, workspaces, or external systems.

Read in this order:

1. `docs/project-context.md`
2. `ARCHITECTURE.md`
3. `docs/decisions.md`
4. `docs/next-actions.md`
5. `docs/session-log.md`

Use the package CLI for the supported loop: `open`, `digest`, `checkpoint`,
`close`, and `verify`. Human-authored instructions belong outside this block.
""",
        "architecture": """
## Harness boundary

The selected project root is the complete write boundary. The harness manages
only its marked blocks, its canonical state, and the directories created by
initialization. Project-specific architecture belongs outside this block.

`plans/` holds working plans, `references/` holds local reference material,
and `generated/` holds generated artifacts. Their contents are not inferred
or rewritten by the harness.
""",
        "project-context": """
## Context contract

Record the project's purpose, constraints, confirmed facts, and open questions
outside this block. The harness does not invent project context.

The durable operational record is projected into the decisions, next-actions,
and session-log documents from canonical local state.
""",
    }
    return bodies[key]


def _record_heading(record: Mapping[str, Any]) -> str:
    return (
        f"### {record['id']} — {record['kind']} — "
        f"{record['at']} — session `{record['session']}`"
    )


def _decisions_body(state: Mapping[str, Any]) -> str:
    lines = [
        "## Durable decision projection",
        "",
        "This block is generated from local harness state.",
    ]
    records = state["records"]
    if not records:
        lines.extend(["", "No records yet."])
    for record in records:
        lines.extend(["", _record_heading(record), "", f"- Summary: {record['summary']}"])
        decisions = record["decisions"]
        if decisions:
            lines.append("- Decisions:")
            lines.extend(f"  - {decision}" for decision in decisions)
        else:
            lines.append("- Decisions: none recorded")
    return "\n".join(lines)


def _next_actions_body(state: Mapping[str, Any]) -> str:
    lines = [
        "## Durable next-action projection",
        "",
        "This block is generated from local harness state.",
    ]
    records = state["records"]
    if not records:
        lines.extend(["", "No records yet."])
    for record in records:
        lines.extend(["", _record_heading(record), ""])
        tasks = record["tasks"]
        if tasks:
            lines.append("- Tasks:")
            lines.extend(f"  - {task}" for task in tasks)
        else:
            lines.append("- Tasks: none recorded")
        lines.append(f"- Next step: {record['nextStep']}")
    return "\n".join(lines)


def _session_log_body(state: Mapping[str, Any]) -> str:
    lines = [
        "## Durable session projection",
        "",
        "This block is generated from local harness state.",
    ]
    records = state["records"]
    if not records:
        lines.extend(["", "No records yet."])
    for record in records:
        lines.extend(
            [
                "",
                _record_heading(record),
                "",
                f"- Summary: {record['summary']}",
                f"- Decisions recorded: {len(record['decisions'])}",
                f"- Tasks recorded: {len(record['tasks'])}",
                f"- Next step: {record['nextStep']}",
            ]
        )
    return "\n".join(lines)


def _body_for(spec: ManagedFile, state: Mapping[str, Any]) -> str:
    if spec.key in {"agents", "architecture", "project-context"}:
        return _static_body(spec.key)
    if spec.key == "decisions":
        return _decisions_body(state)
    if spec.key == "next-actions":
        return _next_actions_body(state)
    if spec.key == "session-log":
        return _session_log_body(state)
    raise AssertionError(f"unsupported managed file key: {spec.key}")


def plan_init(root_argument: str | os.PathLike[str] | Path) -> tuple[Path, ChangePlan]:
    """Preflight initialization and return a zero-write plan."""

    root = _root_path(root_argument)
    missing_directories: list[PurePosixPath] = []
    for relative in REQUIRED_DIRECTORIES:
        if not _ensure_directory_shape(root, relative):
            missing_directories.append(relative)

    state_read = _read_regular_file(root, STATE_PATH)
    state_exists = state_read is not None
    if state_read is None:
        state = _empty_state()
        state_before = None
        state_mode = 0o644
    else:
        state_before, state_mode = state_read
        state = _decode_state(state_before)

    file_mutations: list[FileMutation] = []
    desired_state = _state_bytes(state)
    if state_before != desired_state:
        file_mutations.append(
            FileMutation(STATE_PATH, state_before, desired_state, state_mode)
        )

    for spec in MANAGED_FILES:
        file_read = _read_regular_file(root, spec.path)
        if file_read is None:
            before = None
            mode = 0o644
        else:
            before, mode = file_read
        after, had_block = _merge_managed_block(
            before,
            spec,
            _body_for(spec, state),
        )
        if (
            not state_exists
            and had_block
            and spec.key in DATA_PROJECTION_KEYS
        ):
            empty_block = _managed_block(
                spec,
                _body_for(spec, _empty_state()),
                _newline_style(before or b""),
            )
            location = _locate_managed_block(before or b"", spec)
            assert location is not None
            begin, end = location
            if (before or b"")[begin:end] != empty_block:
                raise CollisionError(
                    "STATE_MISSING",
                    spec.path.as_posix(),
                    "durable projection exists without canonical state",
                )
        if before != after:
            file_mutations.append(FileMutation(spec.path, before, after, mode))

    return root, ChangePlan(
        directories=tuple(missing_directories),
        files=tuple(file_mutations),
    )


def _write_staged_file(path: Path, data: bytes, mode: int) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".project-harness-",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return temporary


def _restore_file(path: Path, data: bytes, mode: int) -> None:
    temporary = _write_staged_file(path, data, mode)
    try:
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _current_regular_bytes(path: Path) -> bytes | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise TransactionError(
            "TRANSACTION_RACE",
            ".",
            "a managed path changed type after preflight",
        )
    return path.read_bytes()


def apply_plan(
    root: Path,
    plan: ChangePlan,
    *,
    before_replace: Callable[[int, PurePosixPath], None] | None = None,
    post_verify: bool = True,
) -> None:
    """Apply a preflighted plan with atomic file replacement and rollback."""

    if plan.is_noop:
        return

    created_directories: list[Path] = []
    staged: dict[PurePosixPath, Path] = {}
    applied: list[FileMutation] = []
    try:
        for relative in plan.directories:
            directory = _target(root, relative)
            directory.mkdir()
            created_directories.append(directory)

        for mutation in plan.files:
            target = _target(root, mutation.path)
            current = _current_regular_bytes(target)
            if current != mutation.before:
                raise TransactionError(
                    "TRANSACTION_RACE",
                    mutation.path.as_posix(),
                    "managed file changed after preflight",
                )
            staged[mutation.path] = _write_staged_file(
                target,
                mutation.after,
                mutation.mode,
            )

        for index, mutation in enumerate(plan.files):
            if before_replace is not None:
                before_replace(index, mutation.path)
            target = _target(root, mutation.path)
            os.replace(staged[mutation.path], target)
            applied.append(mutation)

        if post_verify:
            issues = verify_root(root)
            if issues:
                raise TransactionError(
                    "POST_VERIFY",
                    ".",
                    "post-write verification failed",
                )
    except BaseException as error:
        rollback_errors: list[Exception] = []
        for temporary in staged.values():
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                rollback_errors.append(cleanup_error)
        for mutation in reversed(applied):
            target = _target(root, mutation.path)
            try:
                if mutation.before is None:
                    target.unlink()
                else:
                    _restore_file(target, mutation.before, mutation.mode)
            except Exception as rollback_error:
                rollback_errors.append(rollback_error)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        if rollback_errors:
            raise TransactionError(
                "ROLLBACK_INCOMPLETE",
                ".",
                "write failed and rollback could not restore every path",
            ) from error
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise TransactionError(
            "TRANSACTION_ROLLED_BACK",
            ".",
            "write failed and all planned changes were rolled back",
        ) from error
    finally:
        for temporary in staged.values():
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def initialize(
    root_argument: str | os.PathLike[str] | Path,
    *,
    dry_run: bool = False,
    before_replace: Callable[[int, PurePosixPath], None] | None = None,
) -> ChangePlan:
    """Initialize or reconcile one project root."""

    root, plan = plan_init(root_argument)
    if not dry_run:
        apply_plan(root, plan, before_replace=before_replace)
    return plan


def _verification_issue_from_error(error: HarnessError) -> VerificationIssue:
    return VerificationIssue(error.path, error.code, error.message)


def verify_root(root_argument: str | os.PathLike[str] | Path) -> list[VerificationIssue]:
    """Verify installed state and projections without writing."""

    try:
        root = (
            root_argument
            if isinstance(root_argument, Path) and root_argument.is_absolute()
            else _root_path(root_argument)
        )
        if isinstance(root, Path):
            root = _root_path(root)
    except HarnessError as error:
        return [_verification_issue_from_error(error)]

    issues: list[VerificationIssue] = []
    for relative in REQUIRED_DIRECTORIES:
        try:
            if not _ensure_directory_shape(root, relative):
                issues.append(
                    VerificationIssue(
                        relative.as_posix(),
                        "DIRECTORY_MISSING",
                        "required harness directory is missing",
                    )
                )
        except HarnessError as error:
            issues.append(_verification_issue_from_error(error))

    state: dict[str, Any] | None = None
    try:
        state_read = _read_regular_file(root, STATE_PATH)
        if state_read is None:
            issues.append(
                VerificationIssue(
                    STATE_PATH.as_posix(),
                    "STATE_MISSING",
                    "canonical harness state is missing",
                )
            )
        else:
            state = _decode_state(state_read[0])
            if state_read[0] != _state_bytes(state):
                issues.append(
                    VerificationIssue(
                        STATE_PATH.as_posix(),
                        "STATE_DRIFT",
                        "canonical harness state is not normalized",
                    )
                )
    except HarnessError as error:
        issues.append(_verification_issue_from_error(error))

    for spec in MANAGED_FILES:
        try:
            file_read = _read_regular_file(root, spec.path)
            if file_read is None:
                issues.append(
                    VerificationIssue(
                        spec.path.as_posix(),
                        "FILE_MISSING",
                        "required managed file is missing",
                    )
                )
                continue
            data, _mode = file_read
            try:
                data.decode("utf-8")
            except UnicodeError:
                issues.append(
                    VerificationIssue(
                        spec.path.as_posix(),
                        "UTF8_INVALID",
                        "managed Markdown file is not valid UTF-8",
                    )
                )
                continue
            location = _locate_managed_block(data, spec)
            if location is None:
                issues.append(
                    VerificationIssue(
                        spec.path.as_posix(),
                        "MANAGED_BLOCK_MISSING",
                        "managed block is missing",
                    )
                )
                continue
            if state is not None:
                begin, end = location
                expected = _managed_block(
                    spec,
                    _body_for(spec, state),
                    _newline_style(data),
                )
                if data[begin:end] != expected:
                    issues.append(
                        VerificationIssue(
                            spec.path.as_posix(),
                            "MANAGED_BLOCK_DRIFT",
                            "managed block does not match canonical state",
                        )
                    )
        except HarnessError as error:
            issues.append(_verification_issue_from_error(error))
    return sorted(set(issues))


def _require_verified(root: Path) -> dict[str, Any]:
    issues = verify_root(root)
    if issues:
        raise HarnessError(
            "VERIFY_FAILED",
            ".",
            "project harness verification failed; run verify for details",
        )
    state_read = _read_regular_file(root, STATE_PATH)
    assert state_read is not None
    return _decode_state(state_read[0])


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _session_id(value: str | None, timestamp: str, next_record: int) -> str:
    candidate = value or (
        timestamp.replace("-", "").replace(":", "")
        + f"-R{next_record:04d}"
    )
    if SESSION_ID_PATTERN.fullmatch(candidate) is None:
        raise HarnessError(
            "SESSION_INVALID",
            ".",
            "session must use letters, digits, dots, underscores, or hyphens",
        )
    return candidate


def _record_plan(
    root: Path,
    current_state_bytes: bytes,
    state: dict[str, Any],
) -> ChangePlan:
    file_mutations: list[FileMutation] = []
    desired_state_bytes = _state_bytes(state)
    state_read = _read_regular_file(root, STATE_PATH)
    assert state_read is not None
    file_mutations.append(
        FileMutation(
            STATE_PATH,
            current_state_bytes,
            desired_state_bytes,
            state_read[1],
        )
    )
    for key in ("decisions", "next-actions", "session-log"):
        spec = next(item for item in MANAGED_FILES if item.key == key)
        file_read = _read_regular_file(root, spec.path)
        assert file_read is not None
        before, mode = file_read
        after, _had_block = _merge_managed_block(
            before,
            spec,
            _body_for(spec, state),
        )
        file_mutations.append(FileMutation(spec.path, before, after, mode))
    return ChangePlan((), tuple(file_mutations))


def record_event(
    root_argument: str | os.PathLike[str] | Path,
    *,
    kind: str,
    summary: str,
    decisions: Sequence[str],
    tasks: Sequence[str],
    next_step: str,
    session: str | None = None,
    now: Callable[[], str] = _timestamp_now,
    before_replace: Callable[[int, PurePosixPath], None] | None = None,
) -> dict[str, Any]:
    """Persist one checkpoint or close record as a single rollback-capable batch."""

    if kind not in {"checkpoint", "close"}:
        raise HarnessError("RECORD_KIND", ".", "record kind is not supported")
    normalized_summary = _normalize_text(
        summary,
        field=f"{kind} summary",
        maximum=MAX_SUMMARY_LENGTH,
    )
    normalized_decisions = _normalize_items(decisions, field="decisions")
    normalized_tasks = _normalize_items(tasks, field="tasks")
    normalized_next_step = _normalize_text(
        next_step,
        field="next step",
        maximum=MAX_ITEM_LENGTH,
    )
    root = _root_path(root_argument)
    state = _require_verified(root)
    state_read = _read_regular_file(root, STATE_PATH)
    assert state_read is not None
    timestamp = now()
    if TIMESTAMP_PATTERN.fullmatch(timestamp) is None:
        raise HarnessError(
            "CLOCK_INVALID",
            ".",
            "clock must return a UTC timestamp",
        )
    next_record = state["nextRecord"]
    record = {
        "id": f"R{next_record:04d}",
        "kind": kind,
        "at": timestamp,
        "session": _session_id(session, timestamp, next_record),
        "summary": normalized_summary,
        "decisions": normalized_decisions,
        "tasks": normalized_tasks,
        "nextStep": normalized_next_step,
    }
    updated_state = {
        **state,
        "nextRecord": next_record + 1,
        "records": [*state["records"], record],
    }
    _validate_state_value(updated_state)
    plan = _record_plan(root, state_read[0], updated_state)
    apply_plan(
        root,
        plan,
        before_replace=before_replace,
        post_verify=True,
    )
    return record


def status_snapshot(
    root_argument: str | os.PathLike[str] | Path,
) -> dict[str, Any]:
    """Return a compact durable-state snapshot without writing."""

    root = _root_path(root_argument)
    state = _require_verified(root)
    records = state["records"]
    latest = records[-1] if records else None
    return {
        "harnessVersion": HARNESS_VERSION,
        "recordCount": len(records),
        "lastRecord": latest,
        "nextStep": latest["nextStep"] if latest else None,
    }


def _human_content(root: Path, spec: ManagedFile) -> str:
    file_read = _read_regular_file(root, spec.path)
    assert file_read is not None
    data = file_read[0]
    if len(data) > MAX_CONTEXT_BYTES:
        raise HarnessError(
            "CONTEXT_LIMIT",
            spec.path.as_posix(),
            "context file exceeds the read limit",
        )
    location = _locate_managed_block(data, spec)
    assert location is not None
    begin, end = location
    try:
        before = data[:begin].decode("utf-8").strip()
        after = data[end:].decode("utf-8").strip()
    except UnicodeError as error:
        raise HarnessError(
            "UTF8_INVALID",
            spec.path.as_posix(),
            "context file is not valid UTF-8",
        ) from error
    before_lines = before.splitlines()
    if before_lines and before_lines[0].strip() == spec.title:
        before = "\n".join(before_lines[1:]).strip()
    return "\n\n".join(part for part in (before, after) if part)


def open_snapshot(
    root_argument: str | os.PathLike[str] | Path,
) -> dict[str, Any]:
    """Return durable status plus human-authored project context without writing."""

    root = _root_path(root_argument)
    snapshot = status_snapshot(root)
    snapshot["projectContext"] = _human_content(
        root,
        MANAGED_BY_PATH[PurePosixPath("docs/project-context.md")],
    )
    snapshot["architectureContext"] = _human_content(
        root,
        MANAGED_BY_PATH[PurePosixPath("ARCHITECTURE.md")],
    )
    return snapshot


def digest_snapshot(
    root_argument: str | os.PathLike[str] | Path,
) -> dict[str, Any]:
    """Collate durable context deterministically without claiming AI synthesis."""

    root = _root_path(root_argument)
    state = _require_verified(root)
    decisions = [
        {"record": record["id"], "value": decision}
        for record in state["records"]
        for decision in record["decisions"]
    ]
    latest = state["records"][-1] if state["records"] else None
    return {
        "recordCount": len(state["records"]),
        "projectContext": _human_content(
            root,
            MANAGED_BY_PATH[PurePosixPath("docs/project-context.md")],
        ),
        "architectureContext": _human_content(
            root,
            MANAGED_BY_PATH[PurePosixPath("ARCHITECTURE.md")],
        ),
        "decisions": decisions,
        "currentTasks": latest["tasks"] if latest else [],
        "nextStep": latest["nextStep"] if latest else None,
        "lastSession": latest["session"] if latest else None,
    }


def _add_root_and_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True, help="existing project root")
    parser.add_argument("--json", action="store_true", help="emit JSON output")


def _add_record_arguments(parser: argparse.ArgumentParser) -> None:
    _add_root_and_json(parser)
    parser.add_argument("--summary", required=True, help="durable event summary")
    parser.add_argument(
        "--decision",
        action="append",
        default=[],
        help="decision to persist; repeat for more than one",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help="task to persist; repeat for more than one",
    )
    parser.add_argument("--next-step", required=True, help="single next step")
    parser.add_argument("--session", help="stable local session label")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage durable context for one local project."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="plan or install the harness")
    _add_root_and_json(init_parser)
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preflight and print changes without writing",
    )

    for command in ("verify", "status", "open", "digest"):
        command_parser = subparsers.add_parser(command)
        _add_root_and_json(command_parser)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    _add_record_arguments(checkpoint_parser)
    close_parser = subparsers.add_parser("close")
    _add_record_arguments(close_parser)
    return parser.parse_args(argv)


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _print_snapshot(command: str, snapshot: Mapping[str, Any]) -> None:
    if command == "status":
        print(f"Project Harness {snapshot['harnessVersion']}")
        print(f"Durable records: {snapshot['recordCount']}")
        print(f"Next step: {snapshot['nextStep'] or 'not recorded'}")
        return
    if command == "open":
        print("Project Harness is ready.")
        print(f"Durable records: {snapshot['recordCount']}")
        print(f"Next step: {snapshot['nextStep'] or 'record the first checkpoint'}")
        if snapshot["projectContext"]:
            print("Project context:")
            print(snapshot["projectContext"])
        if snapshot["architectureContext"]:
            print("Architecture context:")
            print(snapshot["architectureContext"])
        return
    print("Deterministic durable digest")
    print(f"Records: {snapshot['recordCount']}")
    print(f"Decisions: {len(snapshot['decisions'])}")
    print(f"Current tasks: {len(snapshot['currentTasks'])}")
    print(f"Next step: {snapshot['nextStep'] or 'not recorded'}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.command == "init":
            plan = initialize(arguments.root, dry_run=arguments.dry_run)
            result = {
                "command": "init",
                "dryRun": arguments.dry_run,
                "changes": plan.rendered_changes(),
                "changed": not plan.is_noop,
            }
            if arguments.json:
                _print_json(result)
            elif plan.is_noop:
                print("No changes. Project Harness is already reconciled.")
            else:
                prefix = "Would apply" if arguments.dry_run else "Applied"
                print(f"{prefix} {len(result['changes'])} change(s):")
                for change in result["changes"]:
                    print(f"- {change['action']}: {change['path']}")
            return 0

        if arguments.command == "verify":
            issues = verify_root(arguments.root)
            result = {
                "valid": not issues,
                "issues": [
                    {
                        "path": issue.path,
                        "code": issue.code,
                        "message": issue.message,
                    }
                    for issue in issues
                ],
            }
            if arguments.json:
                _print_json(result)
            elif issues:
                for issue in issues:
                    print(issue.render())
            else:
                print("PASS: Project Harness state and projections verified.")
            return 0 if not issues else 1

        if arguments.command in {"status", "open"}:
            snapshot = (
                open_snapshot(arguments.root)
                if arguments.command == "open"
                else status_snapshot(arguments.root)
            )
            if arguments.json:
                _print_json(snapshot)
            else:
                _print_snapshot(arguments.command, snapshot)
            return 0

        if arguments.command == "digest":
            snapshot = digest_snapshot(arguments.root)
            if arguments.json:
                _print_json(snapshot)
            else:
                _print_snapshot(arguments.command, snapshot)
            return 0

        if arguments.command in {"checkpoint", "close"}:
            record = record_event(
                arguments.root,
                kind=arguments.command,
                summary=arguments.summary,
                decisions=arguments.decision,
                tasks=arguments.task,
                next_step=arguments.next_step,
                session=arguments.session,
            )
            if arguments.json:
                _print_json(record)
            else:
                print(
                    f"Recorded {record['kind']} {record['id']} "
                    f"for session {record['session']}."
                )
            return 0
    except HarnessError as error:
        print(error.render(), file=sys.stderr)
        return 2
    raise AssertionError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
