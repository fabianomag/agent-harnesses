# Multi-Project Harness — operator guide

This is the complete, agent-agnostic operating contract for the installed runtime. It does not require a formal Skill or an agent-specific API. Use one public Python 3.10+ executable and the target-local entrypoint shown below.

- Entrypoint: `scripts/cross_project.py`
- Package: `cross-project` v`0.2.1`

## Operational memory

The coordination root owns the canonical cross-project manifest and concise projections; each independent project keeps its detailed local memory.

- Canonical state: `harness.config.json`
- Readable projections: `AGENTS.md`, `FRONTS.md`, `NEXT.md`

## Installation readiness

- The coordination root and the independent existing project roots are explicit.
- The projects have known boundaries and a real need for handoffs or structural sync across roots.
- The user can supply each selected project's role and next action without repository discovery or invented state.

## Ready means

The coordination manifest has at least one explicit existing project registration, every managed projection matches it, and hq-sync reports consistent state.

## Before a write

Inspect read-only, state the intended command, inputs, paths, and effects, then obtain explicit confirmation. Never infer, reorganize, or summarize project data for a mutation. Retain placeholders until the user supplies the corresponding values.

## Command inventory

| Command | Kind | Purpose | Inputs | Effects |
| --- | --- | --- | --- | --- |
| `bom-dia` | `read` | Open the cross-project coordination state or one named project's resumption point. | `<coordination-root>`, `<front-id?>` | Reads bounded coordination state and reports the current next action without writing. |
| `hq-init` | `write` | Preview or register one existing independent project under an explicit coordination root. | `<coordination-root>`, `<master-name>`, `<front-id>`, `<front-name>`, `<project-path>`, `<role>`, `<next-action>`, `--dry-run&#124;apply` | Creates or updates only the canonical coordination manifest and its root projections; it does not take ownership of project-local details. |
| `hq-sync` | `read` | Validate the canonical manifest and all managed coordination projections. | `<coordination-root>` | Reports consistency and issues without repair. |
| `digere` | `read` | Classify one explicit input as project-local, coordination-wide, or ephemeral. | `<coordination-root>`, `<front-id>`, `<local&#124;coordination&#124;ephemeral>` | Returns ownership routing and writes nothing; it does not synthesize a digest. |
| `registra` | `write` | Persist one minimal confirmed coordination checkpoint for a registered project. | `<coordination-root>`, `<front-id>`, `<state>`, `<next-action>`, `<blocker?>` | Updates only explicit coordination state and leaves the initial reflection pending when applicable. |
| `encerra` | `write` | Persist a complete explicit reflection or later cross-project handoff. | `<coordination-root>`, `<front-id>`, `<role>`, `<state>`, `<next-action>`, `<summary>`, `<reflect-when>`, `<blocker?>` | Closes the coordination block, clears the pending reflection, and records the confirmed resumption contract. |

## Placeholder examples

### `bom-dia`

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>" --front "<front-id>"
```

### `hq-init`

```text
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --master-name "<master-name>" --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<role>" --next "<next-action>" --dry-run
```

### `hq-sync`

```text
<python> -B scripts/cross_project.py hq-sync --root "<coordination-root>"
```

### `digere`

```text
<python> -B scripts/cross_project.py digere --root "<coordination-root>" --front "<front-id>" --scope "<local|coordination|ephemeral>"
```

### `registra`

```text
<python> -B scripts/cross_project.py registra --root "<coordination-root>" --front "<front-id>" --state "<state>" --next "<next-action>" --blocker "<blocker>"
```

### `encerra`

```text
<python> -B scripts/cross_project.py encerra --root "<coordination-root>" --front "<front-id>" --role "<role>" --state "<state>" --next "<next-action>" --summary "<summary>" --reflect-when "<reflect-when>" --blocker "<blocker>"
```

## Workflows

### First use

Open read-only, preview and register one confirmed existing project, then require clean structural sync.

`bom-dia` → `hq-init` → `hq-sync`

### Daily use

Open one named project, route explicit input, and save only the minimal confirmed coordination delta.

`bom-dia` → `digere` → `registra` → `hq-sync`

### Close and resume

Close with a complete reflection and reopen the same named project from its recorded next action.

`encerra` → `hq-sync` → `bom-dia`

### Verify or recover

Use hq-sync as read-only diagnosis; on inconsistency, stop for explicit manual recovery because this harness has no repair command.

`hq-sync`

## Installation receipt, rollback, update, and uninstall

- Receipt: target-relative `.agent-harnesses/runtime/cross-project/0.2.1/.agent-harness-receipt.json`.
- From a checksum-verified `0.2.1` bundle, preview package removal with `<python> -B installer.py uninstall cross-project --target "<target>" --dry-run --json`; after review, apply it with `<python> -B installer.py uninstall cross-project --target "<target>" --apply --json`.
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
