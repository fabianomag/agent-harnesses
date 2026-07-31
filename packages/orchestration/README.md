# Orchestration Harness

- Package ID: `orchestration`
- Version: `0.1.0`
- Artifact status: implemented, published
- Runtime: Python 3.10 or newer, standard library only

## Purpose

Orchestration Harness is a transactional local control plane for one Master
root and explicitly registered execution fronts. It keeps a strict JSON
registry as authority, renders deterministic coordination views, records an
explicit lifecycle, and provides journal-based rollback and recovery.

Use it when registry consistency, validated mutations, recovery, and explicit
front lifecycle records justify a more advanced control surface. Do not use it
as an agent dispatcher, process runner, project implementation engine, remote
service, or language-model digest.

It does not call a model, dispatch agents, execute project commands, publish
content, or infer reflection text.

## Prerequisites

- Python 3.10 or newer.
- An existing real installation root for the common package manager.
- An existing real workspace root for runtime commands.
- Explicit portable IDs, names, root-relative front paths, and optional
  aliases.
- No selected root or managed path component may be link-like.
- A source checkout is required only for repository-level installation,
  verification, and shared checks.

On POSIX systems, the runtime checks each existing lexical component of the
selected workspace root before canonicalization. A path that crosses a parent
symlink is rejected; the equivalent direct physical path remains valid.

## Structure

The managed workspace contains:

```text
.orchestration/manifest.json
AGENTS.md
ARCHITECTURE.md
FRONTS.md
NEXT.md
<front-path>/AGENTS.md
<front-path>/ARCHITECTURE.md
<front-path>/NEXT.md
<front-path>/RECORDS.md
<front-path>/REFLECTIONS.md
<front-path>/SESSIONS.md
```

The manifest is canonical. `FRONTS.md` is a deterministic pending-state panel.
IDs, aliases, and paths are portable and root-relative. The runtime rejects
absolute paths, traversal, drive-qualified paths, ambiguous separators,
reserved names, case-insensitive collisions, nested front collisions, root
escapes, and link traversal.

## Installation

From the source repository root:

```text
python3 -B tools/package_manager.py install --package orchestration --version 0.1.0 --root <install-root> --dry-run
python3 -B tools/package_manager.py install --package orchestration --version 0.1.0 --root <install-root> --apply
python3 -B tools/package_manager.py verify --package orchestration --version 0.1.0 --root <install-root>
```

The installed copy is `<install-root>/orchestration-0.1.0/`. The common package
manager is repository-level tooling; it does not create a global command or
invoke this package runtime.

## Preflight

Enter the installed package root. Open the selected workspace without writing:

```text
python3 -B hq.py --root <workspace> --json bom-dia
```

An unused root reports `uninitialized`. Preview one exact registration:

```text
python3 -B hq.py --root <workspace> --json init --id sample-front --name "Sample Front" --path fronts/sample-front --alias sample --dry-run
```

Review the complete output before repeating the same command with `--apply`.
Every dry-run is read-only.

## Verify

Validate registry and generated state from the installed package root:

```text
python3 -B hq.py --root <workspace> --json hq-sync
```

This is structural sync, not a published-version eval and not a `verified`
badge claim.

Verify installed package bytes from the source repository root:

```text
python3 -B tools/package_manager.py verify --package orchestration --version 0.1.0 --root <install-root>
```

Run package-local automated and structural checks from the installed package
root:

```text
python3 -B -m unittest discover -s tests -v
python3 -B scripts/verify_package.py
python3 -B scripts/structural_check.py
```

## First use

Run this sequence from the installed package root:

```text
python3 -B hq.py --root <workspace> --json bom-dia
python3 -B hq.py --root <workspace> --json init --id sample-front --name "Sample Front" --path fronts/sample-front --alias sample --dry-run
python3 -B hq.py --root <workspace> --json init --id sample-front --name "Sample Front" --path fronts/sample-front --alias sample --apply
python3 -B hq.py --root <workspace> --json hq-sync
python3 -B hq.py --root <workspace> --json foco sample-front
python3 -B hq.py --root <workspace> --json digere --summary "Validated the current slice" --pending "Register the validated delta"
python3 -B hq.py --root <workspace> --json registra --note "Evidence recorded"
python3 -B hq.py --root <workspace> --json encerra --summary "Closed the work block" --next "Review the next bounded slice"
python3 -B hq.py --root <workspace> --json bom-dia
```

When working from the source repository root, replace `hq.py` with
`packages/orchestration/hq.py`. Do not mix installed-copy and repository-root
paths.

`foco` is a no-op when the requested front is already active. With multiple
fronts, select one explicitly. The lifecycle is:

```text
registered -> digested -> recorded -> closed
                      closed -> digested
```

Repeated `init --apply` with the exact registered identity is an idempotent
no-op; differing reuse of an ID fails as a collision.

## Recovery

Every mutation uses an atomic-directory lock, staged desired bytes, verified
backups, a durable phase journal, file and directory flushes where supported,
same-filesystem atomic replacement, and digest-checked recovery.

Inspect without writing:

```text
python3 -B hq.py --root <workspace> --json recover --dry-run
```

Apply only the verified recovery plan:

```text
python3 -B hq.py --root <workspace> --json recover --apply
```

Explicit recovery rolls back a pre-commit journal. A durable committed phase
keeps verified new bytes and completes cleanup. Unknown target digests stop
recovery without deletion or overwrite. Use `--break-stale-lock` only when the
lock exactly matches the journal transaction.

`repair-panel` is narrower than recovery and may repair only a missing or
mismatched generated `FRONTS.md` after all other registry, path, and generated
state checks pass:

```text
python3 -B hq.py --root <workspace> --json repair-panel --dry-run
python3 -B hq.py --root <workspace> --json repair-panel --apply
```

## Limitations

- The package does not call a model, dispatch agents, or execute projects.
- Operators supply every digest, reflection, record, and closeout explicitly.
- Recovery depends on recognized journal phases and expected file digests.
- Narrow repair does not repoint, delete, merge, or resolve conflicting
  authorities.
- Windows reparse-point detection remains implemented, but Windows and reparse
  behavior were not validated locally for this change.
- Remote operations, background services, and publication are outside the
  package.

## Evidence

- **Automated — defined:** the package test suite contains repeatable model,
  CLI, transaction, recovery, and workflow tests.
- **Structural — defined:** `scripts/verify_package.py` and
  `scripts/structural_check.py` provide repeatable package and isolated-cycle
  checks.
- **Manual Codex — verified:** a fresh Orchestration walkthrough passed for
  this exact release bundle and candidate. The immutable evidence is
  [published with the release](https://github.com/fabianomag/agent-harnesses/releases/download/orchestration-v0.1.0/manual-codex-evidence.json).

The local runner does not execute manual evidence. Publishable results must
come from a release manifest or evidence asset bound to the exact published
package version and commit.

## Version and immutable links

Version `0.1.0` is published from the immutable `orchestration-v0.1.0`
release tag.

- Immutable documentation URL: https://github.com/fabianomag/agent-harnesses/blob/orchestration-v0.1.0/packages/orchestration/README.md
- Immutable install prompt: `Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/orchestration-v0.1.0/orchestration-0.1.0.zip`
- Immutable source URL: https://github.com/fabianomag/agent-harnesses/tree/orchestration-v0.1.0/packages/orchestration
- Release URL: https://github.com/fabianomag/agent-harnesses/releases/tag/orchestration-v0.1.0
- Installation report: https://github.com/fabianomag/agent-harnesses/issues/new?template=installation-report.yml

Do not substitute a mutable branch URL for the version-bound fields.

## Diagrams

- Graph ID: `orchestration-flow`
- Source-tree spec: `graphs/orchestration.graph.json`
- Source-tree static asset: `assets/orchestration.svg`
- Interactive diagram: https://fabianomag.vercel.app/artifacts/agent-harnesses

The static graph represents: strategic opening → registry validation → dry-run
→ transactional apply/rollback → pending reflection → verified sync.
