# Agent Harnesses

Agent Harnesses is a clean-room, English-first, MIT-licensed collection of
four local harness packages. It solves a practical continuity problem: agent
work becomes fragile when project context, coordination boundaries, decisions,
and next actions exist only in chat history.

Each package makes a different local boundary durable. They are sibling
choices, not maturity levels and not a quality ranking.

## Choose by boundary

Complexity describes the operational surface, not which package is better.
`implemented` means a package runtime exists in this source tree. Publication
does not by itself mean Codex-verified or proven on every platform.

| Package | Problem | Complexity | Use when | Do not use when | Main difference | Version | Docs | Interactive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Project Harness (`project-harness`) | One project loses durable context between work blocks | Low to intermediate | One explicit project needs context, checkpoints, closeout, and a durable next action | Coordination must cross project roots | Smallest executable project-local lifecycle | `0.1.0` | [README](packages/project-harness/README.md) | [Open](https://fabianomag.vercel.app/artifacts/agent-harnesses) |
| Workspace Coordination Harness (`workspace-coordination`) | A containing workspace needs a small map without copying child-local state | Intermediate | Autonomous child folders share one coordinator and governance boundary | Projects are independent roots, or one project is the whole scope | Coordinator index plus child-local ownership; single writer in `0.1.0` | `0.1.0` | [README](packages/workspace-coordination/README.md) | [Open](https://fabianomag.vercel.app/artifacts/agent-harnesses) |
| Cross-Project Harness (`cross-project`) | Named independent projects need deterministic transversal state and handoffs | High | One selected root coordinates named fronts while implementation remains local | A contained child index is enough, or journaled Master recovery is required | Canonical cross-project manifest, structural sync, and bounded reflection | `0.1.1` | [README](packages/cross-project/README.md) | [Open](https://fabianomag.vercel.app/artifacts/agent-harnesses) |
| Orchestration Harness (`orchestration`) | A local control plane needs registry consistency, validated mutations, and recovery | Advanced | A strict Master registry, explicit lifecycle, transactions, and recovery are justified | The goal is to dispatch agents, execute projects, or manage one simple project | Transactional control plane with journaled recovery; it does not call a model or execute projects | `0.1.0` | [README](packages/orchestration/README.md) | [Open](https://fabianomag.vercel.app/artifacts/agent-harnesses) |

## Catalog, badges, and diagrams

The deterministic [catalog](catalog/harnesses.json) contains purpose,
complexity, non-ranking evolutionary position, intended audience, artifact
status, limitations, evidence methods, exact payload hashes, and graph
references for all four packages. Its public schema is
[schemas/harness-catalog.schema.json](schemas/harness-catalog.schema.json).

Badges are evidence dimensions:

- `Context`
- `Skill`
- `Harness`
- `Loop`
- `Guardrails`

Their exact levels are `absent`, `basic`, `partial`, `strong`, and `verified`.
Levels describe evidence strength for one dimension, not overall package
quality. `verified` requires repeatable evaluations of the exact published
version. No package claims that level before its public walkthrough evidence
is attached to the immutable release.

Each package has a distinct generated graph spec and static SVG:

| Package | Graph ID | Spec | Static asset |
| --- | --- | --- | --- |
| Project Harness | `project-harness-flow` | [JSON](graphs/project-harness.graph.json) | [SVG](assets/project-harness.svg) |
| Workspace Coordination Harness | `workspace-coordination-flow` | [JSON](graphs/workspace-coordination.graph.json) | [SVG](assets/workspace-coordination.svg) |
| Cross-Project Harness | `cross-project-flow` | [JSON](graphs/cross-project.graph.json) | [SVG](assets/cross-project.svg) |
| Orchestration Harness | `orchestration-flow` | [JSON](graphs/orchestration.graph.json) | [SVG](assets/orchestration.svg) |

The optional [collection graph](graphs/harnesses.graph.json) and
[collection SVG](assets/harnesses.svg) show membership only. They do not assert
dependency, progression, or preference.

The [interactive experience](https://fabianomag.vercel.app/artifacts/agent-harnesses)
and every version-bound documentation, install, source, and release URL are
published explicitly in the catalog. Release tags and assets are protected by
GitHub Immutable Releases; the interactive URL is the stable collection page.

## Install from one immutable URL

Copy exactly one prompt. Each URL downloads a package-selected, self-contained
release bundle with this source tree, the common installer/verifier, manifests,
documentation, and the selected package's First use instructions.

```text
Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/project-harness-v0.1.0/project-harness-0.1.0.zip
Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/workspace-coordination-v0.1.0/workspace-coordination-0.1.0.zip
Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/cross-project-v0.1.1/cross-project-0.1.1.zip
Install this harness for me: https://github.com/fabianomag/agent-harnesses/releases/download/orchestration-v0.1.0/orchestration-0.1.0.zip
```

The receiving agent must read [INSTALL_FROM_RELEASE.md](INSTALL_FROM_RELEASE.md),
preview the exact no-overwrite installation, apply only after the preview,
verify the installed bytes, and explain the selected package's First use.
Release-page asset metadata and the adjacent `SHA256SUMS` asset carry the
authoritative archive checksum; the checksum is deliberately outside the
archive it authenticates.

## Install one exact package from a source tree

Python 3.10 or newer is required. Package implementations and common tools use
only the Python standard library.

Create one existing real directory as the installation boundary:

```text
python3 -B -c "from pathlib import Path; Path('local-harness-packages').mkdir(exist_ok=True)"
```

Preview, install, and verify one exact package ID and version:

```text
python3 -B tools/package_manager.py install --package project-harness --version 0.1.0 --root local-harness-packages --dry-run
python3 -B tools/package_manager.py install --package project-harness --version 0.1.0 --root local-harness-packages --apply
python3 -B tools/package_manager.py verify --package project-harness --version 0.1.0 --root local-harness-packages
```

Use these exact selections for the other packages:

```text
python3 -B tools/package_manager.py install --package workspace-coordination --version 0.1.0 --root local-harness-packages --dry-run
python3 -B tools/package_manager.py install --package cross-project --version 0.1.1 --root local-harness-packages --dry-run
python3 -B tools/package_manager.py install --package orchestration --version 0.1.0 --root local-harness-packages --dry-run
```

Repeat the selected command with `--apply`, then run `verify` with the same
package ID, version, and root.

The installer copies the cataloged package payload without invoking it. It is
root-bound and inspects every existing lexical component of the installation
root before canonicalizing it, rejecting link-like components. Dry-run writes
nothing. When an apply still needs publication, it stages that attempt under a
unique root-local name and exposes the complete payload with one
platform-native no-clobber directory rename (`renamex_np` on macOS,
`renameat2` on Linux, and non-replacing `os.rename` behavior on Windows). If
that primitive is unavailable, apply fails closed. Concurrent identical
attempts converge on the one verified destination. Repeating an exact
installation is a no-op. A changed destination or extra entry is refused
rather than overwritten.

Successful publication moves its unique stage into place, so it leaves no
stage from that successful attempt behind. Before publication, failed,
interrupted, or losing concurrent attempts deliberately do not auto-delete
their stage: portable pathname cleanup cannot be bound atomically to the
original filesystem object, and deleting by name could erase a replacement
created by another actor. Such a concurrent loser reports
`unchanged-residual`, not a plain no-op. A later apply that reaches staging
uses a fresh stage name; an apply that first sees a verified destination is an
`unchanged` no-op. Neither path alters residual stages.

There is no cleanup journal for process kill or power loss. A failed attempt
can therefore leave an empty, partial, or complete visible stage, while
interruption after publish can leave a complete destination; retry or `verify`
determines whether the destination is valid. Inspect any residual stage before
manual removal. POSIX symbolic-link rejection is exercised locally; no Windows
reparse-point result is claimed by this local candidate.

Installation includes the common MIT `LICENSE` with Fabiano Magalhães as the
documented copyright holder.

## First real use

Read the selected package README first. Package CLIs intentionally keep their
own argument and mutation contracts.

### Project Harness

```text
python3 -B -c "from pathlib import Path; Path('example-project').mkdir(exist_ok=True)"
python3 -B local-harness-packages/project-harness-0.1.0/project_harness.py init --root example-project --dry-run
python3 -B local-harness-packages/project-harness-0.1.0/project_harness.py init --root example-project
python3 -B local-harness-packages/project-harness-0.1.0/project_harness.py verify --root example-project
python3 -B local-harness-packages/project-harness-0.1.0/project_harness.py open --root example-project
```

Continue with the documented `checkpoint` and `close` commands.

### Workspace Coordination Harness

Create the coordinator root, both child folders, and their declared owner files
before registration:

```text
python3 -B -c "from pathlib import Path; root=Path('example-workspace'); (root/'child-alpha').mkdir(parents=True, exist_ok=True); (root/'child-beta').mkdir(parents=True, exist_ok=True); (root/'child-alpha'/'AGENTS.md').write_text('# Alpha owner\n', encoding='utf-8'); (root/'child-beta'/'OWNER.md').write_text('# Beta owner\n', encoding='utf-8')"
python3 -B local-harness-packages/workspace-coordination-0.1.0/workspace_coordination.py --root example-workspace init --dry-run
python3 -B local-harness-packages/workspace-coordination-0.1.0/workspace_coordination.py --root example-workspace init --apply
python3 -B local-harness-packages/workspace-coordination-0.1.0/workspace_coordination.py --root example-workspace verify
python3 -B local-harness-packages/workspace-coordination-0.1.0/workspace_coordination.py --root example-workspace open
```

The package README contains the complete two-child registration and reflection
loop.

### Cross-Project Harness

Create `example-cross/projects/alpha` before registration:

```text
python3 -B -c "from pathlib import Path; Path('example-cross/projects/alpha').mkdir(parents=True, exist_ok=True)"
python3 -B local-harness-packages/cross-project-0.1.1/scripts/cross_project.py bom-dia --root example-cross
python3 -B local-harness-packages/cross-project-0.1.1/scripts/cross_project.py hq-init --root example-cross --dry-run --front alpha --name "Alpha" --path projects/alpha --role "Produces one synthetic component" --next "Validate the first slice"
python3 -B local-harness-packages/cross-project-0.1.1/scripts/cross_project.py hq-init --root example-cross --front alpha --name "Alpha" --path projects/alpha --role "Produces one synthetic component" --next "Validate the first slice"
python3 -B local-harness-packages/cross-project-0.1.1/scripts/cross_project.py hq-sync --root example-cross
```

Continue with the documented `digere`, `registra`, and `encerra` reflection
cycle.

### Orchestration Harness

```text
python3 -B -c "from pathlib import Path; Path('example-orchestration').mkdir(exist_ok=True)"
python3 -B local-harness-packages/orchestration-0.1.0/hq.py --root example-orchestration --json bom-dia
python3 -B local-harness-packages/orchestration-0.1.0/hq.py --root example-orchestration --json init --id alpha --name "Alpha" --path fronts/alpha --dry-run
python3 -B local-harness-packages/orchestration-0.1.0/hq.py --root example-orchestration --json init --id alpha --name "Alpha" --path fronts/alpha --apply
python3 -B local-harness-packages/orchestration-0.1.0/hq.py --root example-orchestration --json hq-sync
```

Continue with the documented focus, digest, record, and closeout commands.

## Agent compatibility

Codex is compatible with the packaged Skill and CLI contracts. Fresh manual
walkthrough evidence is bound to each exact release bundle and candidate commit
in that release's immutable `manual-codex-evidence.json` asset.

Other agent environments are compatible at the explicit CLI and Markdown
contract boundary, but their agent-specific integrations are unverified. The
Codex verification claim does not extend to those other environments.

## Local verification

Run the complete automated and structural integration suite:

```text
python3 -B tools/run_checks.py
```

The runner does not execute manual Codex evidence and does not claim a final
candidate. Publishable manual evidence must come from a release manifest or
evidence asset bound to the exact published package version and commit.

To add private deny patterns, provide only an external literal pattern file:

```text
python3 -B tools/validate.py --private-pattern-file OUTSIDE_REPOSITORY
```

The validator reports generic codes and locations. It never prints the
external patterns, matching content, source excerpts, or external input path.

## Optional installation report

**Problems installing? Report it.** Start with a private, reviewable draft;
nothing is created or submitted automatically.

First, copy this prompt into your local agent session. It asks for a draft only:

```text
Draft a short installation report for my review. Do not create or submit an issue.
Package ID: <one exact catalog ID>
Package version: <exact version>
Phase: <dry-run | install | verify | first-use>
Result: <succeeded | failed safely | unclear>
OS family: <Linux | macOS | Windows | other or undisclosed>
Python: <major.minor>
Synthetic summary: <one bounded sentence>
Exclude secrets, credentials, tokens, private identifiers, private or absolute local paths, full logs, and sensitive attachments.
```

Review and edit the draft yourself. No repository tool opens, transmits,
creates, or submits a report. If you then choose to share it, use the
[Installation Report Issue Form](.github/ISSUE_TEMPLATE/installation-report.yml)
as a fallback. It is not a security channel. Report vulnerabilities only
through the private route described in [SECURITY.md](SECURITY.md).

Copyright is held by Fabiano Magalhães. See [LICENSE](LICENSE).
