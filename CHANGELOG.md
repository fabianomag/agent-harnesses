# Changelog

All notable public changes to Agent Harnesses are recorded here. Historical
`0.1.x` package tags remain immutable; collection releases begin at `v0.2.0`.

## [0.2.3] - 2026-08-29

- Keep every Multi-Project row inside the `FRONTS.md` table and render all
  closeout resumption notes in a separate deterministic section.
- Require Workspace Harness to contain at least one explicitly registered
  child before operational verification can report `ready=true`.
- Clarify that Workspace `--owner` is relative to the selected child root.
- Distinguish the Control Plane's verified root-relative path containment from
  semantic responsibility boundaries, which remain explicit user-owned
  context and are never inferred or certified by `hq-sync`.
- Preserve reversible receipt-owned upgrades from immutable `v0.2.2`,
  including installations that themselves preserved a `v0.2.1` predecessor.
- Serialize concurrent exact installs without misclassifying a cooperatively
  managed onboarding block as unreceipted, while keeping mismatch preflight
  read-only.
- Supersede immutable `v0.2.2` after public copied-prompt smoke testing exposed
  the Multi-Project projection and empty-Workspace readiness defects.

## [0.2.2] - 2026-08-29

- Allow Multi-Project Harness to coordinate confirmed independent project
  roots outside the coordination directory while preserving fail-closed path
  validation and zero writes to those projects.
- Correct the generated operator contracts for Workspace `add`/`recover` and
  Control Plane `digere`/`recover` so their persistent effects match the
  runtimes exactly.
- Preserve direct, non-mutating reads of Project Harness state created by
  `0.1.0`, `0.2.0`, and `0.2.1` during the `0.2.2` update.
- Supersede immutable `v0.2.1` after public copied-prompt smoke testing exposed
  the Multi-Project external-root defect.

## [0.2.1] - 2026-08-29

- Make the core packages explicitly agent-agnostic: each package ships its
  complete local runtime, a machine-readable `operations.json`, and operator
  guides in English and PT-BR without requiring an agent-specific Skill.
- Require the Copy Install flow to finish with a conversational tutorial that
  explains the selected harness's operations, persistence, resumption,
  verification, recovery, and removal without writing synthetic onboarding
  records into the user's target.
- Separate optional OpenAI adapters under `adapters/openai/`; they remain
  manual, opt-in integrations and are excluded from the installer, core ZIPs,
  and primary site snapshot.
- Distinguish package installation and structural readiness from completed
  human onboarding, and extend deterministic release tests around the portable
  operating contract.

## [0.2.0] - 2026-08-29

- Rename the public choices to Project Harness, Workspace Harness,
  Multi-Project Harness, and Control Plane Harness while preserving stable
  package IDs.
- Add a dependency-free, target-local installer with explicit
  `downloaded → installed → initialized → verified → ready` semantics.
- Prevent installed-but-uninitialized targets from being reported as ready and
  reject incompatible existing layouts before installation writes.
- Add concise English and PT-BR documentation, one isolated install prompt per
  harness, and a generated site snapshot.
- Publish one deterministic package-only ZIP per harness, one checksum sidecar
  per primary asset, and a commit-bound release manifest.
- Preserve state schema `1` compatibility, including read-only support for
  Project Harness `0.1.0` state without implicit migration.
