"""Tests for the clean-room repository baseline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import validate


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "manifests"


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (
                REPOSITORY_ROOT
                / "schemas"
                / "harness-package.schema.json"
            ).read_text(encoding="utf-8")
        )

    def test_valid_synthetic_manifest_passes(self) -> None:
        issues = validate.validate_schema_instance(
            _load_fixture("valid.json"),
            self.schema,
            artifact="synthetic.json",
        )
        self.assertEqual([], issues)

    def test_invalid_id_fails_pattern_contract(self) -> None:
        issues = validate.validate_schema_instance(
            _load_fixture("invalid-id.json"),
            self.schema,
            artifact="synthetic.json",
        )
        self.assertIn("SCHEMA_PATTERN", {issue.code for issue in issues})

    def test_additional_property_is_rejected(self) -> None:
        issues = validate.validate_schema_instance(
            _load_fixture("invalid-extra-property.json"),
            self.schema,
            artifact="synthetic.json",
        )
        self.assertIn(
            "SCHEMA_ADDITIONAL_PROPERTY",
            {issue.code for issue in issues},
        )


class ReferenceContractTests(unittest.TestCase):
    def test_relative_existing_reference_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "packages" / "synthetic"
            package.mkdir(parents=True)
            manifest = package / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            (package / "README.md").write_text("synthetic", encoding="utf-8")

            issues = validate.validate_reference(
                root,
                manifest,
                "README.md",
                field_name="readme",
            )
            self.assertEqual([], issues)

    def test_absolute_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            target = root / "README.md"
            target.write_text("synthetic", encoding="utf-8")

            issues = validate.validate_reference(
                root,
                manifest,
                str(target.resolve()),
                field_name="readme",
            )
            self.assertIn(
                "ABSOLUTE_REFERENCE",
                {issue.code for issue in issues},
            )

    def test_escaping_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            root = outer / "repository"
            package = root / "package"
            package.mkdir(parents=True)
            manifest = package / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            (outer / "outside.txt").write_text("synthetic", encoding="utf-8")

            issues = validate.validate_reference(
                root,
                manifest,
                "../../outside.txt",
                field_name="readme",
            )
            self.assertIn("REFERENCE_ESCAPE", {issue.code for issue in issues})

    def test_missing_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")

            issues = validate.validate_reference(
                root,
                manifest,
                "missing.txt",
                field_name="readme",
            )
            self.assertIn("REFERENCE_MISSING", {issue.code for issue in issues})

    def test_malformed_reference_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            malformed = "bad" + "\x00" + "reference"

            issues = validate.validate_reference(
                root,
                manifest,
                malformed,
                field_name="readme",
            )
            self.assertIn("REFERENCE_INVALID", {issue.code for issue in issues})


class SafetyContractTests(unittest.TestCase):
    def test_linked_worktree_marker_is_not_scanned_but_public_files_are(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            administrative_path = "/" + "synthetic/git/worktrees/example"
            (repository / ".git").write_text(
                f"gitdir: {administrative_path}\n",
                encoding="utf-8",
            )
            public_path = "/" + "synthetic/public/private.txt"
            (repository / "PUBLIC.md").write_text(
                f"unsafe public reference: {public_path}\n",
                encoding="utf-8",
            )
            nested = repository / "nested"
            nested.mkdir()
            (nested / ".git").write_text(
                f"unsafe public reference: {public_path}\n",
                encoding="utf-8",
            )

            issues = validate.scan_repository_text(repository)

            self.assertFalse(any(issue.path == ".git" for issue in issues))
            self.assertIn(
                ("PUBLIC.md", "ABSOLUTE_PATH"),
                {(issue.path, issue.code) for issue in issues},
            )
            self.assertIn(
                ("nested/.git", "ABSOLUTE_PATH"),
                {(issue.path, issue.code) for issue in issues},
            )

    def test_synthetic_unsafe_content_triggers_generic_findings(self) -> None:
        absolute_path = "/" + "Users/" + "synthetic/private.txt"
        absolute_directory = "/" + "tmp"
        unc_path = "\\" + "\\synthetic\\share\\private.txt"
        email = "synthetic" + "@" + "example.invalid"
        phone = "+" + "55 00 00000-0000"
        private_key = "-----BEGIN " + "RSA " + "PRIVATE KEY-----"
        credential = '"' + "password" + '": "' + "syntheticvalue12345" + '"'
        bearer = "Bearer" + " " + "synthetic-token-value"
        text = "\n".join(
            (
                absolute_path,
                absolute_directory,
                unc_path,
                email,
                phone,
                private_key,
                credential,
                bearer,
            )
        )

        issues = validate.scan_text("synthetic.txt", text)
        codes = {issue.code for issue in issues}
        self.assertTrue(
            {
                "ABSOLUTE_PATH",
                "UNC_PATH",
                "EMAIL",
                "PHONE",
                "PRIVATE_KEY",
                "CREDENTIAL_ASSIGNMENT",
                "BEARER_TOKEN",
            }.issubset(codes)
        )

    def test_only_the_declared_public_support_email_is_allowed(self) -> None:
        allowed = validate.scan_text(
            "PUBLIC.md",
            "Support: " + "fm" + "@" + "fabianomag.com",
        )
        self.assertFalse(any(issue.code == "EMAIL" for issue in allowed))

        rejected = validate.scan_text(
            "PUBLIC.md",
            "Contact: " + "someone" + "@" + "example.invalid",
        )
        self.assertTrue(any(issue.code == "EMAIL" for issue in rejected))

    def test_external_pattern_is_not_disclosed_in_finding(self) -> None:
        marker = "synthetic-" + "private-marker"
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            repository = outer / "repository"
            repository.mkdir()
            pattern_file = outer / "patterns.txt"
            pattern_file.write_text(marker, encoding="utf-8")

            patterns = validate.load_private_patterns(
                pattern_file,
                repository,
            )
            issues = validate.scan_text(
                "synthetic.txt",
                f"prefix {marker} suffix",
                private_patterns=patterns,
            )
            rendered = "\n".join(issue.render() for issue in issues)
            self.assertIn("PRIVATE_PATTERN", rendered)
            self.assertNotIn(marker, rendered)

    def test_external_pattern_and_input_path_are_not_disclosed_by_cli(self) -> None:
        marker = "Agent " + "Harnesses"
        with tempfile.TemporaryDirectory() as directory:
            pattern_file = Path(directory) / "private-patterns.txt"
            pattern_file.write_text(marker, encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPOSITORY_ROOT / "tools" / "validate.py"),
                    "--private-pattern-file",
                    str(pattern_file),
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            output = process.stdout + process.stderr
            self.assertEqual(1, process.returncode)
            self.assertIn("PRIVATE_PATTERN", output)
            self.assertNotIn(marker, output)
            self.assertNotIn(str(pattern_file), output)

    def test_private_pattern_file_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            pattern_file = repository / "patterns.txt"
            pattern_file.write_text("safe-pattern", encoding="utf-8")

            with self.assertRaises(validate.ContractError):
                validate.load_private_patterns(pattern_file, repository)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("synthetic", encoding="utf-8")
            os.symlink(target.name, root / "link.txt")

            issues = validate.find_symlink_issues(root)
            self.assertIn("SYMLINK", {issue.code for issue in issues})


class RepositoryContractTests(unittest.TestCase):
    def test_checked_in_baseline_passes(self) -> None:
        issues = validate.validate_repository(REPOSITORY_ROOT)
        self.assertEqual([], issues, "\n".join(issue.render() for issue in issues))

    def test_exact_package_identity_set(self) -> None:
        observed: dict[str, str] = {}
        for manifest_path in sorted(
            (REPOSITORY_ROOT / "packages").glob("*/harness.package.json")
        ):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            observed[manifest["id"]] = manifest["displayName"]
        self.assertEqual(validate.EXPECTED_PACKAGES, observed)

    def test_package_entry_must_be_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = root / "packages"
            packages.mkdir()
            (packages / "project-harness").write_text(
                "synthetic",
                encoding="utf-8",
            )
            schema = json.loads(
                (
                    REPOSITORY_ROOT
                    / "schemas"
                    / "harness-package.schema.json"
                ).read_text(encoding="utf-8")
            )

            issues = validate._validate_package_set(root, schema)
            self.assertIn("PACKAGE_TYPE", {issue.code for issue in issues})

    def test_scope_accepts_package_only_and_rejects_shared_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Synthetic Test"],
                cwd=root,
                check=True,
            )
            synthetic_email = "synthetic" + "@" + "example.invalid"
            subprocess.run(
                ["git", "config", "user.email", synthetic_email],
                cwd=root,
                check=True,
            )
            package = root / "packages" / "project-harness"
            package.mkdir(parents=True)
            (root / ".gitignore").write_text(
                "ignored-root.txt\n",
                encoding="utf-8",
            )
            (package / "baseline.txt").write_text(
                "synthetic baseline",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Synthetic baseline"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            baseline = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            (package / "allowed.txt").write_text("allowed", encoding="utf-8")
            allowed_issues = validate.validate_git_scope(
                root,
                package_id="project-harness",
                baseline=baseline,
            )
            self.assertEqual([], allowed_issues)

            (root / "README.md").write_text("shared change", encoding="utf-8")
            rejected_issues = validate.validate_git_scope(
                root,
                package_id="project-harness",
                baseline=baseline,
            )
            self.assertIn(
                "SCOPE_VIOLATION",
                {issue.code for issue in rejected_issues},
            )

            (root / "README.md").unlink()
            (root / "ignored-root.txt").write_text(
                "ignored shared change",
                encoding="utf-8",
            )
            ignored_issues = validate.validate_git_scope(
                root,
                package_id="project-harness",
                baseline=baseline,
            )
            self.assertIn(
                "SCOPE_VIOLATION",
                {issue.code for issue in ignored_issues},
            )

            (package / "allowed.txt").unlink()
            (root / "ignored-root.txt").unlink()
            (root / "README.md").write_text(
                "temporary shared change",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Synthetic shared change"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            (root / "README.md").unlink()
            subprocess.run(["git", "add", "-u"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Synthetic shared revert"],
                cwd=root,
                check=True,
                capture_output=True,
            )

            history_issues = validate.validate_git_scope(
                root,
                package_id="project-harness",
                baseline=baseline,
            )
            self.assertIn(
                "SCOPE_VIOLATION",
                {issue.code for issue in history_issues},
            )


if __name__ == "__main__":
    unittest.main()
