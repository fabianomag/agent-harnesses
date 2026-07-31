"""Run a complete synthetic control-plane cycle in an isolated fixture."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from orchestration_harness.service import ControlPlane


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve(strict=True)
        control = ControlPlane(root)
        dry_run = control.plan_init(
            front_id="sample-front",
            display_name="Sample Front",
            path="fronts/sample-front",
            aliases=("sample",),
        )
        applied = control.init(
            front_id="sample-front",
            display_name="Sample Front",
            path="fronts/sample-front",
            aliases=("sample",),
        )
        control.digere(
            summary="Validated the synthetic first slice",
            pending="Register the validated delta",
        )
        control.registra(note="Synthetic structural evidence")
        control.encerra(
            summary="Completed the isolated structural cycle",
            next_action="Review the next synthetic slice",
        )
        sync = control.sync()
        result = {
            "applyChanged": applied["changed"],
            "dryRunChanged": dry_run["changed"],
            "finalSync": sync,
            "journalPresent": (root / ".orchestration-journal.json").exists(),
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if sync["clean"] and not result["journalPresent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
