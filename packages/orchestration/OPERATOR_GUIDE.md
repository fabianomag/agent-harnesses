# Control Plane Harness — operator guide

This is the complete, agent-agnostic operating contract for the installed runtime. It does not require a formal Skill or an agent-specific API. Use one public Python 3.10+ executable and the target-local entrypoint shown below.

- Entrypoint: `hq.py`
- Package: `orchestration` v`0.2.2`

## Operational memory

The new control-plane root owns a transactional registry and lifecycle projections; registered fronts retain their bounded records below their confirmed paths.

- Canonical state: `.orchestration/manifest.json`
- Readable projections: `FRONTS.md`, `NEXT.md`, `<front-path>/REFLECTIONS.md`, `<front-path>/RECORDS.md`, `<front-path>/SESSIONS.md`

## Installation readiness

- The explicit target is a deliberate new Master or control-plane root, not an existing coordination structure to adopt.
- The initial fronts, their intended relative paths, and their boundaries are already known.
- The work genuinely requires a transactional registry, validated mutations, rollback, and recovery rather than only project handoffs.

## Ready means

A new control plane has at least one explicit registered front, the registry and generated lifecycle files are coherent, no recovery is pending, and hq-sync reports clean state.

## Before a write

Inspect read-only, state the intended command, inputs, paths, and effects, then obtain explicit confirmation. Never infer, reorganize, or summarize project data for a mutation. Retain placeholders until the user supplies the corresponding values.

## Command inventory

| Command | Kind | Purpose | Inputs | Effects |
| --- | --- | --- | --- | --- |
| `bom-dia` | `read` | Open the control plane or one selected front and determine the safe next operation. | `<workspace>`, `<front-selector?>` | Reads registry, sync, and recovery state without writing. |
| `foco` | `write` | Transactionally select one explicit registered front. | `<workspace>`, `<front-selector>` | Updates the active-front selection in the strict registry and deterministic views. |
| `init` | `write` | Preview or transactionally initialize the control plane and register one new front. | `<workspace>`, `<front-id>`, `<front-name>`, `<front-path>`, `<alias?>`, `--dry-run&#124;--apply` | Dry-run writes nothing; apply creates the strict registry and declared Master/front lifecycle files through a journaled transaction. |
| `hq-sync` | `read` | Strictly validate registry, front boundaries, generated files, locks, and recovery state. | `<workspace>` | Reports clean state or bounded issues without repair. |
| `digere` | `write` | Persist one explicit reflection and pending action for a selected front. | `<workspace>`, `<front-selector?>`, `<summary>`, `<pending-action>` | Transactionally records the supplied reflection and pending action, refreshes deterministic views and counters, and moves the front to digested state. |
| `registra` | `write` | Promote the current explicit digest to a durable record. | `<workspace>`, `<front-selector?>`, `<note?>` | Transactionally records the current digest and moves the selected front to recorded state. |
| `encerra` | `write` | Close a recorded work block with an explicit summary and next action. | `<workspace>`, `<front-selector?>`, `<summary>`, `<next-action>` | Transactionally persists closeout and the next resumption point, then moves the front to closed state. |
| `repair-panel` | `repair` | Preview or repair only a derivable generated pending-panel mismatch. | `<workspace>`, `--dry-run&#124;--apply` | Repairs only the generated panel after every registry and boundary check passes; it never repoints or merges fronts. |
| `recover` | `repair` | Inspect or apply verified recovery for a durable transaction journal. | `<workspace>`, `--dry-run&#124;--apply`, `--break-stale-lock?` | Rolls back a recognized pre-commit transaction or completes verified cleanup after a durable commit; unknown managed-target bytes stop recovery. |

## Placeholder examples

### `bom-dia`

```text
<python> -B hq.py --root "<workspace>" --json bom-dia "<front-selector>"
```

### `foco`

```text
<python> -B hq.py --root "<workspace>" --json foco "<front-selector>"
```

### `init`

```text
<python> -B hq.py --root "<workspace>" --json init --id "<front-id>" --name "<front-name>" --path "<front-path>" --alias "<alias>" --dry-run
```

### `hq-sync`

```text
<python> -B hq.py --root "<workspace>" --json hq-sync
```

### `digere`

```text
<python> -B hq.py --root "<workspace>" --json digere --front "<front-selector>" --summary "<summary>" --pending "<pending-action>"
```

### `registra`

```text
<python> -B hq.py --root "<workspace>" --json registra --front "<front-selector>" --note "<note>"
```

### `encerra`

```text
<python> -B hq.py --root "<workspace>" --json encerra --front "<front-selector>" --summary "<summary>" --next "<next-action>"
```

### `repair-panel`

```text
<python> -B hq.py --root "<workspace>" --json repair-panel --dry-run
```

### `recover`

```text
<python> -B hq.py --root "<workspace>" --json recover --dry-run
```

## Workflows

### First use

Open read-only, preview one confirmed registration, apply it, require clean sync, and select the registered front.

`bom-dia` → `init` → `hq-sync` → `foco`

### Daily use

Open, require clean sync, select the intended front, persist only an explicit digest, and promote it deliberately.

`bom-dia` → `hq-sync` → `foco` → `digere` → `registra`

### Close and resume

Close a recorded block and reopen from its durable next action.

`encerra` → `bom-dia`

### Verify or recover

Use hq-sync for diagnosis, inspect recovery before apply when a journal exists, use panel repair only for its narrow derivable case, and require clean sync afterward.

`hq-sync` → `recover` → `repair-panel` → `hq-sync`

## Installation receipt, rollback, update, and uninstall

- Receipt: target-relative `.agent-harnesses/runtime/orchestration/0.2.2/.agent-harness-receipt.json`.
- From a checksum-verified `0.2.2` bundle, preview package removal with `<python> -B installer.py uninstall orchestration --target "<target>" --dry-run --json`; after review, apply it with `<python> -B installer.py uninstall orchestration --target "<target>" --apply --json`.
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
