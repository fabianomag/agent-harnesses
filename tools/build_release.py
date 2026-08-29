"""Build and verify immutable Agent Harnesses release assets.

The builder is intentionally dependency-free.  It emits ZIP_STORED archives
with fixed metadata so the same source commit produces the same bytes on every
supported host.  Verification inspects the exact files in an output or
download directory; it never rebuilds assets as part of the release job.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

try:
    from tools import build_product, catalog, product
except ModuleNotFoundError:  # Direct execution from the tools directory.
    import build_product  # type: ignore[no-redef]
    import catalog  # type: ignore[no-redef]
    import product  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST_NAME = "release-manifest.json"
CHANGELOG_NAME = "CHANGELOG.md"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReleaseBuildError(ValueError):
    """The release inputs or exact asset bytes violate the public contract."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ReleaseBuildError("JSON contains a duplicate property")
        value[key] = item
    return value


def _loads_strict(content: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            content.decode("utf-8"), object_pairs_hook=_reject_duplicate
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseBuildError(f"{label} is not strict UTF-8 JSON") from error


def _canonical_json_bytes(value: Any) -> bytes:
    return product.canonical_json_bytes(value)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _checked_commit(value: str) -> str:
    if COMMIT_PATTERN.fullmatch(value) is None:
        raise ReleaseBuildError("source commit must be one full lowercase SHA-1")
    return value


def _regular_file_bytes(path: Path, *, label: str) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReleaseBuildError(f"{label} is missing or unreadable") from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(reparse and attributes & reparse)
    ):
        raise ReleaseBuildError(f"{label} must be one real regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReleaseBuildError(f"{label} is unreadable") from error


def _portable_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
    ):
        raise ReleaseBuildError("package inventory contains an unsafe path")
    return path


def _checked_sources(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes, bytes]:
    product_value = product.load_product(repository_root)
    product_drift = build_product.check(repository_root)
    if product_drift:
        raise ReleaseBuildError(
            "product-derived installer, snapshot, manifests, or README blocks drift"
        )

    catalog_path = repository_root / catalog.CATALOG_PATH
    try:
        catalog_value = catalog.load_json_strict(catalog_path)
        expected_catalog = catalog.expected_catalog(repository_root)
    except catalog.CommonContractError as error:
        raise ReleaseBuildError("catalog violates its generated contract") from error
    if catalog_value != expected_catalog:
        raise ReleaseBuildError("catalog is not synchronized with package sources")
    if _regular_file_bytes(catalog_path, label="catalog") != catalog.canonical_json_bytes(
        expected_catalog
    ):
        raise ReleaseBuildError("catalog serialization is not canonical")

    expected_installer = build_product.expected_installer(repository_root)
    installer_bytes = _regular_file_bytes(
        repository_root / build_product.INSTALLER_PATH, label="installer"
    )
    if installer_bytes != expected_installer:
        raise ReleaseBuildError("installer is not synchronized with the product source")

    changelog_bytes = _regular_file_bytes(
        repository_root / CHANGELOG_NAME, label="changelog"
    )
    version_heading = f"## [{product_value['release']['version']}]".encode("utf-8")
    if version_heading not in changelog_bytes:
        raise ReleaseBuildError("changelog does not describe the selected release")

    snapshot_path = repository_root / product.SITE_SNAPSHOT_PATH
    snapshot_bytes = _regular_file_bytes(snapshot_path, label="site snapshot")
    expected_snapshot = _canonical_json_bytes(product.site_snapshot(product_value))
    if snapshot_bytes != expected_snapshot:
        raise ReleaseBuildError("site snapshot is not synchronized with the product source")

    expected_ids = [item["id"] for item in product_value["packages"]]
    observed_ids = [item.get("id") for item in catalog_value.get("packages", [])]
    if observed_ids != expected_ids:
        raise ReleaseBuildError("catalog package order does not match the product source")
    for definition, entry in zip(
        product_value["packages"], catalog_value["packages"], strict=True
    ):
        if (
            entry.get("version") != product_value["release"]["version"]
            or entry.get("displayName") != definition["displayName"]
        ):
            raise ReleaseBuildError("catalog package identity is not release-aligned")

    return (
        product_value,
        catalog_value,
        installer_bytes,
        snapshot_bytes,
        changelog_bytes,
    )


def _package_payload(
    repository_root: Path,
    catalog_value: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    package_id = entry["id"]
    package_root = repository_root / "packages" / package_id
    payload: dict[str, bytes] = {}
    inventory: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entry.get("files", []):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ReleaseBuildError("catalog package inventory is invalid")
        relative = _portable_path(item["path"])
        relative_text = relative.as_posix()
        if relative_text in seen or relative_text == "LICENSE":
            raise ReleaseBuildError("catalog package inventory contains a collision")
        content = _regular_file_bytes(
            package_root.joinpath(*relative.parts),
            label=f"{package_id} package file",
        )
        if _sha256(content) != item["sha256"]:
            raise ReleaseBuildError("catalog package digest does not match source bytes")
        seen.add(relative_text)
        payload[relative_text] = content
        inventory.append({"path": relative_text, "sha256": item["sha256"]})

    license_item = catalog_value.get("licenseFile")
    if (
        not isinstance(license_item, dict)
        or license_item.get("path") != "LICENSE"
        or not isinstance(license_item.get("sha256"), str)
    ):
        raise ReleaseBuildError("catalog license contract is invalid")
    license_bytes = _regular_file_bytes(repository_root / "LICENSE", label="license")
    if _sha256(license_bytes) != license_item["sha256"]:
        raise ReleaseBuildError("catalog license digest does not match source bytes")
    payload["LICENSE"] = license_bytes
    inventory.append({"path": "LICENSE", "sha256": license_item["sha256"]})
    inventory.sort(key=lambda item: item["path"])
    return payload, inventory


def _bundle_manifest(
    product_value: Mapping[str, Any],
    definition: Mapping[str, Any],
    inventory: list[dict[str, str]],
    installer_bytes: bytes,
    source_commit: str,
) -> dict[str, Any]:
    release = product_value["release"]
    return {
        "schemaVersion": 1,
        "release": {
            "repository": release["repository"],
            "sourceCommit": source_commit,
            "tag": release["tag"],
            "version": release["version"],
        },
        "package": {
            "displayName": definition["displayName"],
            "id": definition["id"],
            "version": release["version"],
        },
        "installer": {
            "path": "installer.py",
            "sha256": _sha256(installer_bytes),
        },
        "files": inventory,
    }


def _zip_info(name: str, *, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    return info


def _package_archive(
    product_value: Mapping[str, Any],
    catalog_value: Mapping[str, Any],
    definition: Mapping[str, Any],
    entry: Mapping[str, Any],
    installer_bytes: bytes,
    source_commit: str,
    repository_root: Path,
) -> bytes:
    payload, inventory = _package_payload(repository_root, catalog_value, entry)
    manifest = _bundle_manifest(
        product_value, definition, inventory, installer_bytes, source_commit
    )
    root = f"{definition['id']}-{product_value['release']['version']}"
    members: list[tuple[str, bytes, bool]] = [
        (f"{root}/bundle-manifest.json", _canonical_json_bytes(manifest), False),
        (f"{root}/installer.py", installer_bytes, True),
    ]
    members.extend(
        (f"{root}/package/{path}", payload[path], False)
        for path in sorted(payload)
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", allowZip64=True) as archive:
        for name, content, executable in members:
            archive.writestr(_zip_info(name, executable=executable), content)
    return stream.getvalue()


def _asset_entry(
    filename: str,
    content: bytes,
    media_type: str,
    *,
    package_id: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "filename": filename,
        "mediaType": media_type,
        "sha256": _sha256(content),
        "size": len(content),
    }
    if package_id is not None:
        value["packageId"] = package_id
    return value


def _primary_assets(
    repository_root: Path, source_commit: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    source_commit = _checked_commit(source_commit)
    (
        product_value,
        catalog_value,
        installer_bytes,
        snapshot_bytes,
        changelog_bytes,
    ) = _checked_sources(repository_root)
    catalog_by_id = {entry["id"]: entry for entry in catalog_value["packages"]}

    assets: dict[str, bytes] = {}
    manifest_entries: list[dict[str, Any]] = []
    for definition in product_value["packages"]:
        filename = definition["asset"]
        archive_bytes = _package_archive(
            product_value,
            catalog_value,
            definition,
            catalog_by_id[definition["id"]],
            installer_bytes,
            source_commit,
            repository_root,
        )
        assets[filename] = archive_bytes
        manifest_entries.append(
            _asset_entry(
                filename,
                archive_bytes,
                "application/zip",
                package_id=definition["id"],
            )
        )

    snapshot_name = product.SITE_SNAPSHOT_PATH.name
    extras = (
        ("installer.py", installer_bytes, "text/x-python"),
        (snapshot_name, snapshot_bytes, "application/json"),
        (CHANGELOG_NAME, changelog_bytes, "text/markdown"),
    )
    for filename, content, media_type in extras:
        if filename in assets:
            raise ReleaseBuildError("release asset filename collision")
        assets[filename] = content
        manifest_entries.append(_asset_entry(filename, content, media_type))

    release = product_value["release"]
    release_manifest = {
        "schemaVersion": 1,
        "release": {
            "repository": release["repository"],
            "sourceCommit": source_commit,
            "tag": release["tag"],
            "version": release["version"],
        },
        "manifestAsset": RELEASE_MANIFEST_NAME,
        "checksumSidecarSuffix": ".sha256",
        "assets": manifest_entries,
    }
    return assets, release_manifest


def _sidecar(filename: str, content: bytes) -> bytes:
    return f"{_sha256(content)}  {filename}\n".encode("ascii")


def _complete_assets(
    repository_root: Path, source_commit: str
) -> dict[str, bytes]:
    primary, manifest = _primary_assets(repository_root, source_commit)
    manifest_bytes = _canonical_json_bytes(manifest)
    primary[RELEASE_MANIFEST_NAME] = manifest_bytes
    complete = dict(primary)
    for filename, content in primary.items():
        sidecar_name = filename + ".sha256"
        if sidecar_name in complete:
            raise ReleaseBuildError("release checksum filename collision")
        complete[sidecar_name] = _sidecar(filename, content)
    return complete


def _write_new_file(path: Path, content: bytes, *, executable: bool = False) -> None:
    mode = 0o755 if executable else 0o644
    try:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, mode)
    except OSError as error:
        raise ReleaseBuildError("release asset could not be written without overwrite") from error


def build_release(
    output: Path,
    *,
    source_commit: str,
    repository_root: Path = REPOSITORY_ROOT,
) -> list[str]:
    """Build one complete immutable asset set into a new directory."""

    assets = _complete_assets(repository_root, source_commit)
    try:
        output.mkdir(mode=0o755)
    except OSError as error:
        raise ReleaseBuildError("release output directory must be new") from error
    for filename in sorted(assets):
        _write_new_file(
            output / filename,
            assets[filename],
            executable=filename == "installer.py",
        )
    verify_release(
        output,
        source_commit=source_commit,
        repository_root=repository_root,
    )
    return sorted(assets)


def _checked_release_directory(directory: Path) -> dict[str, bytes]:
    try:
        metadata = directory.lstat()
    except OSError as error:
        raise ReleaseBuildError("release directory is missing or unreadable") from error
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ReleaseBuildError("release directory must be one real directory")
    observed: dict[str, bytes] = {}
    try:
        children = sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError as error:
        raise ReleaseBuildError("release directory is unreadable") from error
    for path in children:
        if path.name in {".", ".."} or "/" in path.name or "\\" in path.name:
            raise ReleaseBuildError("release directory contains an unsafe name")
        observed[path.name] = _regular_file_bytes(path, label="release asset")
    return observed


def _manifest_asset_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("assets")
    if not isinstance(entries, list) or not entries:
        raise ReleaseBuildError("release manifest asset list is invalid")
    assets: dict[str, dict[str, Any]] = {}
    for entry in entries:
        allowed = {"filename", "mediaType", "sha256", "size", "packageId"}
        if (
            not isinstance(entry, dict)
            or not {"filename", "mediaType", "sha256", "size"}.issubset(entry)
            or not set(entry).issubset(allowed)
        ):
            raise ReleaseBuildError("release manifest asset entry is invalid")
        filename = entry["filename"]
        if (
            not isinstance(filename, str)
            or PurePosixPath(filename).name != filename
            or filename in assets
        ):
            raise ReleaseBuildError("release manifest asset filename is invalid")
        if (
            not isinstance(entry["mediaType"], str)
            or DIGEST_PATTERN.fullmatch(entry["sha256"]) is None
            or not isinstance(entry["size"], int)
            or isinstance(entry["size"], bool)
            or entry["size"] < 0
        ):
            raise ReleaseBuildError("release manifest asset metadata is invalid")
        assets[filename] = entry
    return assets


def _expected_bundle_manifest_from_sources(
    product_value: Mapping[str, Any],
    catalog_value: Mapping[str, Any],
    definition: Mapping[str, Any],
    entry: Mapping[str, Any],
    installer_bytes: bytes,
    source_commit: str,
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    payload, inventory = _package_payload(repository_root, catalog_value, entry)
    return (
        _bundle_manifest(
            product_value, definition, inventory, installer_bytes, source_commit
        ),
        payload,
    )


def _verify_package_archive(
    content: bytes,
    *,
    product_value: Mapping[str, Any],
    catalog_value: Mapping[str, Any],
    definition: Mapping[str, Any],
    entry: Mapping[str, Any],
    installer_bytes: bytes,
    source_commit: str,
    repository_root: Path,
) -> None:
    root = f"{definition['id']}-{product_value['release']['version']}"
    expected_manifest, payload = _expected_bundle_manifest_from_sources(
        product_value,
        catalog_value,
        definition,
        entry,
        installer_bytes,
        source_commit,
        repository_root,
    )
    expected_names = [
        f"{root}/bundle-manifest.json",
        f"{root}/installer.py",
        *(f"{root}/package/{name}" for name in sorted(payload)),
    ]
    try:
        with zipfile.ZipFile(io.BytesIO(content), mode="r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != expected_names or len(names) != len(set(names)):
                raise ReleaseBuildError("package archive is not package-only or ordered")
            for info in infos:
                relative = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                expected_mode = stat.S_IFREG | (
                    0o755 if info.filename == f"{root}/installer.py" else 0o644
                )
                if (
                    relative.is_absolute()
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or info.is_dir()
                    or stat.S_ISLNK(mode)
                    or mode != expected_mode
                    or info.date_time != FIXED_ZIP_TIME
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.create_system != 3
                ):
                    raise ReleaseBuildError("package archive metadata is not deterministic")
            manifest_bytes = archive.read(expected_names[0])
            if manifest_bytes != _canonical_json_bytes(expected_manifest):
                raise ReleaseBuildError("bundle manifest does not match source contract")
            if archive.read(expected_names[1]) != installer_bytes:
                raise ReleaseBuildError("bundle installer does not match release installer")
            for relative_text, expected_bytes in payload.items():
                if archive.read(f"{root}/package/{relative_text}") != expected_bytes:
                    raise ReleaseBuildError("bundle package bytes do not match source")
    except zipfile.BadZipFile as error:
        raise ReleaseBuildError("package archive is not a valid ZIP") from error


def verify_release(
    directory: Path,
    *,
    source_commit: str,
    repository_root: Path = REPOSITORY_ROOT,
) -> list[str]:
    """Verify exact built or downloaded assets without rebuilding them."""

    source_commit = _checked_commit(source_commit)
    observed = _checked_release_directory(directory)
    manifest_bytes = observed.get(RELEASE_MANIFEST_NAME)
    if manifest_bytes is None:
        raise ReleaseBuildError("release manifest asset is missing")
    manifest = _loads_strict(manifest_bytes, label="release manifest")
    if not isinstance(manifest, dict) or manifest_bytes != _canonical_json_bytes(manifest):
        raise ReleaseBuildError("release manifest serialization is not canonical")

    (
        product_value,
        catalog_value,
        installer_bytes,
        snapshot_bytes,
        changelog_bytes,
    ) = _checked_sources(repository_root)
    release = product_value["release"]
    expected_release = {
        "repository": release["repository"],
        "sourceCommit": source_commit,
        "tag": release["tag"],
        "version": release["version"],
    }
    if (
        set(manifest) != {
            "schemaVersion",
            "release",
            "manifestAsset",
            "checksumSidecarSuffix",
            "assets",
        }
        or manifest.get("schemaVersion") != 1
        or manifest.get("release") != expected_release
        or manifest.get("manifestAsset") != RELEASE_MANIFEST_NAME
        or manifest.get("checksumSidecarSuffix") != ".sha256"
    ):
        raise ReleaseBuildError("release manifest identity is invalid")

    manifest_assets = _manifest_asset_map(manifest)
    expected_primary_names = {
        *(definition["asset"] for definition in product_value["packages"]),
        "installer.py",
        product.SITE_SNAPSHOT_PATH.name,
        CHANGELOG_NAME,
    }
    if set(manifest_assets) != expected_primary_names:
        raise ReleaseBuildError("release manifest primary asset set is invalid")
    package_asset_names = {
        definition["asset"] for definition in product_value["packages"]
    }
    expected_media_types = {
        **{name: "application/zip" for name in package_asset_names},
        "installer.py": "text/x-python",
        product.SITE_SNAPSHOT_PATH.name: "application/json",
        CHANGELOG_NAME: "text/markdown",
    }
    for filename, media_type in expected_media_types.items():
        entry = manifest_assets[filename]
        if entry.get("mediaType") != media_type:
            raise ReleaseBuildError("release manifest media type is invalid")
        if filename not in package_asset_names and "packageId" in entry:
            raise ReleaseBuildError("non-package asset claims a package identity")
    all_primary = {*expected_primary_names, RELEASE_MANIFEST_NAME}
    expected_names = all_primary | {name + ".sha256" for name in all_primary}
    if set(observed) != expected_names:
        raise ReleaseBuildError("release directory has missing or extra assets")

    for filename, entry in manifest_assets.items():
        content = observed[filename]
        if entry["size"] != len(content) or entry["sha256"] != _sha256(content):
            raise ReleaseBuildError("release manifest asset digest or size is invalid")
    for filename in all_primary:
        if observed[filename + ".sha256"] != _sidecar(filename, observed[filename]):
            raise ReleaseBuildError("release checksum sidecar is invalid")

    if observed["installer.py"] != installer_bytes:
        raise ReleaseBuildError("release installer asset differs from checked source")
    if observed[product.SITE_SNAPSHOT_PATH.name] != snapshot_bytes:
        raise ReleaseBuildError("release site snapshot differs from checked source")
    if observed[CHANGELOG_NAME] != changelog_bytes:
        raise ReleaseBuildError("release changelog differs from checked source")

    catalog_by_id = {entry["id"]: entry for entry in catalog_value["packages"]}
    package_asset_ids: set[str] = set()
    for definition in product_value["packages"]:
        filename = definition["asset"]
        entry = manifest_assets[filename]
        if (
            entry.get("packageId") != definition["id"]
            or entry.get("mediaType") != "application/zip"
        ):
            raise ReleaseBuildError("package asset metadata is invalid")
        package_asset_ids.add(entry["packageId"])
        _verify_package_archive(
            observed[filename],
            product_value=product_value,
            catalog_value=catalog_value,
            definition=definition,
            entry=catalog_by_id[definition["id"]],
            installer_bytes=installer_bytes,
            source_commit=source_commit,
            repository_root=repository_root,
        )
    if package_asset_ids != set(product.PACKAGE_IDS):
        raise ReleaseBuildError("package assets are not one-to-one with public IDs")
    return sorted(observed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or verify immutable Agent Harnesses release assets."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--commit", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.command == "build":
            files = build_release(arguments.output, source_commit=arguments.commit)
            print(f"PASS: built and verified {len(files)} immutable release files")
        else:
            files = verify_release(arguments.input, source_commit=arguments.commit)
            print(f"PASS: verified {len(files)} exact release files")
    except ReleaseBuildError as error:
        print(f"ERROR [RELEASE_CONTRACT] {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
