---
name: workspace-coordination
description: Coordinate explicit autonomous child folders contained by one local workspace root while keeping dense execution state in each child.
---

# Workspace Coordination

Use this skill when one coordinator folder contains multiple autonomous child
folders and the task is to choose a child, preserve its local ownership, or
reflect a small shared boundary delta.

Operate the already installed agent-agnostic runtime at
`<target>/.agent-harnesses/runtime/workspace-coordination/0.2.2/`. Treat its
`operations.json` as the machine-readable command authority and its operator
guide as the user-facing contract. This optional adapter does not replace or
install the runtime.

Do not use it merely because several repositories are mentioned:

- Use Project Harness for work and continuity inside one project.
- Use Workspace Harness for children contained by one coordinator
  root.
- Use Multi-Project Harness for handoffs between independent projects or
  workspaces.
- Use Control Plane Harness for a transactional local control plane with a
  strict registry, explicit lifecycle records, structural sync, and recovery.
  It does not dispatch agents or execute processes.

These are boundary choices, not a ranking.

## Operating rules

1. Require an explicit coordinator root. Never discover children by scanning.
2. Open the coordinator and select one registered child.
3. Read only that child's declared owner plus managed local continuity.
4. Keep detailed work, evidence, and next action in the child.
5. Reflect only an explicit concise cross-child boundary or decision delta.
6. Close with `record --kind close` and reopen from its recorded next action.
7. Run `verify` before claiming continuity or structural health.

For every mutation, run the same command with `--dry-run` first when practical,
then use `--apply`. Never replace a collision, follow a symlink, infer an
unregistered child, or treat generated Markdown as the source of truth.

Use `recover` only when `verify` marks generated or canonical drift as
recoverable. Corrupt canonical JSON requires restoration from an independent
known-good source; do not invent missing state.

See the installed runtime's `operations.json` and operator guide for the exact
implemented command surface and walkthrough.
