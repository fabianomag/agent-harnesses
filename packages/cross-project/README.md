<!-- BEGIN GENERATED:PRODUCT -->
# Multi-Project Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.1`

**Best for:** Existing independent project roots that need explicit handoffs and transversal coordination.

**Not for:** A contained child index or a new strict registry with journaled recovery.

**What it changes:** Creates a canonical coordination manifest and managed root projections without taking ownership of project-local details.

Strengths: **Independent projects · Handoffs · Structural sync**. Complexity: medium.

**Ready means:** The coordination manifest has at least one explicit existing project registration, every managed projection matches it, and hq-sync reports consistent state.

**Before installation, confirm:**

- The coordination root and the independent existing project roots are explicit.
- The projects have known boundaries and a real need for handoffs or structural sync across roots.
- The user can supply each selected project's role and next action without repository discovery or invented state.

## Installation

Copy only this prompt:

```text
Install Multi-Project Harness (`cross-project`) v0.2.1 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.1/cross-project-0.2.1.zip.

Before proposing execution, confirm every selected-harness readiness fact:
- The coordination root and the independent existing project roots are explicit.
- The projects have known boundaries and a real need for handoffs or structural sync across roots.
- The user can supply each selected project's role and next action without repository discovery or invented state.
If any fact is unknown or false, stop before downloads or target writes, explain what must be organized first, and offer the support contacts below.

If the current mode cannot execute, request a switch to an execution-capable mode only after presenting the plan and receiving confirmation.

Use the agent's native Plan mode and structured questions when available; otherwise present the same plan and questions conversationally. Work in two explicit stages: plan first, then execute only after confirmation. Before any write, including a download or temporary extraction, inspect only the explicit target and available public tooling read-only. Present four separate checklists: (1) fit and target, (2) safety and write plan, (3) initialization and readiness, and (4) tutorial and handoff. State the selected harness, target, one user- or system-available Python 3.10+ executable as `<python>` (for example `python3`, `python`, or `py -3`), expected writes, required initialization inputs, verification, rollback, and tutorial steps; ask the user to confirm that plan. Never use a private Codex runtime. Do not organize, rename, summarize, migrate, or infer the user's project data. Ask for any missing value instead of inventing it. After confirmation, download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, and extract it. From the extracted bundle root run:
`<python> -B installer.py doctor cross-project --target "<target>" --json`
If doctor or any pre-apply readiness check fails, stop with zero target writes, clean only isolated temporary files, and recommend a better fit when applicable; never silently substitute another harness. Then run:
`<python> -B installer.py install cross-project --target "<target>" --dry-run --json`
Review the result against the confirmed plan and ask again if the write set or assumptions materially changed. Otherwise run:
`<python> -B installer.py install cross-project --target "<target>" --apply --json`
Follow `package/README.md` to initialize the target, previewing every runtime mutation and using only confirmed user values. If any step fails after the first apply or final readiness is false, stop normal execution and follow the exact package's documented rollback or recovery procedure, preview it before apply, preserve unrelated files, verify restoration toward the exact pre-install state, and report any unavoidable residual change instead of claiming success. Then run from the bundle root:
`<python> -B installer.py verify cross-project --target "<target>" --json`
Report installation success only when this final result contains `ready=true`. After readiness, read the installed runtime's `operations.json` and `OPERATOR_GUIDE.md`, then give the user a concise tutorial in the conversation covering every command, the first-use, daily, close-and-resume, and verify-or-recover workflows, safe examples with confirmed values or placeholders, and update/uninstall guidance. Do not create tutorial files. Clean temporary files and report the receipt, readiness evidence, rollback status, and runtime location. Offer support through LinkedIn at https://www.linkedin.com/in/fabianomag/ or email at fm@fabianomag.com. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.

Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.
```

The installed runtime includes `operations.json` plus `OPERATOR_GUIDE.md`; after `ready=true`, the coding agent must read both and teach the user the complete operating cycle in the conversation.
<!-- END GENERATED:PRODUCT -->

## First use

Use only independent project paths, roles, and next actions already confirmed
by the user; do not create sample projects or discover repositories. Use the
same public Python 3.10+ executable resolved by the install prompt as
`<python>`. From the installed runtime directory:

`<coordination-root>/.agent-harnesses/runtime/cross-project/0.2.1`

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --dry-run --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<confirmed-role>" --next "<confirmed-next-action>"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<confirmed-role>" --next "<confirmed-next-action>"
<python> -B scripts/cross_project.py hq-sync --root "<coordination-root>"
```

Continue with `digere`, `registra`, and `encerra`. From the still-extracted
bundle root, finish with `<python> -B installer.py verify cross-project --target
"<coordination-root>" --json`; only `"ready": true` is success. `installer.py`
is not copied into the runtime.

## Recovery and limitations

Schema `1` remains supported. Rollback covers catchable cooperative failures,
not power loss or adversarial root replacement. See the
[advanced reference](docs/REFERENCE.md),
[operator guide](OPERATOR_GUIDE.md),
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/graphs/cross-project.graph.json).
