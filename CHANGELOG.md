# Changelog

All notable public changes to Agent Harnesses are recorded here. Historical
`0.1.x` package tags remain immutable; collection releases begin at `v0.2.0`.

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
