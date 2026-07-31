# Repository Instructions

This repository is a clean-room public baseline. Use only its public contracts
and task-specific requirements. Do not import private source material, names,
paths, logs, identifiers, fixtures, credentials, hashes, or mappings.

## Write ownership

Package work is isolated:

- S1A owns only `packages/project-harness/`.
- S1B owns only `packages/workspace-coordination/`.
- S1C owns only `packages/cross-project/`.
- S1D owns only `packages/orchestration/`.

Those package owners must not change root documentation, schemas, tooling,
tests, a future catalog, a future installer, or shared verification behavior.
The common-maintainer phase S2 owns those shared surfaces.

Use `python3 -B tools/validate.py --scope <package-id> --base <baseline-sha>` to
verify a package task's Git write boundary.

## Public-safety boundary

- Keep fixtures entirely synthetic.
- Keep package status and capability claims evidence-based.
- Supply any private deny patterns through an external file accepted by the
  validator. The file must remain outside this repository, and its contents
  must never be copied into output, tests, fixtures, or commits.
- Add a dependency only after checking its license and required attribution.
- Publishing, tagging, releasing, and remote changes require separate
  authorization.
