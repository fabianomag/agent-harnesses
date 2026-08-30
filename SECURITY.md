# Security Policy

## Supported versions

The supported public line is the unified Agent Harnesses `v0.2.3` release.
Historical `0.1.x` tags and `v0.2.0` remain immutable but are superseded.
Package version and state schema are independent; Project Harness `0.2.3` reads and verifies
its `0.1.0` state without silently rewriting it.

## Local safety boundary

The standalone installer requires Python 3.10 or newer, one explicit existing
target, one harness selector, and an individual release-asset checksum. It
rejects linked target components, unsafe marker/control paths, mismatched
harness markers, malformed inventories, and changed installed bytes.

`doctor` is read-only. `install --dry-run` verifies the selected bundle
inventory and target compatibility without writing. `install --apply` copies
only the selected package into a target-local runtime boundary and records an
exact receipt. It also manages one bounded onboarding block in target-root
`AGENTS.md`, preserving all content outside that block. It does not change
`PATH`, install a global Skill, edit `.gitignore`, initialize the target, or
edit unrelated documentation.

Publication uses a unique target-local stage and a platform-native no-clobber
directory rename. A failed or interrupted installer-owned download, extraction,
or pre-publication stage is cleaned up. An already published exact runtime is
verified and treated idempotently; divergent or extra bytes are refused rather
than overwritten. `uninstall` removes only unchanged receipt-owned runtime
bytes and its unchanged onboarding block. It never removes initialized harness
state or unrelated `AGENTS.md` content.

Operational readiness is separate from package installation. The installer
returns `ready: true` only after the selected runtime verifies an initialized
target. The onboarding pointer must also remain intact. Installed but
uninitialized targets fail with `E_NOT_READY`. Conversational tutorial delivery
is a separate coding-agent obligation and is never fabricated as installer
state.

These guarantees assume a cooperative local filesystem. They do not promise
durability across power loss, hostile filesystem replacement, network
filesystem semantics, or an adversary mutating the target concurrently.
Package runtimes have additional transaction, rollback, locking, and recovery
boundaries documented in their advanced references.

## Public-safety validation

The repository validator scans public text for generic high-risk patterns and
rejects symbolic links. In a linked worktree it ignores only the administrative
`.git` marker at the repository root; other public files remain in scope.

Optional private deny patterns are accepted only from a regular UTF-8 file
outside the repository. Diagnostics contain generic codes and locations only.
They never print the external input path, pattern, match, or source excerpt.

## Reporting

GitHub private vulnerability reporting is a publication gate and must be
enabled before any tag or release is created.

Use [Report a vulnerability](https://github.com/fabianomag/agent-harnesses/security/advisories/new)
for a private GitHub security advisory. Never place a credential, token,
private identifier, deny pattern, private or absolute local path, full log, or
sensitive reproduction in a public issue. The Installation Report Issue Form
is not a security channel. A public issue is appropriate only for a fully
synthetic, non-sensitive reproduction.
