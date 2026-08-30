# Install one harness from an immutable release

Choose exactly one `v0.2.3` package asset:

| Public name | Selector | Asset |
| --- | --- | --- |
| Project Harness | `project-harness` | `project-harness-0.2.3.zip` |
| Workspace Harness | `workspace-coordination` | `workspace-coordination-0.2.3.zip` |
| Multi-Project Harness | `cross-project` | `cross-project-0.2.3.zip` |
| Control Plane Harness | `orchestration` | `orchestration-0.2.3.zip` |

Download that ZIP and only its matching `<asset>.sha256` sidecar into an
isolated temporary directory. Verify the recorded SHA-256 before extracting or
executing anything. A mismatch is terminal: discard both files and download
them again. There is no collection-wide checksum file.

Resolve exactly one Python 3.10 or newer executable from the user or system
environment as `<python>` (for example `python3`, `python`, or `py -3`) and
reuse it for every command. Never substitute a private application runtime.
Extract the verified ZIP, enter its single top-level bundle directory, and keep
that directory until final verification.

Before downloading, confirm that the selected target already has the real
project/workspace boundaries required by that harness. Do not use the harness
to organize an ambiguous folder tree or create sample projects. Run these
commands with one selector and one explicit, existing target:

```text
<python> -B installer.py doctor <selector> --target "<target>" --json
<python> -B installer.py install <selector> --target "<target>" --dry-run --json
<python> -B installer.py install <selector> --target "<target>" --apply --json
```

Stop on any nonzero result. A mismatch recommends another harness but never
substitutes it or writes to the target. Package installation places the runtime
at `<target>/.agent-harnesses/runtime/<id>/0.2.3`; it does not initialize the
target and is not success by itself. It creates or updates only the bounded
Agent Harness onboarding block in target-root `AGENTS.md`.

Read the selected bundle's `package/README.md`, run its package-specific initialization
with the documented `dry-run`/`apply` sequence, and then return to the still-
extracted bundle root:

```text
<python> -B installer.py verify <selector> --target "<target>" --json
```

Report success only when this command exits zero with `"ready": true`. Do not
edit content outside the managed `AGENTS.md` block, `ARCHITECTURE.md`, decision
documents, `PATH`, or `.gitignore` merely to record installation. After
`ready=true`, read the installed `operations.json` and localized operator guide
and teach the user the complete command surface before removing the temporary
download and extraction.

Uninstall removes only unchanged runtime bytes recorded by the target-local
receipt and removes only its unchanged managed `AGENTS.md` block. It leaves
package-initialized project/workspace files untouched:

```text
<python> -B installer.py uninstall <selector> --target "<target>" --dry-run --json
<python> -B installer.py uninstall <selector> --target "<target>" --apply --json
```
