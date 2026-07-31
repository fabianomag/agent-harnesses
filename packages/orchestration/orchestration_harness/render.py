"""Deterministic Markdown projections and append-only records."""

from __future__ import annotations

from .model import Front, Manifest


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def render_panel(manifest: Manifest) -> str:
    rows = [
        "# Fronts",
        "",
        "Generated from the orchestration manifest. Do not edit this panel manually.",
        "",
        f"- Revision: `{manifest.revision}`",
        f"- Transaction: `{manifest.last_transaction}`",
        f"- Active focus: `{manifest.active_focus or 'none'}`",
        "",
        "| ID | Name | Path | Aliases | Stage | Pending |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for front in manifest.fronts:
        aliases = ", ".join(front.aliases) if front.aliases else "-"
        rows.append(
            "| "
            + " | ".join(
                (
                    _cell(front.id),
                    _cell(front.display_name),
                    _cell(front.path),
                    _cell(aliases),
                    _cell(front.stage),
                    _cell(front.pending),
                )
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def render_next(front: Front) -> str:
    return (
        "# Next Action\n\n"
        "This file is generated from the orchestration manifest.\n\n"
        f"- Stage: `{front.stage}`\n"
        f"- Pending: {front.pending}\n"
    )


def append_reflection(current: str, front: Front, summary: str) -> str:
    number = front.reflection_count + 1
    return (
        current.rstrip()
        + f"\n\n## Reflection {number}\n\n"
        + summary
        + "\n"
    )


def append_record(current: str, front: Front, note: str) -> str:
    number = front.record_count + 1
    body = front.last_digest if not note else f"{front.last_digest}\n\nNote: {note}"
    return current.rstrip() + f"\n\n## Record {number}\n\n" + body + "\n"


def append_session(current: str, front: Front, summary: str, next_action: str) -> str:
    number = front.session_count + 1
    return (
        current.rstrip()
        + f"\n\n## Session {number}\n\n"
        + f"Summary: {summary}\n\n"
        + f"Next: {next_action}\n"
    )
