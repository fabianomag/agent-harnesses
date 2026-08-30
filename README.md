<!-- BEGIN GENERATED:PRODUCT -->
# Agent Harnesses

[Português do Brasil](README.pt-BR.md)

Four local harnesses for four different coordination boundaries. Choose the smallest boundary that matches your actual work; the packages are siblings, not levels in a maturity ladder.

Interactive guide: https://fabianomag.com/projects/agent-harnesses

Requirements: Python 3.10 or newer, an explicit existing target directory, and one exact `v0.2.2` ZIP with its matching checksum sidecar. Each ZIP installs the complete Python-standard-library runtime, command inventory, and agent-agnostic operator guide for one harness. It does not change `PATH`, edit `.gitignore`, or require a global Skill.

## What do you need to coordinate?

| Harness | Choose it when | Not for | Strengths | Complexity |
| --- | --- | --- | --- | --- |
| [Project Harness](packages/project-harness/README.md) (`project-harness`) | I need one project to remember context between work sessions. | Coordination across workspace children or independent project roots. | Checkpoints · Close and resume · Fast setup | Low |
| [Workspace Harness](packages/workspace-coordination/README.md) (`workspace-coordination`) | I have autonomous child folders inside one containing workspace. | Independent repositories or a single project with no child coordination. | Child index · Ownership boundaries · Shared workspace view | Medium |
| [Multi-Project Harness](packages/cross-project/README.md) (`cross-project`) | I need handoffs and shared state across existing independent projects. | A contained child index or a new strict registry with journaled recovery. | Independent projects · Handoffs · Structural sync | Medium |
| [Control Plane Harness](packages/orchestration/README.md) (`orchestration`) | I am creating a new structure that needs a strict registry, transactions, and recovery. | Adopting an existing project layout, dispatching agents, or executing project work. | Strict registry · Transactions · Recovery | High |

Control Plane Harness is a local control plane. It does not call models, dispatch agents, or execute projects, and it intentionally refuses to adopt an existing Master-like structure when ownership would be ambiguous.

## Copy one install prompt

Copy only the block for the harness you chose. Each block names one package, one version, and one ZIP.

### Project Harness

```text
Install Project Harness (`project-harness`) v0.2.2 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/project-harness-0.2.2.zip.

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

### Workspace Harness

```text
Install Workspace Harness (`workspace-coordination`) v0.2.2 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/workspace-coordination-0.2.2.zip.

Before proposing execution, confirm every selected-harness readiness fact:
- The explicit target is the container workspace, not one of its child projects.
- The existing contained child projects to register are already known.
- Each selected child has an explicit local owner file and its detailed state will remain locally owned.
If any fact is unknown or false, stop before downloads or target writes, explain what must be organized first, and offer the support contacts below.

If the current mode cannot execute, request a switch to an execution-capable mode only after presenting the plan and receiving confirmation.

Use the agent's native Plan mode and structured questions when available; otherwise present the same plan and questions conversationally. Work in two explicit stages: plan first, then execute only after confirmation. Before any write, including a download or temporary extraction, inspect only the explicit target and available public tooling read-only. Present four separate checklists: (1) fit and target, (2) safety and write plan, (3) initialization and readiness, and (4) tutorial and handoff. State the selected harness, target, one user- or system-available Python 3.10+ executable as `<python>` (for example `python3`, `python`, or `py -3`), expected writes, required initialization inputs, verification, rollback, and tutorial steps; ask the user to confirm that plan. Never use a private Codex runtime. Do not organize, rename, summarize, migrate, or infer the user's project data. Ask for any missing value instead of inventing it. After confirmation, download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, and extract it. From the extracted bundle root run:
`<python> -B installer.py doctor workspace-coordination --target "<target>" --json`
If doctor or any pre-apply readiness check fails, stop with zero target writes, clean only isolated temporary files, and recommend a better fit when applicable; never silently substitute another harness. Then run:
`<python> -B installer.py install workspace-coordination --target "<target>" --dry-run --json`
Review the result against the confirmed plan and ask again if the write set or assumptions materially changed. Otherwise run:
`<python> -B installer.py install workspace-coordination --target "<target>" --apply --json`
Follow `package/README.md` to initialize the target, previewing every runtime mutation and using only confirmed user values. If any step fails after the first apply or final readiness is false, stop normal execution and follow the exact package's documented rollback or recovery procedure, preview it before apply, preserve unrelated files, verify restoration toward the exact pre-install state, and report any unavoidable residual change instead of claiming success. Then run from the bundle root:
`<python> -B installer.py verify workspace-coordination --target "<target>" --json`
Report installation success only when this final result contains `ready=true`. After readiness, read the installed runtime's `operations.json` and `OPERATOR_GUIDE.md`, then give the user a concise tutorial in the conversation covering every command, the first-use, daily, close-and-resume, and verify-or-recover workflows, safe examples with confirmed values or placeholders, and update/uninstall guidance. Do not create tutorial files. Clean temporary files and report the receipt, readiness evidence, rollback status, and runtime location. Offer support through LinkedIn at https://www.linkedin.com/in/fabianomag/ or email at fm@fabianomag.com. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.

Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.
```

### Multi-Project Harness

```text
Install Multi-Project Harness (`cross-project`) v0.2.2 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/cross-project-0.2.2.zip.

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

### Control Plane Harness

```text
Install Control Plane Harness (`orchestration`) v0.2.2 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/orchestration-0.2.2.zip.

Before proposing execution, confirm every selected-harness readiness fact:
- The explicit target is a deliberate new Master or control-plane root, not an existing coordination structure to adopt.
- The initial fronts, their intended relative paths, and their boundaries are already known.
- The work genuinely requires a transactional registry, validated mutations, rollback, and recovery rather than only project handoffs.
If any fact is unknown or false, stop before downloads or target writes, explain what must be organized first, and offer the support contacts below.

If the current mode cannot execute, request a switch to an execution-capable mode only after presenting the plan and receiving confirmation.

Use the agent's native Plan mode and structured questions when available; otherwise present the same plan and questions conversationally. Work in two explicit stages: plan first, then execute only after confirmation. Before any write, including a download or temporary extraction, inspect only the explicit target and available public tooling read-only. Present four separate checklists: (1) fit and target, (2) safety and write plan, (3) initialization and readiness, and (4) tutorial and handoff. State the selected harness, target, one user- or system-available Python 3.10+ executable as `<python>` (for example `python3`, `python`, or `py -3`), expected writes, required initialization inputs, verification, rollback, and tutorial steps; ask the user to confirm that plan. Never use a private Codex runtime. Do not organize, rename, summarize, migrate, or infer the user's project data. Ask for any missing value instead of inventing it. After confirmation, download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, and extract it. From the extracted bundle root run:
`<python> -B installer.py doctor orchestration --target "<target>" --json`
If doctor or any pre-apply readiness check fails, stop with zero target writes, clean only isolated temporary files, and recommend a better fit when applicable; never silently substitute another harness. Then run:
`<python> -B installer.py install orchestration --target "<target>" --dry-run --json`
Review the result against the confirmed plan and ask again if the write set or assumptions materially changed. Otherwise run:
`<python> -B installer.py install orchestration --target "<target>" --apply --json`
Follow `package/README.md` to initialize the target, previewing every runtime mutation and using only confirmed user values. If any step fails after the first apply or final readiness is false, stop normal execution and follow the exact package's documented rollback or recovery procedure, preview it before apply, preserve unrelated files, verify restoration toward the exact pre-install state, and report any unavoidable residual change instead of claiming success. Then run from the bundle root:
`<python> -B installer.py verify orchestration --target "<target>" --json`
Report installation success only when this final result contains `ready=true`. After readiness, read the installed runtime's `operations.json` and `OPERATOR_GUIDE.md`, then give the user a concise tutorial in the conversation covering every command, the first-use, daily, close-and-resume, and verify-or-recover workflows, safe examples with confirmed values or placeholders, and update/uninstall guidance. Do not create tutorial files. Clean temporary files and report the receipt, readiness evidence, rollback status, and runtime location. Offer support through LinkedIn at https://www.linkedin.com/in/fabianomag/ or email at fm@fabianomag.com. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.

Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.
```

## Agent compatibility

Codex is the primary guided-install experience. Claude Code Desktop is the agent-agnostic smoke target; neither path requires a global Skill.

## Support

LinkedIn: https://www.linkedin.com/in/fabianomag/ · Email: fm@fabianomag.com
<!-- END GENERATED:PRODUCT -->

## Manual install

Download one ZIP and its matching `<asset>.sha256` file. Verify that individual
sidecar before extraction; there is no collection-wide `SHA256SUMS` file.

After extraction, run from the bundle root. Keep that root until the final
`verify`; `installer.py` is not copied into the installed runtime. Resolve one
user- or system-available Python 3.10+ executable as `<python>` (for example
`python3`, `python`, or `py -3`) and reuse it for every command:

```text
<python> -B installer.py doctor <selector> --target "<target>" --json
<python> -B installer.py install <selector> --target "<target>" --dry-run --json
<python> -B installer.py install <selector> --target "<target>" --apply --json
```

Then follow `package/README.md` in the extracted bundle and finish with:

```text
<python> -B installer.py verify <selector> --target "<target>" --json
```

The selected runtime lives at
`<target>/.agent-harnesses/runtime/<id>/0.2.2`.

The state is explicit: `downloaded → installed → initialized → verified →
ready`. Installing package bytes is not operational success. Only a successful
`verify` result with `"ready": true` means the initialized target is ready.
`tutorial delivered` is a separate conversational outcome: after readiness,
the coding agent reads the installed operator contract and teaches the user;
the installer does not pretend to measure whether that explanation happened.

To remove only the exact managed onboarding block and unchanged, receipt-owned
runtime bytes while leaving initialized project files untouched:

```text
<python> -B installer.py uninstall <selector> --target "<target>" --dry-run --json
<python> -B installer.py uninstall <selector> --target "<target>" --apply --json
```

## Technical evidence and advanced detail

The five evidence dimensions (`Context`, `Skill`, `Harness`, `Loop`, and
`Guardrails`) remain technical evidence, not comparison badges or a package
ranking. See the generated [catalog](catalog/harnesses.json),
[graphs](graphs/), and the [advanced reference](docs/REFERENCE.md).
Optional platform-native integrations live under [`adapters/`](adapters/) and
are never part of the four core ZIPs or the default installation.

Release `v0.2.2` contains four deterministic package-only ZIPs, one checksum
sidecar per asset, the standalone installer, the release manifest, the site
snapshot, and the changelog. Historical `0.1.x` tags and immutable `v0.2.0`
remain available and are superseded rather than rewritten.

Copyright Fabiano Magalhães. [MIT License](LICENSE).
