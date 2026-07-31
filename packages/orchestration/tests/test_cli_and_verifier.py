"""CLI exit behavior and package-local verifier tests."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import _bootstrap

from helpers import snapshot
from orchestration_harness.cli import main
from orchestration_harness.verifier import verify_package


class CliTests(unittest.TestCase):
    def _run(self, arguments: list[str]) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(arguments)
        return code, json.loads(output.getvalue())

    def test_cli_init_sync_and_error_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = ["--root", str(root), "--json"]
            code, opening = self._run([*prefix, "bom-dia"])
            self.assertEqual(0, code)
            self.assertEqual("uninitialized", opening["status"])

            code, preview = self._run(
                [
                    *prefix,
                    "init",
                    "--id",
                    "sample-front",
                    "--name",
                    "Sample Front",
                    "--path",
                    "fronts/sample-front",
                    "--dry-run",
                ]
            )
            self.assertEqual(0, code)
            self.assertTrue(preview["changed"])

            code, applied = self._run(
                [
                    *prefix,
                    "init",
                    "--id",
                    "sample-front",
                    "--name",
                    "Sample Front",
                    "--path",
                    "fronts/sample-front",
                    "--apply",
                ]
            )
            self.assertEqual(0, code)
            self.assertTrue(applied["changed"])

            code, sync = self._run([*prefix, "hq-sync"])
            self.assertEqual(0, code)
            self.assertTrue(sync["clean"])

            code, error = self._run([*prefix, "registra"])
            self.assertEqual(2, code)
            self.assertEqual("StateError", error["error"])

    def test_inconsistent_sync_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, result = self._run(["--root", str(root), "--json", "hq-sync"])
            self.assertEqual(1, code)
            self.assertFalse(result["clean"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_parent_symlink_root_is_rejected_by_open_and_init_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(strict=True)
            physical_parent = base / "physical-parent"
            physical_root = physical_parent / "workspace"
            physical_root.mkdir(parents=True)
            linked_parent = base / "linked-parent"
            linked_parent.symlink_to(physical_parent, target_is_directory=True)
            linked_root = linked_parent / "workspace"
            before = snapshot(physical_root)

            init_arguments = [
                "init",
                "--id",
                "sample-front",
                "--name",
                "Sample Front",
                "--path",
                "fronts/sample-front",
            ]
            commands = (
                ["bom-dia"],
                [*init_arguments, "--dry-run"],
                [*init_arguments, "--apply"],
            )
            for command in commands:
                with self.subTest(command=command):
                    code, result = self._run(
                        ["--root", str(linked_root), "--json", *command]
                    )
                    self.assertEqual(2, code)
                    self.assertEqual("ValidationError", result["error"])
                    self.assertEqual(before, snapshot(physical_root))

            code, opening = self._run(
                ["--root", str(physical_root), "--json", "bom-dia"]
            )
            self.assertEqual(0, code)
            self.assertEqual("uninitialized", opening["status"])
            self.assertEqual(before, snapshot(physical_root))

            code, preview = self._run(
                [
                    "--root",
                    str(physical_root),
                    "--json",
                    *init_arguments,
                    "--dry-run",
                ]
            )
            self.assertEqual(0, code)
            self.assertTrue(preview["changed"])
            self.assertEqual(before, snapshot(physical_root))

            code, applied = self._run(
                [
                    "--root",
                    str(physical_root),
                    "--json",
                    *init_arguments,
                    "--apply",
                ]
            )
            self.assertEqual(0, code)
            self.assertTrue(applied["changed"])


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package_root = Path(__file__).resolve().parents[1]

    def test_checked_in_package_passes(self) -> None:
        self.assertEqual([], verify_package(self.package_root))

    def test_manifest_corruption_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "orchestration"
            shutil.copytree(self.package_root, copy)
            manifest_path = copy / "harness.package.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "contract-only"
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertIn("MANIFEST:contract", verify_package(copy))

    def test_skill_frontmatter_corruption_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "orchestration"
            shutil.copytree(self.package_root, copy)
            (copy / "SKILL.md").write_text(
                "# Missing frontmatter\n",
                encoding="utf-8",
            )
            self.assertIn("SKILL:frontmatter", verify_package(copy))
