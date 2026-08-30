"""A confined, standard-library workspace coordination harness.

The coordinator stores only a child index, shared boundary deltas, and generated
instructions. Child-owned execution state remains inside each registered child.
No operation discovers children: every filesystem target comes from an explicit
root, a validated relative path, or the coordinator manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = 1
TOOL_ID = "workspace-coordination"
MAX_MANAGED_BYTES = 1_000_000
MAX_OWNER_BYTES = 1_000_000
MAX_CHILDREN = 1_000
MAX_RECORDS = 10_000
MAX_DELTAS = 1_000
MAX_LOCAL_TEXT = 2_000
MAX_SHARED_TEXT = 280

ENTRYPOINT_PATH = Path("WORKSPACE_COORDINATION.md")
CONTROL_DIRECTORY = Path(".workspace-coordination")
MANIFEST_PATH = CONTROL_DIRECTORY / "workspace.json"
INDEX_PATH = CONTROL_DIRECTORY / "INDEX.md"
BOUNDARIES_PATH = CONTROL_DIRECTORY / "BOUNDARIES.md"
SHARED_PATH = CONTROL_DIRECTORY / "SHARED_DELTAS.md"
LOCAL_STATE_PATH = CONTROL_DIRECTORY / "local-state.json"

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_FORBIDDEN_PATH_CHARACTERS = frozenset('<>:"\\|?*')
_RECORD_KINDS = frozenset({"update", "decision", "close"})


class HarnessError(RuntimeError):
    """A stable operational failure suitable for CLI reporting."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VerificationIssue:
    """A verification issue that points only to a root-relative artifact."""

    code: str
    path: str
    message: str
    recoverable: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class VerificationReport:
    """Read-only verification result."""

    issues: tuple[VerificationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, object]:
        return {
            "issues": [issue.as_dict() for issue in self.issues],
            "ok": self.ok,
        }


@dataclass(frozen=True)
class OperationResult:
    """Result of a planned or applied mutation."""

    action: str
    mode: str
    changed: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "changed": list(self.changed),
            "mode": self.mode,
            "ok": True,
        }


@dataclass
class _WritePlan:
    root: Path
    action: str
    writes: dict[Path, bytes]
    expected: dict[Path, bytes | None]

    @property
    def changed(self) -> tuple[str, ...]:
        return tuple(
            sorted(path.relative_to(self.root).as_posix() for path in self.writes)
        )


def _validate_slug(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _SLUG_PATTERN.fullmatch(value):
        raise HarnessError(
            "INVALID_ID",
            f"{field} must be a lowercase portable slug",
        )
    if len(value) > 64:
        raise HarnessError("INVALID_ID", f"{field} exceeds 64 characters")
    return value


def _validate_text(
    value: str,
    *,
    field: str,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise HarnessError("INVALID_TEXT", f"{field} must be text")
    if value != unicodedata.normalize("NFC", value):
        raise HarnessError("INVALID_TEXT", f"{field} must use Unicode NFC")
    if value != value.strip():
        raise HarnessError(
            "INVALID_TEXT",
            f"{field} must not have surrounding whitespace",
        )
    if not value and not allow_empty:
        raise HarnessError("INVALID_TEXT", f"{field} must not be empty")
    if len(value) > maximum:
        raise HarnessError(
            "INVALID_TEXT",
            f"{field} exceeds {maximum} characters",
        )
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise HarnessError(
            "INVALID_TEXT",
            f"{field} must be a single printable line",
        )
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise HarnessError("INVALID_TEXT", f"{field} is not valid UTF-8") from error
    return value


def validate_relative_path(value: str, *, field: str) -> str:
    """Return a canonical portable POSIX relative path or raise."""

    if not isinstance(value, str) or not value:
        raise HarnessError("INVALID_PATH", f"{field} must be a relative path")
    if value != unicodedata.normalize("NFC", value):
        raise HarnessError("INVALID_PATH", f"{field} must use Unicode NFC")
    if value != value.strip():
        raise HarnessError(
            "INVALID_PATH",
            f"{field} must not have surrounding whitespace",
        )
    if "\\" in value:
        raise HarnessError(
            "INVALID_PATH",
            f"{field} must use portable forward separators",
        )
    try:
        windows_path = PureWindowsPath(value)
        portable_path = PurePosixPath(value)
    except (OSError, ValueError) as error:
        raise HarnessError("INVALID_PATH", f"{field} is malformed") from error
    if portable_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise HarnessError("INVALID_PATH", f"{field} must be relative")
    if not portable_path.parts or value != portable_path.as_posix():
        raise HarnessError("INVALID_PATH", f"{field} is not canonical")

    for component in portable_path.parts:
        if component in {".", ".."}:
            raise HarnessError("INVALID_PATH", f"{field} cannot traverse parents")
        if component.endswith((" ", ".")):
            raise HarnessError(
                "INVALID_PATH",
                f"{field} has a non-portable component ending",
            )
        if any(character in _FORBIDDEN_PATH_CHARACTERS for character in component):
            raise HarnessError(
                "INVALID_PATH",
                f"{field} contains a non-portable character",
            )
        if any(
            unicodedata.category(character).startswith("C")
            for character in component
        ):
            raise HarnessError(
                "INVALID_PATH",
                f"{field} contains a control character",
            )
        reserved_stem = component.split(".", 1)[0].upper()
        if reserved_stem in _WINDOWS_RESERVED:
            raise HarnessError(
                "INVALID_PATH",
                f"{field} contains a reserved portable name",
            )
    if len(value) > 500:
        raise HarnessError("INVALID_PATH", f"{field} is too long")
    return portable_path.as_posix()


def _is_link_like(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _path_is_link_like(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError as error:
        raise HarnessError("PATH_UNREADABLE", "path metadata is unreadable") from error
    return _is_link_like(metadata)


def _root_path(value: str | os.PathLike[str]) -> Path:
    requested = Path(value)
    lexical = requested if requested.is_absolute() else Path.cwd() / requested
    current = Path(lexical.anchor)
    try:
        metadata = current.lstat()
    except OSError as error:
        raise HarnessError("ROOT_MISSING", "coordinator root does not exist") from error
    if _is_link_like(metadata):
        raise HarnessError(
            "ROOT_SYMLINK",
            "coordinator root or any lexical component cannot be a symlink",
        )

    for component in lexical.parts[1:]:
        current = current.parent if component == ".." else current / component
        try:
            metadata = current.lstat()
        except OSError as error:
            raise HarnessError(
                "ROOT_MISSING",
                "coordinator root does not exist",
            ) from error
        if _is_link_like(metadata):
            raise HarnessError(
                "ROOT_SYMLINK",
                "coordinator root or any lexical component cannot be a symlink",
            )

    if not stat.S_ISDIR(metadata.st_mode):
        raise HarnessError("ROOT_TYPE", "coordinator root must be a directory")
    try:
        return current.resolve(strict=True)
    except OSError as error:
        raise HarnessError("ROOT_INVALID", "coordinator root is unreadable") from error


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "<outside-root>"


def _path_from_relative(root: Path, relative: str, *, field: str) -> Path:
    portable = validate_relative_path(relative, field=field)
    candidate = root.joinpath(*PurePosixPath(portable).parts)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise HarnessError("PATH_ESCAPE", f"{field} escapes the coordinator") from error
    return candidate


def _assert_no_symlink_components(
    root: Path,
    path: Path,
    *,
    include_target: bool = True,
) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise HarnessError("PATH_ESCAPE", "path escapes the coordinator") from error

    current = root
    parts = relative.parts if include_target else relative.parts[:-1]
    for component in parts:
        current = current / component
        try:
            metadata = current.lstat()
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as error:
            raise HarnessError(
                "PATH_UNREADABLE",
                f"path metadata is unreadable at {_relative(root, current)}",
            ) from error
        if _is_link_like(metadata):
            raise HarnessError(
                "SYMLINK",
                "symbolic link or link-like path is not allowed at "
                f"{_relative(root, current)}",
            )


def _resolve_child_directory(root: Path, relative: str) -> Path:
    candidate = _path_from_relative(root, relative, field="child path")
    reserved = CONTROL_DIRECTORY.name.casefold()
    if any(
        component.casefold() == reserved
        for component in candidate.relative_to(root).parts
    ):
        raise HarnessError(
            "INVALID_PATH",
            "child path cannot use a managed control directory",
        )
    _assert_no_symlink_components(root, candidate)
    if not candidate.exists():
        raise HarnessError("CHILD_MISSING", "registered child does not exist")
    if not candidate.is_dir():
        raise HarnessError("CHILD_TYPE", "registered child must be a directory")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise HarnessError("PATH_ESCAPE", "child resolves outside the coordinator") from error
    if resolved == root:
        raise HarnessError("INVALID_PATH", "child cannot be the coordinator root")
    control_root = root / CONTROL_DIRECTORY
    if control_root.exists() and _physical_paths_overlap(
        resolved,
        control_root,
        root,
    ):
        raise HarnessError(
            "INVALID_PATH",
            "child path cannot use a managed control directory",
        )
    return resolved


def _resolve_owner_file(child: Path, relative: str, coordinator: Path) -> Path:
    portable = validate_relative_path(relative, field="owner path")
    reserved = CONTROL_DIRECTORY.name.casefold()
    if any(
        component.casefold() == reserved
        for component in PurePosixPath(portable).parts
    ):
        raise HarnessError(
            "INVALID_PATH",
            "owner path cannot use a managed control directory",
        )
    candidate = child.joinpath(*PurePosixPath(portable).parts)
    _assert_no_symlink_components(coordinator, candidate)
    if not candidate.exists():
        raise HarnessError("OWNER_MISSING", "child owner file does not exist")
    if not candidate.is_file():
        raise HarnessError("OWNER_TYPE", "child owner must be a regular file")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(child)
        resolved.relative_to(coordinator)
    except (OSError, ValueError) as error:
        raise HarnessError("PATH_ESCAPE", "owner resolves outside its child") from error
    return resolved


def _read_bytes(
    path: Path,
    *,
    root: Path,
    maximum: int = MAX_MANAGED_BYTES,
) -> bytes:
    _assert_no_symlink_components(root, path)
    if not path.exists():
        raise HarnessError("FILE_MISSING", f"{_relative(root, path)} is missing")
    if not path.is_file():
        raise HarnessError(
            "FILE_TYPE",
            f"{_relative(root, path)} must be a regular file",
        )
    try:
        if path.stat().st_size > maximum:
            raise HarnessError(
                "FILE_TOO_LARGE",
                f"{_relative(root, path)} exceeds the size limit",
            )
        return path.read_bytes()
    except HarnessError:
        raise
    except OSError as error:
        raise HarnessError(
            "FILE_UNREADABLE",
            f"{_relative(root, path)} is unreadable",
        ) from error


def _decode_utf8(data: bytes, *, path: str) -> str:
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise HarnessError("INVALID_UTF8", f"{path} is not valid UTF-8") from error


def _read_utf8(
    path: Path,
    *,
    root: Path,
    maximum: int = MAX_MANAGED_BYTES,
) -> tuple[str, bytes]:
    data = _read_bytes(path, root=root, maximum=maximum)
    return _decode_utf8(data, path=_relative(root, path)), data


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    encoded = (text + "\n").encode("utf-8")
    if len(encoded) > MAX_MANAGED_BYTES:
        raise HarnessError("LIMIT", "managed JSON exceeds the size limit")
    return encoded


def _parse_json(data: bytes, *, path: str) -> Any:
    text = _decode_utf8(data, path=path)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, RecursionError) as error:
        raise HarnessError("INVALID_JSON", f"{path} is not valid JSON") from error


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    artifact: str,
) -> None:
    if set(value) != expected:
        raise HarnessError(
            "INVALID_SCHEMA",
            f"{artifact} has unsupported or missing fields",
        )


def _normalize_child(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise HarnessError("INVALID_SCHEMA", "child entry must be an object")
    _require_exact_keys(
        value,
        {"id", "owner", "path"},
        artifact="child entry",
    )
    child_id = _validate_slug(value.get("id"), field="child id")
    child_path = validate_relative_path(value.get("path"), field="child path")
    owner = validate_relative_path(value.get("owner"), field="owner path")
    return {"id": child_id, "owner": owner, "path": child_path}


def _normalize_delta(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise HarnessError("INVALID_SCHEMA", "shared delta must be an object")
    _require_exact_keys(
        value,
        {"child", "key", "summary"},
        artifact="shared delta",
    )
    return {
        "child": _validate_slug(value.get("child"), field="delta child"),
        "key": _validate_slug(value.get("key"), field="delta key"),
        "summary": _validate_text(
            value.get("summary"),
            field="shared summary",
            maximum=MAX_SHARED_TEXT,
        ),
    }


def _paths_overlap(first: str, second: str) -> bool:
    first_parts = tuple(
        component.casefold() for component in PurePosixPath(first).parts
    )
    second_parts = tuple(
        component.casefold() for component in PurePosixPath(second).parts
    )
    shorter = min(len(first_parts), len(second_parts))
    return first_parts[:shorter] == second_parts[:shorter]


def _same_physical_path(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError as error:
        raise HarnessError(
            "CHILD_UNREADABLE",
            "physical path identity could not be compared safely",
        ) from error


def _physical_ancestor(
    ancestor: Path,
    descendant: Path,
    root: Path,
) -> bool:
    current = descendant
    while True:
        if _same_physical_path(ancestor, current):
            return True
        if _same_physical_path(current, root):
            return False
        parent = current.parent
        if parent == current:
            raise HarnessError(
                "PATH_ESCAPE",
                "physical path ancestry escaped the coordinator",
            )
        current = parent


def _physical_paths_overlap(first: Path, second: Path, root: Path) -> bool:
    return _physical_ancestor(first, second, root) or _physical_ancestor(
        second,
        first,
        root,
    )


def _normalize_workspace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessError("INVALID_SCHEMA", "workspace manifest must be an object")
    _require_exact_keys(
        value,
        {"children", "schemaVersion", "sharedDeltas", "tool"},
        artifact="workspace manifest",
    )
    schema_version = value.get("schemaVersion")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        raise HarnessError("INVALID_SCHEMA", "unsupported workspace schema version")
    if value.get("tool") != TOOL_ID:
        raise HarnessError("INVALID_SCHEMA", "workspace tool identity is invalid")
    if not isinstance(value.get("children"), list):
        raise HarnessError("INVALID_SCHEMA", "children must be a list")
    if not isinstance(value.get("sharedDeltas"), list):
        raise HarnessError("INVALID_SCHEMA", "sharedDeltas must be a list")
    if len(value["children"]) > MAX_CHILDREN:
        raise HarnessError("LIMIT", "workspace contains too many children")
    if len(value["sharedDeltas"]) > MAX_DELTAS:
        raise HarnessError("LIMIT", "workspace contains too many shared deltas")

    children = sorted(
        (_normalize_child(child) for child in value["children"]),
        key=lambda child: child["id"],
    )
    child_ids = [child["id"] for child in children]
    if len(child_ids) != len(set(child_ids)):
        raise HarnessError("COLLISION", "child ids must be unique")
    for index, child in enumerate(children):
        for other in children[index + 1 :]:
            if _paths_overlap(child["path"], other["path"]):
                raise HarnessError(
                    "COLLISION",
                    "registered child paths must not overlap",
                )

    deltas = [
        _normalize_delta(delta) for delta in value["sharedDeltas"]
    ]
    delta_keys = [delta["key"] for delta in deltas]
    if len(delta_keys) != len(set(delta_keys)):
        raise HarnessError("COLLISION", "shared delta keys must be unique")
    return {
        "children": children,
        "schemaVersion": SCHEMA_VERSION,
        "sharedDeltas": deltas,
        "tool": TOOL_ID,
    }


def _normalize_record(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise HarnessError("INVALID_SCHEMA", "local record must be an object")
    _require_exact_keys(
        value,
        {"key", "kind", "next", "summary"},
        artifact="local record",
    )
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in _RECORD_KINDS:
        raise HarnessError("INVALID_SCHEMA", "local record kind is unsupported")
    next_text = _validate_text(
        value.get("next"),
        field="next action",
        maximum=MAX_LOCAL_TEXT,
        allow_empty=True,
    )
    if kind == "close" and not next_text:
        raise HarnessError(
            "INVALID_TEXT",
            "a close record requires a next action",
        )
    return {
        "key": _validate_slug(value.get("key"), field="record key"),
        "kind": kind,
        "next": next_text,
        "summary": _validate_text(
            value.get("summary"),
            field="local summary",
            maximum=MAX_LOCAL_TEXT,
        ),
    }


def _normalize_local_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessError("INVALID_SCHEMA", "local state must be an object")
    _require_exact_keys(
        value,
        {"childId", "records", "schemaVersion", "tool"},
        artifact="local state",
    )
    schema_version = value.get("schemaVersion")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        raise HarnessError("INVALID_SCHEMA", "unsupported local state schema version")
    if value.get("tool") != TOOL_ID:
        raise HarnessError("INVALID_SCHEMA", "local state tool identity is invalid")
    if not isinstance(value.get("records"), list):
        raise HarnessError("INVALID_SCHEMA", "local records must be a list")
    if len(value["records"]) > MAX_RECORDS:
        raise HarnessError("LIMIT", "local state contains too many records")
    records = [_normalize_record(record) for record in value["records"]]
    keys = [record["key"] for record in records]
    if len(keys) != len(set(keys)):
        raise HarnessError("COLLISION", "local record keys must be unique")
    return {
        "childId": _validate_slug(value.get("childId"), field="state child id"),
        "records": records,
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_ID,
    }


def _empty_workspace() -> dict[str, Any]:
    return {
        "children": [],
        "schemaVersion": SCHEMA_VERSION,
        "sharedDeltas": [],
        "tool": TOOL_ID,
    }


def _empty_local_state(child_id: str) -> dict[str, Any]:
    return {
        "childId": child_id,
        "records": [],
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_ID,
    }


def _managed_header() -> str:
    return "<!-- workspace-coordination:managed schema=1 -->\n"


def _render_entrypoint() -> bytes:
    text = (
        _managed_header()
        + "# Workspace coordination\n\n"
        + "This folder coordinates autonomous child folders without absorbing "
        + "their execution state.\n\n"
        + "Read `.workspace-coordination/INDEX.md`, then choose one child and "
        + "read its declared owner file. Keep detailed work and continuity in "
        + "that child. Reflect only a concise boundary or shared-decision delta "
        + "back to this coordinator.\n\n"
        + "Run the package CLI with an explicit coordinator root. Mutating "
        + "commands require either `--dry-run` or `--apply`.\n"
    )
    return text.encode("utf-8")


def _render_boundaries() -> bytes:
    text = (
        _managed_header()
        + "# Boundaries\n\n"
        + "- The coordinator owns the child index and concise shared deltas.\n"
        + "- Each child owns its local instructions, dense context, execution, "
        + "and next action.\n"
        + "- Registration reads only the explicitly declared child and owner "
        + "paths; it does not discover directories.\n"
        + "- Reflection accepts explicit concise text; it never copies child "
        + "state automatically.\n"
        + "- Removing a registration never deletes or edits the child.\n"
    )
    return text.encode("utf-8")


def _markdown_code(value: str) -> str:
    longest = 0
    current = 0
    for character in value:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    delimiter = "`" * (longest + 1)
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{delimiter}{padding}{value}{padding}{delimiter}"


def _render_index(workspace: Mapping[str, Any]) -> bytes:
    lines = [
        _managed_header().rstrip("\n"),
        "# Children",
        "",
        "Choose a child, then read its local owner before doing work.",
        "",
    ]
    children = workspace["children"]
    if not children:
        lines.append("No children are registered.")
    else:
        lines.extend(
            [
                "| ID | Relative path | Local owner |",
                "| --- | --- | --- |",
            ]
        )
        for child in children:
            lines.append(
                f"| {_markdown_code(child['id'])} "
                f"| {_markdown_code(child['path'])} "
                f"| {_markdown_code(child['owner'])} |"
            )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_shared(workspace: Mapping[str, Any]) -> bytes:
    lines = [
        _managed_header().rstrip("\n"),
        "# Shared deltas",
        "",
        "Only concise cross-child boundaries and shared decisions belong here.",
        "",
    ]
    deltas = workspace["sharedDeltas"]
    if not deltas:
        lines.append("No shared deltas are recorded.")
    else:
        for delta in deltas:
            lines.extend(
                [
                    f"## {delta['key']}",
                    "",
                    f"- Child: {_markdown_code(delta['child'])}",
                    f"- Delta: {delta['summary']}",
                    "",
                ]
            )
        if lines[-1] == "":
            lines.pop()
    return ("\n".join(lines) + "\n").encode("utf-8")


def _derived_files(workspace: Mapping[str, Any]) -> dict[Path, bytes]:
    return {
        ENTRYPOINT_PATH: _render_entrypoint(),
        INDEX_PATH: _render_index(workspace),
        BOUNDARIES_PATH: _render_boundaries(),
        SHARED_PATH: _render_shared(workspace),
    }


def _load_workspace(
    root: Path,
    *,
    require_canonical: bool,
) -> tuple[dict[str, Any], bytes]:
    manifest = root / MANIFEST_PATH
    if not manifest.exists() and not _path_is_link_like(manifest):
        raise HarnessError("NOT_INITIALIZED", "coordinator is not initialized")
    raw = _read_bytes(manifest, root=root)
    value = _parse_json(raw, path=MANIFEST_PATH.as_posix())
    normalized = _normalize_workspace(value)
    if require_canonical and raw != _json_bytes(normalized):
        raise HarnessError(
            "MANIFEST_DRIFT",
            "workspace manifest is not canonical; run recover",
        )
    return normalized, raw


def _read_expected_derived(
    root: Path,
    workspace: Mapping[str, Any],
) -> dict[Path, bytes]:
    observed: dict[Path, bytes] = {}
    for relative, expected in _derived_files(workspace).items():
        target = root / relative
        raw = _read_bytes(target, root=root)
        if raw != expected:
            raise HarnessError(
                "DERIVED_DRIFT",
                f"{relative.as_posix()} differs from generated state; run recover",
            )
        observed[target] = raw
    return observed


def _operable_workspace(root: Path) -> tuple[dict[str, Any], bytes, dict[Path, bytes]]:
    workspace, manifest_raw = _load_workspace(root, require_canonical=True)
    derived_raw = _read_expected_derived(root, workspace)
    return workspace, manifest_raw, derived_raw


def _child_by_id(workspace: Mapping[str, Any], child_id: str) -> dict[str, str]:
    validated = _validate_slug(child_id, field="child id")
    for child in workspace["children"]:
        if child["id"] == validated:
            return child
    raise HarnessError("CHILD_UNKNOWN", "child id is not registered")


def _load_owner(
    root: Path,
    child: Mapping[str, str],
) -> tuple[Path, str]:
    child_root = _resolve_child_directory(root, child["path"])
    owner_path = _resolve_owner_file(child_root, child["owner"], root)
    owner_text, _raw = _read_utf8(
        owner_path,
        root=root,
        maximum=MAX_OWNER_BYTES,
    )
    return child_root, owner_text


def _local_state_file(child_root: Path) -> Path:
    return child_root / LOCAL_STATE_PATH


def _load_local_state(
    root: Path,
    child_root: Path,
    child_id: str,
    *,
    require_canonical: bool,
) -> tuple[dict[str, Any], bytes | None]:
    state_path = _local_state_file(child_root)
    if not state_path.exists() and not _path_is_link_like(state_path):
        return _empty_local_state(child_id), None
    raw = _read_bytes(state_path, root=root)
    value = _parse_json(raw, path=_relative(root, state_path))
    normalized = _normalize_local_state(value)
    if normalized["childId"] != child_id:
        raise HarnessError(
            "STATE_MISMATCH",
            "local state belongs to a different child id",
        )
    if require_canonical and raw != _json_bytes(normalized):
        raise HarnessError(
            "LOCAL_STATE_DRIFT",
            "local state is not canonical; run recover",
        )
    return normalized, raw


def _inspect_target(
    root: Path,
    target: Path,
    expected: bytes | None,
) -> None:
    try:
        target.relative_to(root)
    except ValueError as error:
        raise HarnessError("PATH_ESCAPE", "write target escapes coordinator") from error
    _assert_no_symlink_components(root, target, include_target=False)
    current = root
    for component in target.parent.relative_to(root).parts:
        current = current / component
        if current.exists() and not current.is_dir():
            raise HarnessError(
                "COLLISION",
                f"{_relative(root, current)} is not a directory",
            )
    if _path_is_link_like(target):
        raise HarnessError(
            "SYMLINK",
            "symbolic link or link-like path is not allowed at "
            f"{_relative(root, target)}",
        )
    if target.exists():
        if not target.is_file():
            raise HarnessError(
                "COLLISION",
                f"{_relative(root, target)} is not a managed regular file",
            )
        observed = _read_bytes(target, root=root)
        if expected is None:
            raise HarnessError(
                "COLLISION",
                f"{_relative(root, target)} already exists",
            )
        if observed != expected:
            raise HarnessError(
                "CONCURRENT_CHANGE",
                f"{_relative(root, target)} changed before commit",
            )
    elif expected is not None:
        raise HarnessError(
            "CONCURRENT_CHANGE",
            f"{_relative(root, target)} disappeared before commit",
        )


def _preflight(plan: _WritePlan) -> None:
    if set(plan.writes) != set(plan.expected):
        raise HarnessError("INTERNAL", "write plan is incomplete")
    for target in sorted(plan.writes):
        _inspect_target(plan.root, target, plan.expected[target])


def _create_missing_parents(root: Path, target: Path) -> list[Path]:
    missing: list[Path] = []
    current = target.parent
    while (
        current != root
        and not current.exists()
        and not _path_is_link_like(current)
    ):
        missing.append(current)
        current = current.parent
    if _path_is_link_like(current):
        raise HarnessError(
            "SYMLINK",
            "write parent cannot be a symbolic link or link-like path",
        )
    if not current.is_dir():
        raise HarnessError("COLLISION", "write parent is not a directory")

    created: list[Path] = []
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if _path_is_link_like(directory) or not directory.is_dir():
                raise HarnessError(
                    "COLLISION",
                    "write parent changed during commit",
                )
        except OSError as error:
            raise HarnessError(
                "WRITE_FAILED",
                "could not create a managed directory",
            ) from error
        else:
            created.append(directory)
    _assert_no_symlink_components(root, target, include_target=False)
    return created


def _stage_bytes(parent: Path, data: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".workspace-coordination-",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return temporary


def _restore_bytes(target: Path, data: bytes) -> None:
    temporary = _stage_bytes(target.parent, data)
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _commit_writes(
    plan: _WritePlan,
    *,
    replace: Callable[[os.PathLike[str], os.PathLike[str]], None] | None = None,
) -> None:
    """Commit a write set with preflight, atomic file moves, and rollback."""

    _preflight(plan)
    replace_file = os.replace if replace is None else replace
    created_directories: list[Path] = []
    staged: dict[Path, Path] = {}
    committed: list[Path] = []
    rollback_errors: list[BaseException] = []

    try:
        for target in sorted(plan.writes):
            created_directories.extend(
                _create_missing_parents(plan.root, target)
            )
            staged[target] = _stage_bytes(target.parent, plan.writes[target])

        _preflight(plan)
        for target in sorted(plan.writes):
            temporary = staged[target]
            replace_file(temporary, target)
            committed.append(target)
    except BaseException as error:
        for target in reversed(committed):
            previous = plan.expected[target]
            try:
                if previous is None:
                    if target.exists() or _path_is_link_like(target):
                        target.unlink()
                else:
                    _restore_bytes(target, previous)
            except BaseException as rollback_error:
                rollback_errors.append(rollback_error)
        if rollback_errors:
            raise HarnessError(
                "RECOVERY_REQUIRED",
                "write failed and rollback was incomplete; run verify",
            ) from error
        raise HarnessError(
            "WRITE_ROLLED_BACK",
            "write failed and all committed changes were rolled back",
        ) from error
    finally:
        for temporary in staged.values():
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
        for directory in sorted(
            set(created_directories),
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass


def _run_plan(plan: _WritePlan, *, apply: bool) -> OperationResult:
    _preflight(plan)
    if not plan.writes:
        return OperationResult(plan.action, "noop", ())
    if not apply:
        return OperationResult(plan.action, "dry-run", plan.changed)
    _commit_writes(plan)
    return OperationResult(plan.action, "applied", plan.changed)


def initialize(
    root_value: str | os.PathLike[str],
    *,
    apply: bool,
) -> OperationResult:
    """Plan or initialize an empty coordinator without overwriting files."""

    root = _root_path(root_value)
    manifest = root / MANIFEST_PATH
    if manifest.exists() or _path_is_link_like(manifest):
        report = verify(root)
        if report.ok or all(
            issue.code == "NO_REGISTERED_CHILDREN"
            for issue in report.issues
        ):
            return OperationResult("init", "noop", ())
        raise HarnessError(
            "NEEDS_RECOVERY",
            "coordinator exists but verification failed; run verify and recover",
        )

    workspace = _empty_workspace()
    relative_writes = {
        MANIFEST_PATH: _json_bytes(workspace),
        **_derived_files(workspace),
    }
    plan = _WritePlan(
        root=root,
        action="init",
        writes={root / path: data for path, data in relative_writes.items()},
        expected={root / path: None for path in relative_writes},
    )
    return _run_plan(plan, apply=apply)


def add_child(
    root_value: str | os.PathLike[str],
    *,
    child_id: str,
    child_path: str,
    owner: str,
    apply: bool,
) -> OperationResult:
    """Register one explicit child and its explicit local owner file."""

    root = _root_path(root_value)
    workspace, manifest_raw, derived_raw = _operable_workspace(root)
    candidate = _normalize_child(
        {"id": child_id, "owner": owner, "path": child_path}
    )
    child_root = _resolve_child_directory(root, candidate["path"])
    owner_path = _resolve_owner_file(child_root, candidate["owner"], root)
    _read_utf8(owner_path, root=root, maximum=MAX_OWNER_BYTES)
    _load_local_state(
        root,
        child_root,
        candidate["id"],
        require_canonical=True,
    )

    for existing in workspace["children"]:
        if existing["id"] == candidate["id"]:
            if existing == candidate:
                return OperationResult("add", "noop", ())
            raise HarnessError("COLLISION", "child id is already registered")
        if _paths_overlap(existing["path"], candidate["path"]):
            raise HarnessError("COLLISION", "registered child paths must not overlap")
        existing_root = _resolve_child_directory(root, existing["path"])
        if _physical_paths_overlap(existing_root, child_root, root):
            raise HarnessError(
                "COLLISION",
                "registered child roots must not overlap physically",
            )

    updated = _normalize_workspace(
        {
            **workspace,
            "children": [*workspace["children"], candidate],
        }
    )
    manifest_target = root / MANIFEST_PATH
    index_target = root / INDEX_PATH
    plan = _WritePlan(
        root=root,
        action="add",
        writes={
            manifest_target: _json_bytes(updated),
            index_target: _render_index(updated),
        },
        expected={
            manifest_target: manifest_raw,
            index_target: derived_raw[index_target],
        },
    )
    return _run_plan(plan, apply=apply)


def remove_child(
    root_value: str | os.PathLike[str],
    *,
    child_id: str,
    apply: bool,
) -> OperationResult:
    """Remove only a registration; never remove or edit the child itself."""

    root = _root_path(root_value)
    workspace, manifest_raw, derived_raw = _operable_workspace(root)
    validated_id = _validate_slug(child_id, field="child id")
    retained = [
        child for child in workspace["children"] if child["id"] != validated_id
    ]
    if len(retained) == len(workspace["children"]):
        return OperationResult("remove", "noop", ())
    updated = _normalize_workspace({**workspace, "children": retained})
    manifest_target = root / MANIFEST_PATH
    index_target = root / INDEX_PATH
    plan = _WritePlan(
        root=root,
        action="remove",
        writes={
            manifest_target: _json_bytes(updated),
            index_target: _render_index(updated),
        },
        expected={
            manifest_target: manifest_raw,
            index_target: derived_raw[index_target],
        },
    )
    return _run_plan(plan, apply=apply)


def open_workspace(
    root_value: str | os.PathLike[str],
    *,
    child_id: str | None = None,
) -> dict[str, Any]:
    """Open coordinator context or one child owner plus latest continuity."""

    root = _root_path(root_value)
    workspace, _manifest_raw, _derived_raw = _operable_workspace(root)
    if child_id is None:
        return {
            "children": workspace["children"],
            "sharedDeltas": workspace["sharedDeltas"],
            "type": "coordinator",
        }

    child = _child_by_id(workspace, child_id)
    child_root, owner_text = _load_owner(root, child)
    local_state, _state_raw = _load_local_state(
        root,
        child_root,
        child["id"],
        require_canonical=True,
    )
    records = local_state["records"]
    return {
        "child": child,
        "continuity": records[-1] if records else None,
        "ownerText": owner_text,
        "type": "child",
    }


def digest_child(
    root_value: str | os.PathLike[str],
    *,
    child_id: str,
) -> dict[str, Any]:
    """Read only the declared owner, managed local state, and shared deltas."""

    root = _root_path(root_value)
    workspace, _manifest_raw, _derived_raw = _operable_workspace(root)
    child = _child_by_id(workspace, child_id)
    child_root, owner_text = _load_owner(root, child)
    local_state, _state_raw = _load_local_state(
        root,
        child_root,
        child["id"],
        require_canonical=True,
    )
    return {
        "child": child,
        "localState": local_state,
        "ownerText": owner_text,
        "sharedDeltas": workspace["sharedDeltas"],
        "type": "digest",
    }


def record_local(
    root_value: str | os.PathLike[str],
    *,
    child_id: str,
    key: str,
    kind: str,
    summary: str,
    next_action: str,
    apply: bool,
) -> OperationResult:
    """Append an idempotent child-local record under the registered child."""

    root = _root_path(root_value)
    workspace, _manifest_raw, _derived_raw = _operable_workspace(root)
    child = _child_by_id(workspace, child_id)
    child_root, _owner_text = _load_owner(root, child)
    state, state_raw = _load_local_state(
        root,
        child_root,
        child["id"],
        require_canonical=True,
    )
    record = _normalize_record(
        {
            "key": key,
            "kind": kind,
            "next": next_action,
            "summary": summary,
        }
    )
    for existing in state["records"]:
        if existing["key"] == record["key"]:
            if existing == record:
                return OperationResult("record", "noop", ())
            raise HarnessError("COLLISION", "local record key is already used")
    if len(state["records"]) >= MAX_RECORDS:
        raise HarnessError("LIMIT", "local state record limit reached")

    updated = _normalize_local_state(
        {**state, "records": [*state["records"], record]}
    )
    target = _local_state_file(child_root)
    plan = _WritePlan(
        root=root,
        action="record",
        writes={target: _json_bytes(updated)},
        expected={target: state_raw},
    )
    return _run_plan(plan, apply=apply)


def reflect_delta(
    root_value: str | os.PathLike[str],
    *,
    child_id: str,
    key: str,
    summary: str,
    apply: bool,
) -> OperationResult:
    """Reflect one explicit concise delta without reading dense child state."""

    root = _root_path(root_value)
    workspace, manifest_raw, derived_raw = _operable_workspace(root)
    child = _child_by_id(workspace, child_id)
    _load_owner(root, child)
    delta = _normalize_delta(
        {"child": child["id"], "key": key, "summary": summary}
    )
    for existing in workspace["sharedDeltas"]:
        if existing["key"] == delta["key"]:
            if existing == delta:
                return OperationResult("reflect", "noop", ())
            raise HarnessError("COLLISION", "shared delta key is already used")
    if len(workspace["sharedDeltas"]) >= MAX_DELTAS:
        raise HarnessError("LIMIT", "shared delta limit reached")

    updated = _normalize_workspace(
        {
            **workspace,
            "sharedDeltas": [*workspace["sharedDeltas"], delta],
        }
    )
    manifest_target = root / MANIFEST_PATH
    shared_target = root / SHARED_PATH
    plan = _WritePlan(
        root=root,
        action="reflect",
        writes={
            manifest_target: _json_bytes(updated),
            shared_target: _render_shared(updated),
        },
        expected={
            manifest_target: manifest_raw,
            shared_target: derived_raw[shared_target],
        },
    )
    return _run_plan(plan, apply=apply)


def _verification_issue_from_error(
    error: HarnessError,
    *,
    path: str,
    recoverable: bool = False,
) -> VerificationIssue:
    return VerificationIssue(
        code=error.code,
        message=error.message,
        path=path,
        recoverable=recoverable,
    )


def verify(root_value: str | os.PathLike[str]) -> VerificationReport:
    """Verify coordinator sources, generated views, child boundaries, and state."""

    try:
        root = _root_path(root_value)
    except HarnessError as error:
        return VerificationReport(
            (_verification_issue_from_error(error, path="."),)
        )

    issues: list[VerificationIssue] = []
    try:
        workspace, manifest_raw = _load_workspace(root, require_canonical=False)
    except HarnessError as error:
        return VerificationReport(
            (
                _verification_issue_from_error(
                    error,
                    path=MANIFEST_PATH.as_posix(),
                ),
            )
        )

    canonical_manifest = _json_bytes(workspace)
    if manifest_raw != canonical_manifest:
        issues.append(
            VerificationIssue(
                "MANIFEST_DRIFT",
                MANIFEST_PATH.as_posix(),
                "manifest is valid but not canonical",
                True,
            )
        )

    if not workspace["children"]:
        issues.append(
            VerificationIssue(
                code="NO_REGISTERED_CHILDREN",
                path=MANIFEST_PATH.as_posix(),
                message="coordinator has no registered children",
                recoverable=False,
            )
        )

    for relative, expected in _derived_files(workspace).items():
        target = root / relative
        try:
            observed = _read_bytes(target, root=root)
        except HarnessError as error:
            issues.append(
                _verification_issue_from_error(
                    error,
                    path=relative.as_posix(),
                    recoverable=error.code in {"FILE_MISSING"},
                )
            )
            continue
        if observed != expected:
            issues.append(
                VerificationIssue(
                    "DERIVED_DRIFT",
                    relative.as_posix(),
                    "generated artifact differs from the manifest",
                    True,
                )
            )

    observed_child_roots: list[tuple[str, Path]] = []
    for child in workspace["children"]:
        child_path = child["path"]
        try:
            child_root = _resolve_child_directory(root, child_path)
            owner_path = _resolve_owner_file(child_root, child["owner"], root)
            _read_utf8(owner_path, root=root, maximum=MAX_OWNER_BYTES)
        except HarnessError as error:
            issues.append(
                _verification_issue_from_error(
                    error,
                    path=child_path,
                )
            )
            continue

        duplicate_root = False
        for _observed_id, observed_root in observed_child_roots:
            try:
                if _physical_paths_overlap(observed_root, child_root, root):
                    duplicate_root = True
                    break
            except HarnessError:
                duplicate_root = True
                break
        if duplicate_root:
            issues.append(
                VerificationIssue(
                    "COLLISION",
                    child_path,
                    "registered child roots overlap physically",
                )
            )
            continue
        observed_child_roots.append((child["id"], child_root))

        state_path = _local_state_file(child_root)
        if not state_path.exists() and not _path_is_link_like(state_path):
            continue
        try:
            state, state_raw = _load_local_state(
                root,
                child_root,
                child["id"],
                require_canonical=False,
            )
        except HarnessError as error:
            issues.append(
                _verification_issue_from_error(
                    error,
                    path=_relative(root, state_path),
                )
            )
            continue
        if state_raw != _json_bytes(state):
            issues.append(
                VerificationIssue(
                    "LOCAL_STATE_DRIFT",
                    _relative(root, state_path),
                    "local state is valid but not canonical",
                    True,
                )
            )

    return VerificationReport(
        tuple(sorted(set(issues), key=lambda issue: (issue.path, issue.code)))
    )


def recover(
    root_value: str | os.PathLike[str],
    *,
    apply: bool,
) -> OperationResult:
    """Regenerate recoverable managed views from validated source data."""

    root = _root_path(root_value)
    workspace, manifest_raw = _load_workspace(root, require_canonical=False)
    writes: dict[Path, bytes] = {}
    expected: dict[Path, bytes | None] = {}

    manifest_target = root / MANIFEST_PATH
    canonical_manifest = _json_bytes(workspace)
    if manifest_raw != canonical_manifest:
        writes[manifest_target] = canonical_manifest
        expected[manifest_target] = manifest_raw

    for relative, desired in _derived_files(workspace).items():
        target = root / relative
        if _path_is_link_like(target):
            raise HarnessError(
                "SYMLINK",
                "symbolic link or link-like path is not allowed at "
                f"{relative.as_posix()}",
            )
        if target.exists():
            if not target.is_file():
                raise HarnessError(
                    "COLLISION",
                    f"{relative.as_posix()} is not a regular file",
                )
            observed = _read_bytes(target, root=root)
        else:
            observed = None
        if observed != desired:
            writes[target] = desired
            expected[target] = observed

    for child in workspace["children"]:
        child_root = _resolve_child_directory(root, child["path"])
        state_path = _local_state_file(child_root)
        if not state_path.exists() and not _path_is_link_like(state_path):
            continue
        state, state_raw = _load_local_state(
            root,
            child_root,
            child["id"],
            require_canonical=False,
        )
        canonical_state = _json_bytes(state)
        if state_raw != canonical_state:
            writes[state_path] = canonical_state
            expected[state_path] = state_raw

    plan = _WritePlan(
        root=root,
        action="recover",
        writes=writes,
        expected=expected,
    )
    return _run_plan(plan, apply=apply)


def _mutation_mode(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the write set without writing",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="apply the validated write set",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coordinate explicit autonomous child folders safely."
    )
    parser.add_argument(
        "--root",
        required=True,
        help="explicit coordinator root; it must already exist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="initialize a coordinator")
    _mutation_mode(init_parser)

    add_parser = commands.add_parser("add", help="register one explicit child")
    add_parser.add_argument("--id", required=True, dest="child_id")
    add_parser.add_argument("--path", required=True, dest="child_path")
    add_parser.add_argument(
        "--owner",
        required=True,
        help="owner-file path relative to the selected child root",
    )
    _mutation_mode(add_parser)

    remove_parser = commands.add_parser(
        "remove",
        help="remove only a child registration",
    )
    remove_parser.add_argument("--id", required=True, dest="child_id")
    _mutation_mode(remove_parser)

    open_parser = commands.add_parser(
        "open",
        help="open coordinator context or one child",
    )
    open_parser.add_argument("--child", dest="child_id")

    digest_parser = commands.add_parser(
        "digest",
        help="read the bounded context for one child",
    )
    digest_parser.add_argument("--child", required=True, dest="child_id")

    record_parser = commands.add_parser(
        "record",
        help="append one child-local continuity record",
    )
    record_parser.add_argument("--child", required=True, dest="child_id")
    record_parser.add_argument("--key", required=True)
    record_parser.add_argument(
        "--kind",
        choices=sorted(_RECORD_KINDS),
        default="update",
    )
    record_parser.add_argument("--summary", required=True)
    record_parser.add_argument("--next", dest="next_action", default="")
    _mutation_mode(record_parser)

    reflect_parser = commands.add_parser(
        "reflect",
        help="reflect one concise shared delta",
    )
    reflect_parser.add_argument("--child", required=True, dest="child_id")
    reflect_parser.add_argument("--key", required=True)
    reflect_parser.add_argument("--summary", required=True)
    _mutation_mode(reflect_parser)

    commands.add_parser("verify", help="verify sources and generated state")

    recover_parser = commands.add_parser(
        "recover",
        help="regenerate recoverable managed state",
    )
    _mutation_mode(recover_parser)
    return parser


def _print_result(result: OperationResult, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
        return
    print(f"{result.mode.upper()}: {result.action}")
    for changed in result.changed:
        print(f"- {changed}")


def _print_verification(
    report: VerificationReport,
    *,
    as_json: bool,
) -> None:
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
        return
    if report.ok:
        print("PASS: coordinator verified")
        return
    print(f"FAIL: {len(report.issues)} verification issue(s)")
    for issue in report.issues:
        suffix = " [recoverable]" if issue.recoverable else ""
        print(f"- {issue.code} {issue.path}: {issue.message}{suffix}")


def _print_opened(value: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
        return
    value_type = value["type"]
    if value_type == "coordinator":
        print("Coordinator")
        children = value["children"]
        if not children:
            print("- no registered children")
        for child in children:
            print(
                f"- {child['id']}: {child['path']} "
                f"(owner: {child['owner']})"
            )
        print(f"Shared deltas: {len(value['sharedDeltas'])}")
        return

    child = value["child"]
    heading = "Digest" if value_type == "digest" else "Child"
    print(f"{heading}: {child['id']}")
    print(f"Path: {child['path']}")
    print(f"Owner: {child['owner']}")
    print("--- local owner ---")
    print(value["ownerText"], end="" if value["ownerText"].endswith("\n") else "\n")
    if value_type == "digest":
        state = value["localState"]
        print(f"Local records: {len(state['records'])}")
        if state["records"]:
            latest = state["records"][-1]
            print(f"Latest: {latest['key']} ({latest['kind']})")
            print(f"Summary: {latest['summary']}")
            if latest["next"]:
                print(f"Next: {latest['next']}")
        print(f"Shared deltas: {len(value['sharedDeltas'])}")
    else:
        continuity = value["continuity"]
        if continuity is None:
            print("Continuity: none")
        else:
            print(
                f"Continuity: {continuity['key']} "
                f"({continuity['kind']})"
            )
            print(f"Summary: {continuity['summary']}")
            if continuity["next"]:
                print(f"Next: {continuity['next']}")


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            result = initialize(arguments.root, apply=arguments.apply)
            _print_result(result, as_json=arguments.json)
            return 0
        if arguments.command == "add":
            result = add_child(
                arguments.root,
                child_id=arguments.child_id,
                child_path=arguments.child_path,
                owner=arguments.owner,
                apply=arguments.apply,
            )
            _print_result(result, as_json=arguments.json)
            return 0
        if arguments.command == "remove":
            result = remove_child(
                arguments.root,
                child_id=arguments.child_id,
                apply=arguments.apply,
            )
            _print_result(result, as_json=arguments.json)
            return 0
        if arguments.command == "open":
            opened = open_workspace(
                arguments.root,
                child_id=arguments.child_id,
            )
            _print_opened(opened, as_json=arguments.json)
            return 0
        if arguments.command == "digest":
            digested = digest_child(
                arguments.root,
                child_id=arguments.child_id,
            )
            _print_opened(digested, as_json=arguments.json)
            return 0
        if arguments.command == "record":
            result = record_local(
                arguments.root,
                child_id=arguments.child_id,
                key=arguments.key,
                kind=arguments.kind,
                summary=arguments.summary,
                next_action=arguments.next_action,
                apply=arguments.apply,
            )
            _print_result(result, as_json=arguments.json)
            return 0
        if arguments.command == "reflect":
            result = reflect_delta(
                arguments.root,
                child_id=arguments.child_id,
                key=arguments.key,
                summary=arguments.summary,
                apply=arguments.apply,
            )
            _print_result(result, as_json=arguments.json)
            return 0
        if arguments.command == "verify":
            report = verify(arguments.root)
            _print_verification(report, as_json=arguments.json)
            return 0 if report.ok else 1
        if arguments.command == "recover":
            result = recover(arguments.root, apply=arguments.apply)
            _print_result(result, as_json=arguments.json)
            return 0
    except HarnessError as error:
        if arguments.json:
            print(
                json.dumps(
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                        },
                        "ok": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"ERROR {error.code}: {error.message}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable command")


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
