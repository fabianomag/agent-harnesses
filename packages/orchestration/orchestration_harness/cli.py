"""Portable command-line interface for the local control plane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .errors import HarnessError
from .service import ControlPlane


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hq",
        description="Operate a local Master and its registered fronts.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="existing workspace root; defaults to the current directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit deterministic JSON",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    morning = commands.add_parser("bom-dia", help="read-only work-block opening")
    morning.add_argument("selector", nargs="?")

    focus = commands.add_parser("foco", help="transactionally select one front")
    focus.add_argument("selector")

    init = commands.add_parser("init", help="initialize or register a front")
    init.add_argument("--id", required=True, dest="front_id")
    init.add_argument("--name", required=True, dest="display_name")
    init.add_argument("--path", required=True)
    init.add_argument("--alias", action="append", default=[], dest="aliases")
    init_mode = init.add_mutually_exclusive_group(required=True)
    init_mode.add_argument("--dry-run", action="store_true")
    init_mode.add_argument("--apply", action="store_true")

    commands.add_parser("hq-sync", help="strictly read-only structural sync")

    digest = commands.add_parser("digere", help="record an explicit reflection")
    digest.add_argument("--summary", required=True)
    digest.add_argument("--pending", required=True)
    digest.add_argument("--front", dest="selector")

    record = commands.add_parser("registra", help="promote the current digest")
    record.add_argument("--note", default="")
    record.add_argument("--front", dest="selector")

    close = commands.add_parser("encerra", help="close a recorded work block")
    close.add_argument("--summary", required=True)
    close.add_argument("--next", required=True, dest="next_action")
    close.add_argument("--front", dest="selector")

    repair = commands.add_parser(
        "repair-panel",
        help="repair only a derivable pending-panel mismatch",
    )
    repair_mode = repair.add_mutually_exclusive_group(required=True)
    repair_mode.add_argument("--dry-run", action="store_true")
    repair_mode.add_argument("--apply", action="store_true")

    recover = commands.add_parser(
        "recover",
        help="inspect or recover a durable transaction journal",
    )
    recover_mode = recover.add_mutually_exclusive_group(required=True)
    recover_mode.add_argument("--dry-run", action="store_true")
    recover_mode.add_argument("--apply", action="store_true")
    recover.add_argument(
        "--break-stale-lock",
        action="store_true",
        help="explicitly remove only the lock matching this journal",
    )
    return parser


def _dispatch(arguments: argparse.Namespace) -> dict[str, Any]:
    control = ControlPlane(arguments.root)
    command = arguments.command
    if command == "bom-dia":
        return control.bom_dia(arguments.selector)
    if command == "foco":
        return control.foco(arguments.selector)
    if command == "init":
        values = {
            "aliases": arguments.aliases,
            "display_name": arguments.display_name,
            "front_id": arguments.front_id,
            "path": arguments.path,
        }
        return control.plan_init(**values) if arguments.dry_run else control.init(**values)
    if command == "hq-sync":
        return control.sync()
    if command == "digere":
        return control.digere(
            summary=arguments.summary,
            pending=arguments.pending,
            selector=arguments.selector,
        )
    if command == "registra":
        return control.registra(
            note=arguments.note,
            selector=arguments.selector,
        )
    if command == "encerra":
        return control.encerra(
            summary=arguments.summary,
            next_action=arguments.next_action,
            selector=arguments.selector,
        )
    if command == "repair-panel":
        return (
            control.plan_repair_panel()
            if arguments.dry_run
            else control.repair_panel()
        )
    if command == "recover":
        if arguments.break_stale_lock and not arguments.apply:
            raise HarnessError("stale-lock authorization is valid only with apply")
        return control.recovery(
            apply=arguments.apply,
            break_stale_lock=arguments.break_stale_lock,
        )
    raise HarnessError("unsupported command")


def _render_human(result: dict[str, Any]) -> str:
    action = result.get("action", "hq")
    if action == "hq-sync":
        status = "clean" if result.get("clean") else "inconsistent"
        issues = result.get("issues", [])
        suffix = "" if not issues else f"; {len(issues)} issue(s)"
        return f"hq-sync: {status}{suffix}"
    if action == "bom-dia":
        status = result.get("status", "unknown")
        front = result.get("front")
        if isinstance(front, dict):
            return (
                f"bom-dia: {status}; front={front.get('id')}; "
                f"pending={front.get('pending')}"
            )
        return f"bom-dia: {status}; next={result.get('next', 'none')}"
    changed = "changed" if result.get("changed") else "no-op"
    return f"{action}: {changed}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = _dispatch(arguments)
    except HarnessError as error:
        payload = {
            "error": error.__class__.__name__,
            "message": str(error),
            "ok": False,
        }
        if arguments.json:
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(f"ERROR {payload['error']}: {payload['message']}", file=sys.stderr)
        return 2

    if arguments.json:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(_render_human(result))
    if result.get("action") == "hq-sync" and not result.get("clean"):
        return 1
    return 0
