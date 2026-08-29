<!-- BEGIN GENERATED:PRODUCT -->
# Project Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.1`

**Best for:** One explicit project that needs checkpoints, closeout, and reliable resumption.

**Not for:** Coordination across workspace children or independent project roots.

**What it changes:** Creates a bounded project state directory and managed context blocks inside the selected project.

Strengths: **Checkpoints · Close and resume · Fast setup**. Complexity: low.

**Ready means:** The exact runtime inventory is installed, project state is initialized, managed projections verify, and the project can be opened from its persisted next step.

**Before installation, confirm:**

- The explicit target is the root of one real project.
- That project's write boundary is understood and does not include sibling projects.
- The requested scope is project-local operational memory, not coordination across multiple projects.

## Installation

Copy only this prompt:

```text
Install Project Harness (`project-harness`) v0.2.1 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.1/project-harness-0.2.1.zip.

Before proposing execution, confirm every selected-harness readiness fact:
- The explicit target is the root of one real project.
- That project's write boundary is understood and does not include sibling projects.
- The requested scope is project-local operational memory, not coordination across multiple projects.
If any fact is unknown or false, stop before downloads or target writes, explain what must be organized first, and offer the support contacts below.

If the current mode cannot execute, request a switch to an execution-capable mode only after presenting the plan and receiving confirmation.

Use the agent's native Plan mode and structured questions when available; otherwise present the same plan and questions conversationally. Work in two explicit stages: plan first, then execute only after confirmation. Before any write, including a download or temporary extraction, inspect only the explicit target and available public tooling read-only. Present four separate checklists: (1) fit and target, (2) safety and write plan, (3) initialization and readiness, and (4) tutorial and handoff. State the selected harness, target, one user- or system-available Python 3.10+ executable as `<python>` (for example `python3`, `python`, or `py -3`), expected writes, required initialization inputs, verification, rollback, and tutorial steps; ask the user to confirm that plan. Never use a private Codex runtime. Do not organize, rename, summarize, migrate, or infer the user's project data. Ask for any missing value instead of inventing it. After confirmation, download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, and extract it. From the extracted bundle root run:
`<python> -B installer.py doctor project-harness --target "<target>" --json`
If doctor or any pre-apply readiness check fails, stop with zero target writes, clean only isolated temporary files, and recommend a better fit when applicable; never silently substitute another harness. Then run:
`<python> -B installer.py install project-harness --target "<target>" --dry-run --json`
Review the result against the confirmed plan and ask again if the write set or assumptions materially changed. Otherwise run:
`<python> -B installer.py install project-harness --target "<target>" --apply --json`
Follow `package/README.md` to initialize the target, previewing every runtime mutation and using only confirmed user values. If any step fails after the first apply or final readiness is false, stop normal execution and follow the exact package's documented rollback or recovery procedure, preview it before apply, preserve unrelated files, verify restoration toward the exact pre-install state, and report any unavoidable residual change instead of claiming success. Then run from the bundle root:
`<python> -B installer.py verify project-harness --target "<target>" --json`
Report installation success only when this final result contains `ready=true`. After readiness, read the installed runtime's `operations.json` and `OPERATOR_GUIDE.md`, then give the user a concise tutorial in the conversation covering every command, the first-use, daily, close-and-resume, and verify-or-recover workflows, safe examples with confirmed values or placeholders, and update/uninstall guidance. Do not create tutorial files. Clean temporary files and report the receipt, readiness evidence, rollback status, and runtime location. Offer support through LinkedIn at https://www.linkedin.com/in/fabianomag/ or email at fm@fabianomag.com. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.

Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.
```

The installed runtime includes `operations.json` plus `OPERATOR_GUIDE.md`; after `ready=true`, the coding agent must read both and teach the user the complete operating cycle in the conversation.
<!-- END GENERATED:PRODUCT -->

For manual installation, verify the individual `.sha256` sidecar before
extraction, then run `installer.py doctor`, `install --dry-run`, and `install
--apply` with selector `project-harness` and one explicit `--target`.

## First use

Use the same public Python 3.10+ executable resolved by the install prompt as
`<python>`. From the installed runtime directory:

`<project-root>/.agent-harnesses/runtime/project-harness/0.2.1`

```text
<python> -B project_harness.py init --root "<project-root>" --dry-run
<python> -B project_harness.py init --root "<project-root>"
<python> -B project_harness.py verify --root "<project-root>"
<python> -B project_harness.py open --root "<project-root>"
```

Continue with `checkpoint` during work and `close` at the end of a work block.
From the still-extracted bundle root, finish the guided install with
`<python> -B installer.py verify project-harness --target "<project-root>" --json`; only
`"ready": true` is success. `installer.py` is not copied into the runtime.

## State compatibility

Package version and state schema are independent. Runtime `0.2.1` creates
schema `1` state and reads/verifies Project Harness `0.1.0` state without
rewriting its `harnessVersion`. No implicit migration occurs.

## Recovery and limitations

The harness is project-local and never coordinates sibling roots or external
services. It preserves existing text outside its managed blocks. Use the
runtime's dry-run before any repair; uninstall removes only unchanged
receipt-owned runtime bytes and leaves initialized project files intact.

Technical implementation, collision, rollback, evidence, and diagram details
are in the [operator guide](OPERATOR_GUIDE.md), [advanced reference](docs/REFERENCE.md),
immutable [catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/graphs/project-harness.graph.json).
