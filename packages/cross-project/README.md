<!-- BEGIN GENERATED:PRODUCT -->
# Multi-Project Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.0`

**Best for:** Existing independent project roots that need explicit handoffs and transversal coordination.

**Not for:** A contained child index or a new strict registry with journaled recovery.

**What it changes:** Creates a canonical coordination manifest and managed root projections without taking ownership of project-local details.

Strengths: **Independent projects · Handoffs · Structural sync**. Complexity: medium.

## Installation

Copy only this prompt:

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
<!-- END GENERATED:PRODUCT -->

## First use

Create the independent project path before registration. Use the same public
Python 3.10+ executable resolved by the install prompt as `<python>`. From the
installed runtime directory:

`<coordination-root>/.agent-harnesses/runtime/cross-project/0.2.0`

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --dry-run --front alpha --name "Alpha" --path projects/alpha --role "Produces one bounded component" --next "Validate the first slice"
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --front alpha --name "Alpha" --path projects/alpha --role "Produces one bounded component" --next "Validate the first slice"
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
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/cross-project.graph.json).
