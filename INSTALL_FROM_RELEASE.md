# Install from an immutable release bundle

This bundle is a self-contained source tree for one exact package selection.
Identify the selection from the downloaded asset name or extracted top-level
directory; do not substitute another package or version.

| Asset | Package ID | Version |
| --- | --- | --- |
| `project-harness-0.1.0.zip` | `project-harness` | `0.1.0` |
| `workspace-coordination-0.1.0.zip` | `workspace-coordination` | `0.1.0` |
| `cross-project-0.1.1.zip` | `cross-project` | `0.1.1` |
| `orchestration-0.1.0.zip` | `orchestration` | `0.1.0` |

After extraction, enter the top-level directory and read the selected package
README under `packages/<package-id>/README.md`. Confirm Python 3.10 or newer.
Create or select one existing real installation root; never use a home folder,
filesystem root, Git metadata directory, symbolic-link path, or a destination
that already contains divergent bytes.

Run from the extracted source-tree root, replacing only the three bracketed
values with the exact row above and the chosen existing installation root:

```text
python3 -B tools/package_manager.py install --package <package-id> --version <version> --root <install-root> --dry-run
python3 -B tools/package_manager.py install --package <package-id> --version <version> --root <install-root> --apply
python3 -B tools/package_manager.py verify --package <package-id> --version <version> --root <install-root>
```

Stop if dry-run or verification fails. The manager refuses overwrite and does
not repair tampered destinations. After verification, enter
`<install-root>/<package-id>-<version>/`, read its README, and explain its
Prerequisites, Preflight, First use, Recovery, and Limitations before running a
project/workspace mutation.

The release asset is bound to an immutable Git tag. Verify its SHA-256 against
the GitHub release asset digest or the adjacent `SHA256SUMS` release asset
before extraction. The checksum is external to the archive, avoiding a
self-referential digest.
