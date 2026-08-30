---
name: cross-project
description: Coordinate several real child projects from one local root with named targets, read-only orientation and sync, bounded digestion, and rollback-protected registration or reflection. Use when a workspace needs a small cross-project control surface without scanning outside its root.
---

# Multi-Project Harness

Keep project-local detail in each child. Store only role, coordination state,
next action, blocker, reflection summary, and reflection trigger in the root.

Operate the already installed agent-agnostic runtime at
`<target>/.agent-harnesses/runtime/cross-project/0.2.3/`. Treat that runtime's
`operations.json` as the machine-readable command authority and its operator
guide as the user-facing contract. This optional adapter does not replace or
install the runtime.

## Operate

1. Run `scripts/cross_project.py bom-dia --root <root>` before changing state.
2. Register only an existing child under the root. Run `hq-init --dry-run`
   first, inspect `changed`, then repeat without `--dry-run`.
3. Run `hq-sync` after mutation. Treat it as diagnosis; never repair from it.
4. Use `digere` to decide whether input belongs to the child, the root, or
   nowhere durable.
5. Use `registra` for a minimal live checkpoint. It does not promote a
   provisional registration.
6. Use `encerra` for the first complete reflection or a later cross-project
   handoff.
7. Run `bom-dia --front <id>` to confirm the recorded resumption point.

Never register an absolute path, a symlinked target, a path outside the root, or
two IDs that resolve to one directory. Never select filesystem root, home, or
Git metadata as the harness root or a child. Do not scan home, parents, sibling
workspaces, Git remotes, or external services. A read that encounters an active
mutation lock must stop and retry; it must not repair.

Use the exact command surface and state fields documented by the installed
runtime's `operations.json` and operator guide.
