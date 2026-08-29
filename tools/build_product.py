"""Generate or check product-derived installer bytes."""

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
    expected = expected_installer(repository_root)
    try:
        actual = (repository_root / INSTALLER_PATH).read_bytes()
    except OSError:
        actual = None
    return [] if actual == expected else [INSTALLER_PATH.as_posix()]


def write(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    destination = repository_root / INSTALLER_PATH
    content = expected_installer(repository_root)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".installer.", suffix=".tmp", dir=repository_root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o755)
        os.replace(temporary, destination)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return [INSTALLER_PATH.as_posix()]


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
        print("ERROR [GENERATED_DRIFT] installer.py: regenerate product artifacts")
        return 1
    print("PASS: product-derived installer matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
