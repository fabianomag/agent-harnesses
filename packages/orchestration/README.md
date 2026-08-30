<!-- BEGIN GENERATED:PRODUCT -->
# Control Plane Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.3`

**Best for:** A new control plane whose registry and lifecycle mutations justify transactions and recovery.

**Not for:** Adopting an existing project layout, dispatching agents, or executing project work.

**What it changes:** Creates a strict Master registry and managed front structure through validated transactional mutations. It does not call models or dispatch agents.

Strengths: **Strict registry · Transactions · Recovery**. Complexity: high.

**Ready means:** Technical readiness means at least one front is registered, every registered root-relative path is contained and safe, the registry and generated lifecycle files are coherent, no recovery is pending, and hq-sync is clean. It does not certify a front's semantic responsibility boundary.

**Before installation, confirm:**

- The explicit target is a deliberate new Master or control-plane root, not an existing coordination structure to adopt.
- The initial fronts and their intended root-relative paths are known, and the user can state each front's semantic responsibility boundary. The harness will not infer that boundary.
- The work genuinely requires a transactional registry, validated mutations, rollback, and recovery rather than only project handoffs.

## Installation

Copy only this prompt:

```text
Install Control Plane Harness (`orchestration`) v0.2.3 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/orchestration-0.2.3.zip.

Before proposing execution, confirm every selected-harness readiness fact:
- The explicit target is a deliberate new Master or control-plane root, not an existing coordination structure to adopt.
- The initial fronts and their intended root-relative paths are known, and the user can state each front's semantic responsibility boundary. The harness will not infer that boundary.
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

The installed runtime includes `operations.json` plus `OPERATOR_GUIDE.md`; after `ready=true`, the coding agent must read both and teach the user the complete operating cycle in the conversation.
<!-- END GENERATED:PRODUCT -->

`doctor` and `install --dry-run` stop without writes when the target looks like
an existing Master or contains projects that this package cannot safely adopt.

## First use

Use a deliberate new control-plane root and only confirmed front values. Do not
adopt an existing structure or create sample fronts. Use the same public Python
3.10+ executable resolved by the install prompt as `<python>`. From the
installed runtime directory:

`<workspace>/.agent-harnesses/runtime/orchestration/0.2.3`

```text
<python> -B hq.py --root "<workspace>" --json bom-dia
<python> -B hq.py --root "<workspace>" --json init --id "<front-id>" --name "<front-name>" --path "<front-path>" --dry-run
<python> -B hq.py --root "<workspace>" --json init --id "<front-id>" --name "<front-name>" --path "<front-path>" --apply
<python> -B hq.py --root "<workspace>" --json hq-sync
```

From the still-extracted bundle root, finish with `<python> -B installer.py verify
orchestration --target "<workspace>" --json`; only `"ready": true` is success.
`installer.py` is not copied into the runtime.

## Recovery and limitations

Schema `1` remains supported. Mutations use a journal and explicit recovery,
but the harness never executes registered projects. See the
[advanced reference](docs/REFERENCE.md),
[operator guide](OPERATOR_GUIDE.md),
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/graphs/orchestration.graph.json).
