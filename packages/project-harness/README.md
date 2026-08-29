<!-- BEGIN GENERATED:PRODUCT -->
# Project Harness

[Português do Brasil](README.pt-BR.md) · Version `0.2.0`

**Best for:** One explicit project that needs checkpoints, closeout, and reliable resumption.

**Not for:** Coordination across workspace children or independent project roots.

**What it changes:** Creates a bounded project state directory and managed context blocks inside the selected project.

Strengths: **Checkpoints · Close and resume · Fast setup**. Complexity: low.

## Installation

Copy only this prompt:

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
<!-- END GENERATED:PRODUCT -->

For manual installation, verify the individual `.sha256` sidecar before
extraction, then run `installer.py doctor`, `install --dry-run`, and `install
--apply` with selector `project-harness` and one explicit `--target`.

## First use

Use the same public Python 3.10+ executable resolved by the install prompt as
`<python>`. From the installed runtime directory:

`<project-root>/.agent-harnesses/runtime/project-harness/0.2.0`

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

Package version and state schema are independent. Runtime `0.2.0` creates
schema `1` state and reads/verifies Project Harness `0.1.0` state without
rewriting its `harnessVersion`. No implicit migration occurs.

## Recovery and limitations

The harness is project-local and never coordinates sibling roots or external
services. It preserves existing text outside its managed blocks. Use the
runtime's dry-run before any repair; uninstall removes only unchanged
receipt-owned runtime bytes and leaves initialized project files intact.

Technical implementation, collision, rollback, evidence, and diagram details
are in the [advanced reference](docs/REFERENCE.md), immutable
[catalog](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json),
and [graph](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/project-harness.graph.json).
