"""Operational control plane for one Master root and its registered fronts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from .errors import (
    CollisionError,
    RecoveryRequiredError,
    StateError,
    ValidationError,
)
from .model import (
    Front,
    Manifest,
    parse_manifest,
    render_manifest,
    validate_display_text,
)
from .paths import (
    MAX_STATE_BYTES,
    canonical_root,
    is_link_like,
    read_owned_text,
    safe_path,
)
from .render import (
    append_record,
    append_reflection,
    append_session,
    render_next,
    render_panel,
)
from .transaction import (
    FaultHook,
    JOURNAL_RELATIVE,
    TransactionResult,
    execute_transaction,
    inspect_recovery,
    recover_transaction,
    workspace_lock_present,
)


MANIFEST_RELATIVE = ".orchestration/manifest.json"
PANEL_RELATIVE = "FRONTS.md"
MASTER_TEMPLATE_FILES = ("AGENTS.md", "ARCHITECTURE.md", "NEXT.md")
PROJECT_STATIC_FILES = ("AGENTS.md", "ARCHITECTURE.md")
PROJECT_LOG_FILES = ("REFLECTIONS.md", "RECORDS.md", "SESSIONS.md")
PROJECT_REQUIRED_FILES = (
    *PROJECT_STATIC_FILES,
    "NEXT.md",
    *PROJECT_LOG_FILES,
)
PACKAGE_VERSION = "0.2.3"
INSTALLER_ONBOARDING_START = (
    "<!-- agent-harnesses:onboarding:orchestration:start -->"
)
INSTALLER_ONBOARDING_END = (
    "<!-- agent-harnesses:onboarding:orchestration:end -->"
)


def _installer_onboarding_block() -> str:
    runtime = f".agent-harnesses/runtime/orchestration/{PACKAGE_VERSION}"
    return (
        f"{INSTALLER_ONBOARDING_START}\n"
        "## Agent Harness operating contract\n\n"
        "Before operating this harness, read these target-relative files:\n\n"
        f"- Operations contract: `{runtime}/operations.json`\n"
        f"- Operator guide (English): `{runtime}/OPERATOR_GUIDE.md`\n"
        f"- Guia do operador (PT-BR): `{runtime}/OPERATOR_GUIDE.pt-BR.md`\n\n"
        "Use only the operations declared for this installed harness.\n"
        f"{INSTALLER_ONBOARDING_END}\n"
    )


@dataclass(frozen=True)
class SyncIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path}


def _operation(
    action: str,
    *,
    changed: bool,
    paths: Iterable[str] = (),
    transaction_id: str | None = None,
    **details: Any,
) -> dict[str, Any]:
    return {
        "action": action,
        "changed": changed,
        "details": details,
        "paths": sorted(paths),
        "transactionId": transaction_id,
    }


class ControlPlane:
    """Coordinate a root using only relative, validated, local state."""

    def __init__(self, root: Path, *, fault_hook: FaultHook | None = None) -> None:
        self.root = canonical_root(Path(root))
        self.fault_hook = fault_hook
        self.package_root = Path(__file__).resolve().parents[1]

    def _manifest_exists(self) -> bool:
        path = safe_path(self.root, MANIFEST_RELATIVE)
        if is_link_like(path):
            raise ValidationError("manifest must not be a symbolic link")
        return path.is_file()

    def _read_manifest(self) -> Manifest:
        return parse_manifest(read_owned_text(self.root, MANIFEST_RELATIVE))

    def _template(self, scope: str, name: str) -> str:
        path = self.package_root / "templates" / scope / name
        if is_link_like(path) or not path.is_file():
            raise ValidationError("package template is unavailable")
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                raise ValidationError("package template exceeds the size limit")
            return path.read_text(encoding="utf-8")
        except ValidationError:
            raise
        except (OSError, UnicodeError) as error:
            raise ValidationError("package template is not readable UTF-8") from error

    @staticmethod
    def _front_relative(front: Front, name: str) -> str:
        return f"{front.path}/{name}"

    def _recovery_guard(self) -> None:
        if inspect_recovery(self.root).present:
            raise RecoveryRequiredError(
                "recover the durable journal before continuing"
            )

    def _sync_issues(
        self,
        *,
        ignore_panel: bool = False,
        ignore_lock: bool = False,
    ) -> tuple[list[SyncIssue], Manifest | None]:
        issues: list[SyncIssue] = []
        if not ignore_lock and workspace_lock_present(self.root):
            return (
                [
                    SyncIssue(
                        "LOCKED",
                        ".",
                        "a writer currently owns the workspace lock",
                    )
                ],
                None,
            )
        before = inspect_recovery(self.root)
        if before.present:
            return (
                [
                    SyncIssue(
                        "RECOVERY_REQUIRED",
                        JOURNAL_DISPLAY,
                        "a durable journal requires recovery",
                    )
                ],
                None,
            )
        if not self._manifest_exists():
            return (
                [
                    SyncIssue(
                        "UNINITIALIZED",
                        MANIFEST_RELATIVE,
                        "the orchestration manifest is missing",
                    )
                ],
                None,
            )
        try:
            manifest = self._read_manifest()
        except ValidationError:
            return (
                [
                    SyncIssue(
                        "MANIFEST_INVALID",
                        MANIFEST_RELATIVE,
                        "the manifest violates its closed schema",
                    )
                ],
                None,
            )

        for name in MASTER_TEMPLATE_FILES:
            path = safe_path(self.root, name)
            if is_link_like(path) or not path.is_file():
                issues.append(
                    SyncIssue(
                        "MASTER_FILE_MISSING",
                        name,
                        "a required Master file is missing or unsafe",
                    )
                )

        panel_path = safe_path(self.root, PANEL_RELATIVE)
        if not ignore_panel:
            if is_link_like(panel_path) or not panel_path.is_file():
                issues.append(
                    SyncIssue(
                        "PANEL_MISSING",
                        PANEL_RELATIVE,
                        "the generated pending panel is missing",
                    )
                )
            else:
                try:
                    panel_value = read_owned_text(self.root, PANEL_RELATIVE)
                except ValidationError:
                    issues.append(
                        SyncIssue(
                            "PANEL_INVALID",
                            PANEL_RELATIVE,
                            "the pending panel is not readable UTF-8 text",
                        )
                    )
                else:
                    if panel_value != render_panel(manifest):
                        issues.append(
                            SyncIssue(
                                "PANEL_MISMATCH",
                                PANEL_RELATIVE,
                                "the pending panel differs from the manifest",
                            )
                        )

        for front in manifest.fronts:
            try:
                directory = safe_path(self.root, front.path)
            except ValidationError:
                issues.append(
                    SyncIssue(
                        "FRONT_BOUNDARY",
                        front.path,
                        "a front path violates the root boundary",
                    )
                )
                continue
            if is_link_like(directory) or not directory.is_dir():
                issues.append(
                    SyncIssue(
                        "FRONT_MISSING",
                        front.path,
                        "a registered front directory is missing or unsafe",
                    )
                )
                continue
            for name in PROJECT_REQUIRED_FILES:
                relative = self._front_relative(front, name)
                path = safe_path(self.root, relative)
                if is_link_like(path) or not path.is_file():
                    issues.append(
                        SyncIssue(
                            "FRONT_FILE_MISSING",
                            relative,
                            "a required front file is missing or unsafe",
                        )
                    )
                    continue
                try:
                    value = read_owned_text(self.root, relative)
                except ValidationError:
                    issues.append(
                        SyncIssue(
                            "FRONT_FILE_INVALID",
                            relative,
                            "a front file is not readable UTF-8 text",
                        )
                    )
                    continue
                if name == "NEXT.md" and value != render_next(front):
                    issues.append(
                        SyncIssue(
                            "NEXT_MISMATCH",
                            relative,
                            "generated front pending state differs from the manifest",
                        )
                    )

        after = inspect_recovery(self.root)
        if after.present != before.present or after.transaction_id != before.transaction_id:
            issues.append(
                SyncIssue(
                    "STATE_CHANGED",
                    ".",
                    "state changed while the read-only sync was running",
                )
            )
        else:
            try:
                final_manifest = self._read_manifest()
            except ValidationError:
                issues.append(
                    SyncIssue(
                        "STATE_CHANGED",
                        MANIFEST_RELATIVE,
                        "manifest changed while read-only sync was running",
                    )
                )
            else:
                if (
                    final_manifest.revision != manifest.revision
                    or final_manifest.last_transaction
                    != manifest.last_transaction
                ):
                    issues.append(
                        SyncIssue(
                            "STATE_CHANGED",
                            MANIFEST_RELATIVE,
                            "manifest changed while read-only sync was running",
                        )
                    )
        return issues, manifest

    def sync(self) -> dict[str, Any]:
        issues, manifest = self._sync_issues()
        return {
            "action": "hq-sync",
            "clean": not issues,
            "frontCount": len(manifest.fronts) if manifest else 0,
            "issues": [issue.to_dict() for issue in issues],
            "revision": manifest.revision if manifest else None,
        }

    def bom_dia(self, selector: str | None = None) -> dict[str, Any]:
        preview = inspect_recovery(self.root)
        if preview.present:
            return {
                "action": "bom-dia",
                "next": "recover --dry-run",
                "status": "recovery-required",
            }
        if not self._manifest_exists():
            return {
                "action": "bom-dia",
                "next": "init --dry-run",
                "status": "uninitialized",
            }
        sync = self.sync()
        if not sync["clean"]:
            return {
                "action": "bom-dia",
                "issues": sync["issues"],
                "next": "hq-sync",
                "status": "inconsistent",
            }
        manifest = self._read_manifest()
        try:
            front = manifest.resolve(selector)
        except ValidationError:
            return {
                "action": "bom-dia",
                "fronts": [
                    {
                        "aliases": list(front.aliases),
                        "id": front.id,
                        "pending": front.pending,
                        "stage": front.stage,
                    }
                    for front in manifest.fronts
                ],
                "next": "foco",
                "status": "focus-required",
            }
        return {
            "action": "bom-dia",
            "front": {
                "displayName": front.display_name,
                "id": front.id,
                "lastDigest": front.last_digest,
                "path": front.path,
                "pending": front.pending,
                "stage": front.stage,
            },
            "status": "ready",
        }

    def _new_front(
        self,
        *,
        front_id: str,
        display_name: str,
        path: str,
        aliases: Iterable[str],
    ) -> Front:
        return Front.create(
            front_id=front_id,
            display_name=display_name,
            path=path,
            aliases=aliases,
        )

    @staticmethod
    def _same_registration(first: Front, second: Front) -> bool:
        return (
            first.id == second.id
            and first.display_name == second.display_name
            and first.path == second.path
            and first.aliases == second.aliases
        )

    def _require_clean(self, *, ignore_lock: bool = False) -> Manifest:
        issues, manifest = self._sync_issues(ignore_lock=ignore_lock)
        if issues or manifest is None:
            raise StateError("hq-sync must be clean before this operation")
        return manifest

    def _first_init_changes(
        self,
        front: Front,
        transaction_id: str,
    ) -> Mapping[str, str]:
        front_directory = safe_path(self.root, front.path)
        if front_directory.exists() or is_link_like(front_directory):
            raise CollisionError("initialization would adopt an existing front path")
        targets = (
            *MASTER_TEMPLATE_FILES,
            PANEL_RELATIVE,
            MANIFEST_RELATIVE,
            *(self._front_relative(front, name) for name in PROJECT_REQUIRED_FILES),
        )
        installer_agents: str | None = None
        for relative in targets:
            path = safe_path(self.root, relative)
            if path.exists() or is_link_like(path):
                if relative == "AGENTS.md" and not is_link_like(path) and path.is_file():
                    try:
                        candidate = path.read_text(encoding="utf-8")
                    except (OSError, UnicodeError) as error:
                        raise CollisionError(
                            "installer onboarding block is not readable UTF-8"
                        ) from error
                    onboarding = _installer_onboarding_block()
                    if (
                        candidate.count(onboarding) == 1
                        and candidate.count(INSTALLER_ONBOARDING_START) == 1
                        and candidate.count(INSTALLER_ONBOARDING_END) == 1
                    ):
                        installer_agents = candidate
                        continue
                raise CollisionError("initialization would overwrite existing state")

        manifest = Manifest.create(front, transaction_id=transaction_id)
        changes: dict[str, str] = {
            MANIFEST_RELATIVE: render_manifest(manifest),
            PANEL_RELATIVE: render_panel(manifest),
        }
        for name in MASTER_TEMPLATE_FILES:
            template = self._template("master", name)
            if name == "AGENTS.md" and installer_agents is not None:
                separator = "" if installer_agents.endswith("\n\n") else "\n"
                changes[name] = installer_agents + separator + template
            else:
                changes[name] = template
        for name in PROJECT_STATIC_FILES:
            changes[self._front_relative(front, name)] = self._template(
                "project",
                name,
            )
        for name in PROJECT_LOG_FILES:
            changes[self._front_relative(front, name)] = self._template(
                "project",
                name,
            )
        changes[self._front_relative(front, "NEXT.md")] = render_next(front)
        return changes

    def _registration_changes(
        self,
        front: Front,
        transaction_id: str,
        *,
        ignore_lock: bool = False,
    ) -> tuple[Mapping[str, str], bool]:
        if not self._manifest_exists():
            return self._first_init_changes(front, transaction_id), False

        manifest = self._require_clean(ignore_lock=ignore_lock)
        for registered in manifest.fronts:
            if registered.id == front.id:
                if self._same_registration(registered, front):
                    return {}, True
                raise CollisionError("front ID is already registered differently")

        target = safe_path(self.root, front.path)
        if target.exists() or is_link_like(target):
            raise CollisionError("front path already exists")
        updated = manifest.with_front(
            front,
            transaction_id=transaction_id,
            preserve_focus=True,
        )
        changes: dict[str, str] = {
            MANIFEST_RELATIVE: render_manifest(updated),
            PANEL_RELATIVE: render_panel(updated),
        }
        for name in PROJECT_STATIC_FILES:
            changes[self._front_relative(front, name)] = self._template(
                "project",
                name,
            )
        for name in PROJECT_LOG_FILES:
            changes[self._front_relative(front, name)] = self._template(
                "project",
                name,
            )
        changes[self._front_relative(front, "NEXT.md")] = render_next(front)
        return changes, False

    def plan_init(
        self,
        *,
        front_id: str,
        display_name: str,
        path: str,
        aliases: Iterable[str] = (),
    ) -> dict[str, Any]:
        self._recovery_guard()
        front = self._new_front(
            front_id=front_id,
            display_name=display_name,
            path=path,
            aliases=aliases,
        )
        preview_id = "0" * 32
        changes, no_op = self._registration_changes(front, preview_id)
        return _operation(
            "init",
            changed=bool(changes),
            paths=changes,
            mode="dry-run",
            noOp=no_op,
        )

    def init(
        self,
        *,
        front_id: str,
        display_name: str,
        path: str,
        aliases: Iterable[str] = (),
    ) -> dict[str, Any]:
        front = self._new_front(
            front_id=front_id,
            display_name=display_name,
            path=path,
            aliases=aliases,
        )

        def builder(transaction_id: str) -> tuple[Mapping[str, str], dict[str, bool]]:
            changes, no_op = self._registration_changes(
                front,
                transaction_id,
                ignore_lock=True,
            )
            return changes, {"noOp": no_op}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("init", result)

    @staticmethod
    def _transaction_operation(
        action: str,
        result: TransactionResult,
    ) -> dict[str, Any]:
        details = result.value if isinstance(result.value, dict) else {}
        return _operation(
            action,
            changed=result.changed,
            paths=result.paths,
            transaction_id=result.transaction_id,
            **details,
        )

    def foco(self, selector: str) -> dict[str, Any]:
        def builder(transaction_id: str) -> tuple[Mapping[str, str], dict[str, Any]]:
            manifest = self._require_clean(ignore_lock=True)
            front = manifest.resolve(selector)
            if manifest.active_focus == front.id:
                return {}, {"front": front.id, "noOp": True}
            updated = manifest.with_focus(front.id, transaction_id=transaction_id)
            return {
                MANIFEST_RELATIVE: render_manifest(updated),
                PANEL_RELATIVE: render_panel(updated),
            }, {"front": front.id, "noOp": False}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("foco", result)

    def digere(
        self,
        *,
        summary: str,
        pending: str,
        selector: str | None = None,
    ) -> dict[str, Any]:
        digest = validate_display_text(summary, label="digest")
        next_action = validate_display_text(
            pending,
            label="pending action",
            maximum=240,
        )

        def builder(transaction_id: str) -> tuple[Mapping[str, str], dict[str, Any]]:
            manifest = self._require_clean(ignore_lock=True)
            front = manifest.resolve(selector)
            if front.stage not in ("registered", "closed"):
                raise StateError("digere requires a registered or closed front")
            reflection_path = self._front_relative(front, "REFLECTIONS.md")
            updated_front = replace(
                front,
                stage="digested",
                pending=next_action,
                last_digest=digest,
                reflection_count=front.reflection_count + 1,
            )
            updated = manifest.with_front(
                updated_front,
                transaction_id=transaction_id,
                active_focus=front.id,
            )
            return {
                MANIFEST_RELATIVE: render_manifest(updated),
                PANEL_RELATIVE: render_panel(updated),
                reflection_path: append_reflection(
                    read_owned_text(self.root, reflection_path),
                    front,
                    digest,
                ),
                self._front_relative(front, "NEXT.md"): render_next(updated_front),
            }, {"front": front.id, "reflection": updated_front.reflection_count}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("digere", result)

    def registra(
        self,
        *,
        note: str = "",
        selector: str | None = None,
    ) -> dict[str, Any]:
        record_note = validate_display_text(
            note,
            label="record note",
            allow_empty=True,
        )

        def builder(transaction_id: str) -> tuple[Mapping[str, str], dict[str, Any]]:
            manifest = self._require_clean(ignore_lock=True)
            front = manifest.resolve(selector)
            if front.stage != "digested":
                raise StateError("registra requires a digested front")
            record_path = self._front_relative(front, "RECORDS.md")
            updated_front = replace(
                front,
                stage="recorded",
                pending="Close the current work block",
                record_count=front.record_count + 1,
            )
            updated = manifest.with_front(
                updated_front,
                transaction_id=transaction_id,
                active_focus=front.id,
            )
            return {
                MANIFEST_RELATIVE: render_manifest(updated),
                PANEL_RELATIVE: render_panel(updated),
                record_path: append_record(
                    read_owned_text(self.root, record_path),
                    front,
                    record_note,
                ),
                self._front_relative(front, "NEXT.md"): render_next(updated_front),
            }, {"front": front.id, "record": updated_front.record_count}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("registra", result)

    def encerra(
        self,
        *,
        summary: str,
        next_action: str,
        selector: str | None = None,
    ) -> dict[str, Any]:
        close_summary = validate_display_text(summary, label="closeout summary")
        pending = validate_display_text(
            next_action,
            label="next action",
            maximum=240,
        )

        def builder(transaction_id: str) -> tuple[Mapping[str, str], dict[str, Any]]:
            manifest = self._require_clean(ignore_lock=True)
            front = manifest.resolve(selector)
            if front.stage != "recorded":
                raise StateError("encerra requires a recorded front")
            session_path = self._front_relative(front, "SESSIONS.md")
            updated_front = replace(
                front,
                stage="closed",
                pending=pending,
                session_count=front.session_count + 1,
            )
            updated = manifest.with_front(
                updated_front,
                transaction_id=transaction_id,
                active_focus=None,
            )
            return {
                MANIFEST_RELATIVE: render_manifest(updated),
                PANEL_RELATIVE: render_panel(updated),
                session_path: append_session(
                    read_owned_text(self.root, session_path),
                    front,
                    close_summary,
                    pending,
                ),
                self._front_relative(front, "NEXT.md"): render_next(updated_front),
            }, {"front": front.id, "session": updated_front.session_count}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("encerra", result)

    def _panel_repair_plan(
        self,
        *,
        ignore_lock: bool = False,
    ) -> tuple[Mapping[str, str], bool]:
        issues, manifest = self._sync_issues(
            ignore_panel=True,
            ignore_lock=ignore_lock,
        )
        if issues or manifest is None:
            raise StateError("repair refuses any inconsistency beyond the panel")
        expected = render_panel(manifest)
        panel = safe_path(self.root, PANEL_RELATIVE)
        if panel.is_file() and not is_link_like(panel):
            try:
                if read_owned_text(self.root, PANEL_RELATIVE) == expected:
                    return {}, True
            except ValidationError:
                pass
        elif panel.exists() or is_link_like(panel):
            raise StateError("repair refuses an unsafe panel target")
        return {PANEL_RELATIVE: expected}, False

    def plan_repair_panel(self) -> dict[str, Any]:
        self._recovery_guard()
        changes, no_op = self._panel_repair_plan()
        return _operation(
            "repair-panel",
            changed=bool(changes),
            paths=changes,
            mode="dry-run",
            noOp=no_op,
        )

    def repair_panel(self) -> dict[str, Any]:
        def builder(_transaction_id: str) -> tuple[Mapping[str, str], dict[str, Any]]:
            changes, no_op = self._panel_repair_plan(ignore_lock=True)
            return changes, {"noOp": no_op}

        result = execute_transaction(
            self.root,
            builder,
            fault_hook=self.fault_hook,
        )
        return self._transaction_operation("repair-panel", result)

    def recovery(self, *, apply: bool, break_stale_lock: bool = False) -> dict[str, Any]:
        if not apply:
            preview = inspect_recovery(self.root)
            return _operation(
                "recover",
                changed=False,
                paths=preview.paths,
                mode="dry-run",
                phase=preview.phase,
                recoveryPresent=preview.present,
            )
        preview = recover_transaction(
            self.root,
            break_stale_lock=break_stale_lock,
        )
        return _operation(
            "recover",
            changed=preview.present,
            paths=preview.paths,
            mode="apply",
            phase=preview.phase,
            recoveryPresent=preview.present,
        )


JOURNAL_DISPLAY = JOURNAL_RELATIVE
