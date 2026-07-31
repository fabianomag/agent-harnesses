# Project Harness

- Package ID: `project-harness`
- Version: `0.1.0`
- Artifact status: implemented, unpublished
- Runtime: Python 3.10 or newer, standard library only

## Purpose

Project Harness keeps durable context and a resumable work cycle inside one
explicit local project. Use it when one project needs persistent context,
decisions, next actions, checkpoints, and closeout without depending on chat
history.

Do not use it to coordinate a containing workspace, sibling projects, a
cross-project control surface, external services, releases, or publication.

## Prerequisites

- Python 3.10 or newer.
- An existing real installation root for the common package manager.
- An existing real project root for runtime commands.
- No lexical component of either managed root may be a symbolic link or
  link-like Windows reparse point.
- A source checkout is required only to run the repository-level installer,
  verifier, and shared checks.

## Structure

`init` creates or reconciles:

```text
.project-harness/state.json
AGENTS.md
ARCHITECTURE.md
docs/project-context.md
docs/decisions.md
docs/next-actions.md
docs/session-log.md
generated/
plans/
references/
```

The JSON file is canonical local state. Markdown files contain stable managed
blocks. Existing regular UTF-8 files are preserved byte-for-byte outside those
blocks; existing directories and unrelated files are preserved.

## Installation

From the source repository root, preview, install, and verify the exact package:

```text
python3 -B tools/package_manager.py install --package project-harness --version 0.1.0 --root <install-root> --dry-run
python3 -B tools/package_manager.py install --package project-harness --version 0.1.0 --root <install-root> --apply
python3 -B tools/package_manager.py verify --package project-harness --version 0.1.0 --root <install-root>
```

The installed copy is `<install-root>/project-harness-0.1.0/`. The common
package manager does not create a global command and does not invoke the
package runtime during installation.

## Preflight

Enter the installed `project-harness-0.1.0/` directory and preview the complete
runtime write set:

```text
python3 -B project_harness.py init --root <project-root> --dry-run
```

The project root must already exist. Preflight performs the same validation as
applied `init` and writes nothing. It refuses ambiguous markers, invalid UTF-8,
path-type collisions, link-like managed paths, a link-like root, and any
destination outside the fixed package allowlist.

## Verify

Verify managed runtime state from the installed package root:

```text
python3 -B project_harness.py verify --root <project-root>
```

Verify package bytes from the source repository root with the common verifier:

```text
python3 -B tools/package_manager.py verify --package project-harness --version 0.1.0 --root <install-root>
```

Package-local automated and structural checks can be run from the installed
package root:

```text
python3 -B -m unittest discover -s tests -v
python3 -B tests/validate_generated_fixture.py
```

## First use

All commands below are relative to the installed package root:

```text
python3 -B project_harness.py init --root <project-root> --dry-run
python3 -B project_harness.py init --root <project-root>
python3 -B project_harness.py verify --root <project-root>
python3 -B project_harness.py open --root <project-root>
```

When working from the source repository root instead, replace
`project_harness.py` with
`packages/project-harness/project_harness.py`. Do not mix installed-copy and
repository-root paths. Repeating `init` reconciles managed projections and is
a true no-op when bytes already match.

## Durable work cycle

`open`, `status`, `digest`, and `verify` are read-only:

```text
python3 -B project_harness.py status --root <project-root>
python3 -B project_harness.py digest --root <project-root>
```

`digest` is a deterministic collation of durable context and recorded state;
it does not claim language-model synthesis.

Record an intermediate checkpoint:

```text
python3 -B project_harness.py checkpoint \
  --root <project-root> \
  --session local-session \
  --summary "Established a synthetic baseline" \
  --decision "Keep the interface project-local" \
  --task "Review the generated structure" \
  --next-step "Close the work block"
```

Close the work block:

```text
python3 -B project_harness.py close \
  --root <project-root> \
  --session local-session \
  --summary "Validated the synthetic project cycle" \
  --decision "Retain the verified structure" \
  --task "Start the next bounded task" \
  --next-step "Reopen from durable state"
```

Both record commands atomically replace each affected file and persist the
event in canonical state and its projections. All commands accept `--json`.

## Recovery

The implementation preflights a complete batch, stages replacement files
beside their destinations, and rolls back files already replaced after a
catchable in-process failure.

A process or machine stop cannot make a multi-file batch globally atomic:

1. Run `verify`.
2. If canonical state is valid but a projection is missing or drifted, run
   `init`, then run `verify` again.
3. If state is invalid or marker ownership is ambiguous, stop and repair from
   an independent known-good source. The harness does not infer lost state.

## Limitations

- Multi-file operations are not physically crash-atomic.
- Hostile concurrent writers are unsupported.
- Automatic schema migration and crash journaling are not implemented.
- Installation is not a global command.
- Link-like Windows reparse metadata has unit coverage, but this candidate has
  not been manually exercised on Windows.
- Remote operations and publication are outside the package.

## Evidence

- **Automated — defined:** `tests/test_project_harness.py` contains repeatable
  package tests. This README does not self-attest a candidate-bound result.
- **Structural — defined:** `tests/validate_generated_fixture.py` checks an
  isolated generated project.
- **Manual Codex — pending:** the next candidate requires a fresh Project
  Harness walkthrough. Earlier walkthrough results are not inherited.

The local runner does not execute manual evidence. Publishable results must
come from a release manifest or evidence asset bound to the exact published
package version and commit.

## Version and immutable links

Version `0.1.0` is implemented locally and remains unpublished.

- Immutable documentation URL: unpublished; no URL exists.
- Immutable install prompt: unpublished; no prompt is claimed.
- Immutable source URL: unpublished; no URL exists.
- Release URL: unpublished; no URL exists.

Do not substitute a mutable branch URL for any of these fields.

## Diagrams

- Graph ID: `project-harness-flow`
- Source-tree spec: `graphs/project-harness.graph.json`
- Source-tree static asset: `assets/project-harness.svg`
- Interactive diagram: unpublished; no URL exists.

The static graph represents: skill trigger → initializer → local context → work
cycle → finalizer → durable next.
