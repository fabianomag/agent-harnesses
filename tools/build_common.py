"""Build or check catalog-derived public artifacts."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

try:
    from tools import catalog
except ModuleNotFoundError:  # Direct execution from the tools directory.
    import catalog  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise catalog.CommonContractError("generated target must not be a link")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        catalog.fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def check(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    """Return paths whose checked-in bytes differ from deterministic output."""

    drift: list[str] = []
    generated = catalog.generated_artifacts(repository_root)
    for relative, expected in generated.items():
        path = repository_root / relative
        try:
            actual = path.read_bytes()
        except OSError:
            actual = None
        if actual != expected:
            drift.append(relative.as_posix())

    managed = {
        catalog.CATALOG_PATH,
        *(
            path.relative_to(repository_root)
            for path in (repository_root / "graphs").glob("*.graph.json")
            if path.is_file()
        ),
        *(
            path.relative_to(repository_root)
            for path in (repository_root / "assets").glob("*.svg")
            if path.is_file()
        ),
    }
    drift.extend(
        path.as_posix() for path in sorted(managed - set(generated))
    )
    return sorted(set(drift))


def write(repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    """Write deterministic artifacts atomically and return their paths."""

    written: list[str] = []
    for relative, content in catalog.generated_artifacts(repository_root).items():
        _write_atomic(repository_root / relative, content)
        written.append(relative.as_posix())
    return written


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or check catalog-derived common artifacts."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="check without writing")
    mode.add_argument("--write", action="store_true", help="write generated artifacts")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.write:
            paths = write()
            print(f"PASS: wrote {len(paths)} deterministic artifact(s)")
            return 0
        drift = check()
    except catalog.CommonContractError:
        print("FAIL: common artifact source violates its contract")
        return 1

    if drift:
        for path in drift:
            print(f"ERROR [GENERATED_DRIFT] {path}: regenerate common artifacts")
        print(f"FAIL: {len(drift)} generated artifact(s) differ")
        return 1
    print("PASS: deterministic common artifacts match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
