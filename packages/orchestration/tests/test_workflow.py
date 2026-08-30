"""Control-plane behavior and read-only guarantees."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import _bootstrap

from orchestration_harness.errors import (
    CollisionError,
    StateError,
    TransactionError,
    ValidationError,
)
from orchestration_harness.model import parse_manifest
from orchestration_harness.service import (
    MANIFEST_RELATIVE,
    ControlPlane,
    _installer_onboarding_block,
)

from helpers import initialize, snapshot


class InitializationTests(unittest.TestCase):
    def test_first_bom_dia_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot(root)
            result = ControlPlane(root).bom_dia()
            self.assertEqual("uninitialized", result["status"])
            self.assertEqual(before, snapshot(root))

    def test_init_dry_run_does_not_change_bytes_modes_or_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot(root)
            result = ControlPlane(root).plan_init(
                front_id="sample-front",
                display_name="Sample Front",
                path="fronts/sample-front",
                aliases=("sample",),
            )
            self.assertTrue(result["changed"])
            self.assertEqual("dry-run", result["details"]["mode"])
            self.assertEqual(before, snapshot(root))

    def test_init_apply_creates_coherent_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            sync = control.sync()
            self.assertTrue(sync["clean"], sync["issues"])
            manifest = parse_manifest(
                (root / MANIFEST_RELATIVE).read_text(encoding="utf-8")
            )
            self.assertEqual(1, manifest.revision)
            self.assertEqual("sample-front", manifest.active_focus)

    def test_front_architecture_is_user_owned_and_not_sync_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            architecture = root / "fronts" / "sample-front" / "ARCHITECTURE.md"
            architecture.write_text(
                "# Front Architecture\n\n"
                "Responsibility boundary: owns the synthetic API only.\n",
                encoding="utf-8",
            )

            sync = control.sync()

            self.assertTrue(sync["clean"], sync["issues"])
            self.assertEqual([], sync["issues"])

    def test_first_init_preserves_exact_installer_onboarding_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block = _installer_onboarding_block()
            (root / "AGENTS.md").write_text(block, encoding="utf-8")
            control = initialize(root)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(agents.startswith(block + "\n"))
            self.assertIn("# Master Operating Contract", agents)

    def test_first_init_preserves_external_agents_bytes_around_onboarding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = (
                "# Existing user instructions\n\n"
                + _installer_onboarding_block()
                + "\nUser-owned tail without a final newline"
            )
            (root / "AGENTS.md").write_text(before, encoding="utf-8")
            control = ControlPlane(root)

            preview = control.plan_init(
                front_id="confirmed-front",
                display_name="Confirmed front",
                path="fronts/confirmed-front",
                aliases=(),
            )
            self.assertTrue(preview["changed"])
            self.assertEqual(before, (root / "AGENTS.md").read_text(encoding="utf-8"))

            applied = control.init(
                front_id="confirmed-front",
                display_name="Confirmed front",
                path="fronts/confirmed-front",
                aliases=(),
            )
            self.assertTrue(applied["changed"])
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(agents.startswith(before))
            self.assertIn("# Master Operating Contract", agents)
            self.assertTrue(control.sync()["clean"])

    def test_first_init_rejects_modified_onboarding_block_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                _installer_onboarding_block().replace(
                    "Use only the operations declared",
                    "Use every operation, including undeclared ones",
                ),
                encoding="utf-8",
            )
            before = snapshot(root)
            with self.assertRaises(CollisionError):
                ControlPlane(root).init(
                    front_id="sample-front",
                    display_name="Sample Front",
                    path="fronts/sample-front",
                    aliases=("sample",),
                )
            self.assertEqual(before, snapshot(root))

    def test_second_identical_init_is_exact_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            before = snapshot(root)
            manifest_before = (root / MANIFEST_RELATIVE).read_bytes()
            result = control.init(
                front_id="sample-front",
                display_name="Sample Front",
                path="fronts/sample-front",
                aliases=("sample",),
            )
            self.assertFalse(result["changed"])
            self.assertTrue(result["details"]["noOp"])
            self.assertEqual(manifest_before, (root / MANIFEST_RELATIVE).read_bytes())
            self.assertEqual(before, snapshot(root))

    def test_id_path_and_alias_collisions_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            before = snapshot(root)
            cases = (
                {
                    "front_id": "sample-front",
                    "display_name": "Different",
                    "path": "fronts/different",
                    "aliases": (),
                },
                {
                    "front_id": "second-front",
                    "display_name": "Second Front",
                    "path": "fronts/sample-front",
                    "aliases": ("second",),
                },
                {
                    "front_id": "second-front",
                    "display_name": "Second Front",
                    "path": "fronts/second-front",
                    "aliases": ("sample",),
                },
            )
            for values in cases:
                with self.subTest(values=values):
                    with self.assertRaises(CollisionError):
                        control.init(**values)
                    self.assertEqual(before, snapshot(root))

    def test_existing_unregistered_target_is_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fronts" / "sample-front").mkdir(parents=True)
            before = snapshot(root)
            with self.assertRaises(CollisionError):
                ControlPlane(root).init(
                    front_id="sample-front",
                    display_name="Sample Front",
                    path="fronts/sample-front",
                )
            self.assertEqual(before, snapshot(root))


class LifecycleTests(unittest.TestCase):
    def test_complete_flow_and_second_bom_dia(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            digested = control.digere(
                summary="Validated the first slice",
                pending="Register the validated delta",
            )
            recorded = control.registra(note="Synthetic evidence")
            closed = control.encerra(
                summary="Closed the work block",
                next_action="Review the next bounded slice",
            )
            self.assertTrue(digested["changed"])
            self.assertTrue(recorded["changed"])
            self.assertTrue(closed["changed"])
            self.assertTrue(control.sync()["clean"])
            opening = control.bom_dia()
            self.assertEqual("ready", opening["status"])
            self.assertEqual("closed", opening["front"]["stage"])
            self.assertEqual(
                "Review the next bounded slice",
                opening["front"]["pending"],
            )

    def test_illegal_transitions_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            before = snapshot(root)
            with self.assertRaises(StateError):
                control.registra()
            with self.assertRaises(StateError):
                control.encerra(
                    summary="Cannot close",
                    next_action="Remain safe",
                )
            self.assertEqual(before, snapshot(root))

    def test_first_reflection_write_failure_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize(root)
            before = snapshot(root)

            def fail(point: str, _path: str, index: int) -> None:
                if point == "after-replace" and index == 1:
                    raise OSError("synthetic reflection failure")

            control = ControlPlane(root, fault_hook=fail)
            with self.assertRaises(TransactionError):
                control.digere(
                    summary="Synthetic reflection",
                    pending="Register it",
                )
            self.assertEqual(before, snapshot(root))
            self.assertTrue(ControlPlane(root).sync()["clean"])

    def test_registra_and_encerra_failures_each_roll_back(self) -> None:
        for action in ("registra", "encerra"):
            with self.subTest(action=action):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    control = initialize(root)
                    control.digere(
                        summary="Synthetic reflection",
                        pending="Register it",
                    )
                    if action == "encerra":
                        control.registra()
                    before = snapshot(root)

                    def fail(point: str, _path: str, index: int) -> None:
                        if point == "after-replace" and index == 2:
                            raise OSError("synthetic lifecycle failure")

                    failing = ControlPlane(root, fault_hook=fail)
                    with self.assertRaises(TransactionError):
                        if action == "registra":
                            failing.registra()
                        else:
                            failing.encerra(
                                summary="Synthetic closeout",
                                next_action="Continue safely",
                            )
                    self.assertEqual(before, snapshot(root))
                    self.assertTrue(ControlPlane(root).sync()["clean"])

    def test_focus_is_transactional_and_alias_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            control.init(
                front_id="second-front",
                display_name="Second Front",
                path="fronts/second-front",
                aliases=("second",),
            )
            result = control.foco("second")
            self.assertTrue(result["changed"])
            manifest = parse_manifest(
                (root / MANIFEST_RELATIVE).read_text(encoding="utf-8")
            )
            self.assertEqual("second-front", manifest.active_focus)
            no_op = control.foco("second-front")
            self.assertFalse(no_op["changed"])


class SyncAndRepairTests(unittest.TestCase):
    def test_clean_sync_is_strictly_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            before = snapshot(root)
            result = control.sync()
            self.assertTrue(result["clean"])
            self.assertEqual(before, snapshot(root))

    def test_sync_reports_corruption_without_repairing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            panel = root / "FRONTS.md"
            panel.write_text("synthetic mismatch\n", encoding="utf-8")
            before = snapshot(root)
            result = control.sync()
            self.assertFalse(result["clean"])
            self.assertIn("PANEL_MISMATCH", {issue["code"] for issue in result["issues"]})
            self.assertEqual(before, snapshot(root))

    def test_narrow_panel_repair_requires_preview_and_restores_only_panel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            panel = root / "FRONTS.md"
            panel.write_text("synthetic mismatch\n", encoding="utf-8")
            before = snapshot(root)
            preview = control.plan_repair_panel()
            self.assertTrue(preview["changed"])
            self.assertEqual(before, snapshot(root))
            applied = control.repair_panel()
            self.assertTrue(applied["changed"])
            self.assertEqual(["FRONTS.md"], applied["paths"])
            self.assertTrue(control.sync()["clean"])

    def test_repair_refuses_non_panel_inconsistency_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            (root / "FRONTS.md").write_text("synthetic mismatch\n", encoding="utf-8")
            next_path = root / "fronts" / "sample-front" / "NEXT.md"
            next_path.write_text("synthetic mismatch\n", encoding="utf-8")
            before = snapshot(root)
            with self.assertRaises(StateError):
                control.plan_repair_panel()
            with self.assertRaises(StateError):
                control.repair_panel()
            self.assertEqual(before, snapshot(root))

    def test_invalid_utf8_manifest_is_reported_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = initialize(root)
            manifest = root / MANIFEST_RELATIVE
            manifest.write_bytes(bytes((255, 254, 253)))
            before = snapshot(root)
            result = control.sync()
            self.assertIn("MANIFEST_INVALID", {issue["code"] for issue in result["issues"]})
            self.assertEqual(before, snapshot(root))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_escape_registration_is_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / (root.name + "-outside")
            outside.mkdir()
            try:
                (root / "fronts").symlink_to(outside, target_is_directory=True)
                before = snapshot(root)
                with self.assertRaises(ValidationError):
                    ControlPlane(root).init(
                        front_id="sample-front",
                        display_name="Sample Front",
                        path="fronts/sample-front",
                    )
                self.assertEqual(before, snapshot(root))
            finally:
                (root / "fronts").unlink()
                outside.rmdir()
