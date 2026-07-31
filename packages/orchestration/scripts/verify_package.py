"""Run the package-local structural verifier."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from orchestration_harness.verifier import verify_package


def main() -> int:
    issues = verify_package(PACKAGE_ROOT)
    print(
        json.dumps(
            {"clean": not issues, "issues": issues},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
