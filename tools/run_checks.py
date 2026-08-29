"""Run the complete local automated and structural integration checks."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    category: str
    name: str
    command: tuple[str, ...]


def _python(*arguments: str) -> tuple[str, ...]:
    return (sys.executable, "-B", *arguments)


CHECKS = (
    Check(
        "automated",
        "common unit and integration tests",
        _python("-m", "unittest", "discover", "-s", "tests", "-v"),
    ),
    Check(
        "automated",
        "project-harness package tests",
        _python(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/project-harness/tests",
            "-v",
        ),
    ),
    Check(
        "automated",
        "workspace-coordination package tests",
        _python(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/workspace-coordination/tests",
            "-v",
        ),
    ),
    Check(
        "automated",
        "cross-project package tests",
        _python("packages/cross-project/tests/test_cross_project.py"),
    ),
    Check(
        "automated",
        "orchestration package tests",
        _python(
            "-m",
            "unittest",
            "discover",
            "-s",
            "packages/orchestration/tests",
            "-v",
        ),
    ),
    Check(
        "structural",
        "generated project-harness fixture",
        _python("packages/project-harness/tests/validate_generated_fixture.py"),
    ),
    Check(
        "structural",
        "orchestration package structure",
        _python("packages/orchestration/scripts/verify_package.py"),
    ),
    Check(
        "structural",
        "orchestration isolated structural cycle",
        _python("packages/orchestration/scripts/structural_check.py"),
    ),
    Check(
        "structural",
        "deterministic common artifacts",
        _python("tools/build_common.py", "--check"),
    ),
    Check(
        "structural",
        "product-derived installer and documentation",
        _python("tools/build_product.py", "--check"),
    ),
    Check(
        "structural",
        "repository contracts and public safety",
        _python("tools/validate.py"),
    ),
    Check(
        "structural",
        "Git whitespace",
        ("git", "diff", "--check"),
    ),
)

def run(checks: Sequence[Check] = CHECKS) -> int:
    failures: list[Check] = []
    totals = {"automated": 0, "structural": 0}
    passed = {"automated": 0, "structural": 0}

    for check in checks:
        totals[check.category] += 1
        print(f"\n{check.category.upper()} — {check.name}", flush=True)
        process = subprocess.run(
            check.command,
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        if process.returncode == 0:
            passed[check.category] += 1
        else:
            failures.append(check)

    print(
        f"\nAUTOMATED: {passed['automated']}/{totals['automated']} "
        "local checks passed"
    )
    print(
        f"STRUCTURAL: {passed['structural']}/{totals['structural']} "
        "local checks passed"
    )
    print(
        "MANUAL CODEX: not executed by this runner; publishable manual "
        "evidence must come from a release manifest or evidence asset bound "
        "to the exact published package version and commit"
    )
    if failures:
        print(f"FAIL: {len(failures)} integration check(s) failed")
        return 1
    print(
        "PASS: automated and structural local checks completed; "
        "no manual evidence claimed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
