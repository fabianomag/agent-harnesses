"""Generate or check all product-owned installer and README blocks."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

try:
    from tools import product
except ModuleNotFoundError:
    import product  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = Path("tools/installer.py.in")
INSTALLER_PATH = Path("installer.py")
TOKEN = "__EMBEDDED_PRODUCT_JSON__"
BEGIN_MARKER = "<!-- BEGIN GENERATED:PRODUCT -->"
END_MARKER = "<!-- END GENERATED:PRODUCT -->"


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise product.ProductContractError(
            f"generated README scaffold is unreadable: {path}"
        ) from error


def _replace_generated_block(path: Path, block: str) -> bytes:
    raw = _read_markdown(path)
    if raw.count(BEGIN_MARKER) != 1 or raw.count(END_MARKER) != 1:
        raise product.ProductContractError(
            f"README needs exactly one generated product block: {path}"
        )
    prefix, tail = raw.split(BEGIN_MARKER, 1)
    _old, suffix = tail.split(END_MARKER, 1)
    rendered = (
        prefix
        + BEGIN_MARKER
        + "\n"
        + block.rstrip()
        + "\n"
        + END_MARKER
        + suffix
    )
    return rendered.encode("utf-8")


def expected_readmes(
    repository_root: Path, value: dict
) -> dict[Path, bytes]:
    expected: dict[Path, bytes] = {}
    root_locales = (("en", Path("README.md")), ("ptBr", Path("README.pt-BR.md")))
    for language, relative in root_locales:
        expected[relative] = _replace_generated_block(
            repository_root / relative,
            product.root_readme_block(value, language),
        )
    for definition in value["packages"]:
        for language, name in (("en", "README.md"), ("ptBr", "README.pt-BR.md")):
            relative = Path("packages") / definition["id"] / name
            expected[relative] = _replace_generated_block(
                repository_root / relative,
                product.package_readme_block(value, definition, language),
            )
    return expected


def expected_operator_artifacts(value: dict) -> dict[Path, bytes]:
    """Render neutral machine and human operator contracts for every package."""
    expected: dict[Path, bytes] = {}
    for definition in value["packages"]:
        package_root = Path("packages") / definition["id"]
        expected[package_root / "operations.json"] = product.canonical_json_bytes(
            product.operations_document(value, definition)
        )
        expected[package_root / "OPERATOR_GUIDE.md"] = (
            product.operator_guide(value, definition, "en").rstrip() + "\n"
        ).encode("utf-8")
        expected[package_root / "OPERATOR_GUIDE.pt-BR.md"] = (
            product.operator_guide(value, definition, "ptBr").rstrip() + "\n"
        ).encode("utf-8")
    return expected


def expected_installer(repository_root: Path = REPOSITORY_ROOT) -> bytes:
    value = product.load_product(repository_root)
    try:
        template = (repository_root / TEMPLATE_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise product.ProductContractError("installer template is unreadable") from error
    if template.count(TOKEN) != 1:
        raise product.ProductContractError("installer template token is invalid")
    embedded = product.canonical_json_bytes(value).decode("utf-8").strip()
    return template.replace(TOKEN, embedded).encode("utf-8")


def check(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    value = product.load_product(repository_root)
    expected = {
        INSTALLER_PATH: expected_installer(repository_root),
        product.SITE_SNAPSHOT_PATH: product.canonical_json_bytes(
            product.site_snapshot(value)
        ),
    }
    expected.update(expected_readmes(repository_root, value))
    expected.update(expected_operator_artifacts(value))
    drift: list[str] = []
    for relative, content in expected.items():
        try:
            actual = (repository_root / relative).read_bytes()
        except OSError:
            actual = None
        if actual != content:
            drift.append(relative.as_posix())
    return sorted(set(drift))


def write(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    value = product.load_product(repository_root)
    expected = {
        INSTALLER_PATH: expected_installer(repository_root),
        product.SITE_SNAPSHOT_PATH: product.canonical_json_bytes(
            product.site_snapshot(value)
        ),
    }
    expected.update(expected_readmes(repository_root, value))
    expected.update(expected_operator_artifacts(value))
    written: list[str] = []
    for relative, content in expected.items():
        destination = repository_root / relative
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o755 if relative == INSTALLER_PATH else 0o644)
            os.replace(temporary, destination)
        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise
        written.append(relative.as_posix())
    return sorted(written)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or check product-derived files.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.write:
            paths = write()
            print(f"PASS: wrote {len(paths)} product-derived file(s)")
            return 0
        drift = check()
    except product.ProductContractError:
        print("FAIL: canonical product source violates its contract")
        return 1
    if drift:
        for path in drift:
            print(f"ERROR [PRODUCT_DRIFT] {path}: align with product/harnesses.json")
        return 1
    print("PASS: product-derived installer and README blocks match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
