<!-- BEGIN GENERATED:PRODUCT -->
# Agent Harnesses

[Português do Brasil](README.pt-BR.md)

Four local harnesses for four different coordination boundaries. Choose the smallest boundary that matches your actual work; the packages are siblings, not levels in a maturity ladder.

Interactive guide: https://fabianomag.com/projects/agent-harnesses

Requirements: Python 3.10 or newer, an explicit existing target directory, and one exact `v0.2.0` release asset. The runtimes use only the Python standard library. The installer does not change `PATH`, edit `.gitignore`, or install a global Skill.

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
Install Project Harness (`project-harness`) v0.2.0 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/project-harness-0.2.0.zip. Before any write, confirm the explicit target and resolve exactly one Python 3.10+ executable available to the user or system as `<python>` (for example `python3`, `python`, or `py -3`); reuse only that executable and never use a private Codex runtime. Download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, then extract it. From the extracted bundle root run:
`<python> -B installer.py doctor project-harness --target "<target>" --json`
Stop without writes on a mismatch and only recommend a better fit; never silently substitute another harness. Then run:
`<python> -B installer.py install project-harness --target "<target>" --dry-run --json`
`<python> -B installer.py install project-harness --target "<target>" --apply --json`
Follow `package/README.md` inside the extracted bundle to initialize the target, then run from the bundle root:
`<python> -B installer.py verify project-harness --target "<target>" --json`
Report success only when this final result contains `ready=true`. Clean up temporary files and report the receipt plus `uninstall`/rollback instructions. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.
```

### Workspace Harness

```text
Install Workspace Harness (`workspace-coordination`) v0.2.0 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/workspace-coordination-0.2.0.zip. Before any write, confirm the explicit target and resolve exactly one Python 3.10+ executable available to the user or system as `<python>` (for example `python3`, `python`, or `py -3`); reuse only that executable and never use a private Codex runtime. Download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, then extract it. From the extracted bundle root run:
`<python> -B installer.py doctor workspace-coordination --target "<target>" --json`
Stop without writes on a mismatch and only recommend a better fit; never silently substitute another harness. Then run:
`<python> -B installer.py install workspace-coordination --target "<target>" --dry-run --json`
`<python> -B installer.py install workspace-coordination --target "<target>" --apply --json`
Follow `package/README.md` inside the extracted bundle to initialize the target, then run from the bundle root:
`<python> -B installer.py verify workspace-coordination --target "<target>" --json`
Report success only when this final result contains `ready=true`. Clean up temporary files and report the receipt plus `uninstall`/rollback instructions. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.
```

### Multi-Project Harness

```text
Install Multi-Project Harness (`cross-project`) v0.2.0 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/cross-project-0.2.0.zip. Before any write, confirm the explicit target and resolve exactly one Python 3.10+ executable available to the user or system as `<python>` (for example `python3`, `python`, or `py -3`); reuse only that executable and never use a private Codex runtime. Download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, then extract it. From the extracted bundle root run:
`<python> -B installer.py doctor cross-project --target "<target>" --json`
Stop without writes on a mismatch and only recommend a better fit; never silently substitute another harness. Then run:
`<python> -B installer.py install cross-project --target "<target>" --dry-run --json`
`<python> -B installer.py install cross-project --target "<target>" --apply --json`
Follow `package/README.md` inside the extracted bundle to initialize the target, then run from the bundle root:
`<python> -B installer.py verify cross-project --target "<target>" --json`
Report success only when this final result contains `ready=true`. Clean up temporary files and report the receipt plus `uninstall`/rollback instructions. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.
```

### Control Plane Harness

```text
Install Control Plane Harness (`orchestration`) v0.2.0 from https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/orchestration-0.2.0.zip. Before any write, confirm the explicit target and resolve exactly one Python 3.10+ executable available to the user or system as `<python>` (for example `python3`, `python`, or `py -3`); reuse only that executable and never use a private Codex runtime. Download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, then extract it. From the extracted bundle root run:
`<python> -B installer.py doctor orchestration --target "<target>" --json`
Stop without writes on a mismatch and only recommend a better fit; never silently substitute another harness. Then run:
`<python> -B installer.py install orchestration --target "<target>" --dry-run --json`
`<python> -B installer.py install orchestration --target "<target>" --apply --json`
Follow `package/README.md` inside the extracted bundle to initialize the target, then run from the bundle root:
`<python> -B installer.py verify orchestration --target "<target>" --json`
Report success only when this final result contains `ready=true`. Clean up temporary files and report the receipt plus `uninstall`/rollback instructions. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.
```
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
`<target>/.agent-harnesses/runtime/<id>/0.2.0`.

The state is explicit: `downloaded → installed → initialized → verified →
ready`. Installing package bytes is not operational success. Only a successful
`verify` result with `"ready": true` means the initialized target is ready.

To remove only unchanged, receipt-owned runtime bytes while leaving initialized
project files untouched:

```text
<python> -B installer.py uninstall <selector> --target "<target>" --dry-run --json
<python> -B installer.py uninstall <selector> --target "<target>" --apply --json
```

## Technical evidence and advanced detail

The five evidence dimensions (`Context`, `Skill`, `Harness`, `Loop`, and
`Guardrails`) remain technical evidence, not comparison badges or a package
ranking. See the generated [catalog](catalog/harnesses.json),
[graphs](graphs/), and the [advanced reference](docs/REFERENCE.md).

Release `v0.2.0` contains four deterministic package-only ZIPs, one checksum
sidecar per asset, the standalone installer, the release manifest, the site
snapshot, and the changelog. Historical `0.1.x` tags remain immutable and are
superseded rather than rewritten.

Copyright Fabiano Magalhães. [MIT License](LICENSE).
