"""Black-box and safety tests for the standalone v0.2.1 installer."""

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
BASE_RESULT_FIELDS = {"code", "phase", "message", "remediation", "ready"}
ONBOARDING_RESULT_FIELDS = BASE_RESULT_FIELDS | {
    "operationsContract",
    "operatorGuides",
}


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
        self.assertEqual(f"v{installer.VERSION}", value["release"]["tag"])
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
                expected_readme = (
                    "`package/README.md`"
                    if language == "en"
                    else "`package/README.pt-BR.md`"
                )
                self.assertIn(expected_readme, prompt)
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

    def test_json_exposes_only_target_relative_operator_contract_paths(self) -> None:
        for selector, package_id in (
            ("project", "project-harness"),
            ("workspace", "workspace-coordination"),
            ("multi-project", "cross-project"),
            ("control-plane", "orchestration"),
        ):
            with self.subTest(selector=selector):
                process, result = _run(self.target, "doctor", selector)

                self.assertEqual(0, process.returncode)
                self.assertEqual(ONBOARDING_RESULT_FIELDS, set(result))
                base = f".agent-harnesses/runtime/{package_id}/{installer.VERSION}"
                self.assertEqual(
                    f"{base}/operations.json",
                    result["operationsContract"],
                )
                self.assertEqual(
                    {
                        "en": f"{base}/OPERATOR_GUIDE.md",
                        "ptBr": f"{base}/OPERATOR_GUIDE.pt-BR.md",
                    },
                    result["operatorGuides"],
                )
                self.assertNotIn(str(self.target), json.dumps(result))

    def test_doctor_rejects_malformed_duplicate_and_conflicting_onboarding_without_writes(self) -> None:
        selected = installer._onboarding_block("project-harness")
        cases = (
            (
                "missing-end",
                b"<!-- agent-harnesses:onboarding:project-harness:start -->\n",
                "E_INITIALIZATION_CONFLICT",
            ),
            ("duplicated", selected + selected, "E_INITIALIZATION_CONFLICT"),
            (
                "out-of-order",
                b"<!-- agent-harnesses:onboarding:project-harness:end -->\n"
                b"<!-- agent-harnesses:onboarding:project-harness:start -->\n",
                "E_INITIALIZATION_CONFLICT",
            ),
            (
                "conflicting-harness",
                installer._onboarding_block("cross-project"),
                "E_HARNESS_MISMATCH",
            ),
        )
        for name, payload, code in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory).resolve(strict=True) / "target"
                target.mkdir()
                agents = target / "AGENTS.md"
                agents.write_bytes(payload)
                before = _snapshot(target)

                process, result = _run(target, "doctor", "project")

                self.assertEqual(2, process.returncode)
                self.assertEqual(code, result["code"])
                self.assertEqual(before, _snapshot(target))

    def test_unreceipted_exact_onboarding_is_never_adopted_or_deleted(self) -> None:
        agents = self.target / "AGENTS.md"
        original = installer._onboarding_block("project-harness")
        agents.write_bytes(original)
        before = _snapshot(self.target)

        checked, checked_result = _run(self.target, "doctor", "project")
        installed, installed_result = _run(
            self.target,
            "install",
            "project",
            "--apply",
        )

        self.assertEqual(2, checked.returncode)
        self.assertEqual("E_INITIALIZATION_CONFLICT", checked_result["code"])
        self.assertEqual(2, installed.returncode)
        self.assertEqual("E_INITIALIZATION_CONFLICT", installed_result["code"])
        self.assertEqual(before, _snapshot(self.target))
        self.assertEqual(original, agents.read_bytes())
        self.assertFalse((self.target / ".agent-harnesses").exists())

    def test_doctor_rejects_linked_agents_for_workspace_without_following_it(self) -> None:
        external = Path(self.temporary.name) / "external-agents.md"
        external.write_bytes(b"# External owner\n")
        agents = self.target / "AGENTS.md"
        try:
            agents.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("file symlinks are unavailable")
        external_before = external.read_bytes()
        target_before = os.lstat(agents)

        process, result = _run(self.target, "doctor", "workspace")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_INITIALIZATION_CONFLICT", result["code"])
        self.assertEqual(external_before, external.read_bytes())
        self.assertEqual(target_before, os.lstat(agents))

    def test_apply_rejects_unsafe_onboarding_lock_without_overwriting_it(self) -> None:
        boundary = self.target / ".agent-harnesses"
        boundary.mkdir()
        lock = boundary / installer.ONBOARDING_LOCK_NAME
        lock.write_bytes(b"external lock owner\n")
        before = _snapshot(self.target)

        process, result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_INITIALIZATION_CONFLICT", result["code"])
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
            ("workspace", "AGENTS.md"),
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
        readme = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}/README.md"
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

    def test_control_plane_preserves_unrelated_agents_when_no_master_shape_exists(self) -> None:
        original = b"# Existing coding-agent instructions without final LF"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        before_doctor = _snapshot(self.target)

        checked, checked_result = _run(self.target, "doctor", "control-plane")

        self.assertEqual(0, checked.returncode)
        self.assertEqual("OK", checked_result["code"])
        self.assertEqual(before_doctor, _snapshot(self.target))

        installed, _result = _run(
            self.target,
            "install",
            "control-plane",
            "--apply",
        )
        self.assertEqual(0, installed.returncode)
        self.assertEqual(
            original
            + installer.ONBOARDING_SEPARATOR
            + installer._onboarding_block("orchestration"),
            agents.read_bytes(),
        )

        removed, _result = _run(
            self.target,
            "uninstall",
            "control-plane",
            "--apply",
        )
        self.assertEqual(0, removed.returncode)
        self.assertEqual(original, agents.read_bytes())

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

    def test_apply_creates_exact_exclusive_onboarding_and_records_ownership(self) -> None:
        process, result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertEqual(
            installer._onboarding_block("project-harness"),
            (self.target / "AGENTS.md").read_bytes(),
        )
        destination = installer._runtime_destination(self.target, "project-harness")
        receipt = json.loads((destination / installer.RECEIPT_NAME).read_bytes())
        self.assertEqual(2, receipt["schemaVersion"])
        self.assertTrue(receipt["onboarding"]["agentsCreated"])
        self.assertEqual(result["operationsContract"], receipt["onboarding"]["operationsContract"])
        self.assertEqual(result["operatorGuides"], receipt["onboarding"]["operatorGuides"])
        for relative in (
            result["operationsContract"],
            result["operatorGuides"]["en"],
            result["operatorGuides"]["ptBr"],
        ):
            self.assertTrue((self.target / relative).is_file())

    def test_apply_preserves_non_utf8_external_agents_bytes_exactly(self) -> None:
        original = b"# Existing instructions\r\n\xff\x00external-tail"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        agents.chmod(0o600)
        original_mode = agents.stat().st_mode & 0o777

        process, _result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertEqual(
            original
            + installer.ONBOARDING_SEPARATOR
            + installer._onboarding_block("project-harness"),
            agents.read_bytes(),
        )
        marker = installer._onboarding_markers("project-harness")[0]
        self.assertIn(b"external-tail\n\n" + marker, agents.read_bytes())
        self.assertEqual(original_mode, agents.stat().st_mode & 0o777)
        receipt = json.loads(
            (
                installer._runtime_destination(self.target, "project-harness")
                / installer.RECEIPT_NAME
            ).read_bytes()
        )
        self.assertFalse(receipt["onboarding"]["agentsCreated"])

        removed, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, removed.returncode)
        self.assertEqual(original, agents.read_bytes())
        self.assertEqual(original_mode, agents.stat().st_mode & 0o777)

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
            observed = (self.target / relative).read_bytes()
            if relative == "AGENTS.md":
                self.assertEqual(
                    content
                    + installer.ONBOARDING_SEPARATOR
                    + installer._onboarding_block("project-harness"),
                    observed,
                )
            else:
                self.assertEqual(content, observed)
        receipts = list(self.target.rglob(installer.RECEIPT_NAME))
        self.assertEqual(1, len(receipts))
        self.assertTrue(
            receipts[0].is_relative_to(
                self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}"
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

    def test_021_install_and_uninstall_preserve_existing_020_runtime_and_state(self) -> None:
        old_runtime = (
            self.target
            / ".agent-harnesses"
            / "runtime"
            / "project-harness"
            / "0.2.0"
        )
        old_runtime.mkdir(parents=True)
        old_payload = old_runtime / "legacy-runtime.txt"
        old_payload.write_bytes(b"synthetic immutable 0.2.0 runtime\n")
        marker = self.target / ".project-harness" / "state.json"
        marker.parent.mkdir()
        marker.write_bytes(b'{"harnessVersion":"0.2.0"}\n')
        agents = self.target / "AGENTS.md"
        old_agents = b"# Existing 0.2.0 project instructions\n"
        agents.write_bytes(old_agents)
        old_before = _snapshot(old_runtime)
        marker_before = marker.read_bytes()

        installed, _result = _run(self.target, "install", "project", "--apply")

        self.assertEqual(0, installed.returncode)
        self.assertEqual(old_before, _snapshot(old_runtime))
        self.assertEqual(marker_before, marker.read_bytes())
        self.assertEqual(
            old_agents
            + installer.ONBOARDING_SEPARATOR
            + installer._onboarding_block("project-harness"),
            agents.read_bytes(),
        )
        self.assertTrue(
            installer._runtime_destination(self.target, "project-harness").is_dir()
        )

        removed, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, removed.returncode)
        self.assertEqual(old_before, _snapshot(old_runtime))
        self.assertEqual(marker_before, marker.read_bytes())
        self.assertEqual(old_agents, agents.read_bytes())

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
        destination = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}"
        installer._verify_runtime_files(destination, "project-harness")
        runtime_root = self.target / ".agent-harnesses/runtime"
        self.assertEqual([], list(runtime_root.glob(".install-*")))

    def test_ready_requires_operational_runtime_verification(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        runtime = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}/project_harness.py"
        subprocess.run(
            [sys.executable, "-B", str(runtime), "init", "--root", str(self.target)],
            check=True,
            capture_output=True,
        )

        verified, result = _run(self.target, "verify", "project")

        self.assertEqual(0, verified.returncode)
        self.assertEqual("ready", result["phase"])
        self.assertTrue(result["ready"])

    def test_verify_requires_intact_onboarding_but_block_alone_is_not_ready(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        agents = self.target / "AGENTS.md"
        exact = agents.read_bytes()

        before_init, before_result = _run(self.target, "verify", "project")
        self.assertEqual(2, before_init.returncode)
        self.assertEqual("E_NOT_READY", before_result["code"])
        self.assertEqual("installed", before_result["phase"])

        agents.write_bytes(exact.replace(b"Operations contract", b"Changed contract", 1))
        before = _snapshot(self.target)
        verified, result = _run(self.target, "verify", "project")

        self.assertEqual(2, verified.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual("installed", result["phase"])
        self.assertFalse(result["ready"])
        self.assertEqual(before, _snapshot(self.target))

    def test_verify_refuses_changed_managed_separator_without_touching_target(self) -> None:
        original = b"# Existing instructions without final LF"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        exact = agents.read_bytes()
        expected = original + installer.ONBOARDING_SEPARATOR
        self.assertTrue(exact.startswith(expected))
        agents.write_bytes(original + b"\n" + exact[len(expected) :])
        before = _snapshot(self.target)

        verified, result = _run(self.target, "verify", "project")

        self.assertEqual(2, verified.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual("installed", result["phase"])
        self.assertEqual(before, _snapshot(self.target))

    def test_uninstall_fails_closed_when_external_insert_precedes_managed_block(self) -> None:
        original = b"OWNER"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        marker = installer._onboarding_markers("project-harness")[0]
        installed_bytes = agents.read_bytes()
        marker_start = installed_bytes.index(marker)
        external_insert = b"USER-INSERT\n\n"
        agents.write_bytes(
            installed_bytes[:marker_start]
            + external_insert
            + installed_bytes[marker_start:]
        )
        before = _snapshot(self.target)

        removed, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, removed.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual("installed", result["phase"])
        self.assertEqual(before, _snapshot(self.target))
        self.assertEqual(
            original
            + installer.ONBOARDING_SEPARATOR
            + external_insert
            + installer._onboarding_block("project-harness"),
            agents.read_bytes(),
        )
        self.assertTrue(
            installer._runtime_destination(self.target, "project-harness").is_dir()
        )

    def test_target_with_spaces_reaches_ready(self) -> None:
        spaced_target = Path(self.temporary.name).resolve(strict=True) / "target with spaces"
        spaced_target.mkdir()
        installed, _result = _run(spaced_target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        runtime = (
            spaced_target
            / f".agent-harnesses/runtime/project-harness/{installer.VERSION}/project_harness.py"
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
        readme = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}/README.md"
        readme.write_text("changed\n", encoding="utf-8")
        before = _snapshot(self.target)

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual(before, _snapshot(self.target))

    def test_uninstall_refuses_unreceipted_empty_directory(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = installer._runtime_destination(self.target, "project-harness")
        unexpected = destination / "external-empty-directory"
        unexpected.mkdir()
        before = _snapshot(self.target)

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertEqual(before, _snapshot(self.target))
        self.assertTrue(unexpected.is_dir())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO entries are unavailable")
    def test_uninstall_refuses_unreceipted_special_entry(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = installer._runtime_destination(self.target, "project-harness")
        unexpected = destination / "external.fifo"
        os.mkfifo(unexpected)

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertTrue(destination.is_dir())
        self.assertTrue(unexpected.exists())

    def test_uninstall_deletes_only_installer_created_exclusive_agents(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        self.assertEqual(
            installer._onboarding_block("project-harness"),
            (self.target / "AGENTS.md").read_bytes(),
        )

        process, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / ".agent-harnesses").exists())

    def test_uninstall_preserves_external_agents_bytes_before_and_after_block(self) -> None:
        before = b"# Existing owner\r\n\xff"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(before)
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        after = b"\n# Added after installation\n"
        agents.write_bytes(agents.read_bytes() + after)

        process, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertTrue(agents.is_file())
        self.assertEqual(before + after, agents.read_bytes())

    def test_uninstall_keeps_preexisting_empty_agents_file(self) -> None:
        agents = self.target / "AGENTS.md"
        agents.write_bytes(b"")
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)

        process, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, process.returncode)
        self.assertTrue(agents.is_file())
        self.assertEqual(b"", agents.read_bytes())

    def test_uninstall_removes_onboarding_but_keeps_runtime_initialized_agents_contract(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        runtime = (
            installer._runtime_destination(self.target, "project-harness")
            / "project_harness.py"
        )
        initialized = subprocess.run(
            [sys.executable, "-B", str(runtime), "init", "--root", str(self.target)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)

        process, _result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(0, process.returncode)
        agents = (self.target / "AGENTS.md").read_bytes()
        self.assertNotIn(installer.ONBOARDING_MARKER_TOKEN, agents)
        self.assertIn(b"project-harness:managed:agents", agents)

    def test_uninstall_refuses_tampered_onboarding_without_removing_runtime(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = installer._runtime_destination(self.target, "project-harness")
        agents = self.target / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"Operator guide", b"Changed guide", 1))
        before = _snapshot(self.target)

        process, result = _run(self.target, "uninstall", "project", "--apply")

        self.assertEqual(2, process.returncode)
        self.assertEqual("E_CHECKSUM_MISMATCH", result["code"])
        self.assertTrue(destination.is_dir())
        self.assertEqual(before, _snapshot(self.target))

    def test_uninstall_failure_restores_runtime_and_agents_exactly(self) -> None:
        original = b"# Existing owner\n"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        package = installer._package_for_selector("project")
        destination = installer._runtime_destination(self.target, package["id"])
        agents_installed = agents.read_bytes()
        runtime_before = tuple(
            (path.relative_to(destination).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(destination.rglob("*"))
            if path.is_file()
        )

        original_remove = installer._remove_owned_tree
        failed = False

        def fail_after_partial_removal(path: Path) -> None:
            nonlocal failed
            if path.name.startswith(".remove-") and not failed:
                first_file = next(candidate for candidate in path.rglob("*") if candidate.is_file())
                first_file.unlink()
                failed = True
                raise OSError("synthetic partial removal failure")
            original_remove(path)

        with mock.patch.object(
            installer,
            "_remove_owned_tree",
            side_effect=fail_after_partial_removal,
        ):
            with self.assertRaises(OSError):
                installer._uninstall(package, self.target, True)

        self.assertEqual(agents_installed, agents.read_bytes())
        self.assertTrue(destination.is_dir())
        runtime_after = tuple(
            (path.relative_to(destination).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(destination.rglob("*"))
            if path.is_file()
        )
        self.assertEqual(runtime_before, runtime_after)
        self.assertEqual([], list(destination.parent.glob(".remove-*")))
        self.assertEqual([], list(destination.parent.glob(".restore-*")))

    def test_malformed_receipts_fail_as_actionable_json_without_removal(self) -> None:
        installed, _result = _run(self.target, "install", "project", "--apply")
        self.assertEqual(0, installed.returncode)
        destination = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}"
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
        missing_onboarding = json.loads(canonical)
        del missing_onboarding["onboarding"]
        mutations.append(("missing-onboarding", missing_onboarding, False))
        invalid_created = json.loads(canonical)
        invalid_created["onboarding"]["agentsCreated"] = "true"
        mutations.append(("invalid-agents-created", invalid_created, False))
        absolute_contract = json.loads(canonical)
        absolute_contract["onboarding"]["operationsContract"] = "/".join(
            ("", "private", "target", "operations.json")
        )
        mutations.append(("absolute-operations-contract", absolute_contract, False))
        invalid_guides = json.loads(canonical)
        invalid_guides["onboarding"]["operatorGuides"]["extra"] = "guide.md"
        mutations.append(("invalid-operator-guides", invalid_guides, False))
        invalid_block_digest = json.loads(canonical)
        invalid_block_digest["onboarding"]["blockSha256"] = "0" * 64
        mutations.append(("invalid-block-digest", invalid_block_digest, False))
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
                    ONBOARDING_RESULT_FIELDS,
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
        destination = self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}"
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
        self.assertEqual(ONBOARDING_RESULT_FIELDS, set(result))
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
            (self.target / f".agent-harnesses/runtime/project-harness/{installer.VERSION}").exists()
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

    def test_failed_runtime_publish_restores_external_agents_bytes_exactly(self) -> None:
        original = b"# Existing owner\r\n\nKeep this byte-for-byte.\n"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(original)
        package = installer._package_for_selector("project")
        source = installer._local_source(package["id"])
        self.assertIsNotNone(source)
        destination = installer._runtime_destination(self.target, package["id"])

        with mock.patch.object(
            installer,
            "_publish_no_replace",
            side_effect=OSError("synthetic publish failure"),
        ):
            with self.assertRaises(OSError):
                installer._copy_install(
                    source[0],
                    source[1],
                    destination,
                    package["id"],
                )

        self.assertEqual(original, agents.read_bytes())
        self.assertEqual([agents], list(self.target.iterdir()))
        self.assertFalse((self.target / ".agent-harnesses").exists())

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

    def test_inventory_requires_all_three_operator_contract_files(self) -> None:
        source = self.target / "source"
        source.mkdir()
        payloads = {
            "operations.json": b"{}\n",
            "OPERATOR_GUIDE.md": b"# English\n",
        }
        inventory = []
        for relative, content in payloads.items():
            path = source / relative
            path.write_bytes(content)
            inventory.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )

        with self.assertRaises(installer.InstallerFailure) as context:
            installer._validate_inventory(source, inventory)

        self.assertEqual("E_CHECKSUM_MISMATCH", context.exception.result["code"])
        self.assertIn("onboarding", context.exception.result["message"])

    def test_archive_paths_are_portable_and_rejected_before_extraction(self) -> None:
        for index, name in enumerate((
            "nested" + chr(92) + "payload.txt",
            "../escape.txt",
            "/".join(("", "absolute.txt")),
        )):
            with self.subTest(name=name):
                archive = self.target / f"synthetic-{index}.zip"
                extraction = self.target / f"extracted-{index}"
                extraction.mkdir()
                portable_name = name.replace(chr(92), "/")
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr(portable_name, b"synthetic")

                if portable_name != name:
                    content = archive.read_bytes()
                    portable_bytes = portable_name.encode("utf-8")
                    raw_bytes = name.encode("utf-8")
                    self.assertEqual(2, content.count(portable_bytes))
                    archive.write_bytes(content.replace(portable_bytes, raw_bytes))

                with zipfile.ZipFile(archive) as bundle:
                    self.assertEqual(name, bundle.infolist()[0].orig_filename)

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
