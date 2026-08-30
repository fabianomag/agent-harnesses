# Multi-Project Harness — advanced reference

- Package ID: `cross-project`
- Version: `0.2.3`
- Artifact status: implemented, published
- Runtime: Python 3.10 or newer, standard library only

## Purpose

Multi-Project Harness coordinates an explicit named set of independent local
projects from one selected root. It keeps minimal transversal state in a
canonical manifest, validates generated coordination views, routes bounded
front state, and records explicit reflections.

Use it when independent projects need named targeting, deterministic
structural sync, and cross-project handoffs. Do not use it for one project's
local lifecycle, for contained children whose coordinator owns shared
governance, or for a journaled transactional Master control plane.

## Prerequisites

- Python 3.10 or newer.
- In commands, `<python>` means the same single user- or system-available
  Python 3.10+ executable selected during installation (for example `python3`,
  `python`, or `py -3`), never a private application runtime.
- An existing real installation root for the common package manager.
- An existing real coordination root for runtime commands.
- Every registered project root must already exist. New registrations may use a
  normalized native absolute path, including a sibling of the coordination
  root. Root-relative POSIX paths remain supported for existing v0.1/v0.2.1
  manifests whose projects are contained by the coordination root.
- The selected coordination root and project roots must not be filesystem
  root, home, Git metadata, symbolic links, or metadata-reported Windows
  reparse points.
- Every existing lexical component of the selected root is inspected without
  following links before the root is resolved.
- A source checkout is required only for repository-level installation,
  verification, and shared checks.

## Structure

The runtime manages:

```text
harness.config.json
AGENTS.md
FRONTS.md
NEXT.md
```

`harness.config.json` is the machine authority. Its exact top-level fields are
`schemaVersion`, `harness`, `master`, and `fronts`. A named front stores only
its public name, normalized absolute root (or a legacy contained relative
path), role, state, next action, blocker, coordination-pending state, last
reflection, and reflection trigger.

The Markdown files contain bounded managed sections. Dense implementation state
remains with each local project owner.

## Installation

From the source repository root:

```text
<python> -B tools/package_manager.py install --package cross-project --version 0.2.3 --root "<install-root>" --dry-run
<python> -B tools/package_manager.py install --package cross-project --version 0.2.3 --root "<install-root>" --apply
<python> -B tools/package_manager.py verify --package cross-project --version 0.2.3 --root "<install-root>"
```

The installed copy is `<install-root>/cross-project-0.2.3/`. The common
package manager does not create a global command or invoke the runtime.

## Preflight

Enter the installed package root. Start with read-only orientation:

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>"
```

Preview the exact registration before applying it:

```text
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --dry-run --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<confirmed-role>" --next "<confirmed-next-action>"
```

The preview writes nothing. Read-only, preview, and applying commands reject a
selected root whose final path or any intermediate parent is link-like. They
also reject non-normalized absolute paths, escaping relative paths, missing or
non-directory roots, filesystem root, home, Git metadata, duplicate identities,
and one physical directory registered under two IDs. Validation touches only
the explicitly supplied coordination and project roots; it never discovers or
scans for other projects.

## Verify

Validate canonical state and managed projections from the installed package
root:

```text
<python> -B scripts/cross_project.py hq-sync --root "<coordination-root>"
```

Verify installed package bytes from the source repository root:

```text
<python> -B tools/package_manager.py verify --package cross-project --version 0.2.3 --root "<install-root>"
```

Run package-local automated checks from the installed package root:

```text
<python> -B tests/test_cross_project.py
```

## First use

Confirm `<project-path>` as the normalized absolute root of a real independent
project before running this installed-copy sequence; do not create a sample
project. A contained relative path is accepted only as the compatibility form
for an existing v0.1/v0.2.1 layout. Pass physical, link-free paths; a lexically
different path through a symlink is rejected even when it names the same
directory:

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --dry-run --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<confirmed-role>" --next "<confirmed-next-action>"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<confirmed-role>" --next "<confirmed-next-action>"
<python> -B scripts/cross_project.py hq-sync --root "<coordination-root>"
<python> -B scripts/cross_project.py digere --root "<coordination-root>" --front "<front-id>" --scope coordination
<python> -B scripts/cross_project.py registra --root "<coordination-root>" --front "<front-id>" --state "<confirmed-state>" --next "<confirmed-next-action>"
<python> -B scripts/cross_project.py encerra --root "<coordination-root>" --front "<front-id>" --role "<confirmed-role>" --state "<confirmed-state>" --next "<confirmed-next-action>" --summary "<confirmed-summary>" --reflect-when "<confirmed-reflection-trigger>"
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>" --front "<front-id>"
```

When working from the source repository root, use
`packages/cross-project/scripts/cross_project.py`. Do not mix installed-copy
and repository-root paths.

`bom-dia`, `digere`, and `hq-sync` are read-only. `hq-init` registers a real
child with rollback protection under a cooperative lock. `registra` writes the
smallest coordination checkpoint. `encerra` records a complete transversal
reflection and clears provisional registration state.

## Recovery

Mutations stage and flush replacement files before commit positions are
acquired. Cooperative readers stop on an active writer or on a state change
during their read. Catchable failures restore replaced bytes and file modes.

1. After a catchable failure, run `hq-sync`.
2. If it passes, reopen the selected front with `bom-dia --front`.
3. After a process kill or power loss, do not use a read-only command as
   implicit repair. Confirm no writer remains, inspect the root and any stale
   lock or staging state, and restore from an independent known-good copy.
4. Run `hq-sync` again before continuing.

The package intentionally has no automatic crash-recovery command.

## Limitations

- Rollback and coherence cover catchable failures and cooperative readers.
- Multi-file changes are not physically crash-safe or atomic after process
  kill or power loss.
- Adversarial replacement of the selected root inode remains a residual risk.
- Windows reparse-point behavior is metadata-aware but has not been validated
  locally on Windows; no Windows/reparse portability result is claimed.
- The package does not discover or scan parents, home, unregistered siblings,
  Git remotes, or external services. It validates metadata only for each exact
  project root that the user explicitly supplies.
- Remote operations and publication are outside the package.

## Evidence

- **Automated — defined:** `tests/test_cross_project.py` contains repeatable
tests for previews, idempotence, preservation, bounded reads, locking,
rollback, link rejection with physical zero-write snapshots, independent
sibling project roots, legacy contained paths, project-root byte preservation,
and the reflection lifecycle.
- **Structural — defined:** common installed-copy and repository validation
  procedures are present; this README does not self-attest a result.
- **Manual Codex — pending:** a fresh Multi-Project Harness walkthrough must
  run against the exact release candidate before publication.

The local runner does not execute manual evidence. Publishable results must
come from a release manifest or evidence asset bound to the exact published
package version and commit.

## Version and immutable links

Version `0.2.3` is bound to the immutable `v0.2.3` release tag and supersedes
the immutable `v0.2.0` collection release without rewriting it.

- Immutable documentation URL: https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/packages/cross-project/README.md
- Immutable install prompt: `Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/cross-project-0.2.3.zip`
- Immutable source URL: https://github.com/fabianomag/agent-harnesses/tree/v0.2.3/packages/cross-project
- Release URL: https://github.com/fabianomag/agent-harnesses/releases/tag/v0.2.3
- Installation report: https://github.com/fabianomag/agent-harnesses/issues/new?template=installation-report.yml

Do not substitute a mutable branch URL for the version-bound fields.

## Diagrams

- Graph ID: `cross-project-flow`
- Immutable spec: https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/graphs/cross-project.graph.json
- Source-tree static asset: `assets/cross-project.svg`
- Interactive diagram: https://fabianomag.com/projects/agent-harnesses

The static graph represents: named target → manifest → structural sync → front
state → local owner → transversal reflection.
