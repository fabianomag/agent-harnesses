"""Failure, lock, rollback, and durable recovery tests."""

from __future__ import annotations

import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap

from orchestration_harness.errors import (
    LockBusyError,
    RecoveryError,
    TransactionError,
)
from orchestration_harness.transaction import (
    PortableLock,
    _fsync_directory,
    execute_transaction,
    inspect_recovery,
    recover_transaction,
)

from helpers import snapshot


class CrashSignal(BaseException):
    """Simulate process death without entering exception rollback."""


class TransactionTests(unittest.TestCase):
    def test_atomic_success_updates_existing_and_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing.txt").write_text("before", encoding="utf-8")

            result = execute_transaction(
                root,
                lambda _txid: (
                    {"existing.txt": "after", "nested/new.txt": "new"},
                    {"ok": True},
                ),
            )

            self.assertTrue(result.changed)
            self.assertEqual("after", (root / "existing.txt").read_text(encoding="utf-8"))
            self.assertEqual("new", (root / "nested/new.txt").read_text(encoding="utf-8"))
            self.assertFalse((root / ".orchestration-journal.json").exists())

    def test_noop_does_not_change_workspace_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "same.txt").write_text("same", encoding="utf-8")
            before = snapshot(root)
            result = execute_transaction(
                root,
                lambda _txid: ({"same.txt": "same"}, None),
            )
            self.assertFalse(result.changed)
            self.assertEqual(before, snapshot(root))

    def test_concurrent_writer_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with PortableLock(root, "a" * 32):
                with self.assertRaises(LockBusyError):
                    execute_transaction(
                        root,
                        lambda _txid: ({"value.txt": "value"}, None),
                    )
            self.assertFalse((root / "value.txt").exists())

    def test_write_failures_roll_back_every_boundary(self) -> None:
        for point, index in (
            ("before-replace", 0),
            ("after-replace", 0),
            ("before-replace", 1),
            ("after-replace", 1),
        ):
            with self.subTest(point=point, index=index):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "existing.txt").write_text("before", encoding="utf-8")
                    before = snapshot(root)

                    def fail(current_point: str, _path: str, current_index: int) -> None:
                        if current_point == point and current_index == index:
                            raise OSError(errno.EIO, "synthetic write failure")

                    with self.assertRaises(TransactionError):
                        execute_transaction(
                            root,
                            lambda _txid: (
                                {
                                    "existing.txt": "after",
                                    "nested/new.txt": "new",
                                },
                                None,
                            ),
                            fault_hook=fail,
                        )
                    self.assertEqual(before, snapshot(root))

    def test_crash_during_apply_is_recovered_by_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing.txt").write_text("before", encoding="utf-8")

            def crash(point: str, _path: str, index: int) -> None:
                if point == "after-replace" and index == 0:
                    raise CrashSignal()

            with self.assertRaises(CrashSignal):
                execute_transaction(
                    root,
                    lambda _txid: (
                        {"existing.txt": "after", "new.txt": "new"},
                        None,
                    ),
                    fault_hook=crash,
                )
            preview = inspect_recovery(root)
            self.assertTrue(preview.present)
            self.assertEqual("applying", preview.phase)

            recover_transaction(root)

            self.assertEqual("before", (root / "existing.txt").read_text(encoding="utf-8"))
            self.assertFalse((root / "new.txt").exists())
            self.assertFalse(inspect_recovery(root).present)

    def test_crash_after_commit_keeps_new_state_and_finishes_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "value.txt").write_text("before", encoding="utf-8")

            def crash(point: str, _path: str, _index: int) -> None:
                if point == "after-commit":
                    raise CrashSignal()

            with self.assertRaises(CrashSignal):
                execute_transaction(
                    root,
                    lambda _txid: ({"value.txt": "after"}, None),
                    fault_hook=crash,
                )
            self.assertEqual("committed", inspect_recovery(root).phase)

            recover_transaction(root)

            self.assertEqual("after", (root / "value.txt").read_text(encoding="utf-8"))
            self.assertFalse(inspect_recovery(root).present)

    def test_normal_error_after_commit_returns_committed_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fail(point: str, _path: str, _index: int) -> None:
                if point == "after-commit":
                    raise OSError("synthetic post-commit failure")

            result = execute_transaction(
                root,
                lambda _txid: ({"value.txt": "committed"}, {"ok": True}),
                fault_hook=fail,
            )

            self.assertTrue(result.changed)
            self.assertEqual("committed", (root / "value.txt").read_text(encoding="utf-8"))
            self.assertFalse(inspect_recovery(root).present)

    def test_unknown_digest_stops_recovery_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "value.txt"
            target.write_text("before", encoding="utf-8")

            def crash(point: str, _path: str, index: int) -> None:
                if point == "after-replace" and index == 0:
                    raise CrashSignal()

            with self.assertRaises(CrashSignal):
                execute_transaction(
                    root,
                    lambda _txid: ({"value.txt": "after"}, None),
                    fault_hook=crash,
                )
            target.write_text("unrelated", encoding="utf-8")

            with self.assertRaises(RecoveryError):
                recover_transaction(root)

            self.assertEqual("unrelated", target.read_text(encoding="utf-8"))
            self.assertTrue(inspect_recovery(root).present)

    def test_stale_lock_requires_explicit_matching_break(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def crash(point: str, _path: str, index: int) -> None:
                if point == "after-replace" and index == 0:
                    raise CrashSignal()

            with self.assertRaises(CrashSignal):
                execute_transaction(
                    root,
                    lambda _txid: ({"value.txt": "new"}, None),
                    fault_hook=crash,
                )
            preview = inspect_recovery(root)
            assert preview.transaction_id is not None
            stale = PortableLock(root, preview.transaction_id)
            stale.__enter__()

            with self.assertRaises(LockBusyError):
                recover_transaction(root)
            recovered = recover_transaction(root, break_stale_lock=True)

            self.assertTrue(recovered.present)
            self.assertFalse((root / "value.txt").exists())
            self.assertFalse(inspect_recovery(root).present)

    def test_directory_fsync_tolerates_known_unsupported_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                os,
                "fsync",
                side_effect=OSError(errno.EINVAL, "synthetic unsupported"),
            ):
                _fsync_directory(Path(directory))

    def test_directory_fsync_propagates_io_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                os,
                "fsync",
                side_effect=OSError(errno.EIO, "synthetic io failure"),
            ):
                with self.assertRaises(OSError):
                    _fsync_directory(Path(directory))
