#!/usr/bin/env python3
"""Automated tests for Multi-Project Harness."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts" / "cross_project.py"
SPEC = importlib.util.spec_from_file_location("cross_project", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CrossProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve(strict=True)
        (self.root / "projects" / "alpha").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *arguments: str, expected: int = 0) -> dict[str, object]:
        result = self.run_process(*arguments)
        self.assertEqual(result.returncode, expected, result.stderr)
        if not result.stdout:
            return {}
        return json.loads(result.stdout)

    def run_process(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def init_arguments(self, root: Path | None = None) -> tuple[str, ...]:
        selected_root = self.root if root is None else root
        return (
            "hq-init",
            "--root",
            str(selected_root),
            "--front",
            "alpha",
            "--name",
            "Alpha",
            "--path",
            "projects/alpha",
            "--role",
            "Produces a shared component",
            "--next",
            "Build the first slice",
        )

    def digest(self) -> str:
        hasher = hashlib.sha256()
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                hasher.update(path.relative_to(self.root).as_posix().encode())
                hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def physical_snapshot(self, root: Path) -> tuple[tuple[object, ...], ...]:
        paths = [root, *root.rglob("*")]
        paths.sort(
            key=lambda path: (
                path != root,
                "" if path == root else path.relative_to(root).as_posix(),
            )
        )
        snapshot: list[tuple[object, ...]] = []
        for path in paths:
            metadata = path.lstat()
            relative = "." if path == root else path.relative_to(root).as_posix()
            if stat.S_ISREG(metadata.st_mode):
                payload: bytes | str = path.read_bytes()
            elif stat.S_ISLNK(metadata.st_mode):
                payload = os.readlink(path)
            else:
                payload = b""
            snapshot.append(
                (
                    relative,
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_mode,
                    metadata.st_nlink,
                    metadata.st_uid,
                    metadata.st_gid,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                    payload,
                )
            )
        return tuple(snapshot)

    def test_complete_first_cycle(self) -> None:
        opening = self.run_cli("bom-dia", "--root", str(self.root))
        self.assertFalse(opening["initialized"])
        preview = self.run_cli(*self.init_arguments(), "--dry-run")
        self.assertTrue(preview["dryRun"])
        self.assertFalse((self.root / MODULE.CONFIG_NAME).exists())
        self.run_cli(*self.init_arguments())
        sync = self.run_cli("hq-sync", "--root", str(self.root))
        self.assertTrue(sync["consistent"])
        digest = self.run_cli(
            "digere",
            "--root",
            str(self.root),
            "--front",
            "alpha",
            "--scope",
            "coordination",
        )
        self.assertEqual(digest["owner"], MODULE.CONFIG_NAME)
        checkpoint = self.run_cli(
            "registra",
            "--root",
            str(self.root),
            "--front",
            "alpha",
            "--state",
            "active",
            "--next",
            "Validate the slice",
        )
        self.assertTrue(checkpoint["coordinationPending"])
        self.run_cli(
            "encerra",
            "--root",
            str(self.root),
            "--front",
            "alpha",
            "--role",
            "Produces a shared component",
            "--state",
            "ready",
            "--next",
            "Hand off the component",
            "--summary",
            "First slice validated",
            "--reflect-when",
            "The shared interface changes",
        )
        final = self.run_cli(
            "bom-dia", "--root", str(self.root), "--front", "alpha"
        )
        self.assertFalse(final["pending"])
        self.assertEqual(final["next"], "Hand off the component")
        self.assertTrue(
            self.run_cli("hq-sync", "--root", str(self.root))["consistent"]
        )

    def test_legacy_contained_relative_project_root_remains_supported(self) -> None:
        self.run_cli(*self.init_arguments())
        state = json.loads(
            (self.root / MODULE.CONFIG_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(state["fronts"]["alpha"]["path"], "projects/alpha")
        self.assertTrue(
            self.run_cli("hq-sync", "--root", str(self.root))["consistent"]
        )

    def test_independent_sibling_project_roots_sync_without_project_writes(self) -> None:
        portfolio = self.root / "portfolio"
        coordination = portfolio / "coordination"
        alpha = portfolio / "alpha-service"
        beta = portfolio / "beta-client"
        for project, marker in ((alpha, b"alpha\n"), (beta, b"beta\n")):
            project.mkdir(parents=True)
            (project / "README.md").write_bytes(marker)
        coordination.mkdir()

        project_snapshots = {
            alpha: self.physical_snapshot(alpha),
            beta: self.physical_snapshot(beta),
        }
        coordination_before = self.physical_snapshot(coordination)
        alpha_arguments = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "alpha",
            "--name",
            "Alpha service",
            "--path",
            str(alpha),
            "--role",
            "Produces the service API",
            "--next",
            "Publish the confirmed contract",
        )
        beta_arguments = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "beta",
            "--name",
            "Beta client",
            "--path",
            str(beta),
            "--role",
            "Consumes the service API",
            "--next",
            "Validate the handoff",
        )

        preview = self.run_cli(*alpha_arguments, "--dry-run")
        self.assertTrue(preview["dryRun"])
        self.assertEqual(
            coordination_before,
            self.physical_snapshot(coordination),
        )
        self.run_cli(*alpha_arguments)
        self.run_cli(*beta_arguments)
        self.assertTrue(
            self.run_cli("hq-sync", "--root", str(coordination))["consistent"]
        )

        state = json.loads(
            (coordination / MODULE.CONFIG_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(state["fronts"]["alpha"]["path"], str(alpha))
        self.assertEqual(state["fronts"]["beta"]["path"], str(beta))
        for project, before in project_snapshots.items():
            self.assertEqual(before, self.physical_snapshot(project))

        coordination_after = self.physical_snapshot(coordination)
        repeated = self.run_cli(*alpha_arguments, "--dry-run")
        self.assertEqual(repeated["changed"], [])
        self.assertEqual(
            coordination_after,
            self.physical_snapshot(coordination),
        )
        for project, before in project_snapshots.items():
            self.assertEqual(before, self.physical_snapshot(project))

        for front_id, role, next_action, reflect_when in (
            (
                "alpha",
                "Produces the service API",
                "Publish the confirmed contract",
                "The API contract changes",
            ),
            (
                "beta",
                "Consumes the service API",
                "Validate the handoff",
                "The client contract changes",
            ),
        ):
            self.run_cli(
                "encerra",
                "--root",
                str(coordination),
                "--front",
                front_id,
                "--role",
                role,
                "--state",
                "ready",
                "--next",
                next_action,
                "--summary",
                "Confirmed project handoff",
                "--reflect-when",
                reflect_when,
            )
        fronts = (coordination / "FRONTS.md").read_text(encoding="utf-8")
        table, resumptions = fronts.split("\n\n## Resumption\n\n", maxsplit=1)
        self.assertIn("| alpha | Alpha service |", table)
        self.assertIn("| beta | Beta client |", table)
        self.assertNotIn("Resumption", table)
        self.assertIn("- `alpha` — Publish the confirmed contract", resumptions)
        self.assertIn("- `beta` — Validate the handoff", resumptions)
        self.assertTrue(
            self.run_cli("hq-sync", "--root", str(coordination))["consistent"]
        )
        for project, before in project_snapshots.items():
            self.assertEqual(before, self.physical_snapshot(project))

    def test_absolute_project_root_cannot_be_owned_by_two_front_ids(self) -> None:
        portfolio = self.root / "absolute-alias"
        coordination = portfolio / "coordination"
        project = portfolio / "project"
        project.mkdir(parents=True)
        coordination.mkdir()
        first = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "first",
            "--name",
            "First",
            "--path",
            str(project),
            "--role",
            "Owns the project",
            "--next",
            "Continue",
        )
        self.run_cli(*first)
        coordination_before = self.physical_snapshot(coordination)
        project_before = self.physical_snapshot(project)
        second = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "second",
            "--name",
            "Second",
            "--path",
            str(project),
            "--role",
            "Must not alias the project",
            "--next",
            "Stop",
        )
        result = self.run_process(*second)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("already owns this path", result.stderr)
        self.assertEqual(coordination_before, self.physical_snapshot(coordination))
        self.assertEqual(project_before, self.physical_snapshot(project))

    def test_preview_and_read_only_commands_do_not_write(self) -> None:
        before = self.digest()
        self.run_cli(*self.init_arguments(), "--dry-run")
        self.assertEqual(before, self.digest())
        self.run_cli(*self.init_arguments())
        before = self.digest()
        self.run_cli("bom-dia", "--root", str(self.root))
        self.run_cli("hq-sync", "--root", str(self.root))
        self.run_cli(
            "digere",
            "--root",
            str(self.root),
            "--front",
            "alpha",
            "--scope",
            "ephemeral",
        )
        self.assertEqual(before, self.digest())

    def test_apply_is_idempotent_and_preserves_unmanaged_text(self) -> None:
        owner_text = "Owner notes \n \n"
        agents = self.root / "AGENTS.md"
        agents.write_text(owner_text, encoding="utf-8")
        agents.chmod(0o640)
        self.run_cli(*self.init_arguments())
        first = self.digest()
        result = self.run_cli(*self.init_arguments())
        self.assertEqual(result["changed"], [])
        self.assertEqual(first, self.digest())
        self.assertTrue(agents.read_text(encoding="utf-8").startswith(owner_text))
        if os.name == "posix":
            self.assertEqual(agents.stat().st_mode & 0o777, 0o640)
        else:
            self.assertTrue(stat.S_ISREG(agents.stat().st_mode))

    def test_id_and_path_collisions_are_rejected(self) -> None:
        self.run_cli(*self.init_arguments())
        self.run_cli(
            "hq-init",
            "--root",
            str(self.root),
            "--front",
            "beta",
            "--name",
            "Beta",
            "--path",
            "projects/alpha",
            "--role",
            "Consumes the component",
            "--next",
            "Integrate",
            expected=2,
        )
        (self.root / "projects" / "beta").mkdir()
        self.run_cli(
            "hq-init",
            "--root",
            str(self.root),
            "--front",
            "alpha",
            "--name",
            "Changed",
            "--path",
            "projects/beta",
            "--role",
            "Changed",
            "--next",
            "Changed",
            expected=2,
        )

    def test_case_alias_collision_is_rejected_when_filesystem_has_aliases(self) -> None:
        actual = self.root / "projects" / "CaseTarget"
        actual.mkdir()
        alias = self.root / "projects" / "casetarget"
        if not alias.exists() or not actual.samefile(alias):
            self.skipTest("filesystem is case-sensitive")
        first = list(self.init_arguments())
        first[first.index("alpha")] = "first"
        first[first.index("Alpha")] = "First"
        first[first.index("projects/alpha")] = "projects/CaseTarget"
        self.run_cli(*first)
        second = list(self.init_arguments())
        second[second.index("alpha")] = "second"
        second[second.index("Alpha")] = "Second"
        second[second.index("projects/alpha")] = "projects/casetarget"
        self.run_cli(*second, expected=2)

    def test_traversal_and_relative_symlink_paths_are_rejected(self) -> None:
        for child in (
            "../outside",
            "projects//alpha",
            "projects/./alpha",
            "projects/alpha/",
        ):
            arguments = list(self.init_arguments())
            arguments[arguments.index("projects/alpha")] = child
            self.run_cli(*arguments, expected=2)
        target = self.root / "projects" / "linked"
        try:
            target.symlink_to(self.root / "projects" / "alpha", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        arguments = list(self.init_arguments())
        arguments[arguments.index("projects/alpha")] = "projects/linked"
        self.run_cli(*arguments, expected=2)

    def test_unsafe_absolute_project_roots_fail_without_coordination_writes(self) -> None:
        portfolio = self.root / "unsafe-absolute"
        coordination = portfolio / "coordination"
        project = portfolio / "project"
        project.mkdir(parents=True)
        coordination.mkdir()
        regular_file = portfolio / "not-a-directory.txt"
        regular_file.write_text("not a root\n", encoding="utf-8")
        git_metadata = portfolio / ".git"
        git_metadata.mkdir()

        non_normalized = (
            os.fspath(project.parent)
            + os.sep
            + "."
            + os.sep
            + project.name
        )
        invalid = (
            non_normalized,
            os.fspath(project) + os.sep,
            os.fspath(Path(project.anchor)),
            str(Path.home()),
            str(portfolio / "missing"),
            str(regular_file),
            str(git_metadata),
            str(coordination),
        )
        before = self.physical_snapshot(coordination)
        project_before = self.physical_snapshot(project)
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                arguments = (
                    "hq-init",
                    "--root",
                    str(coordination),
                    "--front",
                    "unsafe",
                    "--name",
                    "Unsafe",
                    "--path",
                    candidate,
                    "--role",
                    "Must not be registered",
                    "--next",
                    "Stop",
                )
                result = self.run_process(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(before, self.physical_snapshot(coordination))
                self.assertEqual(project_before, self.physical_snapshot(project))
                self.assertFalse((coordination / MODULE.CONFIG_NAME).exists())
                self.assertFalse((coordination / MODULE.LOCK_NAME).exists())
                self.assertEqual([], list(coordination.glob(".cross-project-*")))

    def test_physical_home_alias_is_rejected_without_coordination_writes(self) -> None:
        home = Path.home().resolve(strict=True)
        candidates = [
            Path(os.sep).joinpath("System", "Volumes", "Data", *home.parts[1:]),
            home.with_name(home.name.swapcase()),
        ]
        alias = next(
            (
                candidate
                for candidate in candidates
                if candidate != home
                and candidate.is_dir()
                and candidate.samefile(home)
            ),
            None,
        )
        if alias is None:
            self.skipTest("no distinct link-free physical alias for the home directory")

        portfolio = self.root / "home-alias"
        coordination = portfolio / "coordination"
        coordination.mkdir(parents=True)
        before = self.physical_snapshot(coordination)
        arguments = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "unsafe-home",
            "--name",
            "Unsafe home",
            "--path",
            str(alias),
            "--role",
            "Must not be registered",
            "--next",
            "Stop",
        )
        result = self.run_process(*arguments)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("home directory must not be a project root", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(before, self.physical_snapshot(coordination))
        self.assertFalse((coordination / MODULE.CONFIG_NAME).exists())
        self.assertFalse((coordination / MODULE.LOCK_NAME).exists())
        self.assertEqual([], list(coordination.glob(".cross-project-*")))

    def test_absolute_project_root_link_is_rejected_without_writes(self) -> None:
        portfolio = self.root / "absolute-link"
        coordination = portfolio / "coordination"
        project = portfolio / "project"
        alias = portfolio / "project-alias"
        project.mkdir(parents=True)
        coordination.mkdir()
        try:
            alias.symlink_to(project, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")

        before = self.physical_snapshot(coordination)
        project_before = self.physical_snapshot(project)
        arguments = (
            "hq-init",
            "--root",
            str(coordination),
            "--front",
            "linked",
            "--name",
            "Linked",
            "--path",
            str(alias),
            "--role",
            "Must not be registered",
            "--next",
            "Stop",
        )
        result = self.run_process(*arguments)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("link-like", result.stderr)
        self.assertEqual(before, self.physical_snapshot(coordination))
        self.assertEqual(project_before, self.physical_snapshot(project))
        self.assertFalse((coordination / MODULE.CONFIG_NAME).exists())

    def test_git_and_dangerous_roots_are_rejected(self) -> None:
        git = self.root / ".git"
        git.mkdir()
        arguments = list(self.init_arguments())
        arguments[arguments.index("projects/alpha")] = ".git"
        self.run_cli(*arguments, expected=2)
        git_child = git / "child"
        git_child.mkdir()
        arguments[arguments.index(str(self.root))] = str(git)
        arguments[arguments.index(".git")] = "child"
        self.run_cli(*arguments, expected=2)
        with self.assertRaises(MODULE.HarnessError):
            MODULE._root(Path("/").anchor)
        with self.assertRaises(MODULE.HarnessError):
            MODULE._root(str(Path.home()))

    def test_intermediate_root_link_is_rejected_without_physical_writes(self) -> None:
        physical_parent = self.root / "physical-parent"
        physical_root = physical_parent / "coordination"
        (physical_root / "projects" / "alpha").mkdir(parents=True)
        physical_root = physical_root.resolve(strict=True)
        alias_parent = self.root / "alias-parent"
        try:
            alias_parent.symlink_to(physical_parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        alias_root = alias_parent / "coordination"
        self.assertFalse(alias_root.is_symlink())
        self.assertTrue(alias_parent.is_symlink())
        self.assertTrue(alias_root.samefile(physical_root))

        before = self.physical_snapshot(physical_root)
        commands = (
            ("bom-dia", "--root", str(alias_root)),
            (*self.init_arguments(alias_root), "--dry-run"),
            self.init_arguments(alias_root),
        )
        for arguments in commands:
            with self.subTest(command=arguments[0]):
                result = self.run_process(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("link-like", result.stderr)
                self.assertEqual(before, self.physical_snapshot(physical_root))
                self.assertFalse((physical_root / MODULE.CONFIG_NAME).exists())
                self.assertFalse((physical_root / MODULE.LOCK_NAME).exists())
                self.assertEqual(
                    [],
                    list(physical_root.glob(".cross-project-*")),
                )

        preview_before = self.physical_snapshot(physical_root)
        preview = self.run_cli(
            *self.init_arguments(physical_root),
            "--dry-run",
        )
        self.assertTrue(preview["dryRun"])
        self.assertEqual(preview_before, self.physical_snapshot(physical_root))
        self.run_cli(*self.init_arguments(physical_root))
        self.assertTrue(
            self.run_cli("hq-sync", "--root", str(physical_root))["consistent"]
        )

    def test_link_like_metadata_recognizes_reparse_flag(self) -> None:
        reparse_flag = 0x400
        reported_reparse = mock.Mock(
            st_mode=stat.S_IFDIR,
            st_file_attributes=reparse_flag,
        )
        ordinary_directory = mock.Mock(
            st_mode=stat.S_IFDIR,
            st_file_attributes=0,
        )
        with mock.patch.object(
            MODULE.stat,
            "FILE_ATTRIBUTE_REPARSE_POINT",
            reparse_flag,
            create=True,
        ):
            self.assertTrue(MODULE._metadata_is_link_like(reported_reparse))
            self.assertFalse(MODULE._metadata_is_link_like(ordinary_directory))

    def test_malformed_managed_markers_are_rejected_without_change(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(f"{MODULE.START}\nmissing end\n", encoding="utf-8")
        before = agents.read_bytes()
        self.run_cli(*self.init_arguments(), expected=2)
        self.assertEqual(before, agents.read_bytes())
        self.assertFalse((self.root / MODULE.CONFIG_NAME).exists())

    def test_reversed_markers_are_a_controlled_error(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(
            f"{MODULE.END}\nowner text\n{MODULE.START}\n",
            encoding="utf-8",
        )
        result = self.run_process(*self.init_arguments())
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("out of order", result.stderr)
        self.assertFalse((self.root / MODULE.CONFIG_NAME).exists())

    def test_manifest_parser_rejects_ambiguous_or_pathological_json(self) -> None:
        config = self.root / MODULE.CONFIG_NAME
        documents = (
            b'{"schemaVersion":true,"harness":"cross-project",'
            b'"master":{"name":"Root"},"fronts":{}}',
            b'{"schemaVersion":1.0,"harness":"cross-project",'
            b'"master":{"name":"Root"},"fronts":{}}',
            b'{"schemaVersion":999,"schemaVersion":1,"harness":"cross-project",'
            b'"master":{"name":"Root"},"fronts":{}}',
            ("[" * 1_100 + "0" + "]" * 1_100).encode(),
            ('{"schemaVersion":' + "9" * 5_000 + "}").encode(),
        )
        for document in documents:
            with self.subTest(prefix=document[:30]):
                config.write_bytes(document)
                result = self.run_process("bom-dia", "--root", str(self.root))
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_manifest_schema_rejects_unsafe_path_and_incomplete_reflection(self) -> None:
        front = {
            "name": "Alpha",
            "path": "../outside",
            "role": "Produces a component",
            "state": "ready",
            "next": "Hand off",
            "blocker": "",
            "coordinationPending": False,
            "lastReflection": "",
            "reflectWhen": "",
        }
        state = {
            "schemaVersion": MODULE.SCHEMA_VERSION,
            "harness": MODULE.HARNESS_ID,
            "master": {"name": "Root"},
            "fronts": {"alpha": front},
        }
        with self.assertRaises(MODULE.HarnessError):
            MODULE._validate_state(state)
        front["path"] = "projects/alpha"
        with self.assertRaises(MODULE.HarnessError):
            MODULE._validate_state(state)

    def test_transaction_rolls_back_all_applied_files(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text("Owner notes\n", encoding="utf-8")
        agents.chmod(0o640)
        state = {
            "schemaVersion": MODULE.SCHEMA_VERSION,
            "harness": MODULE.HARNESS_ID,
            "master": {"name": "Synthetic root"},
            "fronts": {},
        }
        rendered = MODULE._render(self.root, state)
        original_replace = MODULE._replace
        calls = 0

        def fail_second(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic failure")
            original_replace(source, target)

        with mock.patch.object(MODULE, "_replace", side_effect=fail_second):
            with self.assertRaises(MODULE.HarnessError):
                MODULE._apply(self.root, rendered)
        for name in (*MODULE.MANAGED_FILES, MODULE.CONFIG_NAME):
            if name == "AGENTS.md":
                self.assertEqual(agents.read_text(encoding="utf-8"), "Owner notes\n")
                if os.name == "posix":
                    self.assertEqual(agents.stat().st_mode & 0o777, 0o640)
                else:
                    self.assertTrue(stat.S_ISREG(agents.stat().st_mode))
            else:
                self.assertFalse((self.root / name).exists())
        self.assertFalse((self.root / MODULE.LOCK_NAME).exists())

    def test_manifest_is_staged_as_transaction_commit_marker(self) -> None:
        state = {
            "schemaVersion": MODULE.SCHEMA_VERSION,
            "harness": MODULE.HARNESS_ID,
            "master": {"name": "Synthetic root"},
            "fronts": {},
        }
        rendered = MODULE._render(self.root, state)
        self.assertEqual(list(rendered)[-1].name, MODULE.CONFIG_NAME)

    def test_optimistic_guard_rejects_stale_managed_state(self) -> None:
        captured = MODULE._capture_managed(self.root)
        state = {
            "schemaVersion": MODULE.SCHEMA_VERSION,
            "harness": MODULE.HARNESS_ID,
            "master": {"name": "Synthetic root"},
            "fronts": {},
        }
        rendered = MODULE._render(self.root, state)
        agents = self.root / "AGENTS.md"
        agents.write_text("Owner changed this concurrently.\n", encoding="utf-8")
        with self.assertRaises(MODULE.HarnessError):
            MODULE._apply(self.root, rendered, expected=captured)
        self.assertEqual(
            agents.read_text(encoding="utf-8"), "Owner changed this concurrently.\n"
        )
        self.assertFalse((self.root / MODULE.CONFIG_NAME).exists())

    def test_sync_reports_divergence_without_repair(self) -> None:
        self.run_cli(*self.init_arguments())
        fronts = self.root / "FRONTS.md"
        fronts.write_text(
            fronts.read_text(encoding="utf-8").replace("# Fronts", "# Altered"),
            encoding="utf-8",
        )
        before = fronts.read_bytes()
        result = self.run_cli(
            "hq-sync", "--root", str(self.root), expected=1
        )
        self.assertFalse(result["consistent"])
        self.assertEqual(before, fronts.read_bytes())

    def test_read_only_commands_do_not_scan_git_or_unmanaged_files(self) -> None:
        self.run_cli(*self.init_arguments())
        (self.root / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        (self.root / "private.bin").write_bytes(b"unmanaged")
        original = Path.read_bytes
        touched: list[str] = []

        def observed(path: Path) -> bytes:
            touched.append(path.name)
            return original(path)

        with mock.patch.object(Path, "read_bytes", observed):
            MODULE._snapshot(self.root)
        self.assertNotIn(".git", touched)
        self.assertNotIn("private.bin", touched)

    def test_lock_blocks_readers_without_changing_managed_state(self) -> None:
        self.run_cli(*self.init_arguments())
        before = self.digest()
        (self.root / MODULE.LOCK_NAME).mkdir()
        for arguments in (
            ("bom-dia", "--root", str(self.root)),
            ("hq-sync", "--root", str(self.root)),
            (
                "digere",
                "--root",
                str(self.root),
                "--front",
                "alpha",
                "--scope",
                "local",
            ),
        ):
            result = self.run_process(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
        (self.root / MODULE.LOCK_NAME).rmdir()
        self.assertEqual(before, self.digest())

    def test_named_target_is_revalidated_after_symlink_replacement(self) -> None:
        self.run_cli(*self.init_arguments())
        child = self.root / "projects" / "alpha"
        child.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            child.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        before = (self.root / MODULE.CONFIG_NAME).read_bytes()
        commands = (
            ("bom-dia", "--root", str(self.root), "--front", "alpha"),
            (
                "digere",
                "--root",
                str(self.root),
                "--front",
                "alpha",
                "--scope",
                "local",
            ),
            (
                "registra",
                "--root",
                str(self.root),
                "--front",
                "alpha",
                "--state",
                "active",
                "--next",
                "Continue",
            ),
        )
        for arguments in commands:
            self.run_cli(*arguments, expected=2)
        self.assertEqual(before, (self.root / MODULE.CONFIG_NAME).read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
