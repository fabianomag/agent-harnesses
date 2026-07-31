"""Behavior tests for the Workspace Coordination Harness."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "coordinator"
sys.path.insert(0, str(PACKAGE_ROOT))

import workspace_coordination as harness  # noqa: E402


def _tree_snapshot(root: Path) -> dict[str, tuple[str, bytes | None]]:
    snapshot: dict[str, tuple[str, bytes | None]] = {}
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in sorted(directory_names + file_names):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                snapshot[relative] = (
                    "symlink",
                    os.readlink(candidate).encode("utf-8"),
                )
            elif stat.S_ISDIR(metadata.st_mode):
                snapshot[relative] = ("directory", None)
            elif stat.S_ISREG(metadata.st_mode):
                snapshot[relative] = ("file", candidate.read_bytes())
            else:
                snapshot[relative] = ("other", None)
    return snapshot


class CoordinatorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary_root = Path(self.temporary.name).resolve(strict=True)
        self.root = temporary_root / "coordinator"
        shutil.copytree(FIXTURE_ROOT, self.root)

    def initialize(self) -> None:
        result = harness.initialize(self.root, apply=True)
        self.assertEqual("applied", result.mode)

    def add_alpha(self) -> None:
        result = harness.add_child(
            self.root,
            child_id="alpha",
            child_path="child-alpha",
            owner="AGENTS.md",
            apply=True,
        )
        self.assertIn(result.mode, {"applied", "noop"})

    def add_beta(self) -> None:
        result = harness.add_child(
            self.root,
            child_id="beta",
            child_path="child-beta",
            owner="OWNER.md",
            apply=True,
        )
        self.assertIn(result.mode, {"applied", "noop"})


class InitializationTests(CoordinatorTestCase):
    def test_dry_run_has_zero_writes(self) -> None:
        before = _tree_snapshot(self.root)
        result = harness.initialize(self.root, apply=False)
        after = _tree_snapshot(self.root)

        self.assertEqual("dry-run", result.mode)
        self.assertEqual(before, after)
        self.assertEqual(
            {
                ".workspace-coordination/BOUNDARIES.md",
                ".workspace-coordination/INDEX.md",
                ".workspace-coordination/SHARED_DELTAS.md",
                ".workspace-coordination/workspace.json",
                "WORKSPACE_COORDINATION.md",
            },
            set(result.changed),
        )

    def test_clean_init_creates_verified_coordinator(self) -> None:
        self.initialize()

        self.assertTrue((self.root / harness.MANIFEST_PATH).is_file())
        self.assertTrue((self.root / harness.INDEX_PATH).is_file())
        self.assertTrue(harness.verify(self.root).ok)

    def test_init_is_byte_idempotent(self) -> None:
        self.initialize()
        before = _tree_snapshot(self.root)

        result = harness.initialize(self.root, apply=True)

        self.assertEqual("noop", result.mode)
        self.assertEqual(before, _tree_snapshot(self.root))

    def test_collision_preserves_existing_file_and_creates_nothing(self) -> None:
        collision = self.root / harness.ENTRYPOINT_PATH
        collision.write_text("synthetic sentinel\n", encoding="utf-8")
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "already exists"):
            harness.initialize(self.root, apply=True)

        self.assertEqual(before, _tree_snapshot(self.root))
        self.assertFalse((self.root / harness.MANIFEST_PATH).exists())

    def test_dry_run_rejects_control_directory_file_collision(self) -> None:
        control = self.root / harness.CONTROL_DIRECTORY
        control.write_text("synthetic sentinel\n", encoding="utf-8")
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "not a directory"):
            harness.initialize(self.root, apply=False)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_missing_root_and_file_root_are_rejected(self) -> None:
        missing = self.root / "missing"
        with self.assertRaisesRegex(harness.HarnessError, "does not exist"):
            harness.initialize(missing, apply=False)

        file_root = self.root / "root-file"
        file_root.write_text("synthetic\n", encoding="utf-8")
        with self.assertRaisesRegex(harness.HarnessError, "must be a directory"):
            harness.initialize(file_root, apply=False)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_root_is_rejected(self) -> None:
        link = self.root.parent / "coordinator-link"
        os.symlink(self.root.name, link)

        with self.assertRaisesRegex(harness.HarnessError, "cannot be a symlink"):
            harness.initialize(link, apply=False)

    def test_windows_reparse_metadata_is_link_like_when_supported(self) -> None:
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not reparse_flag:
            self.skipTest("reparse metadata constant unavailable")
        metadata = SimpleNamespace(
            st_mode=stat.S_IFDIR,
            st_file_attributes=reparse_flag,
        )

        self.assertTrue(harness._is_link_like(metadata))


class ChildManifestTests(CoordinatorTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.initialize()

    def test_two_child_fixture_builds_manifest_and_index(self) -> None:
        preserved = (
            self.root / "child-alpha" / "PROJECT_STATE.md"
        ).read_bytes()
        self.add_beta()
        self.add_alpha()

        manifest = json.loads(
            (self.root / harness.MANIFEST_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(["alpha", "beta"], [
            child["id"] for child in manifest["children"]
        ])
        index = (self.root / harness.INDEX_PATH).read_text(encoding="utf-8")
        self.assertIn("child-alpha", index)
        self.assertIn("child-beta", index)
        self.assertEqual(
            preserved,
            (self.root / "child-alpha" / "PROJECT_STATE.md").read_bytes(),
        )
        self.assertTrue(harness.verify(self.root).ok)

    def test_identical_add_is_idempotent(self) -> None:
        self.add_alpha()
        before = _tree_snapshot(self.root)

        result = harness.add_child(
            self.root,
            child_id="alpha",
            child_path="child-alpha",
            owner="AGENTS.md",
            apply=True,
        )

        self.assertEqual("noop", result.mode)
        self.assertEqual(before, _tree_snapshot(self.root))

    def test_physical_case_alias_cannot_be_registered_twice(self) -> None:
        alias = self.root / "CHILD-ALPHA"
        try:
            same_fixture = os.path.samefile(alias, self.root / "child-alpha")
        except OSError:
            same_fixture = False
        if not same_fixture:
            self.skipTest("fixture filesystem is case-sensitive")
        self.add_alpha()
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "overlap"):
            harness.add_child(
                self.root,
                child_id="alias",
                child_path="CHILD-ALPHA",
                owner="AGENTS.md",
                apply=True,
            )

        self.assertEqual(before, _tree_snapshot(self.root))
        nested = self.root / "child-alpha" / "nested"
        nested.mkdir()
        (nested / "OWNER.md").write_text("synthetic\n", encoding="utf-8")
        before_nested = _tree_snapshot(self.root)
        with self.assertRaisesRegex(harness.HarnessError, "overlap"):
            harness.add_child(
                self.root,
                child_id="nested-alias",
                child_path="CHILD-ALPHA/nested",
                owner="OWNER.md",
                apply=True,
            )

        self.assertEqual(before_nested, _tree_snapshot(self.root))

    def test_portable_overlap_is_case_insensitive(self) -> None:
        self.assertTrue(harness._paths_overlap("Child", "child/nested"))
        self.assertTrue(harness._paths_overlap("ALPHA/nested", "alpha"))

    def test_child_id_collision_is_non_destructive(self) -> None:
        self.add_alpha()
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "already registered"):
            harness.add_child(
                self.root,
                child_id="alpha",
                child_path="child-beta",
                owner="OWNER.md",
                apply=True,
            )

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_remove_only_changes_registration(self) -> None:
        self.add_alpha()
        child_before = _tree_snapshot(self.root / "child-alpha")

        result = harness.remove_child(
            self.root,
            child_id="alpha",
            apply=True,
        )

        self.assertEqual("applied", result.mode)
        self.assertEqual(child_before, _tree_snapshot(self.root / "child-alpha"))
        self.assertEqual(
            [],
            json.loads(
                (self.root / harness.MANIFEST_PATH).read_text(encoding="utf-8")
            )["children"],
        )
        self.assertEqual(
            "noop",
            harness.remove_child(
                self.root,
                child_id="alpha",
                apply=True,
            ).mode,
        )

    def test_re_registration_cannot_claim_another_child_local_state(self) -> None:
        self.add_alpha()
        harness.record_local(
            self.root,
            child_id="alpha",
            key="local-001",
            kind="update",
            summary="Synthetic alpha state.",
            next_action="Continue alpha.",
            apply=True,
        )
        harness.remove_child(self.root, child_id="alpha", apply=True)
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "different child id"):
            harness.add_child(
                self.root,
                child_id="replacement",
                child_path="child-alpha",
                owner="AGENTS.md",
                apply=True,
            )

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_absolute_parent_and_backslash_paths_are_rejected(self) -> None:
        absolute = str((self.root / "child-alpha").resolve())
        invalid_values = (
            absolute,
            "../child-alpha",
            "child" + "\\" + "alpha",
            "child-alpha/",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(harness.HarnessError):
                    harness.add_child(
                        self.root,
                        child_id="candidate",
                        child_path=value,
                        owner="AGENTS.md",
                        apply=False,
                    )

    def test_windows_reserved_and_overlapping_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(harness.HarnessError, "reserved"):
            harness.validate_relative_path("NUL/state.md", field="synthetic")

        self.add_alpha()
        nested = self.root / "child-alpha" / "nested"
        nested.mkdir()
        (nested / "OWNER.md").write_text("synthetic\n", encoding="utf-8")
        with self.assertRaisesRegex(harness.HarnessError, "must not overlap"):
            harness.add_child(
                self.root,
                child_id="nested",
                child_path="child-alpha/nested",
                owner="OWNER.md",
                apply=False,
            )

    def test_managed_control_directory_cannot_be_a_child_or_owner(self) -> None:
        for control_path in (
            ".workspace-coordination",
            ".WORKSPACE-COORDINATION",
        ):
            with self.subTest(control_path=control_path):
                with self.assertRaisesRegex(
                    harness.HarnessError,
                    "control directory",
                ):
                    harness.add_child(
                        self.root,
                        child_id="control",
                        child_path=control_path,
                        owner="INDEX.md",
                        apply=False,
                    )

        child_control = self.root / "child-alpha" / ".workspace-coordination"
        child_control.mkdir()
        (child_control / "OWNER.md").write_text(
            "synthetic\n",
            encoding="utf-8",
        )
        for owner_path in (
            ".workspace-coordination/OWNER.md",
            ".WORKSPACE-COORDINATION/OWNER.md",
        ):
            with self.subTest(owner_path=owner_path):
                with self.assertRaisesRegex(
                    harness.HarnessError,
                    "control directory",
                ):
                    harness.add_child(
                        self.root,
                        child_id="alpha",
                        child_path="child-alpha",
                        owner=owner_path,
                        apply=False,
                    )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_child_symlink_escape_is_rejected_without_outside_write(self) -> None:
        outside = self.root.parent / "outside-child"
        outside.mkdir()
        (outside / "OWNER.md").write_text("outside sentinel\n", encoding="utf-8")
        link = self.root / "linked-child"
        os.symlink(outside, link)
        outside_before = _tree_snapshot(outside)

        with self.assertRaisesRegex(harness.HarnessError, "symbolic link"):
            harness.add_child(
                self.root,
                child_id="linked",
                child_path="linked-child",
                owner="OWNER.md",
                apply=True,
            )

        self.assertEqual(outside_before, _tree_snapshot(outside))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_owner_symlink_escape_is_rejected(self) -> None:
        outside = self.root.parent / "outside-owner.md"
        outside.write_text("outside sentinel\n", encoding="utf-8")
        os.symlink(outside, self.root / "child-alpha" / "LINK.md")

        with self.assertRaisesRegex(harness.HarnessError, "symbolic link"):
            harness.add_child(
                self.root,
                child_id="alpha",
                child_path="child-alpha",
                owner="LINK.md",
                apply=True,
            )

    def test_utf8_owner_and_path_are_supported(self) -> None:
        unicode_child = self.root / "criança"
        unicode_child.mkdir()
        (unicode_child / "ORIENTAÇÃO.md").write_text(
            "# Orientação sintética\n",
            encoding="utf-8",
        )

        harness.add_child(
            self.root,
            child_id="unicode",
            child_path="criança",
            owner="ORIENTAÇÃO.md",
            apply=True,
        )

        opened = harness.open_workspace(self.root, child_id="unicode")
        self.assertIn("Orientação sintética", opened["ownerText"])
        self.assertTrue(harness.verify(self.root).ok)

    def test_invalid_utf8_owner_is_rejected(self) -> None:
        owner = self.root / "child-alpha" / "BROKEN.md"
        owner.write_bytes(bytes((0xFF, 0xFE)))
        before = (self.root / harness.MANIFEST_PATH).read_bytes()

        with self.assertRaisesRegex(harness.HarnessError, "valid UTF-8"):
            harness.add_child(
                self.root,
                child_id="broken",
                child_path="child-alpha",
                owner="BROKEN.md",
                apply=True,
            )

        self.assertEqual(before, (self.root / harness.MANIFEST_PATH).read_bytes())


class WorkflowTests(CoordinatorTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.initialize()
        self.add_alpha()
        self.add_beta()

    def test_open_digest_record_reflect_close_and_reopen(self) -> None:
        coordinator = harness.open_workspace(self.root)
        self.assertEqual(["alpha", "beta"], [
            child["id"] for child in coordinator["children"]
        ])

        initial = harness.digest_child(self.root, child_id="alpha")
        self.assertEqual([], initial["localState"]["records"])
        self.assertIn("Child Alpha Owner", initial["ownerText"])

        record = harness.record_local(
            self.root,
            child_id="alpha",
            key="cycle-001",
            kind="decision",
            summary="Keep the synthetic parser local to alpha.",
            next_action="Exercise the local parser fixture.",
            apply=True,
        )
        self.assertEqual("applied", record.mode)

        reflected = harness.reflect_delta(
            self.root,
            child_id="alpha",
            key="shared-001",
            summary="Both children use the same fixture naming boundary.",
            apply=True,
        )
        self.assertEqual("applied", reflected.mode)

        harness.record_local(
            self.root,
            child_id="alpha",
            key="cycle-002",
            kind="close",
            summary="Alpha cycle closed with local evidence recorded.",
            next_action="Reopen alpha and continue from the parser fixture.",
            apply=True,
        )
        reopened = harness.open_workspace(self.root, child_id="alpha")

        self.assertEqual("cycle-002", reopened["continuity"]["key"])
        self.assertIn("Reopen alpha", reopened["continuity"]["next"])
        self.assertTrue(harness.verify(self.root).ok)

    def test_digest_and_verify_ignore_unmanaged_child_files_and_siblings(self) -> None:
        (self.root / "child-alpha" / "unmanaged.bin").write_bytes(
            bytes((0xFF, 0xFE))
        )
        sibling = self.root / "unregistered"
        sibling.mkdir()
        (sibling / "unmanaged.bin").write_bytes(bytes((0xFF,)))

        digested = harness.digest_child(self.root, child_id="alpha")

        self.assertEqual("alpha", digested["child"]["id"])
        self.assertTrue(harness.verify(self.root).ok)

    def test_record_dry_run_idempotence_and_key_collision(self) -> None:
        before = _tree_snapshot(self.root)
        arguments = dict(
            child_id="alpha",
            key="local-001",
            kind="update",
            summary="Synthetic local state is ready.",
            next_action="Run the next bounded check.",
        )
        dry_run = harness.record_local(self.root, apply=False, **arguments)
        self.assertEqual("dry-run", dry_run.mode)
        self.assertEqual(before, _tree_snapshot(self.root))

        harness.record_local(self.root, apply=True, **arguments)
        applied = _tree_snapshot(self.root)
        self.assertEqual(
            "noop",
            harness.record_local(self.root, apply=True, **arguments).mode,
        )
        self.assertEqual(applied, _tree_snapshot(self.root))

        with self.assertRaisesRegex(harness.HarnessError, "already used"):
            harness.record_local(
                self.root,
                apply=True,
                **{**arguments, "summary": "Different synthetic content."},
            )
        self.assertEqual(applied, _tree_snapshot(self.root))

    def test_continuity_uses_append_order_not_lexical_key_order(self) -> None:
        for key, summary in (
            ("z-first", "First synthetic record."),
            ("a-second", "Second synthetic record."),
        ):
            harness.record_local(
                self.root,
                child_id="alpha",
                key=key,
                kind="update",
                summary=summary,
                next_action="Continue.",
                apply=True,
            )

        reopened = harness.open_workspace(self.root, child_id="alpha")

        self.assertEqual("a-second", reopened["continuity"]["key"])

    def test_reflection_is_minimal_idempotent_and_bounded(self) -> None:
        dense_local = "dense child-only detail"
        harness.record_local(
            self.root,
            child_id="alpha",
            key="local-001",
            kind="update",
            summary=dense_local,
            next_action="Keep detail local.",
            apply=True,
        )
        arguments = dict(
            child_id="alpha",
            key="shared-001",
            summary="A concise shared boundary changed.",
        )
        harness.reflect_delta(self.root, apply=True, **arguments)
        snapshot = _tree_snapshot(self.root)

        self.assertEqual(
            "noop",
            harness.reflect_delta(self.root, apply=True, **arguments).mode,
        )
        shared_text = (self.root / harness.SHARED_PATH).read_text(encoding="utf-8")
        self.assertIn(arguments["summary"], shared_text)
        self.assertNotIn(dense_local, shared_text)
        self.assertEqual(snapshot, _tree_snapshot(self.root))

        with self.assertRaisesRegex(harness.HarnessError, "single printable line"):
            harness.reflect_delta(
                self.root,
                child_id="alpha",
                key="shared-002",
                summary="line one\nline two",
                apply=False,
            )
        with self.assertRaisesRegex(harness.HarnessError, "exceeds"):
            harness.reflect_delta(
                self.root,
                child_id="alpha",
                key="shared-003",
                summary="x" * (harness.MAX_SHARED_TEXT + 1),
                apply=False,
            )

    def test_remove_preserves_child_and_historical_shared_delta(self) -> None:
        harness.reflect_delta(
            self.root,
            child_id="alpha",
            key="shared-001",
            summary="Synthetic boundary retained for history.",
            apply=True,
        )
        child_before = _tree_snapshot(self.root / "child-alpha")

        harness.remove_child(self.root, child_id="alpha", apply=True)

        workspace = json.loads(
            (self.root / harness.MANIFEST_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(["beta"], [child["id"] for child in workspace["children"]])
        self.assertEqual("alpha", workspace["sharedDeltas"][0]["child"])
        self.assertEqual(child_before, _tree_snapshot(self.root / "child-alpha"))
        self.assertTrue(harness.verify(self.root).ok)


class VerificationAndRecoveryTests(CoordinatorTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.initialize()
        self.add_alpha()

    def test_verify_detects_drift_and_recovery_restores_it(self) -> None:
        index = self.root / harness.INDEX_PATH
        index.write_text("synthetic drift\n", encoding="utf-8")
        before = _tree_snapshot(self.root)

        report = harness.verify(self.root)
        self.assertFalse(report.ok)
        self.assertIn("DERIVED_DRIFT", {issue.code for issue in report.issues})
        self.assertTrue(all(
            issue.recoverable
            for issue in report.issues
            if issue.code == "DERIVED_DRIFT"
        ))

        dry_run = harness.recover(self.root, apply=False)
        self.assertEqual("dry-run", dry_run.mode)
        self.assertEqual(before, _tree_snapshot(self.root))

        applied = harness.recover(self.root, apply=True)
        self.assertEqual("applied", applied.mode)
        self.assertTrue(harness.verify(self.root).ok)
        self.assertIn("child-alpha", index.read_text(encoding="utf-8"))

    def test_recovery_recreates_missing_generated_file(self) -> None:
        shared = self.root / harness.SHARED_PATH
        shared.unlink()

        report = harness.verify(self.root)
        self.assertIn("FILE_MISSING", {issue.code for issue in report.issues})
        harness.recover(self.root, apply=True)

        self.assertTrue(shared.is_file())
        self.assertTrue(harness.verify(self.root).ok)

    def test_recovery_canonicalizes_valid_manifest_and_local_state(self) -> None:
        harness.record_local(
            self.root,
            child_id="alpha",
            key="local-001",
            kind="update",
            summary="Synthetic state.",
            next_action="Continue.",
            apply=True,
        )
        manifest_path = self.root / harness.MANIFEST_PATH
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        state_path = self.root / "child-alpha" / harness.LOCAL_STATE_PATH
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state_path.write_text(
            json.dumps(state, ensure_ascii=False),
            encoding="utf-8",
        )

        codes = {issue.code for issue in harness.verify(self.root).issues}
        self.assertTrue({"MANIFEST_DRIFT", "LOCAL_STATE_DRIFT"}.issubset(codes))
        harness.recover(self.root, apply=True)
        self.assertTrue(harness.verify(self.root).ok)

    def test_corrupt_manifest_fails_closed_and_is_not_overwritten(self) -> None:
        manifest = self.root / harness.MANIFEST_PATH
        manifest.write_text("{broken", encoding="utf-8")
        before = manifest.read_bytes()

        report = harness.verify(self.root)
        self.assertEqual("INVALID_JSON", report.issues[0].code)
        with self.assertRaisesRegex(harness.HarnessError, "not valid JSON"):
            harness.recover(self.root, apply=True)

        self.assertEqual(before, manifest.read_bytes())

    def test_invalid_utf8_manifest_is_reported_without_write(self) -> None:
        manifest = self.root / harness.MANIFEST_PATH
        manifest.write_bytes(bytes((0xFF,)))
        before = manifest.read_bytes()

        report = harness.verify(self.root)

        self.assertEqual("INVALID_UTF8", report.issues[0].code)
        self.assertEqual(before, manifest.read_bytes())

    def test_boolean_schema_version_is_rejected(self) -> None:
        manifest_path = self.root / harness.MANIFEST_PATH
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schemaVersion"] = True
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )

        report = harness.verify(self.root)

        self.assertEqual("INVALID_SCHEMA", report.issues[0].code)

    def test_non_string_record_kind_is_reported_without_crash(self) -> None:
        state_path = self.root / "child-alpha" / harness.LOCAL_STATE_PATH
        state_path.parent.mkdir()
        state_path.write_text(
            json.dumps(
                {
                    "childId": "alpha",
                    "records": [
                        {
                            "key": "local-001",
                            "kind": [],
                            "next": "",
                            "summary": "Synthetic state.",
                        }
                    ],
                    "schemaVersion": 1,
                    "tool": "workspace-coordination",
                }
            ),
            encoding="utf-8",
        )

        report = harness.verify(self.root)

        self.assertEqual("INVALID_SCHEMA", report.issues[0].code)

    def test_recover_refuses_missing_registered_child_before_writing(self) -> None:
        missing = self.root / "child-alpha-missing"
        (self.root / "child-alpha").rename(missing)
        index = self.root / harness.INDEX_PATH
        index.write_text("synthetic drift\n", encoding="utf-8")
        before = _tree_snapshot(self.root)

        with self.assertRaisesRegex(harness.HarnessError, "does not exist"):
            harness.recover(self.root, apply=True)

        self.assertEqual(before, _tree_snapshot(self.root))

    def test_managed_json_size_limit_fails_before_a_write_plan(self) -> None:
        with self.assertRaisesRegex(harness.HarnessError, "size limit"):
            harness._json_bytes({"value": "x" * harness.MAX_MANAGED_BYTES})

    def test_atomic_multi_file_failure_rolls_back(self) -> None:
        resolved_root = harness._root_path(self.root)
        workspace, manifest_raw, derived_raw = harness._operable_workspace(
            resolved_root
        )
        updated = harness._normalize_workspace(
            {
                **workspace,
                "sharedDeltas": [
                    {
                        "child": "alpha",
                        "key": "shared-001",
                        "summary": "Synthetic rollback boundary.",
                    }
                ],
            }
        )
        manifest_target = resolved_root / harness.MANIFEST_PATH
        shared_target = resolved_root / harness.SHARED_PATH
        plan = harness._WritePlan(
            root=resolved_root,
            action="synthetic-rollback",
            writes={
                manifest_target: harness._json_bytes(updated),
                shared_target: harness._render_shared(updated),
            },
            expected={
                manifest_target: manifest_raw,
                shared_target: derived_raw[shared_target],
            },
        )
        before = _tree_snapshot(self.root)
        real_replace = os.replace
        calls = 0

        def fail_second(source: os.PathLike[str], target: os.PathLike[str]) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic injected failure")
            real_replace(source, target)

        with self.assertRaisesRegex(harness.HarnessError, "rolled back"):
            harness._commit_writes(plan, replace=fail_second)

        self.assertEqual(before, _tree_snapshot(self.root))
        self.assertTrue(harness.verify(self.root).ok)


class CliTests(CoordinatorTestCase):
    def _run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = harness.run_cli(arguments)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_cli_rejects_parent_symlink_and_accepts_physical_root(self) -> None:
        physical_parent = self.root.parent / "physical-parent"
        physical_root = physical_parent / "selected-root"
        shutil.copytree(FIXTURE_ROOT, physical_root)
        alias_parent = self.root.parent / "alias-parent"
        os.symlink(physical_parent.name, alias_parent)
        linked_root = alias_parent / physical_root.name
        before = _tree_snapshot(physical_root)

        for arguments in (
            ["--root", str(linked_root), "init", "--dry-run"],
            ["--root", str(linked_root), "init", "--apply"],
        ):
            exit_code, _stdout, stderr = self._run_cli(arguments)
            self.assertEqual(1, exit_code)
            self.assertIn("ROOT_SYMLINK", stderr)
            self.assertEqual(before, _tree_snapshot(physical_root))

        dry_exit, _stdout, dry_stderr = self._run_cli(
            ["--root", str(physical_root), "init", "--dry-run"]
        )
        self.assertEqual(0, dry_exit, dry_stderr)
        self.assertEqual(before, _tree_snapshot(physical_root))

        apply_exit, _stdout, apply_stderr = self._run_cli(
            ["--root", str(physical_root), "init", "--apply"]
        )
        verify_exit, _stdout, verify_stderr = self._run_cli(
            ["--root", str(physical_root), "verify"]
        )
        self.assertEqual(0, apply_exit, apply_stderr)
        self.assertEqual(0, verify_exit, verify_stderr)

    def test_json_cli_cycle_and_explicit_mode(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = harness.run_cli(
                [
                    "--root",
                    str(self.root),
                    "--json",
                    "init",
                    "--apply",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertTrue(payload["ok"])
        self.assertEqual("applied", payload["mode"])

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as context:
                harness.run_cli(
                    [
                        "--root",
                        str(self.root),
                        "recover",
                    ]
                )
        self.assertEqual(2, context.exception.code)

    def test_verify_cli_uses_nonzero_for_drift(self) -> None:
        self.initialize()
        (self.root / harness.INDEX_PATH).write_text(
            "synthetic drift\n",
            encoding="utf-8",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = harness.run_cli(
                [
                    "--root",
                    str(self.root),
                    "--json",
                    "verify",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
