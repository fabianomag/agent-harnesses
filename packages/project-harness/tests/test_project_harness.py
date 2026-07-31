"""Package-local tests for the clean-room Project Harness."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest import mock


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

import project_harness as harness  # noqa: E402


def _tree_snapshot(root: Path) -> dict[str, tuple[str, int, int, bytes | None]]:
    snapshot: dict[str, tuple[str, int, int, bytes | None]] = {}
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in sorted(directory_names + file_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                kind = "symlink"
                content: bytes | None = os.readlink(path).encode("utf-8")
            elif stat.S_ISDIR(metadata.st_mode):
                kind = "directory"
                content = None
            elif stat.S_ISREG(metadata.st_mode):
                kind = "file"
                content = path.read_bytes()
            else:
                kind = "other"
                content = None
            snapshot[relative] = (
                kind,
                stat.S_IMODE(metadata.st_mode),
                metadata.st_mtime_ns,
                content,
            )
    return snapshot


def _logical_snapshot(root: Path) -> dict[str, tuple[str, int, bytes | None]]:
    return {
        path: (kind, mode, content)
        for path, (kind, mode, _modified, content) in _tree_snapshot(root).items()
    }


def _fixed_time(value: str):
    return lambda: value


class TemporaryProjectTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name).resolve(strict=True)
        self.root = temporary_root / "synthetic-project"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()


class InitializationTests(TemporaryProjectTestCase):
    def test_dry_run_has_zero_writes_and_complete_plan(self) -> None:
        existing = self.root / "existing.txt"
        existing.write_text("synthetic", encoding="utf-8")
        before = _tree_snapshot(self.root)

        plan = harness.initialize(self.root, dry_run=True)

        self.assertEqual(before, _tree_snapshot(self.root))
        observed = {
            (change["action"], change["path"])
            for change in plan.rendered_changes()
        }
        expected_directories = {
            ("create-directory", path.as_posix())
            for path in harness.REQUIRED_DIRECTORIES
        }
        expected_files = {
            ("create-file", harness.STATE_PATH.as_posix()),
            *{
                ("create-file", spec.path.as_posix())
                for spec in harness.MANAGED_FILES
            },
        }
        self.assertEqual(expected_directories | expected_files, observed)

    def test_clean_install_has_required_structure_and_verifies(self) -> None:
        plan = harness.initialize(self.root)

        self.assertFalse(plan.is_noop)
        self.assertEqual([], harness.verify_root(self.root))
        for relative in harness.REQUIRED_DIRECTORIES:
            self.assertTrue((self.root / relative).is_dir())
        for spec in harness.MANAGED_FILES:
            data = (self.root / spec.path).read_bytes()
            self.assertEqual(1, data.count(spec.begin_marker))
            self.assertEqual(1, data.count(spec.end_marker))
        state = json.loads(
            (self.root / harness.STATE_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(harness.HARNESS_VERSION, state["harnessVersion"])
        self.assertEqual([], state["records"])

    def test_preexisting_utf8_content_is_preserved_outside_managed_block(self) -> None:
        existing = b"# Existing\r\n\r\nSynthetic owner text\r\n"
        agents = self.root / "AGENTS.md"
        agents.write_bytes(existing)

        harness.initialize(self.root)

        installed = agents.read_bytes()
        self.assertTrue(installed.startswith(existing))
        suffix = b"\r\nSynthetic tail\r\n"
        agents.write_bytes(installed + suffix)
        begin = installed.index(harness.MANAGED_FILES[0].begin_marker)
        preserved_prefix = installed[:begin]
        inside = installed.replace(
            b"This harness coordinates context",
            b"This block drifted",
            1,
        )
        agents.write_bytes(inside + suffix)

        harness.initialize(self.root)

        reconciled = agents.read_bytes()
        self.assertEqual(preserved_prefix, reconciled[:begin])
        self.assertTrue(reconciled.startswith(existing))
        self.assertTrue(reconciled.endswith(suffix))
        self.assertNotIn(b"This block drifted", reconciled)
        self.assertEqual([], harness.verify_root(self.root))

    def test_second_init_is_true_noop(self) -> None:
        harness.initialize(self.root)
        before = _tree_snapshot(self.root)

        plan = harness.initialize(self.root)

        self.assertTrue(plan.is_noop)
        self.assertEqual(before, _tree_snapshot(self.root))

    def test_duplicate_marker_is_a_zero_write_collision(self) -> None:
        spec = harness.MANAGED_FILES[0]
        (self.root / spec.path).write_bytes(
            spec.begin_marker
            + b"\nsynthetic\n"
            + spec.begin_marker
            + b"\n"
            + spec.end_marker
            + b"\n"
        )
        before = _tree_snapshot(self.root)

        with self.assertRaises(harness.CollisionError):
            harness.initialize(self.root)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_file_directory_collision_is_zero_write(self) -> None:
        (self.root / "docs").write_text("synthetic collision", encoding="utf-8")
        before = _tree_snapshot(self.root)

        with self.assertRaises(harness.CollisionError):
            harness.initialize(self.root)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_invalid_utf8_is_zero_write_collision(self) -> None:
        (self.root / "AGENTS.md").write_bytes(b"\xff")
        before = _tree_snapshot(self.root)

        with self.assertRaises(harness.CollisionError):
            harness.initialize(self.root)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_projection_without_canonical_state_is_not_inferred(self) -> None:
        harness.initialize(self.root)
        (self.root / harness.STATE_PATH).unlink()
        decisions = self.root / "docs" / "decisions.md"
        decisions.write_bytes(
            decisions.read_bytes().replace(b"No records yet.", b"Synthetic history")
        )
        before = _tree_snapshot(self.root)

        with self.assertRaises(harness.CollisionError) as context:
            harness.initialize(self.root)

        self.assertEqual("STATE_MISSING", context.exception.code)
        self.assertEqual(before, _tree_snapshot(self.root))


class BoundaryTests(TemporaryProjectTestCase):
    def test_empty_root_argument_is_rejected(self) -> None:
        with self.assertRaises(harness.HarnessError) as context:
            harness.initialize("", dry_run=True)

        self.assertEqual("ROOT_INVALID", context.exception.code)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symbolic_link_root_is_rejected(self) -> None:
        target = self.root / "target"
        target.mkdir()
        linked_root = self.root / "linked"
        os.symlink(target.name, linked_root)

        with self.assertRaises(harness.HarnessError) as context:
            harness.initialize(linked_root)

        self.assertEqual("ROOT_SYMLINK", context.exception.code)
        self.assertEqual([], list(target.iterdir()))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symbolic_link_component_does_not_touch_external_target(self) -> None:
        external = self.root.parent / "synthetic-external"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("unchanged", encoding="utf-8")
        os.symlink(external, self.root / "docs")
        before = _tree_snapshot(external)

        with self.assertRaises(harness.CollisionError) as context:
            harness.initialize(self.root)

        self.assertEqual("PATH_SYMLINK", context.exception.code)
        self.assertEqual(before, _tree_snapshot(external))

    def test_path_traversal_is_rejected(self) -> None:
        canonical = self.root.resolve()

        with self.assertRaises(harness.HarnessError) as context:
            harness._target(canonical, PurePosixPath("..") / "outside")

        self.assertEqual("PATH_BOUNDARY", context.exception.code)

    def test_windows_reparse_metadata_is_link_like_when_supported(self) -> None:
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not reparse_flag:
            self.skipTest("reparse metadata constant unavailable")
        metadata = SimpleNamespace(
            st_mode=stat.S_IFDIR,
            st_file_attributes=reparse_flag,
        )

        self.assertTrue(harness._is_link_like(metadata))


class TransactionTests(TemporaryProjectTestCase):
    def test_failure_before_each_replace_rolls_back_complete_init(self) -> None:
        for fail_index in range(1 + len(harness.MANAGED_FILES)):
            with self.subTest(fail_index=fail_index):
                project = self.root / f"case-{fail_index}"
                project.mkdir()
                (project / "existing.txt").write_text(
                    "synthetic",
                    encoding="utf-8",
                )
                before = _tree_snapshot(project)

                def fail_at(index: int, _path: PurePosixPath) -> None:
                    if index == fail_index:
                        raise OSError("injected write failure")

                with self.assertRaises(harness.TransactionError) as context:
                    harness.initialize(project, before_replace=fail_at)

                self.assertEqual("TRANSACTION_ROLLED_BACK", context.exception.code)
                self.assertEqual(before, _tree_snapshot(project))

    def test_post_verify_failure_rolls_back(self) -> None:
        before = _tree_snapshot(self.root)
        issue = harness.VerificationIssue(
            ".",
            "INJECTED",
            "synthetic verification failure",
        )

        with mock.patch.object(harness, "verify_root", return_value=[issue]):
            with self.assertRaises(harness.TransactionError):
                harness.initialize(self.root)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_keyboard_interrupt_rolls_back_before_propagating(self) -> None:
        before = _tree_snapshot(self.root)

        def interrupt_second(index: int, _path: PurePosixPath) -> None:
            if index == 1:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            harness.initialize(self.root, before_replace=interrupt_second)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_record_failure_rolls_back_state_and_projections(self) -> None:
        harness.initialize(self.root)
        before = _logical_snapshot(self.root)

        def fail_third(index: int, _path: PurePosixPath) -> None:
            if index == 2:
                raise OSError("injected record failure")

        with self.assertRaises(harness.TransactionError):
            harness.record_event(
                self.root,
                kind="close",
                summary="Synthetic close",
                decisions=["Keep the synthetic boundary"],
                tasks=["Review synthetic output"],
                next_step="Reopen the synthetic project",
                session="rollback-session",
                now=_fixed_time("2026-01-02T03:04:05Z"),
                before_replace=fail_third,
            )

        self.assertEqual(before, _logical_snapshot(self.root))
        self.assertEqual([], harness.verify_root(self.root))


class LifecycleTests(TemporaryProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        harness.initialize(self.root)

    def test_empty_close_summary_is_rejected_without_writes(self) -> None:
        before = _tree_snapshot(self.root)

        with self.assertRaises(harness.HarnessError) as context:
            harness.record_event(
                self.root,
                kind="close",
                summary="   ",
                decisions=[],
                tasks=[],
                next_step="Continue synthetic work",
            )

        self.assertEqual("INPUT_EMPTY", context.exception.code)
        self.assertEqual(before, _tree_snapshot(self.root))

    def test_checkpoint_close_and_reopen_persist_durable_state(self) -> None:
        checkpoint = harness.record_event(
            self.root,
            kind="checkpoint",
            summary="Established the café baseline",
            decisions=["Keep Unicode state"],
            tasks=["Inspect the generated fixture"],
            next_step="Close the synthetic block",
            session="synthetic-session",
            now=_fixed_time("2026-01-02T03:04:05Z"),
        )
        closed = harness.record_event(
            self.root,
            kind="close",
            summary="Completed the synthetic cycle",
            decisions=["Retain the verified layout"],
            tasks=["Reopen from durable state"],
            next_step="Begin the next bounded task",
            session="synthetic-session",
            now=_fixed_time("2026-01-02T03:05:06Z"),
        )

        self.assertEqual("R0001", checkpoint["id"])
        self.assertEqual("R0002", closed["id"])
        self.assertEqual([], harness.verify_root(self.root))
        reopened = harness.status_snapshot(self.root)
        digest = harness.digest_snapshot(self.root)
        self.assertEqual(2, reopened["recordCount"])
        self.assertEqual("close", reopened["lastRecord"]["kind"])
        self.assertEqual("Begin the next bounded task", reopened["nextStep"])
        self.assertEqual(2, len(digest["decisions"]))
        self.assertEqual(["Reopen from durable state"], digest["currentTasks"])
        for relative in (
            "docs/decisions.md",
            "docs/next-actions.md",
            "docs/session-log.md",
        ):
            text = (self.root / relative).read_text(encoding="utf-8")
            self.assertIn("R0001", text)
            self.assertIn("R0002", text)
        state = json.loads(
            (self.root / harness.STATE_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(3, state["nextRecord"])
        self.assertEqual(2, len(state["records"]))

    def test_read_only_commands_do_not_change_tree(self) -> None:
        context_path = self.root / "docs" / "project-context.md"
        architecture_path = self.root / "ARCHITECTURE.md"
        context_path.write_bytes(
            context_path.read_bytes()
            + b"\nSynthetic purpose and confirmed constraints.\n"
        )
        architecture_path.write_bytes(
            architecture_path.read_bytes()
            + b"\nSynthetic component boundary.\n"
        )
        before = _tree_snapshot(self.root)

        harness.status_snapshot(self.root)
        opened = harness.open_snapshot(self.root)
        digested = harness.digest_snapshot(self.root)
        harness.verify_root(self.root)

        self.assertEqual(
            "Synthetic purpose and confirmed constraints.",
            opened["projectContext"],
        )
        self.assertEqual(
            "Synthetic component boundary.",
            opened["architectureContext"],
        )
        self.assertEqual(opened["projectContext"], digested["projectContext"])
        self.assertEqual(
            opened["architectureContext"],
            digested["architectureContext"],
        )
        self.assertEqual(before, _tree_snapshot(self.root))


class VerificationTests(TemporaryProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        harness.initialize(self.root)

    def test_verify_detects_missing_file_without_writing(self) -> None:
        (self.root / "docs" / "session-log.md").unlink()
        before = _tree_snapshot(self.root)

        issues = harness.verify_root(self.root)

        self.assertIn("FILE_MISSING", {issue.code for issue in issues})
        self.assertEqual(before, _tree_snapshot(self.root))

    def test_verify_detects_managed_block_drift_and_init_repairs_it(self) -> None:
        decisions = self.root / "docs" / "decisions.md"
        decisions.write_bytes(
            decisions.read_bytes().replace(b"No records yet.", b"Drifted content")
        )
        before_verify = _tree_snapshot(self.root)

        issues = harness.verify_root(self.root)

        self.assertIn("MANAGED_BLOCK_DRIFT", {issue.code for issue in issues})
        self.assertEqual(before_verify, _tree_snapshot(self.root))
        harness.initialize(self.root)
        self.assertEqual([], harness.verify_root(self.root))

    def test_verify_reports_duplicate_marker(self) -> None:
        spec = harness.MANAGED_FILES[1]
        path = self.root / spec.path
        path.write_bytes(path.read_bytes() + b"\n" + spec.begin_marker + b"\n")

        issues = harness.verify_root(self.root)

        self.assertIn("MARKER_COLLISION", {issue.code for issue in issues})


class CommandLineTests(TemporaryProjectTestCase):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(PACKAGE_ROOT / "project_harness.py"),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_cli_init_verify_and_open(self) -> None:
        dry_run = self._run(
            "init",
            "--root",
            str(self.root),
            "--dry-run",
            "--json",
        )
        self.assertEqual(0, dry_run.returncode, dry_run.stderr)
        self.assertEqual({}, _tree_snapshot(self.root))

        installed = self._run("init", "--root", str(self.root))
        verified = self._run("verify", "--root", str(self.root))
        opened = self._run("open", "--root", str(self.root), "--json")

        self.assertEqual(0, installed.returncode, installed.stderr)
        self.assertEqual(0, verified.returncode, verified.stderr)
        self.assertEqual(0, opened.returncode, opened.stderr)
        self.assertEqual(0, json.loads(opened.stdout)["recordCount"])

    def test_cli_rejects_empty_root_argument(self) -> None:
        result = self._run("init", "--root", "", "--dry-run")

        self.assertEqual(2, result.returncode)
        self.assertIn("ROOT_INVALID", result.stderr)
        self.assertEqual({}, _tree_snapshot(self.root))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_cli_rejects_parent_symlink_and_accepts_physical_root(self) -> None:
        physical_parent = self.root.parent / "physical-parent"
        physical_root = physical_parent / "selected-root"
        physical_root.mkdir(parents=True)
        (physical_root / "sentinel.txt").write_text(
            "synthetic sentinel\n",
            encoding="utf-8",
        )
        alias_parent = self.root.parent / "alias-parent"
        os.symlink(physical_parent.name, alias_parent)
        linked_root = alias_parent / physical_root.name
        before = _tree_snapshot(physical_root)

        for arguments in (
            ("init", "--root", str(linked_root), "--dry-run"),
            ("init", "--root", str(linked_root)),
        ):
            result = self._run(*arguments)
            self.assertEqual(2, result.returncode)
            self.assertIn("ROOT_SYMLINK", result.stderr)
            self.assertEqual(before, _tree_snapshot(physical_root))

        physical_dry_run = self._run(
            "init",
            "--root",
            str(physical_root),
            "--dry-run",
        )
        self.assertEqual(0, physical_dry_run.returncode, physical_dry_run.stderr)
        self.assertEqual(before, _tree_snapshot(physical_root))

        physical_apply = self._run("init", "--root", str(physical_root))
        physical_verify = self._run("verify", "--root", str(physical_root))
        self.assertEqual(0, physical_apply.returncode, physical_apply.stderr)
        self.assertEqual(0, physical_verify.returncode, physical_verify.stderr)

    def test_cli_empty_close_is_nonzero_and_zero_write(self) -> None:
        self.assertEqual(0, self._run("init", "--root", str(self.root)).returncode)
        before = _tree_snapshot(self.root)

        closed = self._run(
            "close",
            "--root",
            str(self.root),
            "--summary",
            " ",
            "--next-step",
            "Continue synthetic work",
        )

        self.assertEqual(2, closed.returncode)
        self.assertIn("INPUT_EMPTY", closed.stderr)
        self.assertEqual(before, _tree_snapshot(self.root))


if __name__ == "__main__":
    unittest.main()
