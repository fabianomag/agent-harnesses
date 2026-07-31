"""Generate and structurally validate one isolated synthetic project fixture."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

import project_harness as harness  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        temporary_root = Path(directory).resolve(strict=True)
        root = temporary_root / "synthetic-project"
        root.mkdir()
        harness.initialize(root)

        expected_files = {
            harness.STATE_PATH,
            *(spec.path for spec in harness.MANAGED_FILES),
        }
        expected_directories = set(harness.REQUIRED_DIRECTORIES)
        for relative in expected_directories:
            if not (root / relative).is_dir():
                raise AssertionError(f"missing generated directory: {relative}")
        for relative in expected_files:
            if not (root / relative).is_file():
                raise AssertionError(f"missing generated file: {relative}")

        state = json.loads(
            (root / harness.STATE_PATH).read_text(encoding="utf-8")
        )
        if state != harness._empty_state():
            raise AssertionError("generated canonical state is not empty baseline state")
        for spec in harness.MANAGED_FILES:
            data = (root / spec.path).read_bytes()
            if data.count(spec.begin_marker) != 1:
                raise AssertionError(f"invalid begin marker count: {spec.path}")
            if data.count(spec.end_marker) != 1:
                raise AssertionError(f"invalid end marker count: {spec.path}")

        issues = harness.verify_root(root)
        if issues:
            raise AssertionError(
                "\n".join(issue.render() for issue in issues)
            )
        required_count = len(expected_files) + len(expected_directories)
        print(
            "PASS: generated synthetic fixture structurally verified "
            f"({required_count} required paths)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
