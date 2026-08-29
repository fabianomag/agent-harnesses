<!-- BEGIN GENERATED:PRODUCT -->
# Control Plane Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.0`

**Best for:** A new control plane whose registry and lifecycle mutations justify transactions and recovery.

**Not for:** Adopting an existing project layout, dispatching agents, or executing project work.

**What it changes:** Creates a strict Master registry and managed front structure through validated transactional mutations. It does not call models or dispatch agents.

Strengths: **Strict registry · Transactions · Recovery**. Complexity: high.

## Installation

Copy only this prompt:

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

`doctor` and `install --dry-run` stop without writes when the target looks like
an existing Master or contains projects that this package cannot safely adopt.

## First use

Use a new empty workspace and the same public Python 3.10+ executable resolved
by the install prompt as `<python>`. From the installed runtime directory:

`<workspace>/.agent-harnesses/runtime/orchestration/0.2.0`

```text
<python> -B hq.py --root "<workspace>" --json bom-dia
<python> -B hq.py --root "<workspace>" --json init --id alpha --name "Alpha" --path fronts/alpha --dry-run
<python> -B hq.py --root "<workspace>" --json init --id alpha --name "Alpha" --path fronts/alpha --apply
<python> -B hq.py --root "<workspace>" --json hq-sync
```

From the still-extracted bundle root, finish with `<python> -B installer.py verify
orchestration --target "<workspace>" --json`; only `"ready": true` is success.
`installer.py` is not copied into the runtime.

## Recovery and limitations

Schema `1` remains supported. Mutations use a journal and explicit recovery,
but the harness never executes registered projects. See the
[advanced reference](docs/REFERENCE.md),
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/orchestration.graph.json).
