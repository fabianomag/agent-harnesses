# Agent Harnesses v0.2.3 — advanced reference

The root [README](../README.md) owns the public choice and installation path.
This reference keeps implementation and evidence detail out of that first
decision. The four packages are siblings with different ownership boundaries,
not maturity levels.

## Technical evidence

The deterministic [catalog](../catalog/harnesses.json) and
[schema](../schemas/harness-catalog.schema.json) describe five evidence
dimensions: `Context`, `Skill`, `Harness`, `Loop`, and `Guardrails`. They are
technical evidence, not comparison badges or a ranking. A generated graph and
static SVG exist for each package under [`graphs/`](../graphs/) and
[`assets/`](../assets/); the collection graph expresses membership only.

Automated checks prove bounded repository contracts. They do not claim that a
fresh coding-agent walkthrough or every public platform was executed unless an
immutable release manifest explicitly binds that evidence to the exact commit
and asset bytes.

## Standalone installer boundary

`installer.py` is dependency-free on Python 3.10+. In command examples,
`<python>` means the same single user- or system-available Python 3.10+
executable selected for installation (for example `python3`, `python`, or
`py -3`), never a private application runtime. The installer operates only
inside an explicit target and exposes:

```text
doctor <selector> --target "<path>"
install <selector> --target "<path>" --dry-run|--apply
verify <selector> --target "<path>"
uninstall <selector> --target "<path>" --dry-run|--apply
```

JSON results contain `code`, `phase`, `message`, `remediation`, and `ready`,
plus target-relative `operationsContract` and `operatorGuides` paths when the
runtime is installed.
The state vocabulary is `downloaded → installed → initialized → verified →
ready`; no installed-but-uninitialized target can report success. Stable
failures include `E_PYTHON_UNSUPPORTED`, `E_TARGET_AMBIGUOUS`,
`E_HARNESS_MISMATCH`, `E_CHECKSUM_MISMATCH`,
`E_INITIALIZATION_CONFLICT`, and `E_NOT_READY`.

`doctor` and `dry-run` are zero-write operations. The installer validates the
individual archive sidecar before extraction, verifies the recorded package
inventory, rejects linked/colliding target paths, and never silently changes
the selected harness. Runtime bytes live at
`<target>/.agent-harnesses/runtime/<id>/0.2.3`. A receipt records exactly those
bytes together with the bounded onboarding block digest and whether the
installer created `AGENTS.md`. Uninstall refuses changed bytes and leaves
initialized state untouched.

The repository's older `tools/package_manager.py` remains a contributor-side
payload verifier. It is not the public `v0.2.3` installation interface.

## Package version and state schema

Package version is not state schema version. Release `0.2.3` keeps the existing
schema `1` contracts. Project Harness `0.2.3` explicitly reads and verifies
state created by Project Harness `0.1.0` while preserving the recorded
`harnessVersion`; it never rewrites that state as an implicit migration. Any
future migration must expose its own `dry-run` and `apply` operation.

## Runtime-specific contracts

- [Project Harness](../packages/project-harness/docs/REFERENCE.md) uses a
  project-local state directory and managed Markdown blocks.
- [Workspace Harness](../packages/workspace-coordination/docs/REFERENCE.md)
  keeps one coordinator index while preserving child-local responsibility. It
  requires a single mutating writer per coordinator root.
- [Multi-Project Harness](../packages/cross-project/docs/REFERENCE.md) owns a
  canonical cross-project manifest, bounded projections, and explicit handoffs.
  Its rollback guarantees cover cooperative catchable failures, not power loss.
- [Control Plane Harness](../packages/orchestration/docs/REFERENCE.md) uses a
  strict registry, validated transactions, a journal, and explicit recovery.
  It does not call models, dispatch coding agents, execute projects, or adopt an
  existing Master-like structure automatically.

## Immutable release shape

Release `v0.2.3` contains four deterministic package-only ZIPs. Each ZIP
contains only the selected package, necessary common files, license, localized
README files, `operations.json`, localized operator guides, installer, and a
recorded inventory. Platform-specific adapters remain repository-only and are
not part of these ZIPs. Each asset has its own
`.sha256` sidecar; there is no checksum file that requires downloading unrelated
assets.

The release manifest binds the source commit and tag to exact asset SHA-256 and
size values. The generated site snapshot contains all EN/PT-BR product copy and
the canonical release-manifest URL, so the site never retypes names, prompts,
versions, URLs, or digests.

## Contributor verification

Run all automated and structural checks with:

```text
<python> -B tools/run_checks.py
```

The runner reports manual coding-agent evidence as not executed. A release is
publishable only after its exact built bytes pass the release verifier and the
required public smoke tests.
