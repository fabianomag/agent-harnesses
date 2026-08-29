<!-- BEGIN GENERATED:PRODUCT -->
# Workspace Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.0`

**Best for:** Contained child projects that share one workspace boundary and a small shared index.

**Not for:** Independent repositories or a single project with no child coordination.

**What it changes:** Creates a workspace control directory and child-local coordination records.

Strengths: **Child index · Ownership boundaries · Shared workspace view**. Complexity: medium.

## Installation

Copy only this prompt:

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
<!-- END GENERATED:PRODUCT -->

## First use

Create the child folders and one declared owner file in each child. Use the
same public Python 3.10+ executable resolved by the install prompt as
`<python>`. From the installed runtime directory:

`<coordinator-root>/.agent-harnesses/runtime/workspace-coordination/0.2.0`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" init --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" init --apply
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id alpha --path child-alpha --owner AGENTS.md --dry-run
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id alpha --path child-alpha --owner AGENTS.md --apply
<python> -B workspace_coordination.py --root "<coordinator-root>" verify
<python> -B workspace_coordination.py --root "<coordinator-root>" open --child alpha
```

From the still-extracted bundle root, finish with `<python> -B installer.py verify
workspace-coordination --target "<coordinator-root>" --json`; only `"ready":
true` is success. `installer.py` is not copied into the runtime.

## Recovery and limitations

The coordinator never discovers children or executes their work. Version
`0.2.0` supports one mutating writer per coordinator root; serialize writers.
State schema remains `1`. See the [advanced reference](docs/REFERENCE.md),
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/workspace-coordination.graph.json).
