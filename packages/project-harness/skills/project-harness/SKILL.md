---
name: project-harness
description: Maintain durable context and a resumable work cycle inside one explicit local project without depending on chat history.
---

# Project Harness

Use this skill when a user wants a durable local context and work cycle for one
project. Do not use it to coordinate a workspace, sibling projects, external
systems, releases, or publication.

## First use

The selected root must already exist and must be the intended project boundary.

1. Run package-local `init --dry-run` and review every planned relative path.
2. Run `init`.
3. Run `verify`.
4. Run `open` to read the durable starting point.

Use the executable documented in the package README. The repository-level
package manager can install an exact package copy, but it does not create a
global command.

## Work cycle

1. Use `open` or `status` for a read-only opening.
2. Use `digest` for a deterministic collation of durable records.
3. Use `checkpoint` with an explicit summary, optional repeated decisions and
   tasks, and one explicit next step.
4. Use `close` with a non-empty summary and next step.
5. Use `open` again to confirm that the state survived the work block.

Do not invent decisions, tasks, context, or a next step. Ask for missing content
when a durable write would otherwise require inference.

## Safety and recovery

- A preflight or collision error writes nothing.
- A normal in-process write failure triggers rollback of the planned batch.
- After an interruption, run `verify`.
- If state is valid but managed projections drifted, run `init` and then
  `verify`.
- If state is invalid or marker ownership is ambiguous, stop for manual repair.

Each file replacement is atomic. A multi-file operation is not crash-atomic,
and the package does not provide hostile concurrent-writer protection,
automatic state reconstruction, remote actions, or publication.
