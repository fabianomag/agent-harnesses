"""Install and verify one cataloged harness package without reimplementing it."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import os
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

try:
    from tools import catalog
except ModuleNotFoundError:  # Direct execution from the tools directory.
    import catalog  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AT_FDCWD = -100
RENAME_NOREPLACE = 0x00000001
RENAME_EXCL = 0x00000004


class PackageManagerError(ValueError):
    """Raised when an install or verification request is unsafe or invalid."""


@dataclass(frozen=True)
class PackageResult:
    action: str
    package_id: str
    version: str
    destination_name: str
    file_count: int


def _is_link_like(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise PackageManagerError("path metadata is unreadable") from error
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _assert_no_link_like_components(path: Path) -> None:
    """Reject link-like components in the lexical path before canonicalizing it."""

    lexical = path if path.is_absolute() else Path.cwd() / path
    current = Path(lexical.anchor)
    if _is_link_like(current):
        raise PackageManagerError(
            "installation root path must not contain a link"
        )
    for component in lexical.parts[1:]:
        if component == "..":
            current = current.parent
            continue
        current = current / component
        if _is_link_like(current):
            raise PackageManagerError(
                "installation root path must not contain a link"
            )


def resolve_install_root(root: Path) -> Path:
    """Require one existing real directory as the complete write boundary."""

    if not os.fspath(root).strip():
        raise PackageManagerError("installation root must be explicit")
    if not _lexists(root):
        raise PackageManagerError("installation root must already exist")
    _assert_no_link_like_components(root)
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise PackageManagerError("installation root is not resolvable") from error
    if not resolved.is_dir():
        raise PackageManagerError("installation root must be a directory")
    return resolved


def _checked_catalog(repository_root: Path) -> dict[str, Any]:
    checked_path = repository_root / catalog.CATALOG_PATH
    try:
        checked = catalog.load_json_strict(checked_path)
        expected = catalog.expected_catalog(repository_root)
    except catalog.CommonContractError as error:
        raise PackageManagerError("catalog source violates its contract") from error
    if checked != expected:
        raise PackageManagerError("catalog is not synchronized with package payloads")
    if checked_path.read_bytes() != catalog.canonical_json_bytes(expected):
        raise PackageManagerError("catalog serialization is not canonical")
    return expected


def _select_entry(
    repository_root: Path,
    *,
    package_id: str,
    version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog_value = _checked_catalog(repository_root)
    for entry in catalog_value["packages"]:
        if entry["id"] == package_id:
            if entry["version"] != version:
                raise PackageManagerError(
                    "requested version does not match the cataloged package"
                )
            if entry["artifactStatus"]["implementation"] != "implemented":
                raise PackageManagerError("requested package is not implemented")
            return catalog_value, entry
    raise PackageManagerError("requested package ID is not cataloged")


def _destination_name(package_id: str, version: str) -> str:
    if package_id not in catalog.EXPECTED_PACKAGES:
        raise PackageManagerError("package ID is not part of the public contract")
    if catalog.SEMVER_PATTERN.fullmatch(version) is None:
        raise PackageManagerError("package version is not valid SemVer")
    return f"{package_id}-{version}"


def _receipt(
    catalog_value: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "package": {
            "id": entry["id"],
            "version": entry["version"],
        },
        "licenseFile": catalog_value["licenseFile"],
        "files": entry["files"],
    }


def _portable_relative_path(value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts:
        raise PackageManagerError("catalog payload path is not portable")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise PackageManagerError("catalog payload path is not portable")
    return Path(*pure.parts)


def _expected_file_map(
    catalog_value: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, str]:
    expected: dict[str, str] = {}
    for item in entry["files"]:
        path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            raise PackageManagerError("catalog payload inventory is invalid")
        _portable_relative_path(path)
        if path in expected:
            raise PackageManagerError("catalog payload paths must be unique")
        expected[path] = digest
    if catalog.RECEIPT_NAME in expected:
        raise PackageManagerError("catalog payload uses the reserved receipt name")
    license_file = catalog_value.get("licenseFile")
    if not isinstance(license_file, dict):
        raise PackageManagerError("catalog license file is invalid")
    license_path = license_file.get("path")
    license_digest = license_file.get("sha256")
    if (
        license_path != catalog.COMMON_LICENSE_NAME
        or not isinstance(license_digest, str)
        or license_path in expected
    ):
        raise PackageManagerError("catalog license file is invalid")
    expected[license_path] = license_digest
    return expected


def _walk_installed_tree(destination: Path) -> tuple[set[str], set[str]]:
    observed_files: set[str] = set()
    observed_directories: set[str] = set()
    for current, directory_names, file_names in os.walk(
        destination, followlinks=False
    ):
        current_path = Path(current)
        for name in tuple(directory_names):
            child = current_path / name
            if _is_link_like(child) or not child.is_dir():
                raise PackageManagerError(
                    "installed package contains a non-directory entry"
                )
            observed_directories.add(
                child.relative_to(destination).as_posix()
            )
        for name in file_names:
            child = current_path / name
            if _is_link_like(child) or not child.is_file():
                raise PackageManagerError("installed package contains a non-file")
            observed_files.add(child.relative_to(destination).as_posix())
    return observed_files, observed_directories


def _verify_destination(
    destination: Path,
    catalog_value: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    if _is_link_like(destination) or not destination.is_dir():
        raise PackageManagerError("installation destination is not a real directory")

    receipt_path = destination / catalog.RECEIPT_NAME
    if not receipt_path.is_file() or _is_link_like(receipt_path):
        raise PackageManagerError("installation receipt is missing or invalid")
    try:
        receipt = catalog.load_json_strict(receipt_path)
    except catalog.CommonContractError as error:
        raise PackageManagerError("installation receipt is invalid") from error
    expected_receipt = _receipt(catalog_value, entry)
    if receipt != expected_receipt:
        raise PackageManagerError("installation receipt does not match the catalog")
    if receipt_path.read_bytes() != catalog.canonical_json_bytes(expected_receipt):
        raise PackageManagerError("installation receipt is not canonical")

    expected = _expected_file_map(catalog_value, entry)
    observed_files, observed_directories = _walk_installed_tree(destination)
    expected_with_receipt = {*expected, catalog.RECEIPT_NAME}
    if observed_files != expected_with_receipt:
        raise PackageManagerError("installed file set does not match the catalog")
    expected_directories: set[str] = set()
    for relative_text in expected_with_receipt:
        relative = _portable_relative_path(relative_text)
        for parent in relative.parents:
            if parent == Path("."):
                break
            expected_directories.add(parent.as_posix())
    if observed_directories != expected_directories:
        raise PackageManagerError(
            "installed directory set does not match the catalog"
        )

    for relative_text, expected_digest in expected.items():
        path = destination / _portable_relative_path(relative_text)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise PackageManagerError("installed package file is unreadable") from error
        if digest != expected_digest:
            raise PackageManagerError("installed package file digest does not match")


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _stage_installation(
    stage: Path,
    *,
    repository_root: Path,
    catalog_value: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    package_root = repository_root / "packages" / entry["id"]
    expected = {
        item["path"]: item["sha256"]
        for item in entry["files"]
    }
    for relative_text, expected_digest in expected.items():
        relative = _portable_relative_path(relative_text)
        source = package_root / relative
        if _is_link_like(source) or not source.is_file():
            raise PackageManagerError("cataloged source file is missing or unsafe")
        try:
            content = source.read_bytes()
        except OSError as error:
            raise PackageManagerError("cataloged source file is unreadable") from error
        if hashlib.sha256(content).hexdigest() != expected_digest:
            raise PackageManagerError("cataloged source file changed during install")
        _write_file(stage / relative, content)

    license_file = catalog_value["licenseFile"]
    license_source = repository_root / license_file["path"]
    if _is_link_like(license_source) or not license_source.is_file():
        raise PackageManagerError("cataloged license file is missing or unsafe")
    try:
        license_content = license_source.read_bytes()
    except OSError as error:
        raise PackageManagerError("cataloged license file is unreadable") from error
    if hashlib.sha256(license_content).hexdigest() != license_file["sha256"]:
        raise PackageManagerError("cataloged license file changed during install")
    _write_file(stage / catalog.COMMON_LICENSE_NAME, license_content)

    _write_file(
        stage / catalog.RECEIPT_NAME,
        catalog.canonical_json_bytes(_receipt(catalog_value, entry)),
    )
    for directory in sorted(
        (path for path in stage.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        catalog.fsync_directory(directory)
    catalog.fsync_directory(stage)


def _raise_publish_error(
    error_number: int,
    *,
    source: Path,
    destination: Path,
) -> None:
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(
            error_number,
            os.strerror(error_number),
            os.fspath(destination),
        )
    raise OSError(
        error_number or errno.EIO,
        os.strerror(error_number or errno.EIO),
        os.fspath(source),
    )


def _publish_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish one directory without replacing any destination."""

    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)

    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            rename_exclusive = libc.renamex_np
        except (AttributeError, OSError) as error:
            raise PackageManagerError(
                "atomic no-overwrite publication is unavailable"
            ) from error
        rename_exclusive.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_exclusive.restype = ctypes.c_int
        ctypes.set_errno(0)
        if rename_exclusive(source_bytes, destination_bytes, RENAME_EXCL) != 0:
            _raise_publish_error(
                ctypes.get_errno(),
                source=source,
                destination=destination,
            )
        return

    if sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            rename_no_replace = libc.renameat2
        except (AttributeError, OSError) as error:
            raise PackageManagerError(
                "atomic no-overwrite publication is unavailable"
            ) from error
        rename_no_replace.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_no_replace.restype = ctypes.c_int
        ctypes.set_errno(0)
        if (
            rename_no_replace(
                AT_FDCWD,
                source_bytes,
                AT_FDCWD,
                destination_bytes,
                RENAME_NOREPLACE,
            )
            != 0
        ):
            _raise_publish_error(
                ctypes.get_errno(),
                source=source,
                destination=destination,
            )
        return

    if sys.platform == "win32":
        os.rename(source, destination)
        return

    raise PackageManagerError("atomic no-overwrite publication is unavailable")


def _finalize_installation_attempt(
    *,
    install_root: Path,
    primary_error: BaseException | None,
) -> None:
    """Sync the write boundary without touching a failed staging pathname."""

    try:
        catalog.fsync_directory(install_root)
    except BaseException as error:
        if not isinstance(error, Exception):
            raise
        if primary_error is not None:
            if isinstance(primary_error, Exception):
                finalize_error = PackageManagerError(
                    "package operation failed and installation root sync "
                    "did not complete"
                )
                raise finalize_error from primary_error
            add_note = getattr(primary_error, "add_note", None)
            if callable(add_note):
                add_note("installation root sync did not complete")
            return
        raise PackageManagerError(
            "installation root sync did not complete"
        ) from error


def install_package(
    *,
    root: Path,
    package_id: str,
    version: str,
    apply: bool,
    repository_root: Path = REPOSITORY_ROOT,
) -> PackageResult:
    """Preview or atomically install one exact package payload."""

    install_root = resolve_install_root(root)
    catalog_value, entry = _select_entry(
        repository_root,
        package_id=package_id,
        version=version,
    )
    destination_name = _destination_name(package_id, version)
    destination = install_root / destination_name
    expected_count = len(entry["files"]) + 1

    if _lexists(destination):
        _verify_destination(destination, catalog_value, entry)
        return PackageResult(
            "unchanged",
            package_id,
            version,
            destination_name,
            expected_count,
        )

    if not apply:
        return PackageResult(
            "planned",
            package_id,
            version,
            destination_name,
            expected_count,
        )

    stage = install_root / (
        f".{package_id}-{version}.stage-{uuid.uuid4().hex}"
    )
    try:
        try:
            stage.mkdir(mode=0o700)
        except FileExistsError as error:
            raise PackageManagerError("staging path collision") from error
        catalog.fsync_directory(install_root)
        if _lexists(destination):
            _verify_destination(destination, catalog_value, entry)
            return PackageResult(
                "unchanged-residual",
                package_id,
                version,
                destination_name,
                expected_count,
            )
        _stage_installation(
            stage,
            repository_root=repository_root,
            catalog_value=catalog_value,
            entry=entry,
        )
        _verify_destination(stage, catalog_value, entry)
        if _lexists(destination):
            _verify_destination(destination, catalog_value, entry)
            return PackageResult(
                "unchanged-residual",
                package_id,
                version,
                destination_name,
                expected_count,
            )
        try:
            _publish_no_replace(stage, destination)
        except FileExistsError as error:
            try:
                _verify_destination(destination, catalog_value, entry)
            except BaseException as verification_error:
                raise verification_error from error
            return PackageResult(
                "unchanged-residual",
                package_id,
                version,
                destination_name,
                expected_count,
            )
        catalog.fsync_directory(install_root)
    finally:
        _finalize_installation_attempt(
            install_root=install_root,
            primary_error=sys.exc_info()[1],
        )

    return PackageResult(
        "installed",
        package_id,
        version,
        destination_name,
        expected_count,
    )


def verify_package(
    *,
    root: Path,
    package_id: str,
    version: str,
    repository_root: Path = REPOSITORY_ROOT,
) -> PackageResult:
    """Verify one exact installation against the synchronized catalog."""

    install_root = resolve_install_root(root)
    catalog_value, entry = _select_entry(
        repository_root,
        package_id=package_id,
        version=version,
    )
    destination_name = _destination_name(package_id, version)
    destination = install_root / destination_name
    if not _lexists(destination):
        raise PackageManagerError("installation destination does not exist")
    _verify_destination(destination, catalog_value, entry)
    return PackageResult(
        "verified",
        package_id,
        version,
        destination_name,
        len(entry["files"]) + 1,
    )


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--package",
        required=True,
        choices=catalog.PACKAGE_ORDER,
        help="exact package ID",
    )
    parser.add_argument("--version", required=True, help="exact cataloged version")
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="existing installation root",
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install or verify one exact cataloged harness package."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser(
        "install",
        help="preview or apply an atomic no-overwrite installation",
    )
    _add_selection_arguments(install_parser)
    mode = install_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate without writing")
    mode.add_argument("--apply", action="store_true", help="apply the installation")

    verify_parser = subparsers.add_parser(
        "verify",
        help="verify an existing installation without writing",
    )
    _add_selection_arguments(verify_parser)
    return parser.parse_args(argv)


def _render_result(result: PackageResult) -> str:
    return (
        f"PASS: {result.action} {result.package_id} {result.version} "
        f"({result.file_count} payload file(s)) at {result.destination_name}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.command == "install":
            result = install_package(
                root=arguments.root,
                package_id=arguments.package,
                version=arguments.version,
                apply=arguments.apply,
            )
        else:
            result = verify_package(
                root=arguments.root,
                package_id=arguments.package,
                version=arguments.version,
            )
    except (PackageManagerError, catalog.CommonContractError, OSError):
        print("FAIL: package operation violates its contract")
        return 1

    print(_render_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
