# Security Policy

## Supported versions

There are no published releases or supported release lines yet. The catalog
separates locally implemented artifacts from publication status. Every
immutable documentation, prompt, source, release, and interactive-diagram link
is `unpublished` with no URL. The catalog is not a release, support, or
published-evaluation declaration.

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

GitHub private vulnerability reporting is a pre-publication gate. It cannot be
enabled while this repository remains private; it will be enabled immediately
after the repository becomes public and before any tag or release is created.
Once the repository Security > Advisories page shows **Report a
vulnerability**, use that form for a private report.

Until that private form is available, do not submit sensitive vulnerability
details. Never place a credential, token, private identifier, deny pattern,
private or absolute local path, full log, or sensitive reproduction in a public
issue. The Installation Report Issue Form is not a security channel. A public
issue is appropriate only for a fully synthetic, non-sensitive reproduction.
