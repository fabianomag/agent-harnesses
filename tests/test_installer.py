"""Black-box and safety tests for the standalone v0.2.0 installer."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import installer
from tools import build_product, product


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _snapshot(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    entries: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*")):
        kind = "directory" if path.is_dir() else "file"
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        entries.append((path.relative_to(root).as_posix(), kind, path.stat().st_mtime_ns, digest))
    return tuple(entries)


def _run(target: Path, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    environment = os.environ.copy()
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    process = subprocess.run(
        [sys.executable, "-B", str(REPOSITORY_ROOT / "installer.py"), *arguments, "--target", str(target), "--json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return process, json.loads(process.stdout)


class ProductContractTests(unittest.TestCase):
    def test_installer_is_generated_from_the_canonical_product(self) -> None:
        self.assertEqual([], build_product.check(REPOSITORY_ROOT))
        value = product.load_product(REPOSITORY_ROOT)
        self.assertEqual("v0.2.0", value["release"]["tag"])
        self.assertEqual(
            ["Project Harness", "Workspace Harness", "Multi-Project Harness", "Control Plane Harness"],
            [entry["displayName"] for entry in value["packages"]],
        )
        self.assertEqual(value, installer.PRODUCT)

    def test_each_prompt_names_one_exact_asset(self) -> None:
        value = product.load_product(REPOSITORY_ROOT)
        for selected in value["packages"]:
            prompt = product.install_prompt(value, selected, "en")
            self.assertEqual(1, prompt.count(".zip"))
            self.assertIn(selected["id"], prompt)
            self.assertIn(selected["asset"], prompt)
            for other in value["packages"]:
                if other is not selected:
                    self.assertNotIn(other["asset"], prompt)

    def test_prompts_forbid_private_codex_runtime_and_require_ready(self) -> None:
        value = product.load_product(REPOSITORY_ROOT)
        for definition in value["packages"]:
            for language in ("en", "ptBr"):
                prompt = product.install_prompt(value, definition, language)
                self.assertIn("private Codex runtime" if language == "en" else "runtime privado do Codex", prompt)
                self.assertIn("ready=true", prompt)
                self.assertIn("`package/README.md`", prompt)
                self.assertIn("`<python>`", prompt)
                self.assertIn("`python3`", prompt)
                self.assertIn("`python`", prompt)
                self.assertIn("`py -3`", prompt)
                commands = (
                    f'<python> -B installer.py doctor {definition["id"]} --target "<target>" --json',
                    f'<python> -B installer.py install {definition["id"]} --target "<target>" --dry-run --json',
                    f'<python> -B installer.py install {definition["id"]} --target "<target>" --apply --json',
                    f'<python> -B installer.py verify {definition["id"]} --target "<target>" --json',
                )
                for command in commands:
                    self.assertEqual(1, prompt.count(command))
                for other in value["packages"]:
                    if other["id"] != definition["id"]:
                        self.assertNotIn(other["id"], prompt)

    def test_public_instructions_name_the_real_bundle_readme(self) -> None:
        for relative in ("README.md", "README.pt-BR.md", "INSTALL_FROM_RELEASE.md"):
            text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("`package/README.md`", text)

    def test_public_commands_reuse_python_placeholder_and_quote_paths(self) -> None:
        relatives = [
            Path("README.md"),
            Path("README.pt-BR.md"),
            Path("INSTALL_FROM_RELEASE.md"),
            Path("docs/REFERENCE.md"),
        ]
        for definition in product.load_product(REPOSITORY_ROOT)["packages"]:
            package_root = Path("packages") / definition["id"]
            relatives.extend(
                (
                    package_root / "README.md",
                    package_root / "README.pt-BR.md",
                    package_root / "docs/REFERENCE.md",
                )
            )
        for relative in relatives:
            with self.subTest(relative=relative.as_posix()):
                text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("python3 -B", text)
                self.assertNotIn("--target <", text)
                self.assertNotIn("--root <", text)
                self.assertIn("<python>", text)


class InstallerSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary.name).resolve(strict=True) / "target"
        self.target.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_doctor_is_zero_write(self) -> None:
        marker = self.target / "existing.txt"
        marker.write_text("synthetic", encoding="utf-8")
        before = _snapshot(self.target)

        process, result = _run(self.target, "doctor", "project")

        self.assertEqual(0, process.returncode)
        self.assertEqual("OK", result["code"])
        self.assertFalse(result["ready"])
        self.assertEqual(before, _snapshot(self.target))

    def test_doctor_rejects_linked_marker_parent_without_writes(self) -> None:
        external = Path(self.temporary.name) / "external-project-state"
        external.mkdir()
        (external / "state.json").write_text("{}\n", encoding="utf-8")
        marker_parent = self.target / ".project-harness"
        try:
            marker_parent.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks are unavailable")
        before_target = os.lstat(marker_parent)
        before_external = _snapshot(external)

        process, result = _run(self.target, "doctor", "project")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_INITIALIZATION_CONFLICT", result["code"])
        self.assertEqual(before_target, os.lstat(marker_parent))
        self.assertEqual(before_external, _snapshot(external))

    def test_doctor_rejects_obvious_managed_path_type_collisions(self) -> None:
        cases = (
            ("project", ".project-harness"),
            ("workspace", ".workspace-coordination"),
            ("cross-project", "AGENTS.md"),
        )
        for selector, relative in cases:
            with self.subTest(selector=selector, relative=relative):
                collision = self.target / relative
                collision.parent.mkdir(parents=True, exist_ok=True)
                if collision.name.startswith("."):
                    collision.write_text("conflict\n", encoding="utf-8")
                else:
                    collision.mkdir()
                before = _snapshot(self.target)

                process, result = _run(self.target, "doctor", selector)

                self.assertEqual(2, process.returncode)
                self.assertEqual("E_INITIALIZATION_CONFLICT", result["code"])
                self.assertEqual(before, _snapshot(self.target))
                if collision.is_dir():
                    collision.rmdir()
                else:
                    collision.unlink()

    def test_doctor_rejects_changed_preexisting_runtime_without_writes(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        readme = self.target / ".agent-harnesses/runtime/project-harness/0.2.0/README.md"
        readme.write_text("changed\n", encoding="utf-8")
        before = _snapshot(self.target)

        process, result = _run(self.target, "doctor", "project")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual(before, _snapshot(self.target))

    def test_control_plane_refuses_existing_master_like_target_without_writes(self) -> None:
        (self.target / "AGENTS.md").write_text("# Existing owner\n", encoding="utf-8")
        (self.target / "projects" / "alpha").mkdir(parents=True)
        before = _snapshot(self.target)

        process, result = _run(self.target, "doctor", "control-plane")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_HARNESS_MISMATCH", result["code"])
        self.assertIn("Multi-Project Harness", result["remediation"])
        self.assertIn("cross-project", result["remediation"])
        self.assertEqual(before, _snapshot(self.target))

    def test_control_plane_apply_refuses_existing_workspace_before_any_write(self) -> None:
        (self.target / "AGENTS.md").write_text("# Existing owner\n", encoding="utf-8")
        (self.target / "ARCHITECTURE.md").write_text("# Existing architecture\n", encoding="utf-8")
        (self.target / "projects" / "alpha").mkdir(parents=True)
        before = _snapshot(self.target)

        process, result = _run(self.target, "install", "control-plane", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_HARNESS_MISMATCH", result["code"])
        self.assertIn("cross-project", result["remediation"])
        self.assertEqual(before, _snapshot(self.target))
        self.assertFalse((self.target / ".agent-harnesses").exists())

    def test_install_dry_run_validates_inventory_and_writes_nothing_to_target(self) -> None:
        before = _snapshot(self.target)

        process, result = _run(self.target, "install", "project", "--dry-run")

        self.assertEqual(0, process.returncode)
        self.assertEqual("downloaded", result["phase"])
        self.assertIn("inventory is verified", result["message"])
        self.assertEqual(before, _snapshot(self.target))

    def test_installed_but_uninitialized_is_not_ready(self) -> None:
        installed, installed_result = _run(self.target, "install", "project", "--apply")
        verified, verified_result = _run(self.target, "verify", "project")

        self.assertEqual(0, installed.returncode)
        self.assertEqual("installed", installed_result["phase"])
        self.assertFalse(installed_result["ready"])
        self.assertEqual(2, verified.returncode)
        self.assertEqual("E_NOT_READY", verified_result["code"])
        self.assertEqual("installed", verified_result["phase"])
        self.assertFalse(verified_result["ready"])

    def test_install_preserves_unrelated_documentation_and_confines_receipt(self) -> None:
        documentation = {
            "AGENTS.md": b"# Existing agent instructions\n",
            "ARCHITECTURE.md": b"# Existing architecture\n",
            "docs/decisions.md": b"# Existing decisions\n",
        }
        for relative, content in documentation.items():
            path = self.target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        process, result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertEqual("installed", result["phase"])
        for relative, content in documentation.items():
            self.assertEqual(content, (self.target / relative).read_bytes())
        receipts = list(self.target.rglob(installer.RECEIPT_NAME))
        self.assertEqual(1, len(receipts))
        self.assertTrue(
            receipts[0].is_relative_to(
                self.target / ".agent-harnesses/runtime/project-harness/0.2.0"
            )
        )

    def test_repeated_exact_install_is_a_zero_write_noop(self) -> None:
        first, first_result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, first.returncode)
        self.assertEqual("installed", first_result["phase"])
        before = _snapshot(self.target)

        second, second_result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(0, second.returncode)
        self.assertIn("unchanged", second_result["message"])
        self.assertEqual(before, _snapshot(self.target))

    def test_concurrent_exact_installs_converge_without_residue(self) -> None:
        environment = os.environ.copy()
        environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        command = [
            sys.executable,
            "-B",
            str(REPOSITORY_ROOT / "installer.py"),
            "install",
            "project",
            "--target",
            str(self.target),
            "--apply",
            "--json",
        ]
        attempts = [
            subprocess.Popen(
                command,
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _index in range(3)
        ]
        completed = [attempt.communicate(timeout=30) for attempt in attempts]

        for attempt, (stdout, stderr) in zip(attempts, completed):
            self.assertEqual(0, attempt.returncode, stdout + stderr)
            self.assertEqual("OK", json.loads(stdout)["code"])
        destination = self.target / ".agent-harnesses/runtime/project-harness/0.2.0"
        installer._verify_runtime_files(destination, "project-harness")
        runtime_root = self.target / ".agent-harnesses/runtime"
        self.assertEqual([], list(runtime_root.glob(".install-*")))

    def test_ready_requires_operational_runtime_verification(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        runtime = self.target / ".agent-harnesses/runtime/project-harness/0.2.0/project_harness.py"
        subprocess.run(
            [sys.executable, "-B", str(runtime), "init", "--root", str(self.target)],
            check=True,
            capture_output=True,
        )

        verified, result = _run(self.target, "verify", "project")

        self.assertEqual(0, verified.returncode)
        self.assertEqual("ready", result["phase"])
        self.assertTrue(result["ready"])

    def test_target_with_spaces_reaches_ready(self) -> None:
        spaced_target = Path(self.temporary.name).resolve(strict=True) / "target with spaces"
        spaced_target.mkdir()
        installed, _result = _run(spaced_target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        runtime = (
            spaced_target
            / ".agent-harnesses/runtime/project-harness/0.2.0/project_harness.py"
        )
        initialized = subprocess.run(
            [sys.executable, "-B", str(runtime), "init", "--root", str(spaced_target)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)

        verified, result = _run(spaced_target, "verify", "project")

        self.assertEqual(0, verified.returncode)
        self.assertEqual("ready", result["phase"])
        self.assertTrue(result["ready"])

    def test_uninstall_refuses_changed_bytes(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        readme = self.target / ".agent-harnesses/runtime/project-harness/0.2.0/README.md"
        readme.write_text("changed\n", encoding="utf-8")
        before = _snapshot(self.target)

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual(before, _snapshot(self.target))

    def test_malformed_receipts_fail_as_actionable_json_without_removal(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = self.target / ".agent-harnesses/runtime/project-harness/0.2.0"
        receipt_path = destination / installer.RECEIPT_NAME
        canonical = receipt_path.read_bytes()
        valid = json.loads(canonical)

        def payload_snapshot() -> tuple[tuple[str, str], ...]:
            return tuple(
                (path.relative_to(destination).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
                for path in sorted(destination.rglob("*"))
                if path.is_file() and path != receipt_path
            )

        baseline = payload_snapshot()
        mutations: list[tuple[str, object, bool]] = []
        mutations.append(("top-level-list", [], False))
        files_not_list = json.loads(canonical)
        files_not_list["files"] = "invalid"
        mutations.append(("files-not-list", files_not_list, False))
        for name, path_value in (
            ("path-unhashable", []),
            ("path-absolute", "/".join(("", "absolute"))),
            ("path-parent", "../escape"),
            ("path-backslash", "nested" + chr(92) + "file"),
        ):
            value = json.loads(canonical)
            value["files"][0]["path"] = path_value
            mutations.append((name, value, False))
        duplicate = json.loads(canonical)
        duplicate["files"].append(dict(duplicate["files"][0]))
        mutations.append(("duplicate-path", duplicate, False))
        for name, digest in (("digest-nonhex", "g" * 64), ("digest-length", "0" * 63)):
            value = json.loads(canonical)
            value["files"][0]["sha256"] = digest
            mutations.append((name, value, False))
        missing_key = json.loads(canonical)
        del missing_key["files"][0]["sha256"]
        mutations.append(("missing-key", missing_key, False))
        extra_key = json.loads(canonical)
        extra_key["files"][0]["extra"] = True
        mutations.append(("extra-key", extra_key, False))
        noncanonical = json.loads(canonical)
        mutations.append(("noncanonical-json", noncanonical, True))

        for name, value, compact in mutations:
            with self.subTest(name=name):
                if compact:
                    receipt_path.write_text(json.dumps(value), encoding="utf-8")
                else:
                    receipt_path.write_text(
                        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )

                process, result = _run(self.target, "uninstall", "project", "--dry-run")

                self.assertEqual(2, process.returncode)
                self.assertEqual("", process.stderr)
                self.assertEqual(
                    {"code", "phase", "message", "remediation", "ready"},
                    set(result),
                )
                self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
                self.assertEqual("installed", result["phase"])
                self.assertFalse(result["ready"])
                self.assertTrue(destination.is_dir())
                self.assertEqual(baseline, payload_snapshot())
                receipt_path.write_bytes(canonical)

    def test_linked_receipt_fails_as_actionable_json_without_removal(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = self.target / ".agent-harnesses/runtime/project-harness/0.2.0"
        receipt_path = destination / installer.RECEIPT_NAME
        external = Path(self.temporary.name) / "external-receipt.json"
        external.write_bytes(receipt_path.read_bytes())
        receipt_path.unlink()
        try:
            receipt_path.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("file symlinks are unavailable")
        before_payload = tuple(
            (path.relative_to(destination).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(destination.rglob("*"))
            if path.is_file() and path != receipt_path
        )

        process, result = _run(self.target, "uninstall", "project", "--dry-run")

        self.assertEqual(2, process.returncode)
        self.assertEqual("", process.stderr)
        self.assertEqual({"code", "phase", "message", "remediation", "ready"}, set(result))
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertTrue(receipt_path.is_symlink())
        self.assertTrue(destination.is_dir())
        after_payload = tuple(
            (path.relative_to(destination).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(destination.rglob("*"))
            if path.is_file() and path != receipt_path
        )
        self.assertEqual(before_payload, after_payload)

    def test_uninstall_does_not_require_operational_doctor_compatibility(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        (self.target / ".orchestration").mkdir()
        (self.target / ".orchestration/manifest.json").write_text("{}\n", encoding="utf-8")

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertEqual("OK", result["code"])
        self.assertFalse(
            (self.target / ".agent-harnesses/runtime/project-harness/0.2.0").exists()
        )

    def test_failed_publish_cleans_every_installer_owned_parent(self) -> None:
        package = installer._package_for_selector("project")
        source = installer._local_source(package["id"])
        self.assertIsNotNone(source)
        destination = installer._runtime_destination(self.target, package["id"])

        with mock.patch.object(installer, "_publish_no_replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                installer._copy_install(source[0], source[1], destination, package["id"])

        self.assertEqual([], list(self.target.iterdir()))

    def test_uninstall_parser_accepts_exactly_one_selector(self) -> None:
        arguments = installer._parser().parse_args(
            ["uninstall", "project", "--target", str(self.target), "--dry-run"]
        )
        self.assertEqual("project", arguments.selector)

    def test_bad_archive_checksum_never_reaches_extraction(self) -> None:
        package = installer._package_for_selector("project")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)

            def fake_download(_url: str, destination: Path) -> None:
                path = Path(destination)
                if path.name.endswith(".sha256"):
                    path.write_text("0" * 64 + "  " + package["asset"] + "\n", encoding="ascii")
                else:
                    path.write_bytes(b"synthetic corrupt archive")

            with (
                mock.patch.object(installer.urllib.request, "urlretrieve", side_effect=fake_download),
                mock.patch.object(installer, "_safe_extract") as extraction,
            ):
                with self.assertRaises(installer.InstallerFailure) as context:
                    installer._download_source(package, temporary)

        self.assertEqual("E_CHECKSUM_MISMATCH", context.exception.result["code"])
        extraction.assert_not_called()

    def test_malformed_and_duplicate_inventory_entries_fail_as_json_errors(self) -> None:
        source = self.target / "source"
        source.mkdir()
        (source / "file.txt").write_text("synthetic\n", encoding="utf-8")
        digest = hashlib.sha256((source / "file.txt").read_bytes()).hexdigest()
        invalid_cases = (
            [{"path": "file.txt", "sha256": digest}, {"path": "file.txt", "sha256": digest}],
            [{"path": "file.txt", "sha256": "not-a-digest"}],
            [{"path": 1, "sha256": digest}],
            [{"path": [], "sha256": digest}],
            [{"path": "/".join(("", "absolute")), "sha256": digest}],
            [{"path": "../escape", "sha256": digest}],
            [{"path": "nested" + chr(92) + "file.txt", "sha256": digest}],
            [{"path": "nested//file.txt", "sha256": digest}],
            [{"path": "file.txt", "sha256": "A" * 64}],
            [{"path": "file.txt"}],
            [{"path": "file.txt", "sha256": digest, "extra": True}],
        )
        for inventory in invalid_cases:
            with self.subTest(inventory=inventory):
                with self.assertRaises(installer.InstallerFailure) as context:
                    installer._validate_inventory(source, inventory)
                self.assertEqual("E_CHECKSUM_MISMATCH", context.exception.result["code"])

    def test_archive_paths_are_portable_and_rejected_before_extraction(self) -> None:
        for name in (
            "nested" + chr(92) + "payload.txt",
            "../escape.txt",
            "/".join(("", "absolute.txt")),
        ):
            with self.subTest(name=name):
                archive = self.target / "synthetic.zip"
                extraction = self.target / "extracted"
                extraction.mkdir()
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr(name, b"synthetic")

                with self.assertRaises(installer.InstallerFailure) as context:
                    installer._safe_extract(archive, extraction)

                self.assertEqual("E_CHECKSUM_MISMATCH", context.exception.result["code"])
                self.assertEqual([], list(extraction.iterdir()))
                archive.unlink()
                extraction.rmdir()

    def test_download_failure_and_interrupt_clean_temporary_boundary(self) -> None:
        original_temporary_directory = tempfile.TemporaryDirectory
        for error in (
            installer.InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "synthetic", "retry"),
            KeyboardInterrupt(),
        ):
            with self.subTest(error=type(error).__name__):
                created: list[Path] = []

                def tracked_temporary(*args, **kwargs):
                    temporary = original_temporary_directory(*args, **kwargs)
                    created.append(Path(temporary.name))
                    return temporary

                def fail_download(_package, boundary: Path):
                    (boundary / "residual.tmp").write_text("synthetic", encoding="utf-8")
                    raise error

                output = io.StringIO()
                patches = (
                    mock.patch.object(installer, "_local_source", return_value=None),
                    mock.patch.object(installer, "_download_source", side_effect=fail_download),
                    mock.patch.object(installer.tempfile, "TemporaryDirectory", side_effect=tracked_temporary),
                )
                with patches[0], patches[1], patches[2], contextlib.redirect_stdout(output):
                    if isinstance(error, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            installer.main(["install", "project", "--target", str(self.target), "--apply", "--json"])
                    else:
                        self.assertEqual(2, installer.main(["install", "project", "--target", str(self.target), "--apply", "--json"]))
                self.assertTrue(created)
                self.assertTrue(all(not path.exists() for path in created))
                self.assertFalse((self.target / ".agent-harnesses").exists())

    def test_python_unsupported_is_actionable_json(self) -> None:
        output = io.StringIO()
        with mock.patch.object(installer.sys, "version_info", (3, 9)):
            with contextlib.redirect_stdout(output):
                code = installer.main(["doctor", "project", "--target", str(self.target), "--json"])
        result = json.loads(output.getvalue())
        self.assertEqual(2, code)
        self.assertEqual("E_PYTHON_UNSUPPORTED", result["code"])
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
