"""Deterministic public catalog and graph artifact construction."""

from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable

try:
    from tools import product
except ModuleNotFoundError:
    import product  # type: ignore[no-redef]


PACKAGE_ORDER = (
    "project-harness",
    "workspace-coordination",
    "cross-project",
    "orchestration",
)

EXPECTED_PACKAGES = {
    "project-harness": "Project Harness",
    "workspace-coordination": "Workspace Harness",
    "cross-project": "Multi-Project Harness",
    "orchestration": "Control Plane Harness",
}

CATALOG_PATH = Path("catalog/harnesses.json")
GRAPH_SPEC_PATH = Path("graphs/harnesses.graph.json")
GRAPH_ASSET_PATH = Path("assets/harnesses.svg")
CATALOG_SCHEMA_REFERENCE = "../schemas/harness-catalog.schema.json"
RECEIPT_NAME = ".harness-package-receipt.json"
COMMON_LICENSE_NAME = "LICENSE"
PUBLIC_REPOSITORY_URL = "https://github.com/fabianomag/agent-harnesses"
BADGE_NAMES = ("Context", "Skill", "Harness", "Loop", "Guardrails")
BADGE_LEVELS = ("absent", "basic", "partial", "strong", "verified")
SKILL_PATHS = {
    "project-harness": "adapters/openai/project-harness/SKILL.md",
    "workspace-coordination": "adapters/openai/workspace-coordination/SKILL.md",
    "cross-project": "adapters/openai/cross-project/SKILL.md",
    "orchestration": "adapters/openai/orchestration/SKILL.md",
}
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

GRAPH_FLOWS = {
    "project-harness": (
        (
            "skill-trigger",
            "Skill trigger",
            "Select the project-local operating contract.",
        ),
        (
            "initializer",
            "Initializer",
            "Preview and create the bounded managed structure.",
        ),
        (
            "local-context",
            "Local context",
            "Open durable project context and current state.",
        ),
        (
            "work-cycle",
            "Work cycle",
            "Digest, checkpoint, and continue one bounded project cycle.",
        ),
        (
            "finalizer",
            "Finalizer",
            "Close the work block with explicit recorded content.",
        ),
        (
            "durable-next",
            "Durable next",
            "Reopen from the persisted next action.",
        ),
    ),
    "workspace-coordination": (
        (
            "workspace-coordinator",
            "Workspace coordinator",
            "Open one explicit containing workspace.",
        ),
        (
            "child-index",
            "Child index",
            "Select only an explicitly registered child folder.",
        ),
        (
            "shared-boundary-governance",
            "Shared boundary / governance",
            "Keep shared constraints and concise deltas at the coordinator.",
        ),
        (
            "child-local-owner",
            "Child-local owner",
            "Leave detailed context and execution state with the child.",
        ),
        (
            "reflection",
            "Reflection",
            "Return only an explicit shared boundary delta.",
        ),
    ),
    "cross-project": (
        (
            "named-target",
            "Named target",
            "Select one explicitly named project front.",
        ),
        (
            "manifest",
            "Manifest",
            "Read the canonical root-relative coordination authority.",
        ),
        (
            "structural-sync",
            "Structural sync",
            "Validate structure and generated projections without repair.",
        ),
        (
            "front-state",
            "Front state",
            "Route the smallest live coordination checkpoint.",
        ),
        (
            "local-owner",
            "Local owner",
            "Keep dense implementation state inside the selected project.",
        ),
        (
            "transversal-reflection",
            "Transversal reflection",
            "Record the explicit cross-project handoff and resumption trigger.",
        ),
    ),
    "orchestration": (
        (
            "strategic-opening",
            "Strategic opening",
            "Open the Master control plane without mutation.",
        ),
        (
            "registry-validation",
            "Registry validation",
            "Validate the canonical registry and front boundaries.",
        ),
        (
            "dry-run",
            "Dry-run",
            "Preview the exact transactional mutation.",
        ),
        (
            "transactional-apply-rollback",
            "Transactional apply / rollback",
            "Apply through a journal or recover verified prior bytes.",
        ),
        (
            "pending-reflection",
            "Pending reflection",
            "Record explicit lifecycle evidence without executing a project.",
        ),
        (
            "verified-sync",
            "Verified sync",
            (
                "Confirm registry and generated state are structurally "
                "consistent. This runtime result is structural evidence, not "
                "a published-version verified badge."
            ),
        ),
    ),
}

PACKAGE_PROFILES: dict[str, dict[str, Any]] = {
    "project-harness": {
        "purpose": (
            "Preserve durable context and a resumable work cycle inside one "
            "explicitly selected local project."
        ),
        "complexity": {
            "level": "low-to-intermediate",
            "description": (
                "One root, one canonical state file, and one project-local "
                "lifecycle."
            ),
        },
        "evolutionaryPosition": {
            "boundary": "single-project",
            "description": (
                "One project is the complete coordination boundary; no "
                "cross-project state is introduced."
            ),
            "ranking": False,
        },
        "audience": {
            "primary": "project-maintainers",
            "description": (
                "People or agents maintaining one local project with explicit "
                "context, decisions, and next actions."
            ),
        },
        "limitations": [
            (
                "It does not coordinate workspaces, sibling projects, external "
                "services, releases, or publication."
            ),
            (
                "Multi-file operations are not crash-atomic, and hostile "
                "concurrent writers are unsupported."
            ),
        ],
        "badges": {
            "Context": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/project-harness/tests/"
                            "test_project_harness.py"
                        ),
                        "claim": (
                            "Exercises canonical state and deterministic "
                            "managed context projections."
                        ),
                    }
                ],
            },
            "Skill": {
                "level": "partial",
                "evidence": [
                    {
                        "method": "structural",
                        "path": (
                            "adapters/openai/project-harness/SKILL.md"
                        ),
                        "claim": (
                            "Provides an optional Codex Skill adapter outside "
                            "the agent-agnostic core package; no adapter is "
                            "installed by the default release flow."
                        ),
                    }
                ],
            },
            "Harness": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": "packages/project-harness/project_harness.py",
                        "claim": (
                            "Provides the implemented root-bound command "
                            "surface exercised by package tests."
                        ),
                    }
                ],
            },
            "Loop": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/project-harness/tests/"
                            "test_project_harness.py"
                        ),
                        "claim": (
                            "Exercises initialization, opening, checkpoint, "
                            "closeout, and durable resumption."
                        ),
                    }
                ],
            },
            "Guardrails": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/project-harness/tests/"
                            "test_project_harness.py"
                        ),
                        "claim": (
                            "Exercises dry-run, bounded paths, collision "
                            "handling, rollback, and link rejection."
                        ),
                    }
                ],
            },
        },
        "evidence": {
            "automated": {
                "method": "automated",
                "status": "defined",
                "references": [
                    "packages/project-harness/tests/test_project_harness.py"
                ],
                "description": (
                    "Repeatable package tests are included; this catalog does "
                    "not record a candidate-bound result."
                ),
            },
            "structural": {
                "method": "structural",
                "status": "defined",
                "references": [
                    (
                        "packages/project-harness/tests/"
                        "validate_generated_fixture.py"
                    )
                ],
                "description": (
                    "A repeatable generated-fixture check is included; this "
                    "catalog does not record a candidate-bound result."
                ),
            },
            "manualCodex": {
                "method": "manual-codex",
                "status": "pending",
                "references": ["packages/project-harness/README.md"],
                "description": (
                    "A fresh Project Harness walkthrough must be executed "
                    "against the next candidate; no manual result is claimed "
                    "here."
                ),
            },
        },
    },
    "workspace-coordination": {
        "purpose": (
            "Coordinate explicitly registered autonomous child folders inside "
            "one containing workspace while preserving child-local ownership."
        ),
        "complexity": {
            "level": "intermediate",
            "description": (
                "One coordinator plus explicit child ownership and shared "
                "governance boundaries."
            ),
        },
        "evolutionaryPosition": {
            "boundary": "contained-workspace",
            "description": (
                "One containing workspace owns the child index and shared "
                "governance while each child owns its detailed state."
            ),
            "ranking": False,
        },
        "audience": {
            "primary": "workspace-coordinators",
            "description": (
                "Operators coordinating autonomous child folders contained by "
                "one explicit local root."
            ),
        },
        "limitations": [
            (
                "It does not discover children, scan adjacent folders, "
                "dispatch agents, or execute child work."
            ),
            (
                "Version 0.2.2 supports one mutating writer per coordinator "
                "root."
            ),
        ],
        "badges": {
            "Context": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/workspace-coordination/tests/"
                            "test_workspace_coordination.py"
                        ),
                        "claim": (
                            "Exercises the child index, shared views, and "
                            "child-local continuity."
                        ),
                    }
                ],
            },
            "Skill": {
                "level": "partial",
                "evidence": [
                    {
                        "method": "structural",
                        "path": (
                            "adapters/openai/workspace-coordination/SKILL.md"
                        ),
                        "claim": (
                            "Provides an optional Codex Skill adapter outside "
                            "the agent-agnostic core package; no adapter is "
                            "installed by the default release flow."
                        ),
                    }
                ],
            },
            "Harness": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/workspace-coordination/"
                            "workspace_coordination.py"
                        ),
                        "claim": (
                            "Provides the implemented explicit-root command "
                            "surface exercised by package tests."
                        ),
                    }
                ],
            },
            "Loop": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/workspace-coordination/tests/"
                            "test_workspace_coordination.py"
                        ),
                        "claim": (
                            "Exercises child selection, local recording, "
                            "shared reflection, closeout, and reopening."
                        ),
                    }
                ],
            },
            "Guardrails": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/workspace-coordination/tests/"
                            "test_workspace_coordination.py"
                        ),
                        "claim": (
                            "Exercises explicit registration, dry-run/apply, "
                            "root boundaries, collisions, and link rejection."
                        ),
                    }
                ],
            },
        },
        "evidence": {
            "automated": {
                "method": "automated",
                "status": "defined",
                "references": [
                    (
                        "packages/workspace-coordination/tests/"
                        "test_workspace_coordination.py"
                    )
                ],
                "description": (
                    "Repeatable package tests are included; this catalog does "
                    "not record a candidate-bound result."
                ),
            },
            "structural": {
                "method": "structural",
                "status": "defined",
                "references": ["tests/test_common.py", "tools/validate.py"],
                "description": (
                    "Installed-copy and repository structure checks are "
                    "defined; this catalog does not record a candidate-bound "
                    "result."
                ),
            },
            "manualCodex": {
                "method": "manual-codex",
                "status": "pending",
                "references": ["packages/workspace-coordination/README.md"],
                "description": (
                    "A fresh Workspace Coordination walkthrough must be "
                    "executed against the next candidate; no manual result is "
                    "claimed here."
                ),
            },
        },
    },
    "cross-project": {
        "purpose": (
            "Coordinate explicit named projects through canonical transversal "
            "state, structural sync, and bounded reflection."
        ),
        "complexity": {
            "level": "high",
            "description": (
                "Named independent fronts, transversal state, cooperative "
                "locking, and rollback-protected multi-file updates."
            ),
        },
        "evolutionaryPosition": {
            "boundary": "independent-projects",
            "description": (
                "Independent project fronts remain local owners while one "
                "selected root holds transversal coordination state."
            ),
            "ranking": False,
        },
        "audience": {
            "primary": "cross-project-coordinators",
            "description": (
                "Operators managing named handoffs and shared state across "
                "independent local projects."
            ),
        },
        "limitations": [
            (
                "Rollback and coherence cover catchable failures and "
                "cooperative readers, not physical crash-safe multi-file "
                "atomicity after process kill or power loss."
            ),
            (
                "Adversarial replacement of the selected root inode remains "
                "a residual risk."
            ),
        ],
        "badges": {
            "Context": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/cross-project/tests/"
                            "test_cross_project.py"
                        ),
                        "claim": (
                            "Exercises canonical front state and bounded "
                            "managed projections."
                        ),
                    }
                ],
            },
            "Skill": {
                "level": "partial",
                "evidence": [
                    {
                        "method": "structural",
                        "path": "adapters/openai/cross-project/SKILL.md",
                        "claim": (
                            "Provides an optional Codex Skill adapter outside "
                            "the agent-agnostic core package; no adapter is "
                            "installed by the default release flow."
                        ),
                    }
                ],
            },
            "Harness": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/cross-project/scripts/"
                            "cross_project.py"
                        ),
                        "claim": (
                            "Provides the implemented named-target command "
                            "surface exercised by package tests."
                        ),
                    }
                ],
            },
            "Loop": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/cross-project/tests/"
                            "test_cross_project.py"
                        ),
                        "claim": (
                            "Exercises registration, structural sync, "
                            "checkpointing, closeout, and transversal "
                            "reflection."
                        ),
                    }
                ],
            },
            "Guardrails": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/cross-project/tests/"
                            "test_cross_project.py"
                        ),
                        "claim": (
                            "Exercises bounded paths, cooperative locking, "
                            "rollback, collision handling, and link rejection."
                        ),
                    }
                ],
            },
        },
        "evidence": {
            "automated": {
                "method": "automated",
                "status": "defined",
                "references": [
                    "packages/cross-project/tests/test_cross_project.py"
                ],
                "description": (
                    "Repeatable package tests are included; this catalog does "
                    "not record a candidate-bound result."
                ),
            },
            "structural": {
                "method": "structural",
                "status": "defined",
                "references": ["tests/test_common.py", "tools/validate.py"],
                "description": (
                    "Installed-copy and repository structure checks are "
                    "defined; this catalog does not record a candidate-bound "
                    "result."
                ),
            },
            "manualCodex": {
                "method": "manual-codex",
                "status": "pending",
                "references": [
                    "packages/cross-project/tests/manual_walkthrough.sh"
                ],
                "description": (
                    "A fresh Cross-Project walkthrough must be executed against "
                    "the next candidate; the procedure is not evidence of "
                    "execution."
                ),
            },
        },
    },
    "orchestration": {
        "purpose": (
            "Operate a transactional local control plane with a strict "
            "registry, explicit lifecycle records, recovery, and structural "
            "sync."
        ),
        "complexity": {
            "level": "advanced",
            "description": (
                "A strict registry, journaled transactions, explicit recovery, "
                "and validated lifecycle coordination."
            ),
        },
        "evolutionaryPosition": {
            "boundary": "transactional-orchestration",
            "description": (
                "One Master control plane coordinates registered fronts "
                "through validated transactions without executing projects."
            ),
            "ranking": False,
        },
        "audience": {
            "primary": "orchestration-operators",
            "description": (
                "Operators who need a transactional local registry, explicit "
                "front focus, lifecycle records, and journal recovery."
            ),
        },
        "limitations": [
            (
                "It does not call a model, dispatch agents, execute project "
                "commands, publish content, or infer reflections."
            ),
            (
                "Its transactional guarantees remain bounded by cooperative "
                "local filesystem and recovery assumptions."
            ),
        ],
        "badges": {
            "Context": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/orchestration/tests/test_workflow.py"
                        ),
                        "claim": (
                            "Exercises canonical registry state, lifecycle "
                            "records, and deterministic projections."
                        ),
                    }
                ],
            },
            "Skill": {
                "level": "partial",
                "evidence": [
                    {
                        "method": "structural",
                        "path": "adapters/openai/orchestration/SKILL.md",
                        "claim": (
                            "Provides an optional Codex Skill adapter outside "
                            "the agent-agnostic core package; no adapter is "
                            "installed by the default release flow."
                        ),
                    }
                ],
            },
            "Harness": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": "packages/orchestration/hq.py",
                        "claim": (
                            "Provides the implemented transactional local "
                            "control-plane command surface."
                        ),
                    }
                ],
            },
            "Loop": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/orchestration/tests/test_workflow.py"
                        ),
                        "claim": (
                            "Exercises opening, focus, digest, record, "
                            "closeout, and structural sync."
                        ),
                    }
                ],
            },
            "Guardrails": {
                "level": "strong",
                "evidence": [
                    {
                        "method": "automated",
                        "path": (
                            "packages/orchestration/tests/"
                            "test_transaction.py"
                        ),
                        "claim": (
                            "Exercises journaling, bounded paths, locking, "
                            "rollback, and explicit recovery."
                        ),
                    }
                ],
            },
        },
        "evidence": {
            "automated": {
                "method": "automated",
                "status": "defined",
                "references": [
                    "packages/orchestration/tests/test_workflow.py",
                    "packages/orchestration/tests/test_transaction.py",
                ],
                "description": (
                    "Repeatable package tests are included; this catalog does "
                    "not record a candidate-bound result."
                ),
            },
            "structural": {
                "method": "structural",
                "status": "defined",
                "references": [
                    "packages/orchestration/scripts/verify_package.py",
                    "packages/orchestration/scripts/structural_check.py",
                ],
                "description": (
                    "Repeatable package structure and isolated-cycle checks "
                    "are included; this catalog does not record a "
                    "candidate-bound result."
                ),
            },
            "manualCodex": {
                "method": "manual-codex",
                "status": "pending",
                "references": ["packages/orchestration/README.md"],
                "description": (
                    "A fresh Orchestration walkthrough must be executed "
                    "against the next candidate; no manual result is claimed "
                    "here."
                ),
            },
        },
    },
}


class CommonContractError(ValueError):
    """Raised when a common artifact cannot be derived safely."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CommonContractError("JSON contains duplicate object properties")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    """Load strict UTF-8 JSON while rejecting duplicate object properties."""

    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except CommonContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CommonContractError("file is not readable strict UTF-8 JSON") from error


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON with stable indentation, ordering, LF, and final newline."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def parse_skill_frontmatter(text: str, *, package_id: str) -> dict[str, str]:
    """Parse the deliberately small frontmatter contract used by packaged Skills."""

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise CommonContractError("packaged Skill is missing frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise CommonContractError("packaged Skill frontmatter is not closed") from error
    if closing <= 1:
        raise CommonContractError("packaged Skill frontmatter is empty")

    frontmatter: dict[str, str] = {}
    for line in lines[1:closing]:
        key, separator, raw_value = line.partition(":")
        value = raw_value[1:] if raw_value.startswith(" ") else ""
        if (
            separator != ":"
            or not key
            or key != key.strip()
            or raw_value != f" {value}"
            or value != value.strip()
            or not value
        ):
            raise CommonContractError("packaged Skill frontmatter is invalid")
        if key in frontmatter:
            raise CommonContractError(
                "packaged Skill frontmatter contains a duplicate key"
            )
        frontmatter[key] = value

    if set(frontmatter) != {"name", "description"}:
        raise CommonContractError(
            "packaged Skill frontmatter fields do not match the contract"
        )
    if frontmatter["name"] != package_id:
        raise CommonContractError(
            "packaged Skill frontmatter name does not match its package"
        )
    if "\n" in frontmatter["description"] or not frontmatter["description"].strip():
        raise CommonContractError(
            "packaged Skill frontmatter description is invalid"
        )
    if closing + 1 >= len(lines) or not any(
        line.strip() for line in lines[closing + 1 :]
    ):
        raise CommonContractError("packaged Skill body is empty")
    return frontmatter


def _is_link_like(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise CommonContractError("path metadata is unreadable") from error
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _relative_files(package_root: Path) -> Iterable[Path]:
    if _is_link_like(package_root) or not package_root.is_dir():
        raise CommonContractError("package root must be a real directory")

    paths = sorted(
        package_root.rglob("*"),
        key=lambda path: path.relative_to(package_root).as_posix(),
    )
    for path in paths:
        relative = path.relative_to(package_root)
        if _is_link_like(path):
            raise CommonContractError("package payload must not contain links")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CommonContractError("package payload contains a non-file entry")
        if relative.as_posix() in {RECEIPT_NAME, COMMON_LICENSE_NAME}:
            raise CommonContractError("package payload uses a reserved common name")
        yield relative


def _file_inventory(package_root: Path) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    for relative in _relative_files(package_root):
        try:
            content = (package_root / relative).read_bytes()
        except OSError as error:
            raise CommonContractError("package payload is unreadable") from error
        inventory.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    if not inventory:
        raise CommonContractError("package payload must not be empty")
    return inventory


def _repository_file(repository_root: Path, reference: str) -> Path:
    relative = Path(reference)
    if relative.is_absolute() or not relative.parts:
        raise CommonContractError("public evidence reference is not root-relative")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise CommonContractError("public evidence reference is not portable")

    candidate = repository_root
    for part in relative.parts:
        candidate = candidate / part
        if _is_link_like(candidate):
            raise CommonContractError("public evidence reference contains a link")
    if not candidate.is_file():
        raise CommonContractError(
            "public evidence reference does not resolve to a regular file"
        )
    return candidate


def _validated_profile(
    repository_root: Path,
    *,
    package_id: str,
) -> dict[str, Any]:
    profile = copy.deepcopy(PACKAGE_PROFILES[package_id])
    badges = profile.get("badges")
    if not isinstance(badges, dict) or tuple(badges) != BADGE_NAMES:
        raise CommonContractError("package badge dimensions are invalid")
    for badge in badges.values():
        level = badge.get("level")
        if level not in BADGE_LEVELS or level == "verified":
            raise CommonContractError(
                "local package badge level exceeds available evidence"
            )
        evidence = badge.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise CommonContractError("package badge evidence is missing")
        for item in evidence:
            if (
                not isinstance(item, dict)
                or set(item) != {"method", "path", "claim"}
                or item.get("method") not in {"automated", "structural"}
                or not isinstance(item.get("claim"), str)
                or not item["claim"].strip()
            ):
                raise CommonContractError("package badge evidence is invalid")
            _repository_file(repository_root, item["path"])

    evidence_surface = profile.get("evidence")
    expected_evidence = {
        "automated": ("automated", "defined"),
        "structural": ("structural", "defined"),
        "manualCodex": ("manual-codex", "pending"),
    }
    if not isinstance(evidence_surface, dict) or tuple(
        evidence_surface
    ) != tuple(expected_evidence):
        raise CommonContractError("package evidence surface is invalid")
    for key, (method, status) in expected_evidence.items():
        entry = evidence_surface[key]
        if (
            not isinstance(entry, dict)
            or set(entry)
            != {"method", "status", "references", "description"}
            or entry.get("method") != method
            or entry.get("status") != status
            or not isinstance(entry.get("references"), list)
            or not entry["references"]
            or not isinstance(entry.get("description"), str)
            or not entry["description"].strip()
        ):
            raise CommonContractError("package evidence method is invalid")
        for reference in entry["references"]:
            if not isinstance(reference, str):
                raise CommonContractError("package evidence reference is invalid")
            _repository_file(repository_root, reference)

    limitations = profile.get("limitations")
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(
            not isinstance(limitation, str) or not limitation.strip()
            for limitation in limitations
        )
    ):
        raise CommonContractError("package limitations are invalid")
    return profile


def _graph_descriptor(package_id: str) -> dict[str, Any]:
    return {
        "id": f"{package_id}-flow",
        "spec": f"graphs/{package_id}.graph.json",
        "staticAsset": f"assets/{package_id}.svg",
        "flow": [
            {
                "id": node_id,
                "label": label,
                "description": description,
            }
            for node_id, label, description in GRAPH_FLOWS[package_id]
        ],
    }


def _release_tag(package_id: str, version: str) -> str:
    del package_id
    return f"v{version}"


def _published_immutable_links(
    package_id: str,
    version: str,
    interactive_url: str,
) -> dict[str, dict[str, str]]:
    tag = _release_tag(package_id, version)
    release_url = f"{PUBLIC_REPOSITORY_URL}/releases/tag/{tag}"
    install_url = (
        f"{PUBLIC_REPOSITORY_URL}/releases/download/{tag}/"
        f"{package_id}-{version}.zip"
    )
    return {
        "documentation": {
            "status": "published",
            "url": (
                f"{PUBLIC_REPOSITORY_URL}/blob/{tag}/packages/"
                f"{package_id}/README.md"
            ),
        },
        "prompt": {
            "status": "published",
            "url": install_url,
        },
        "source": {
            "status": "published",
            "url": (
                f"{PUBLIC_REPOSITORY_URL}/tree/{tag}/packages/{package_id}"
            ),
        },
        "release": {"status": "published", "url": release_url},
        "interactiveDiagram": {
            # The site is deployed by a separate single-writer task after this
            # immutable repository snapshot is handed off.
            "status": "planned",
            "url": interactive_url,
        },
    }


def _release_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Keep candidate-bound manual evidence pending until it actually exists."""
    return copy.deepcopy(evidence)


def _agent_compatibility() -> dict[str, Any]:
    return {
        "description": (
            "Agent compatibility is separate from package capability badges "
            "and from published-version verification."
        ),
        "codex": {
            "status": "compatible",
            "verification": "pending",
            "verifiedEligible": False,
            "scope": (
                "The agent-agnostic CLI, operations contract, and Markdown "
                "guides are primary. Optional Codex adapters remain outside "
                "the core assets; a fresh walkthrough of the exact v0.2.2 "
                "release assets is still pending."
            ),
        },
        "otherAgents": {
            "status": "compatible",
            "verification": "unverified",
            "verifiedEligible": False,
            "scope": (
                "The core uses explicit CLI, JSON, and Markdown contracts. "
                "Claude Code Desktop receives a bounded compatibility smoke; "
                "no generic agent-specific Skill behavior is claimed."
            ),
        },
    }


def _validate_manifest_identity(
    manifest: Any,
    *,
    package_id: str,
    display_name: str,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise CommonContractError("package manifest must be an object")
    required = {
        "$schema",
        "schemaVersion",
        "id",
        "displayName",
        "version",
        "license",
        "status",
        "readme",
    }
    if set(manifest) != required:
        raise CommonContractError("package manifest fields do not match the contract")
    if manifest.get("$schema") != "../../schemas/harness-package.schema.json":
        raise CommonContractError("package manifest schema reference is invalid")
    if manifest.get("schemaVersion") != 1:
        raise CommonContractError("package manifest schema version is invalid")
    if manifest.get("id") != package_id:
        raise CommonContractError("package manifest ID does not match its directory")
    if manifest.get("displayName") != display_name:
        raise CommonContractError("package manifest display name is invalid")
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise CommonContractError("package manifest version is invalid")
    if manifest.get("license") != "MIT":
        raise CommonContractError("package manifest license is invalid")
    if manifest.get("status") not in {"contract-only", "implemented"}:
        raise CommonContractError("package manifest status is invalid")
    if manifest.get("readme") != "README.md":
        raise CommonContractError("package manifest README reference is invalid")
    return manifest


def expected_catalog(repository_root: Path) -> dict[str, Any]:
    """Derive the public catalog from package contracts and exact payload bytes."""

    product_value = product.load_product(repository_root)
    definitions = product.package_map(product_value)
    release = product_value["release"]
    interactive_url = release["site"]["en"]

    license_path = repository_root / COMMON_LICENSE_NAME
    try:
        license_bytes = license_path.read_bytes()
        license_text = license_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise CommonContractError("common license is not readable UTF-8") from error
    if not license_text.startswith("MIT License\n"):
        raise CommonContractError("common license is not the MIT license text")
    if "Copyright (c) 2026 Fabiano Magalhães" not in license_text:
        raise CommonContractError("common license holder is not documented")

    packages: list[dict[str, Any]] = []
    for package_id in PACKAGE_ORDER:
        definition = definitions[package_id]
        display_name = definition["displayName"]
        if display_name != EXPECTED_PACKAGES[package_id]:
            raise CommonContractError("product display name is invalid")
        package_root = repository_root / "packages" / package_id
        manifest_path = package_root / "harness.package.json"
        manifest = _validate_manifest_identity(
            load_json_strict(manifest_path),
            package_id=package_id,
            display_name=display_name,
        )
        if manifest["version"] != release["version"]:
            raise CommonContractError("package version differs from collection release")
        skill_path = repository_root / SKILL_PATHS[package_id]
        try:
            skill_text = skill_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise CommonContractError(
                "optional Skill adapter is not readable UTF-8"
            ) from error
        parse_skill_frontmatter(skill_text, package_id=package_id)
        profile = _validated_profile(repository_root, package_id=package_id)
        packages.append(
            {
                "id": package_id,
                "displayName": display_name,
                "version": manifest["version"],
                "license": manifest["license"],
                "artifactStatus": {
                    "implementation": manifest["status"],
                    "publication": "published",
                },
                "manifest": manifest_path.relative_to(repository_root).as_posix(),
                "purpose": definition["content"]["en"]["summary"],
                "complexity": {
                    "level": definition["complexity"]["level"],
                    "description": definition["content"]["en"]["bestFor"],
                },
                "evolutionaryPosition": profile["evolutionaryPosition"],
                "audience": {
                    "primary": profile["audience"]["primary"],
                    "description": definition["content"]["en"]["bestFor"],
                },
                "badges": profile["badges"],
                "limitations": [
                    definition["content"]["en"]["notFor"],
                    *profile["limitations"],
                ],
                "graph": _graph_descriptor(package_id),
                "immutableLinks": _published_immutable_links(
                    package_id,
                    manifest["version"],
                    interactive_url,
                ),
                "evidence": _release_evidence(profile["evidence"]),
                "files": _file_inventory(package_root),
            }
        )

    return {
        "$schema": CATALOG_SCHEMA_REFERENCE,
        "schemaVersion": 2,
        "license": "MIT",
        "copyrightHolder": "Fabiano Magalhães",
        "licenseFile": {
            "path": COMMON_LICENSE_NAME,
            "sha256": hashlib.sha256(license_bytes).hexdigest(),
        },
        "evolutionModel": {
            "axis": "coordination-boundary",
            "ranking": False,
            "description": (
                "Package order is stable presentation order. Boundary and "
                "operational complexity guide selection; neither is a quality "
                "ranking."
            ),
        },
        "badgeScale": {
            "levels": list(BADGE_LEVELS),
            "packageRanking": False,
            "description": (
                "Levels describe evidence strength for each capability "
                "dimension, not overall package quality."
            ),
            "verifiedRequirement": (
                "Repeatable evaluations of the exact published version."
            ),
        },
        "agentCompatibility": _agent_compatibility(),
        "packages": packages,
    }


def expected_graph_spec(catalog_value: dict[str, Any]) -> dict[str, Any]:
    """Build a membership-only graph; package order is presentation order."""

    package_nodes = [
        {
            "id": entry["id"],
            "kind": "package",
            "label": entry["displayName"],
            "version": entry["version"],
            "artifactStatus": entry["artifactStatus"],
        }
        for entry in catalog_value["packages"]
    ]
    edges = [
        {
            "from": "agent-harnesses",
            "to": entry["id"],
            "kind": "contains",
        }
        for entry in catalog_value["packages"]
    ]
    return {
        "schemaVersion": 1,
        "source": CATALOG_PATH.as_posix(),
        "interactiveDiagram": catalog_value["packages"][0]["immutableLinks"][
            "interactiveDiagram"
        ]["url"],
        "meaning": "Collection membership only; no dependency or ranking.",
        "nodes": [
            {
                "id": "agent-harnesses",
                "kind": "collection",
                "label": "Agent Harnesses",
            },
            *package_nodes,
        ],
        "edges": edges,
    }


def expected_graph_svg(catalog_value: dict[str, Any]) -> bytes:
    """Render a small deterministic SVG from catalog identity fields."""

    entries = catalog_value["packages"]
    width = 1100
    height = 560
    card_x = 430
    card_width = 620
    card_height = 100
    card_ys = (20, 150, 280, 410)
    root_x = 40
    root_y = 220
    root_width = 280
    root_height = 120

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            'aria-labelledby="title description">'
        ),
        "  <title id=\"title\">Agent Harnesses package catalog</title>",
        (
            "  <desc id=\"description\">Four sibling package entries connected "
            "to one neutral collection. Connections show membership, not "
            "dependency or ranking.</desc>"
        ),
        "  <style>",
        (
            "    .surface { fill: #ffffff; stroke: #1f2937; stroke-width: 2; }"
        ),
        "    .edge { fill: none; stroke: #94a3b8; stroke-width: 2; }",
        (
            "    .title { fill: #111827; font: 600 16px ui-sans-serif, "
            "system-ui, sans-serif; }"
        ),
        (
            "    .meta { fill: #475569; font: 13px ui-monospace, "
            "SFMono-Regular, monospace; }"
        ),
        (
            "    .link { fill: #1d4ed8; font: 600 13px ui-sans-serif, "
            "system-ui, sans-serif; text-decoration: underline; }"
        ),
        "  </style>",
        (
            f'  <rect class="surface" x="{root_x}" y="{root_y}" '
            f'width="{root_width}" height="{root_height}" rx="16"/>'
        ),
        (
            f'  <text class="title" x="{root_x + root_width // 2}" y="267" '
            'text-anchor="middle">Agent Harnesses</text>'
        ),
        (
            f'  <text class="meta" x="{root_x + root_width // 2}" y="298" '
            'text-anchor="middle">MIT package collection</text>'
        ),
    ]

    root_right_x = root_x + root_width
    root_center_y = root_y + root_height // 2
    for y in card_ys:
        lines.append(
            f'  <path class="edge" d="M {root_right_x} {root_center_y} '
            f'L {card_x} {y + card_height // 2}"/>'
        )

    for entry, y in zip(entries, card_ys):
        label = html.escape(str(entry["displayName"]))
        package_id = html.escape(str(entry["id"]))
        artifact_status = entry["artifactStatus"]
        metadata = html.escape(
            f'{entry["version"]} · {artifact_status["implementation"]} · '
            f'{artifact_status["publication"]}'
        )
        lines.extend(
            (
                (
                    f'  <rect class="surface" x="{card_x}" y="{y}" '
                    f'width="{card_width}" height="{card_height}" rx="14"/>'
                ),
                (
                    f'  <text class="title" x="{card_x + 30}" '
                    f'y="{y + 38}">{label}</text>'
                ),
                (
                    f'  <text class="meta" x="{card_x + 30}" '
                    f'y="{y + 70}">{package_id}</text>'
                ),
                (
                    f'  <text class="meta" x="{card_x + card_width - 30}" '
                    f'y="{y + 70}" text-anchor="end">{metadata}</text>'
                ),
            )
        )

    interactive_url = html.escape(
        str(
            catalog_value["packages"][0]["immutableLinks"][
                "interactiveDiagram"
            ]["url"]
        ),
        quote=True,
    )
    lines.extend(
        (
            f'  <a href="{interactive_url}" aria-label="Open the interactive '
            'Agent Harnesses diagram">',
            '    <text class="link" x="40" y="545">Interactive diagram</text>',
            "  </a>",
            "</svg>",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def expected_package_graph_spec(entry: dict[str, Any]) -> dict[str, Any]:
    """Build one package-specific conceptual flow from its catalog entry."""

    graph = entry["graph"]
    nodes = [
        {
            "id": step["id"],
            "kind": "flow-step",
            "position": index,
            "label": step["label"],
            "description": step["description"],
        }
        for index, step in enumerate(graph["flow"], start=1)
    ]
    edges = [
        {
            "from": current["id"],
            "to": following["id"],
            "kind": "next",
        }
        for current, following in zip(graph["flow"], graph["flow"][1:])
    ]
    return {
        "schemaVersion": 1,
        "id": graph["id"],
        "package": {
            "id": entry["id"],
            "displayName": entry["displayName"],
            "version": entry["version"],
            "artifactStatus": entry["artifactStatus"],
        },
        "source": {
            "catalog": CATALOG_PATH.as_posix(),
            "spec": graph["spec"],
            "staticAsset": graph["staticAsset"],
            "interactiveDiagram": entry["immutableLinks"][
                "interactiveDiagram"
            ]["url"],
        },
        "purpose": entry["purpose"],
        "meaning": (
            "Package-specific conceptual flow. Edges show operating sequence, "
            "not package ranking or dependency."
        ),
        "nodes": nodes,
        "edges": edges,
    }


def _svg_label_lines(label: str) -> tuple[str, ...]:
    if len(label) <= 23:
        return (label,)
    words = label.split()
    first: list[str] = []
    second: list[str] = []
    for word in words:
        target = first if len(" ".join((*first, word))) <= 21 else second
        target.append(word)
    if not first or not second:
        midpoint = max(1, len(words) // 2)
        first = words[:midpoint]
        second = words[midpoint:]
    return (" ".join(first), " ".join(second))


def expected_package_graph_svg(graph_spec: dict[str, Any]) -> bytes:
    """Render one deterministic accessible SVG from a package graph spec."""

    nodes = graph_spec["nodes"]
    node_width = 230
    node_height = 150
    gap = 30
    margin = 40
    width = margin * 2 + len(nodes) * node_width + (len(nodes) - 1) * gap
    height = 350
    card_y = 115
    center_y = card_y + node_height // 2
    graph_id = html.escape(str(graph_spec["id"]))
    package = graph_spec["package"]
    title = html.escape(f'{package["displayName"]} conceptual flow')
    description = html.escape(
        " then ".join(str(node["label"]) for node in nodes)
        + ". This is an operating sequence, not a ranking."
    )
    package_id = html.escape(str(package["id"]))
    status = package["artifactStatus"]
    footer = html.escape(
        f'{package["version"]} · {status["implementation"]} · '
        f'{status["publication"]}'
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="title description" data-graph-id="{graph_id}" '
            f'data-package-id="{package_id}">'
        ),
        f'  <title id="title">{title}</title>',
        f'  <desc id="description">{description}</desc>',
        "  <defs>",
        (
            '    <marker id="arrow" markerWidth="10" markerHeight="10" '
            'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        ),
        '      <path d="M0,0 L0,6 L9,3 z" fill="#64748b"/>',
        "    </marker>",
        "  </defs>",
        "  <style>",
        (
            "    .surface { fill: #ffffff; stroke: #1f2937; stroke-width: 2; }"
        ),
        (
            "    .edge { fill: none; stroke: #64748b; stroke-width: 2; "
            "marker-end: url(#arrow); }"
        ),
        (
            "    .heading { fill: #111827; font: 600 18px ui-sans-serif, "
            "system-ui, sans-serif; }"
        ),
        (
            "    .step { fill: #111827; font: 600 15px ui-sans-serif, "
            "system-ui, sans-serif; }"
        ),
        (
            "    .meta { fill: #475569; font: 13px ui-monospace, "
            "SFMono-Regular, monospace; }"
        ),
        (
            "    .link { fill: #1d4ed8; font: 600 13px ui-sans-serif, "
            "system-ui, sans-serif; text-decoration: underline; }"
        ),
        "  </style>",
        f'  <text class="heading" x="{margin}" y="38">{title}</text>',
        (
            f'  <text class="meta" x="{margin}" y="66">'
            f'{package_id} · graph {graph_id}</text>'
        ),
    ]

    for index in range(len(nodes) - 1):
        start_x = margin + index * (node_width + gap) + node_width
        end_x = start_x + gap - 8
        lines.append(
            f'  <path class="edge" d="M {start_x} {center_y} '
            f'L {end_x} {center_y}"/>'
        )

    for index, node in enumerate(nodes):
        x = margin + index * (node_width + gap)
        label_lines = _svg_label_lines(str(node["label"]))
        accessible = html.escape(
            f'Step {node["position"]}: {node["label"]}. {node["description"]}'
        )
        lines.extend(
            (
                f'  <g aria-label="{accessible}">',
                (
                    f'    <rect class="surface" x="{x}" y="{card_y}" '
                    f'width="{node_width}" height="{node_height}" rx="14"/>'
                ),
                (
                    f'    <text class="meta" x="{x + 20}" y="{card_y + 30}">'
                    f'Step {node["position"]}</text>'
                ),
                (
                    f'    <text class="step" x="{x + 20}" '
                    f'y="{card_y + 70}">'
                ),
            )
        )
        for line_index, label_line in enumerate(label_lines):
            dy = "0" if line_index == 0 else "22"
            lines.append(
                f'      <tspan x="{x + 20}" dy="{dy}">'
                f"{html.escape(label_line)}</tspan>"
            )
        lines.extend(("    </text>", "  </g>"))

    interactive_url = html.escape(
        str(graph_spec["source"]["interactiveDiagram"]),
        quote=True,
    )
    lines.extend(
        (
            f'  <text class="meta" x="{margin}" y="320">{footer}</text>',
            f'  <a href="{interactive_url}" aria-label="Open the interactive '
            f'{html.escape(str(package["displayName"]), quote=True)} diagram">',
            f'    <text class="link" x="{margin}" y="345">'
            "Interactive diagram</text>",
            "  </a>",
            "</svg>",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def generated_artifacts(repository_root: Path) -> dict[Path, bytes]:
    """Return every deterministic common artifact and its expected bytes."""

    catalog_value = expected_catalog(repository_root)
    membership_graph = expected_graph_spec(catalog_value)
    artifacts = {
        CATALOG_PATH: canonical_json_bytes(catalog_value),
        GRAPH_SPEC_PATH: canonical_json_bytes(membership_graph),
        GRAPH_ASSET_PATH: expected_graph_svg(catalog_value),
    }
    for entry in catalog_value["packages"]:
        graph_spec = expected_package_graph_spec(entry)
        artifacts[Path(entry["graph"]["spec"])] = canonical_json_bytes(graph_spec)
        artifacts[Path(entry["graph"]["staticAsset"])] = (
            expected_package_graph_svg(graph_spec)
        )
    return artifacts


def fsync_directory(path: Path) -> None:
    """Best-effort directory fsync for platforms that support it."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
