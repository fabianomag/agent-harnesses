"""Portable locking, durable journaling, rollback, and recovery."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from .errors import (
    LockBusyError,
    RecoveryError,
    RecoveryRequiredError,
    TransactionError,
    ValidationError,
)
from .model import (
    dumps_canonical_json,
    loads_strict_json,
    validate_relative_path,
    validate_transaction_id,
)
from .paths import MAX_STATE_BYTES, canonical_root, is_link_like, safe_path


JOURNAL_RELATIVE = ".orchestration-journal.json"
JOURNAL_SCHEMA_VERSION = 1
JOURNAL_PHASES = frozenset(("preparing", "prepared", "applying", "committed"))
FaultHook = Callable[[str, str, int], None]
Builder = Callable[[str], tuple[Mapping[str, str | bytes], Any]]

_DIGEST_PATTERN = __import__("re").compile(r"^[0-9a-f]{64}$")
_JOURNAL_KEYS = frozenset(
    (
        "schemaVersion",
        "txid",
        "phase",
        "files",
        "createdDirs",
        "directoryMetadata",
    )
)
_RECORD_KEYS = frozenset(
    (
        "atimeNs",
        "path",
        "existed",
        "mode",
        "mtimeNs",
        "oldDigest",
        "newDigest",
        "newFile",
        "backupFile",
        "tempFile",
    )
)
_DIRECTORY_KEYS = frozenset(("path", "mode", "atimeNs", "mtimeNs"))
_UNSUPPORTED_DIRECTORY_FSYNC = frozenset(
    error
    for error in (
        getattr(errno, "EACCES", None),
        getattr(errno, "EBADF", None),
        getattr(errno, "EINVAL", None),
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EPERM", None),
    )
    if error is not None
)


@dataclass(frozen=True)
class TransactionResult:
    changed: bool
    paths: tuple[str, ...]
    transaction_id: str | None
    value: Any


@dataclass(frozen=True)
class RecoveryPreview:
    present: bool
    phase: str | None
    paths: tuple[str, ...]
    transaction_id: str | None


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as error:
        if error.errno in _UNSUPPORTED_DIRECTORY_FSYNC:
            return
        raise
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in _UNSUPPORTED_DIRECTORY_FSYNC:
                raise
    finally:
        os.close(descriptor)


def _write_bytes(path: Path, value: bytes, *, mode: int = 0o644) -> None:
    with path.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(path, mode)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def _write_bytes_replace(path: Path, value: bytes, temporary: Path, *, mode: int) -> None:
    if temporary.exists() or is_link_like(temporary):
        raise RecoveryError("transaction temporary path already exists")
    _write_bytes(temporary, value, mode=mode)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _unlink_file(path: Path) -> None:
    path.unlink()
    _fsync_directory(path.parent)


def _lock_location(root: Path) -> tuple[Path, Path]:
    lock_parent = Path(tempfile.gettempdir()) / "orchestration-harness-locks"
    key = hashlib.sha256(os.fsencode(str(root))).hexdigest()
    return lock_parent, lock_parent / key


def workspace_lock_present(root: Path) -> bool:
    boundary = canonical_root(root)
    _parent, lock = _lock_location(boundary)
    return lock.exists()


class PortableLock:
    """Cross-platform exclusive lock using atomic directory creation."""

    def __init__(self, root: Path, transaction_id: str) -> None:
        self.root = canonical_root(root)
        self.transaction_id = validate_transaction_id(transaction_id)
        self.parent, self.path = _lock_location(self.root)
        self.acquired = False

    def __enter__(self) -> "PortableLock":
        try:
            self.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.mkdir(self.path, mode=0o700)
        except FileExistsError as error:
            raise LockBusyError("another writer owns the workspace lock") from error
        try:
            owner = dumps_canonical_json(
                {
                    "pid": os.getpid(),
                    "schemaVersion": 1,
                    "txid": self.transaction_id,
                }
            ).encode("utf-8")
            _write_bytes(self.path / "owner.json", owner, mode=0o600)
        except Exception:
            try:
                self.path.rmdir()
            except OSError:
                pass
            raise
        self.acquired = True
        return self

    def __exit__(self, _kind: Any, _value: Any, _traceback: Any) -> None:
        if not self.acquired:
            return
        try:
            owner = self.path / "owner.json"
            if owner.is_file() and not is_link_like(owner):
                owner.unlink()
            self.path.rmdir()
        finally:
            self.acquired = False
            try:
                self.parent.rmdir()
            except OSError:
                pass


def _break_matching_lock(root: Path, transaction_id: str) -> None:
    parent, lock = _lock_location(canonical_root(root))
    if not lock.exists():
        return
    if is_link_like(lock) or not lock.is_dir():
        raise RecoveryError("workspace lock has an unsafe type")
    entries = list(lock.iterdir())
    if len(entries) != 1 or entries[0].name != "owner.json":
        raise RecoveryError("workspace lock cannot be safely broken")
    owner_path = entries[0]
    if is_link_like(owner_path) or not owner_path.is_file():
        raise RecoveryError("workspace lock owner is invalid")
    try:
        owner = loads_strict_json(owner_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as error:
        raise RecoveryError("workspace lock owner is invalid") from error
    if (
        not isinstance(owner, dict)
        or frozenset(owner) != frozenset(("pid", "schemaVersion", "txid"))
        or owner.get("schemaVersion") != 1
        or owner.get("txid") != transaction_id
    ):
        raise RecoveryError("workspace lock does not match the journal")
    owner_path.unlink()
    lock.rmdir()
    try:
        parent.rmdir()
    except OSError:
        pass


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists():
        if current.parent == current:
            raise ValidationError("managed path has no existing parent")
        current = current.parent
    if is_link_like(current) or not current.is_dir():
        raise ValidationError("managed destination parent is unsafe")
    return current


def _created_directories(root: Path, destinations: tuple[Path, ...]) -> list[str]:
    values: set[str] = set()
    for destination in destinations:
        current = destination.parent
        while current != root:
            if current.exists():
                break
            values.add(current.relative_to(root).as_posix())
            current = current.parent
    return sorted(values, key=lambda value: (len(PurePosixPath(value).parts), value))


def _directory_metadata(
    root: Path,
    destinations: tuple[Path, ...],
) -> list[dict[str, Any]]:
    directories: set[Path] = {root}
    for destination in destinations:
        current = destination.parent
        while True:
            if current.exists():
                if is_link_like(current) or not current.is_dir():
                    raise ValidationError("transaction directory path is unsafe")
                directories.add(current)
            if current == root:
                break
            current = current.parent
    values: list[dict[str, Any]] = []
    for directory in sorted(
        directories,
        key=lambda value: (
            len(value.relative_to(root).parts),
            value.relative_to(root).as_posix(),
        ),
    ):
        stat = directory.stat()
        relative = "." if directory == root else directory.relative_to(root).as_posix()
        values.append(
            {
                "atimeNs": stat.st_atime_ns,
                "mode": stat.st_mode & 0o777,
                "mtimeNs": stat.st_mtime_ns,
                "path": relative,
            }
        )
    return values


def _canonical_changes(
    root: Path,
    changes: Mapping[str, str | bytes],
) -> dict[str, bytes]:
    normalized: dict[str, bytes] = {}
    folded: set[str] = set()
    root_device = root.stat().st_dev
    for relative, value in changes.items():
        validated = validate_relative_path(
            relative,
            label="transaction path",
            allow_reserved=True,
        )
        key = validated.casefold()
        if key in folded:
            raise ValidationError("transaction contains a path collision")
        folded.add(key)
        destination = safe_path(root, validated)
        if destination.exists() and not destination.is_file():
            raise ValidationError("transaction destination must be a regular file")
        parent = _nearest_existing_parent(destination.parent)
        if parent.stat().st_dev != root_device:
            raise ValidationError("managed destinations must share one filesystem")
        encoded = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        if len(encoded) > MAX_STATE_BYTES:
            raise ValidationError("transaction value exceeds the size limit")
        if destination.is_file() and destination.read_bytes() == encoded:
            continue
        normalized[validated] = encoded
    return dict(sorted(normalized.items()))


def _journal_path(root: Path) -> Path:
    return safe_path(root, JOURNAL_RELATIVE)


def _journal_write_path(root: Path, transaction_id: str) -> Path:
    return safe_path(root, f".orchestration-journal-write-{transaction_id}")


def _write_journal(root: Path, journal: dict[str, Any]) -> None:
    transaction_id = validate_transaction_id(journal["txid"])
    destination = _journal_path(root)
    temporary = _journal_write_path(root, transaction_id)
    if temporary.exists() or is_link_like(temporary):
        raise RecoveryError("journal temporary path already exists")
    value = dumps_canonical_json(journal).encode("utf-8")
    _write_bytes(temporary, value, mode=0o600)
    os.replace(temporary, destination)
    _fsync_directory(root)


def _record_paths(transaction_id: str, relative: str, index: int) -> tuple[str, str, str]:
    stage = f".orchestration-stage-{transaction_id}"
    new_file = f"{stage}/new/{relative}"
    backup_file = f"{stage}/backup/{relative}"
    parent = PurePosixPath(relative).parent
    temporary_name = f".orchestration-write-{transaction_id}-{index}"
    temporary = (
        temporary_name
        if str(parent) == "."
        else f"{parent.as_posix()}/{temporary_name}"
    )
    return new_file, backup_file, temporary


def _build_journal(
    root: Path,
    transaction_id: str,
    changes: Mapping[str, bytes],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    destinations: list[Path] = []
    for index, (relative, new_value) in enumerate(changes.items()):
        destination = safe_path(root, relative)
        destinations.append(destination)
        existed = destination.is_file()
        original_stat = destination.stat() if existed else None
        old_value = destination.read_bytes() if existed else b""
        new_file, backup_file, temporary = _record_paths(
            transaction_id,
            relative,
            index,
        )
        records.append(
            {
                "atimeNs": original_stat.st_atime_ns if original_stat else None,
                "backupFile": backup_file if existed else None,
                "existed": existed,
                "mode": (original_stat.st_mode & 0o777) if original_stat else None,
                "mtimeNs": original_stat.st_mtime_ns if original_stat else None,
                "newDigest": _digest(new_value),
                "newFile": new_file,
                "oldDigest": _digest(old_value) if existed else None,
                "path": relative,
                "tempFile": temporary,
            }
        )
    return {
        "createdDirs": _created_directories(root, tuple(destinations)),
        "directoryMetadata": _directory_metadata(root, tuple(destinations)),
        "files": records,
        "phase": "preparing",
        "schemaVersion": JOURNAL_SCHEMA_VERSION,
        "txid": transaction_id,
    }


def _stage_values(
    root: Path,
    journal: dict[str, Any],
    changes: Mapping[str, bytes],
) -> None:
    transaction_id = journal["txid"]
    stage_root = safe_path(root, f".orchestration-stage-{transaction_id}")
    stage_root.mkdir(mode=0o700)
    _fsync_directory(root)
    for record in journal["files"]:
        relative = record["path"]
        new_path = safe_path(root, record["newFile"])
        new_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _write_bytes(new_path, changes[relative], mode=0o600)
        if record["existed"]:
            destination = safe_path(root, relative)
            backup_path = safe_path(root, record["backupFile"])
            backup_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_bytes(backup_path, destination.read_bytes(), mode=0o600)
    journal["phase"] = "prepared"
    _write_journal(root, journal)


def _create_destination_directories(root: Path, journal: dict[str, Any]) -> None:
    for relative in journal["createdDirs"]:
        directory = safe_path(root, relative)
        if directory.exists():
            if is_link_like(directory) or not directory.is_dir():
                raise ValidationError("transaction directory path is unsafe")
            continue
        directory.mkdir(mode=0o755)
        _fsync_directory(directory.parent)


def _apply_records(
    root: Path,
    journal: dict[str, Any],
    fault_hook: FaultHook | None,
) -> None:
    journal["phase"] = "applying"
    _write_journal(root, journal)
    _create_destination_directories(root, journal)
    for index, record in enumerate(journal["files"]):
        relative = record["path"]
        staged = safe_path(root, record["newFile"])
        try:
            value = staged.read_bytes()
        except OSError as error:
            raise RecoveryError("staged transaction value is missing") from error
        if _digest(value) != record["newDigest"]:
            raise RecoveryError("staged transaction value failed verification")
        destination = safe_path(root, relative)
        temporary = safe_path(root, record["tempFile"])
        mode = record["mode"] if record["mode"] is not None else 0o644
        if fault_hook is not None:
            fault_hook("before-replace", relative, index)
        _write_bytes_replace(destination, value, temporary, mode=mode)
        if fault_hook is not None:
            fault_hook("after-replace", relative, index)
    journal["phase"] = "committed"
    _write_journal(root, journal)
    if fault_hook is not None:
        fault_hook("after-commit", "", len(journal["files"]))


def _validate_digest(value: Any, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise RecoveryError("journal contains an invalid digest")
    return value


def _load_journal(root: Path) -> dict[str, Any] | None:
    path = _journal_path(root)
    if not path.exists():
        return None
    if is_link_like(path) or not path.is_file():
        raise RecoveryError("journal has an unsafe type")
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise RecoveryError("journal exceeds the size limit")
        value = loads_strict_json(path.read_text(encoding="utf-8"))
    except RecoveryError:
        raise
    except (OSError, UnicodeError, ValidationError) as error:
        raise RecoveryError("journal is not valid UTF-8 JSON") from error
    if not isinstance(value, dict) or frozenset(value) != _JOURNAL_KEYS:
        raise RecoveryError("journal violates its closed schema")
    if value["schemaVersion"] != JOURNAL_SCHEMA_VERSION:
        raise RecoveryError("journal schema version is unsupported")
    try:
        transaction_id = validate_transaction_id(value["txid"])
    except ValidationError as error:
        raise RecoveryError("journal transaction ID is invalid") from error
    if value["phase"] not in JOURNAL_PHASES:
        raise RecoveryError("journal phase is unsupported")
    if not isinstance(value["files"], list) or not value["files"]:
        raise RecoveryError("journal must contain file records")
    if not isinstance(value["createdDirs"], list):
        raise RecoveryError("journal directory records are invalid")

    seen_paths: set[str] = set()
    for index, record in enumerate(value["files"]):
        if not isinstance(record, dict) or frozenset(record) != _RECORD_KEYS:
            raise RecoveryError("journal file record violates its schema")
        try:
            relative = validate_relative_path(
                record["path"],
                label="journal path",
                allow_reserved=True,
            )
        except ValidationError as error:
            raise RecoveryError("journal file path is invalid") from error
        if relative.casefold() in seen_paths:
            raise RecoveryError("journal contains a path collision")
        seen_paths.add(relative.casefold())
        if not isinstance(record["existed"], bool):
            raise RecoveryError("journal existence flag is invalid")
        if record["existed"]:
            if (
                not isinstance(record["mode"], int)
                or isinstance(record["mode"], bool)
                or record["mode"] < 0
                or record["mode"] > 0o777
            ):
                raise RecoveryError("journal file mode is invalid")
            for field in ("atimeNs", "mtimeNs"):
                timestamp = record[field]
                if (
                    not isinstance(timestamp, int)
                    or isinstance(timestamp, bool)
                    or timestamp < 0
                ):
                    raise RecoveryError("journal file timestamp is invalid")
        elif record["mode"] is not None:
            raise RecoveryError("journal mode must be empty for a new file")
        elif record["atimeNs"] is not None or record["mtimeNs"] is not None:
            raise RecoveryError("journal timestamps must be empty for a new file")
        _validate_digest(record["oldDigest"], optional=not record["existed"])
        _validate_digest(record["newDigest"])
        expected_new, expected_backup, expected_temporary = _record_paths(
            transaction_id,
            relative,
            index,
        )
        if record["newFile"] != expected_new:
            raise RecoveryError("journal staged path is invalid")
        expected_backup_value = expected_backup if record["existed"] else None
        if record["backupFile"] != expected_backup_value:
            raise RecoveryError("journal backup path is invalid")
        if record["tempFile"] != expected_temporary:
            raise RecoveryError("journal temporary path is invalid")

    seen_directories: set[str] = set()
    for relative in value["createdDirs"]:
        try:
            validated = validate_relative_path(
                relative,
                label="journal directory",
                allow_reserved=True,
            )
        except ValidationError as error:
            raise RecoveryError("journal directory path is invalid") from error
        if validated in seen_directories:
            raise RecoveryError("journal contains duplicate directories")
        seen_directories.add(validated)

    metadata = value["directoryMetadata"]
    if not isinstance(metadata, list) or not metadata:
        raise RecoveryError("journal directory metadata is invalid")
    metadata_paths: set[str] = set()
    for record in metadata:
        if not isinstance(record, dict) or frozenset(record) != _DIRECTORY_KEYS:
            raise RecoveryError("journal directory metadata violates its schema")
        relative = record["path"]
        if relative != ".":
            try:
                relative = validate_relative_path(
                    relative,
                    label="journal metadata path",
                    allow_reserved=True,
                )
            except ValidationError as error:
                raise RecoveryError("journal metadata path is invalid") from error
        if relative in metadata_paths:
            raise RecoveryError("journal directory metadata is duplicated")
        metadata_paths.add(relative)
        if (
            not isinstance(record["mode"], int)
            or isinstance(record["mode"], bool)
            or record["mode"] < 0
            or record["mode"] > 0o777
        ):
            raise RecoveryError("journal directory mode is invalid")
        for field in ("atimeNs", "mtimeNs"):
            timestamp = record[field]
            if (
                not isinstance(timestamp, int)
                or isinstance(timestamp, bool)
                or timestamp < 0
            ):
                raise RecoveryError("journal directory timestamp is invalid")
    if "." not in metadata_paths:
        raise RecoveryError("journal omits workspace metadata")
    return value


def inspect_recovery(root: Path) -> RecoveryPreview:
    boundary = canonical_root(root)
    journal = _load_journal(boundary)
    if journal is None:
        return RecoveryPreview(False, None, (), None)
    return RecoveryPreview(
        True,
        journal["phase"],
        tuple(record["path"] for record in journal["files"]),
        journal["txid"],
    )


def _current_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    if is_link_like(path) or not path.is_file():
        raise RecoveryError("managed target has an unsafe type during recovery")
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise RecoveryError("managed target exceeds the recovery size limit")
        return _digest(path.read_bytes())
    except RecoveryError:
        raise
    except OSError as error:
        raise RecoveryError("managed target is unreadable during recovery") from error


def _remove_transaction_temporary(root: Path, record: dict[str, Any]) -> None:
    temporary = safe_path(root, record["tempFile"])
    if is_link_like(temporary) or (temporary.exists() and not temporary.is_file()):
        raise RecoveryError("transaction temporary has an unsafe type")
    if temporary.is_file():
        _unlink_file(temporary)


def _remove_stage(root: Path, transaction_id: str) -> None:
    stage = safe_path(root, f".orchestration-stage-{transaction_id}")
    if not stage.exists():
        return
    if is_link_like(stage) or not stage.is_dir():
        raise RecoveryError("transaction stage has an unsafe type")
    shutil.rmtree(stage)
    _fsync_directory(root)


def _remove_created_directories(root: Path, directories: list[str]) -> None:
    for relative in sorted(
        directories,
        key=lambda value: (len(PurePosixPath(value).parts), value),
        reverse=True,
    ):
        directory = safe_path(root, relative)
        if not directory.exists():
            continue
        if is_link_like(directory) or not directory.is_dir():
            raise RecoveryError("created directory has an unsafe type")
        try:
            directory.rmdir()
            _fsync_directory(directory.parent)
        except OSError as error:
            if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                raise


def _remove_journal(root: Path) -> None:
    journal = _journal_path(root)
    if journal.exists():
        if is_link_like(journal) or not journal.is_file():
            raise RecoveryError("journal has an unsafe type")
        _unlink_file(journal)


def _cleanup_artifacts(root: Path, journal: dict[str, Any]) -> None:
    for record in journal["files"]:
        _remove_transaction_temporary(root, record)
    _remove_stage(root, journal["txid"])
    _remove_journal(root)


def _verify_original_targets(root: Path, journal: dict[str, Any]) -> None:
    for record in journal["files"]:
        current = _current_digest(safe_path(root, record["path"]))
        expected = record["oldDigest"] if record["existed"] else None
        if current != expected:
            raise RecoveryError("target changed before transaction preparation completed")


def _preflight_rollback(root: Path, journal: dict[str, Any]) -> None:
    for record in journal["files"]:
        destination = safe_path(root, record["path"])
        current = _current_digest(destination)
        old_digest = record["oldDigest"]
        new_digest = record["newDigest"]
        valid = (
            current in (old_digest, new_digest)
            if record["existed"]
            else current in (None, new_digest)
        )
        if not valid:
            raise RecoveryError("target digest is unknown; recovery stopped safely")
        if record["existed"] and current == new_digest:
            backup = safe_path(root, record["backupFile"])
            if is_link_like(backup) or not backup.is_file():
                raise RecoveryError("verified backup is unavailable")
            value = backup.read_bytes()
            if _digest(value) != old_digest:
                raise RecoveryError("backup digest verification failed")


def _rollback_applying(root: Path, journal: dict[str, Any]) -> None:
    _preflight_rollback(root, journal)
    for record in reversed(journal["files"]):
        destination = safe_path(root, record["path"])
        current = _current_digest(destination)
        old_digest = record["oldDigest"]
        new_digest = record["newDigest"]
        if record["existed"]:
            if current == old_digest:
                continue
            if current != new_digest:
                raise RecoveryError("target digest is unknown; recovery stopped safely")
            backup = safe_path(root, record["backupFile"])
            if is_link_like(backup) or not backup.is_file():
                raise RecoveryError("verified backup is unavailable")
            value = backup.read_bytes()
            if _digest(value) != old_digest:
                raise RecoveryError("backup digest verification failed")
            temporary = safe_path(root, record["tempFile"])
            _write_bytes_replace(
                destination,
                value,
                temporary,
                mode=record["mode"],
            )
            os.utime(
                destination,
                ns=(record["atimeNs"], record["mtimeNs"]),
            )
        else:
            if current is None:
                continue
            if current != new_digest:
                raise RecoveryError("new target digest is unknown; recovery stopped safely")
            _unlink_file(destination)
    _remove_created_directories(root, journal["createdDirs"])


def _restore_directory_metadata(root: Path, journal: dict[str, Any]) -> None:
    for record in sorted(
        journal["directoryMetadata"],
        key=lambda value: (
            len(PurePosixPath(value["path"]).parts),
            value["path"],
        ),
        reverse=True,
    ):
        directory = root if record["path"] == "." else safe_path(root, record["path"])
        if is_link_like(directory) or not directory.is_dir():
            raise RecoveryError("original directory metadata target is unavailable")
        os.chmod(directory, record["mode"])
        os.utime(
            directory,
            ns=(record["atimeNs"], record["mtimeNs"]),
        )


def _verify_committed_targets(root: Path, journal: dict[str, Any]) -> None:
    for record in journal["files"]:
        current = _current_digest(safe_path(root, record["path"]))
        if current != record["newDigest"]:
            raise RecoveryError("committed target failed digest verification")


def _recover_locked(root: Path) -> RecoveryPreview:
    journal = _load_journal(root)
    if journal is None:
        return RecoveryPreview(False, None, (), None)
    preview = RecoveryPreview(
        True,
        journal["phase"],
        tuple(record["path"] for record in journal["files"]),
        journal["txid"],
    )
    phase = journal["phase"]
    restore_metadata = phase != "committed"
    if phase in ("preparing", "prepared"):
        _verify_original_targets(root, journal)
    elif phase == "applying":
        _rollback_applying(root, journal)
    elif phase == "committed":
        _verify_committed_targets(root, journal)
    _cleanup_artifacts(root, journal)
    if restore_metadata:
        _restore_directory_metadata(root, journal)
    return preview


def recover_transaction(root: Path, *, break_stale_lock: bool = False) -> RecoveryPreview:
    boundary = canonical_root(root)
    preview = inspect_recovery(boundary)
    if not preview.present:
        return preview
    assert preview.transaction_id is not None
    _parent, lock = _lock_location(boundary)
    if lock.exists():
        if not break_stale_lock:
            raise LockBusyError(
                "recovery requires explicit stale-lock authorization"
            )
        _break_matching_lock(boundary, preview.transaction_id)
    recovery_id = uuid.uuid4().hex
    with PortableLock(boundary, recovery_id):
        return _recover_locked(boundary)


def execute_transaction(
    root: Path,
    builder: Builder,
    *,
    fault_hook: FaultHook | None = None,
) -> TransactionResult:
    """Build under lock, then apply every changed file as one transaction."""

    boundary = canonical_root(root)
    transaction_id = uuid.uuid4().hex
    with PortableLock(boundary, transaction_id):
        if _load_journal(boundary) is not None:
            raise RecoveryRequiredError(
                "a durable journal must be recovered before mutation"
            )
        requested, value = builder(transaction_id)
        changes = _canonical_changes(boundary, requested)
        if not changes:
            return TransactionResult(False, (), None, value)

        journal = _build_journal(boundary, transaction_id, changes)
        try:
            _write_journal(boundary, journal)
            _stage_values(boundary, journal, changes)
            _apply_records(boundary, journal, fault_hook)
            _cleanup_artifacts(boundary, journal)
        except Exception as error:
            committed = False
            try:
                persisted = _load_journal(boundary)
                committed = bool(
                    persisted is not None and persisted["phase"] == "committed"
                )
                _recover_locked(boundary)
            except Exception as recovery_error:
                raise RecoveryRequiredError(
                    "transaction failed and requires explicit recovery"
                ) from recovery_error
            if committed:
                return TransactionResult(
                    True,
                    tuple(changes),
                    transaction_id,
                    value,
                )
            raise TransactionError("transaction failed and was rolled back") from error
        return TransactionResult(
            True,
            tuple(changes),
            transaction_id,
            value,
        )
