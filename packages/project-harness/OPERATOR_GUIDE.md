# Project Harness — operator guide

This is the complete, agent-agnostic operating contract for the installed runtime. It does not require a formal Skill or an agent-specific API. Use one public Python 3.10+ executable and the target-local entrypoint shown below.

- Entrypoint: `project_harness.py`
- Package: `project-harness` v`0.2.2`

## Operational memory

Operational memory remains inside the selected project: one canonical state document plus deterministic Markdown projections.

- Canonical state: `.project-harness/state.json`
- Readable projections: `docs/decisions.md`, `docs/next-actions.md`, `docs/session-log.md`

## Installation readiness

- The explicit target is the root of one real project.
- That project's write boundary is understood and does not include sibling projects.
- The requested scope is project-local operational memory, not coordination across multiple projects.

## Ready means

The exact runtime inventory is installed, project state is initialized, managed projections verify, and the project can be opened from its persisted next step.

## Before a write

Inspect read-only, state the intended command, inputs, paths, and effects, then obtain explicit confirmation. Never infer, reorganize, or summarize project data for a mutation. Retain placeholders until the user supplies the corresponding values.

## Command inventory

| Command | Kind | Purpose | Inputs | Effects |
| --- | --- | --- | --- | --- |
| `init` | `write` | Preview or initialize the bounded project state and managed context projections. | `<project-root>`, `--dry-run&#124;apply` | Dry-run writes nothing; apply creates or reconciles only the declared project-local managed paths. |
| `verify` | `read` | Check canonical state, ownership markers, and every managed projection. | `<project-root>` | Reads the bounded project state and reports drift without repair. |
| `status` | `read` | Show the current durable state and next action. | `<project-root>` | Reads canonical state without changing project files. |
| `open` | `read` | Open one work block from durable project context. | `<project-root>` | Returns the resumption context and next step without writing. |
| `digest` | `read` | Collate the bounded durable records for review. | `<project-root>` | Returns deterministic recorded context and does not synthesize or persist new content. |
| `checkpoint` | `write` | Persist an explicit intermediate work record and one next step. | `<project-root>`, `<session-id>`, `<summary>`, `<decision>`, `<task>`, `<next-step>` | Appends confirmed content to canonical state and refreshes its managed projections. |
| `close` | `write` | Close the current work block with an explicit durable resumption point. | `<project-root>`, `<session-id>`, `<summary>`, `<decision>`, `<task>`, `<next-step>` | Persists the confirmed closeout and next step in canonical state and projections. |

## Placeholder examples

### `init`

```text
<python> -B project_harness.py init --root "<project-root>" --dry-run
```

### `verify`

```text
<python> -B project_harness.py verify --root "<project-root>" --json
```

### `status`

```text
<python> -B project_harness.py status --root "<project-root>" --json
```

### `open`

```text
<python> -B project_harness.py open --root "<project-root>" --json
```

### `digest`

```text
<python> -B project_harness.py digest --root "<project-root>" --json
```

### `checkpoint`

```text
<python> -B project_harness.py checkpoint --root "<project-root>" --session "<session-id>" --summary "<summary>" --decision "<decision>" --task "<task>" --next-step "<next-step>" --json
```

### `close`

```text
<python> -B project_harness.py close --root "<project-root>" --session "<session-id>" --summary "<summary>" --decision "<decision>" --task "<task>" --next-step "<next-step>" --json
```

## Workflows

### First use

Preview initialization, apply it after confirmation, verify, and open the first work block.

`init` → `verify` → `open`

### Daily use

Open durable context, review it, and save only a confirmed checkpoint when needed.

`open` → `digest` → `checkpoint`

### Close and resume

Close with an explicit next step and later reopen from that persisted point.

`close` → `open`

### Verify or recover

Verify first; when canonical state is valid but projections drift, preview and rerun init before verifying again.

`verify` → `init` → `verify`

## Installation receipt, rollback, update, and uninstall

- Receipt: target-relative `.agent-harnesses/runtime/project-harness/0.2.2/.agent-harness-receipt.json`.
- From a checksum-verified `0.2.2` bundle, preview package removal with `<python> -B installer.py uninstall project-harness --target "<target>" --dry-run --json`; after review, apply it with `<python> -B installer.py uninstall project-harness --target "<target>" --apply --json`.
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
