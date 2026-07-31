# Contributing

Contributions must remain clean-room, synthetic, evidence-bound, and local.
Do not copy private source material, names, paths, logs, identifiers,
credentials, fixtures, hashes, or mappings into this repository.

## Change boundaries

- Package behavior belongs under `packages/<package-id>/`.
- Shared schemas, catalog generation, installer/verifier behavior, root
  documentation, graphs, and common tests belong to the common layer.
- Do not normalize package CLIs or reimplement package behavior in a common
  wrapper.
- A functional package correction requires focused regression coverage and a
  fresh run of that package's checks.
- Change a package version or status only when the package manifest and
  validation evidence support the new value.
- Keep `Context`, `Skill`, `Harness`, `Loop`, and `Guardrails` claims tied to
  specific public evidence. `verified` requires repeatable evaluations of an
  exact published version.

The repository uses only the Python standard library. Before adding a
third-party dependency, verify its license, document required attribution, and
explain why the standard library is insufficient.

## Deterministic artifacts

`catalog/harnesses.json`, the optional collection graph, all four package graph
specs, and all five corresponding SVGs are generated from package contracts
and payload bytes. Do not hand-edit them.

After a package payload or manifest changes, run:

```text
python3 -B tools/build_common.py --write
python3 -B tools/build_common.py --check
```

Review the catalog version, artifact/publication status, file inventory,
badge evidence, limitations, graph IDs, and every graph diff. The collection
graph expresses membership only. Each package graph expresses only its
cataloged operating flow; do not turn complexity into a quality ranking.

Immutable documentation, prompt, source, and release links must name the exact
published tag or release asset. The interactive-diagram link names the stable
public collection page. Never substitute a mutable branch URL for a
version-bound field.

## Required checks

Run:

```text
python3 -B tools/run_checks.py
```

The runner executes common tests, every package's automated tests, structural
checks, public-safety validation, generated-artifact validation, and
`git diff --check`.

Keep evidence categories separate:

- **Automated** means a programmatic test completed successfully.
- **Structural** means repository shape, deterministic bytes, or a bounded
  local cycle was checked.
- **Manual** means a named human walkthrough was actually performed.

Do not convert automated or structural evidence into a manual claim. The local
runner does not execute manual Codex evidence. Candidate-bound and publishable
results belong in a release manifest or evidence asset for the exact package
version and commit.

Any package, prompt, catalog, graph, installer, verifier, or backlink change
invalidates the affected candidate evidence and requires the corresponding
checks and walkthroughs to run again.

Optional private deny patterns must come from a file outside the repository.
The file, its patterns, and matching content must never be echoed, copied into
fixtures, or committed.

## Optional installation reports

An installation report is always user-reviewed and manually submitted. Start
with the copyable draft prompt in the root README; no repository tool opens,
transmits, creates, or submits an issue. The Installation Report Issue Form is
only a fallback after review.

Keep reports minimal and synthetic. Include only the exact package ID and
version, phase, result, OS family, Python major.minor, and a short synthetic
summary. Never include secrets, credentials, tokens, private identifiers,
private or absolute local paths, full logs, or sensitive attachments. Do not
use an installation report for a vulnerability.

Remote changes, tags, releases, deployments, and publication require separate
authorization.
