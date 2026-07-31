# Security Policy

## Supported versions

The published release lines are `project-harness` `0.1.0`,
`workspace-coordination` `0.1.0`, `cross-project` `0.1.1`, and
`orchestration` `0.1.0`. Each release binds its documentation, source, install
bundle, and evidence to an immutable tag. Publication does not extend the
platform and recovery claims documented by each package.

## Local safety boundary

The common package manager requires an explicit existing installation root and
an exact package ID plus version. It inspects existing lexical root components
before canonicalization, rejects link-like managed paths, validates cataloged
hashes, and performs a zero-write dry-run. If the destination already exists,
it is verified before any stage is created: an exact destination reports
`unchanged`, while a changed destination or one with an extra entry is refused.
When publication is still needed, the manager creates a unique stage, writes
and verifies the complete payload, and publishes it with a platform-native
no-clobber directory rename. The rename provides atomic visibility on a
cooperative local filesystem. Concurrent identical attempts are not serialized
by a common lock. A contender that has already created its stage and then finds
a verified destination reports `unchanged-residual` and preserves that stage.
POSIX symbolic-link rejection is exercised locally; this candidate does not
claim a Windows reparse-point validation result.

That does not promise durability across power loss, hostile filesystem
replacement, network filesystem semantics, or uncooperative concurrent
mutation. A failed, interrupted, or losing pre-publication attempt can leave an
empty, partial, or complete hidden stage; interruption after publication can
leave a complete destination. The common package manager never removes residual
stages automatically. A later apply that reaches staging uses a fresh stage; an
apply whose initial pre-stage check finds a verified destination reports
`unchanged`. Package runtimes have distinct safety and recovery contracts; read
the selected package README instead of assuming the common installer extends
those guarantees.

In particular, Cross-Project Harness `0.1.1` provides rollback/coherence for
catchable failures and cooperative readers. It does not claim physically
crash-safe multi-file atomicity after a process kill or power loss, and
adversarial replacement of the selected root inode remains a residual risk.

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
