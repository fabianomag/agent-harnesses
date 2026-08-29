# Workspace Harness — advanced reference

- Package ID: `workspace-coordination`
- Version: `0.2.0`
- Artifact status: implemented, published
- Runtime: Python 3.10 or newer, standard library only

## Purpose

Workspace Harness coordinates autonomous child folders contained
by one explicit local root. The coordinator owns a small child index, shared
boundaries, and concise shared deltas. Detailed context, execution evidence,
and continuity remain with each child-local owner.

Use it when one containing workspace needs explicit child selection and shared
governance. Do not use it for a single project, independent projects without a
containing coordinator, or a transactional Master control plane.

The four packages are boundary choices, not a capability ranking:

- Project Harness keeps one project-local context and cycle.
- Workspace Harness indexes contained autonomous children.
- Multi-Project Harness coordinates named independent projects and transversal
  handoffs.
- Control Plane Harness provides a transactional local control plane with a
  strict registry, explicit lifecycle records, structural sync, and recovery.
  It does not dispatch agents or execute projects.

## Prerequisites

- Python 3.10 or newer.
- In commands, `<python>` means the same single user- or system-available
  Python 3.10+ executable selected during installation (for example `python3`,
  `python`, or `py -3`), never a private application runtime.
- An existing real installation root for the common package manager.
- An existing real coordinator root for runtime commands.
- Each child must already exist below that root and contain its declared owner
  file before `add`.
- No managed root, child path, owner path, or path component may be link-like.
- Root validation walks existing lexical components before canonicalization.
- A source checkout is required only for repository-level installation,
  verification, and shared checks.

## Structure

`init` creates only:

```text
WORKSPACE_COORDINATION.md
.workspace-coordination/
  BOUNDARIES.md
  INDEX.md
  SHARED_DELTAS.md
  workspace.json
```

`workspace.json` is canonical. It stores schema version `1`, registered
children, and concise shared deltas with normalized root-relative POSIX paths.
The Markdown files are deterministic managed views. Detailed continuity is
stored only under the selected child at
`.workspace-coordination/local-state.json`.

Keys are portable lowercase slugs and idempotency keys. Repeating one with
identical content is a no-op; reusing it with different content is a collision.

## Installation

From the source repository root:

```text
<python> -B tools/package_manager.py install --package workspace-coordination --version 0.2.0 --root "<install-root>" --dry-run
<python> -B tools/package_manager.py install --package workspace-coordination --version 0.2.0 --root "<install-root>" --apply
<python> -B tools/package_manager.py verify --package workspace-coordination --version 0.2.0 --root "<install-root>"
```

The installed copy is
`<install-root>/workspace-coordination-0.2.0/`. The common package manager does
not create a global command or invoke the runtime.

## Preflight

Enter the installed package root. Every mutating runtime command requires
exactly one of `--dry-run` or `--apply`. Begin with:

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" init --dry-run
```

Preflight validates the complete root-relative write set and writes nothing.
It never discovers children, scans adjacent folders, or searches a home
directory or disk.

Preview each registration before applying it:

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id alpha --path child-alpha --owner AGENTS.md --dry-run
```

## Verify

Verify runtime state from the installed package root:

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" verify
```

Verify installed package bytes from the source repository root:

```text
<python> -B tools/package_manager.py verify --package workspace-coordination --version 0.2.0 --root "<install-root>"
```

Run package-local automated checks from the installed package root:

```text
<python> -B -m unittest discover -s tests -v
```

## First use

Before these commands, create `<coordinator-root>/child-alpha/AGENTS.md` and
`<coordinator-root>/child-beta/OWNER.md` as regular UTF-8 files. Then, from the
installed package root:

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" init --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" init --apply

<python> -B workspace_coordination.py --root "<coordinator-root>" add --id alpha --path child-alpha --owner AGENTS.md --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id alpha --path child-alpha --owner AGENTS.md --apply
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id beta --path child-beta --owner OWNER.md --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id beta --path child-beta --owner OWNER.md --apply

<python> -B workspace_coordination.py --root "<coordinator-root>" open
<python> -B workspace_coordination.py --root "<coordinator-root>" open --child alpha
<python> -B workspace_coordination.py --root "<coordinator-root>" digest --child alpha

<python> -B workspace_coordination.py --root "<coordinator-root>" record --child alpha --key cycle-001 --kind decision --summary "Keep this implementation local to alpha." --next "Run the local fixture." --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" record --child alpha --key cycle-001 --kind decision --summary "Keep this implementation local to alpha." --next "Run the local fixture." --apply
<python> -B workspace_coordination.py --root "<coordinator-root>" reflect --child alpha --key shared-001 --summary "Both children share one fixture naming boundary." --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" reflect --child alpha --key shared-001 --summary "Both children share one fixture naming boundary." --apply
<python> -B workspace_coordination.py --root "<coordinator-root>" record --child alpha --key cycle-002 --kind close --summary "The local cycle is closed." --next "Reopen alpha from its recorded next action." --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" record --child alpha --key cycle-002 --kind close --summary "The local cycle is closed." --next "Reopen alpha from its recorded next action." --apply

<python> -B workspace_coordination.py --root "<coordinator-root>" verify
<python> -B workspace_coordination.py --root "<coordinator-root>" open --child alpha
```

When working from the source repository root, replace
`workspace_coordination.py` with
`packages/workspace-coordination/workspace_coordination.py`. Do not mix path
contexts.

`open` lists explicit choices or reads one child owner. `digest` reads only the
declared owner, managed local state, and coordinator deltas. `record` writes
detailed continuity locally. `reflect` accepts only one explicit concise shared
delta and never copies child state automatically. `remove` unregisters a child
without deleting or editing it.

## Recovery

Multi-file updates stage files beside their targets, recheck expected bytes,
replace each file atomically, and roll back already committed files after a
catchable later failure.

1. Run `verify`.
2. Run `recover --dry-run` only when verification identifies recoverable
   generated or canonical drift.
3. Run `recover --apply` to regenerate managed views and canonicalize
   semantically valid JSON.
4. Stop on corrupt source JSON, a symlink, or a non-file collision. Restore
   from an independent known-good source instead of inventing state.

## Limitations

- Version `0.2.0` supports one mutating writer per coordinator root; serialize
  writers externally.
- Children must be explicitly registered and contained by one coordinator.
- The harness does not execute child work or dispatch agents.
- It does not coordinate independent roots without a containing workspace.
- Link-like Windows reparse metadata is rejected when exposed by the host, but
  this candidate has not been manually exercised on Windows.
- Remote operations and publication are outside the package.

## Evidence

- **Automated — defined:** `tests/test_workspace_coordination.py` contains
  repeatable package tests over synthetic two-child fixtures.
- **Structural — defined:** common installed-copy and repository validation
  procedures are present; this README does not self-attest a result.
- **Manual Codex — verified:** a fresh Workspace Coordination walkthrough
  passed for this exact release bundle and candidate. The immutable evidence
  is [published with the release](https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/manual-codex-evidence.json).

The local runner does not execute manual evidence. Publishable results must
come from a release manifest or evidence asset bound to the exact published
package version and commit.

## Version and immutable links

Version `0.2.0` is published from the immutable
`v0.2.0` release tag.

- Immutable documentation URL: https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/packages/workspace-coordination/README.md
- Immutable install prompt: `Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/workspace-coordination-0.2.0.zip`
- Immutable source URL: https://github.com/fabianomag/agent-harnesses/tree/v0.2.0/packages/workspace-coordination
- Release URL: https://github.com/fabianomag/agent-harnesses/releases/tag/v0.2.0
- Installation report: https://github.com/fabianomag/agent-harnesses/issues/new?template=installation-report.yml

Do not substitute a mutable branch URL for the version-bound fields.

## Diagrams

- Graph ID: `workspace-coordination-flow`
- Immutable spec: https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/workspace-coordination.graph.json
- Source-tree static asset: `assets/workspace-coordination.svg`
- Interactive diagram: https://fabianomag.com/projects/agent-harnesses

The static graph represents: workspace coordinator → child index → shared
boundary/governance → child-local owner → reflection.
