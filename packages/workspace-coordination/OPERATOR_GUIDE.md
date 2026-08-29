# Workspace Harness — operator guide

This is the complete, agent-agnostic operating contract for the installed runtime. It does not require a formal Skill or an agent-specific API. Use one public Python 3.10+ executable and the target-local entrypoint shown below.

- Entrypoint: `workspace_coordination.py`
- Package: `workspace-coordination` v`0.2.1`

## Operational memory

The workspace index and shared deltas remain at the coordinator root; detailed continuity remains in each explicitly registered child.

- Canonical state: `.workspace-coordination/workspace.json`, `<child-path>/.workspace-coordination/local-state.json`
- Readable projections: `.workspace-coordination/INDEX.md`, `.workspace-coordination/BOUNDARIES.md`, `.workspace-coordination/SHARED_DELTAS.md`

## Installation readiness

- The explicit target is the container workspace, not one of its child projects.
- The existing contained child projects to register are already known.
- Each selected child has an explicit local owner file and its detailed state will remain locally owned.

## Ready means

The coordinator is initialized, every registered child and owner path is explicit and valid, and canonical plus generated workspace state verifies cleanly.

## Before a write

Inspect read-only, state the intended command, inputs, paths, and effects, then obtain explicit confirmation. Never infer, reorganize, or summarize project data for a mutation. Retain placeholders until the user supplies the corresponding values.

## Command inventory

| Command | Kind | Purpose | Inputs | Effects |
| --- | --- | --- | --- | --- |
| `init` | `write` | Preview or initialize the workspace coordinator boundary. | `<coordinator-root>`, `--dry-run&#124;--apply` | Dry-run writes nothing; apply creates only the coordinator's canonical and generated files. |
| `add` | `write` | Register one existing contained child with its explicit owner file. | `<coordinator-root>`, `<child-id>`, `<child-path>`, `<owner-file>`, `--dry-run&#124;--apply` | Updates only the coordinator index and the selected child's local coordination record. |
| `remove` | `write` | Remove one child registration without deleting or editing the child project. | `<coordinator-root>`, `<child-id>`, `--dry-run&#124;--apply` | Removes only coordinator-owned registration state and preserves the child. |
| `open` | `read` | Open the coordinator or one registered child's bounded resumption context. | `<coordinator-root>`, `<child-id?>` | Reads coordinator and selected child records without writing. |
| `digest` | `read` | Read the bounded owner and continuity context for one child. | `<coordinator-root>`, `<child-id>` | Returns explicit child-local context without discovering or copying other project data. |
| `record` | `write` | Append one explicit child-local continuity record. | `<coordinator-root>`, `<child-id>`, `<record-key>`, `<record-kind>`, `<summary>`, `<next-action>`, `--dry-run&#124;--apply` | Writes the confirmed record only to the selected child's harness-owned local state. |
| `reflect` | `write` | Reflect one confirmed concise shared delta into the coordinator. | `<coordinator-root>`, `<child-id>`, `<reflection-key>`, `<summary>`, `--dry-run&#124;--apply` | Adds one bounded shared delta without absorbing the child's detailed state. |
| `verify` | `read` | Validate coordinator state, registrations, child ownership, and generated views. | `<coordinator-root>` | Reports structural issues without repair. |
| `recover` | `repair` | Preview or regenerate only recoverable managed workspace state. | `<coordinator-root>`, `--dry-run&#124;--apply` | Repairs derivable coordinator-managed state and never reconstructs missing child-owned facts. |

## Placeholder examples

### `init`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" init --dry-run
```

### `add`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id "<child-id>" --path "<child-path>" --owner "<owner-file>" --dry-run
```

### `remove`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" remove --id "<child-id>" --dry-run
```

### `open`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json open --child "<child-id>"
```

### `digest`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json digest --child "<child-id>"
```

### `record`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" record --child "<child-id>" --key "<record-key>" --kind update --summary "<summary>" --next "<next-action>" --dry-run
```

### `reflect`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" reflect --child "<child-id>" --key "<reflection-key>" --summary "<summary>" --dry-run
```

### `verify`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json verify
```

### `recover`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" recover --dry-run
```

## Workflows

### First use

Preview and initialize the coordinator, register one confirmed existing child, verify, and open it.

`init` → `add` → `verify` → `open`

### Daily use

Open one child, digest only its bounded context, record local continuity, and reflect only a confirmed shared delta.

`open` → `digest` → `record` → `reflect`

### Close and resume

Record an explicit close record with a next action, then reopen that child from local state.

`record` → `open`

### Verify or recover

Verify first; preview recover only for derivable managed drift, apply after confirmation, and verify again.

`verify` → `recover` → `verify`

## Installation receipt, rollback, update, and uninstall

- Receipt: target-relative `.agent-harnesses/runtime/workspace-coordination/0.2.1/.agent-harness-receipt.json`.
- From a checksum-verified `0.2.1` bundle, preview package removal with `<python> -B installer.py uninstall workspace-coordination --target "<target>" --dry-run --json`; after review, apply it with `<python> -B installer.py uninstall workspace-coordination --target "<target>" --apply --json`.
- Uninstall removes only the receipt-owned runtime and installer-managed onboarding block. It never removes initialized operational state.
- If a step fails after package apply, first run this package's verify-or-recover workflow. If the target still is not ready, preview and then apply uninstall to roll back the package. Preserve and report any residual initialized state; never delete it automatically.
- To update, download the new version's ZIP and matching checksum sidecar, verify the checksum, read its migration notes, then run the new bundle's doctor, install --dry-run, and install --apply. Do not edit a versioned runtime in place; keep the old version until the new one reaches ready=true.

## Required tutorial after readiness

After installer verification returns `ready=true`, read this guide and `operations.json`, then teach the user the installed harness in the conversation. Do not create a tutorial file. Cover:

- The mental model: what the installed harness remembers and what remains outside its boundary.
- The exact target-local locations of canonical operational memory and readable projections.
- Every installed command, its read, write, or repair kind, and when to use it.
- The first-use, daily, close-and-resume, and verify-or-recover workflows.
- A first safe example that uses only confirmed user values and retains placeholders for anything unknown.
- How to close, resume, verify, and recover without inventing state.
- The installation receipt, how to preview mutations, and how to roll back, update, or uninstall.

Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.

## Support

- LinkedIn: https://www.linkedin.com/in/fabianomag/
- Email: fm@fabianomag.com
