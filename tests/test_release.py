"""Deterministic release packaging and workflow safety tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from tools import build_release, product


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_COMMIT = "1" * 40


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(root.iterdir(), key=lambda item: item.name)
    }


class ReleaseAssetTests(unittest.TestCase):
    def _build(self, parent: Path, name: str = "release") -> Path:
        output = parent / name
        build_release.build_release(
            output,
            source_commit=SYNTHETIC_COMMIT,
            repository_root=REPOSITORY_ROOT,
        )
        return output

    def test_two_builds_are_byte_identical_and_verify_exact_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            first = self._build(parent, "first")
            second = self._build(parent, "second")

            self.assertEqual(_files(first), _files(second))
            verified = build_release.verify_release(
                first,
                source_commit=SYNTHETIC_COMMIT,
                repository_root=REPOSITORY_ROOT,
            )
            self.assertEqual(sorted(_files(first)), verified)
            self.assertEqual(16, len(verified))
            self.assertNotIn("SHA256SUMS", verified)

    def test_manifest_binds_commit_tag_sizes_and_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self._build(Path(directory))
            files = _files(output)
            manifest = json.loads(files[build_release.RELEASE_MANIFEST_NAME])
            value = product.load_product(REPOSITORY_ROOT)

            self.assertEqual(1, manifest["schemaVersion"])
            self.assertEqual(SYNTHETIC_COMMIT, manifest["release"]["sourceCommit"])
            self.assertEqual(value["release"]["tag"], manifest["release"]["tag"])
            self.assertEqual(
                value["release"]["version"], manifest["release"]["version"]
            )
            entries = {entry["filename"]: entry for entry in manifest["assets"]}
            expected_primary = {
                *(item["asset"] for item in value["packages"]),
                "installer.py",
                product.SITE_SNAPSHOT_PATH.name,
                build_release.CHANGELOG_NAME,
            }
            self.assertEqual(expected_primary, set(entries))
            for filename, entry in entries.items():
                content = files[filename]
                self.assertEqual(len(content), entry["size"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])

    def test_every_primary_asset_has_one_independent_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self._build(Path(directory))
            files = _files(output)
            primary = {name for name in files if not name.endswith(".sha256")}

            self.assertEqual(
                {name + ".sha256" for name in primary},
                {name for name in files if name.endswith(".sha256")},
            )
            for filename in primary:
                digest = hashlib.sha256(files[filename]).hexdigest()
                self.assertEqual(
                    f"{digest}  {filename}\n".encode("ascii"),
                    files[filename + ".sha256"],
                )

    def test_each_zip_is_one_package_only_with_fixed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self._build(Path(directory))
            value = product.load_product(REPOSITORY_ROOT)
            files = _files(output)
            all_ids = {item["id"] for item in value["packages"]}

            for definition in value["packages"]:
                root = f"{definition['id']}-{value['release']['version']}"
                with zipfile.ZipFile(output / definition["asset"]) as archive:
                    infos = archive.infolist()
                    names = [info.filename for info in infos]
                    self.assertEqual(len(names), len(set(names)))
                    self.assertTrue(all(name.startswith(root + "/") for name in names))
                    self.assertIn(f"{root}/bundle-manifest.json", names)
                    self.assertIn(f"{root}/installer.py", names)
                    self.assertIn(f"{root}/package/LICENSE", names)
                    self.assertTrue(
                        all(
                            info.date_time == build_release.FIXED_ZIP_TIME
                            and info.compress_type == zipfile.ZIP_STORED
                            and info.create_system == 3
                            and not info.is_dir()
                            for info in infos
                        )
                    )
                    manifest = json.loads(
                        archive.read(f"{root}/bundle-manifest.json")
                    )
                    self.assertEqual(definition["id"], manifest["package"]["id"])
                    self.assertEqual(
                        SYNTHETIC_COMMIT, manifest["release"]["sourceCommit"]
                    )
                    payload_names = {
                        name.removeprefix(f"{root}/package/")
                        for name in names
                        if name.startswith(f"{root}/package/")
                    }
                    self.assertTrue(
                        build_release.CORE_OPERATION_FILES.issubset(payload_names)
                    )
                    self.assertFalse(
                        any(
                            build_release._is_agent_adapter_path(
                                PurePosixPath(name)
                            )
                            for name in payload_names
                        )
                    )
                    operations = json.loads(
                        archive.read(f"{root}/package/operations.json")
                    )
                    self.assertEqual(1, operations["schemaVersion"])
                    self.assertEqual(
                        definition["id"], operations["package"]["id"]
                    )
                    self.assertEqual(
                        value["release"]["version"],
                        operations["package"]["version"],
                    )
                    self.assertTrue(operations["tutorial"]["requiredAfterReady"])
                    for guide in (
                        "OPERATOR_GUIDE.md",
                        "OPERATOR_GUIDE.pt-BR.md",
                    ):
                        rendered = archive.read(f"{root}/package/{guide}").decode(
                            "utf-8"
                        )
                        self.assertIn("operations.json", rendered)
                        self.assertIn(definition["id"], rendered)
                    bundle_manifest = json.loads(
                        archive.read(f"{root}/bundle-manifest.json")
                    )
                    inventory_names = {
                        item["path"] for item in bundle_manifest["files"]
                    }
                    self.assertEqual(payload_names, inventory_names)
                    for other_id in all_ids - {definition["id"]}:
                        self.assertFalse(
                            any(
                                name.startswith(f"packages/{other_id}/")
                                or f"/{other_id}/" in name
                                for name in payload_names
                            )
                        )

    def test_site_snapshot_points_to_the_public_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self._build(Path(directory))
            snapshot = json.loads(
                (output / product.SITE_SNAPSHOT_PATH.name).read_text(
                    encoding="utf-8"
                )
            )
            value = product.load_product(REPOSITORY_ROOT)
            expected = (
                "https://github.com/fabianomag/agent-harnesses/releases/"
                f"download/{value['release']['tag']}/release-manifest.json"
            )
            self.assertEqual(2, snapshot["schemaVersion"])
            self.assertEqual("0.2.2", snapshot["release"]["version"])
            self.assertEqual("v0.2.2", snapshot["release"]["tag"])
            self.assertEqual(expected, snapshot["releaseManifest"]["url"])
            self.assertTrue(snapshot["tutorial"]["requiredAfterReady"])
            self.assertEqual("conversation", snapshot["tutorial"]["delivery"])
            self.assertNotIn("adapters", snapshot)
            for package in snapshot["packages"]:
                self.assertNotIn("adapters", package)
                self.assertEqual(
                    product.EXPECTED_OPERATIONS[package["id"]],
                    tuple(
                        operation["command"]
                        for operation in package["operator"]["operations"]
                    ),
                )
            rendered_snapshot = json.dumps(snapshot, ensure_ascii=False)
            self.assertNotIn("adapters/openai", rendered_snapshot)
            self.assertNotIn("SKILL.md", rendered_snapshot)
            self.assertNotIn("openai.yaml", rendered_snapshot)

    def test_openai_adapters_are_optional_repository_only_files(self) -> None:
        adapters = REPOSITORY_ROOT / "adapters" / "openai"
        for package_id in product.PACKAGE_IDS:
            with self.subTest(package_id=package_id):
                adapter = adapters / package_id
                skill = (adapter / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("operations.json", skill)
                self.assertIn(
                    f".agent-harnesses/runtime/{package_id}/0.2.2/",
                    skill,
                )
                self.assertIn("optional adapter", skill.lower())

        expected_yaml = {
            "cross-project/agents/openai.yaml",
            "orchestration/agents/openai.yaml",
        }
        observed_yaml = {
            path.relative_to(adapters).as_posix()
            for path in adapters.rglob("openai.yaml")
        }
        self.assertEqual(expected_yaml, observed_yaml)

        legacy_paths = (
            "packages/project-harness/skills/project-harness/SKILL.md",
            "packages/workspace-coordination/SKILL.md",
            "packages/cross-project/SKILL.md",
            "packages/cross-project/agents/openai.yaml",
            "packages/orchestration/SKILL.md",
            "packages/orchestration/agents/openai.yaml",
        )
        self.assertFalse(
            any((REPOSITORY_ROOT / relative).exists() for relative in legacy_paths)
        )

    def test_core_adapter_path_guard_covers_legacy_layouts(self) -> None:
        for relative in (
            "SKILL.md",
            "skill.md",
            "skills/project-harness/SKILL.md",
            "agents/openai.yaml",
            "AGENTS/OpenAI.yaml",
            "adapters/openai/example/SKILL.md",
        ):
            with self.subTest(relative=relative):
                self.assertTrue(
                    build_release._is_agent_adapter_path(PurePosixPath(relative))
                )
        for relative in build_release.CORE_OPERATION_FILES:
            self.assertFalse(
                build_release._is_agent_adapter_path(PurePosixPath(relative))
            )

    def test_exact_package_archives_reach_ready_after_documented_first_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory).resolve(strict=True)
            output = self._build(outer, "release")
            value = product.load_product(REPOSITORY_ROOT)
            environment = os.environ.copy()
            environment.update(
                {
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUTF8": "1",
                }
            )

            def run(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
                process = subprocess.run(
                    [sys.executable, "-B", *arguments],
                    cwd=cwd,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    0,
                    process.returncode,
                    process.stdout + process.stderr,
                )
                return process

            for definition in value["packages"]:
                package_id = definition["id"]
                with self.subTest(package_id=package_id):
                    extracted = outer / f"extracted-{package_id}"
                    with zipfile.ZipFile(output / definition["asset"]) as archive:
                        archive.extractall(extracted)
                    bundle = extracted / f"{package_id}-{value['release']['version']}"
                    self.assertTrue((bundle / "package" / "README.md").is_file())
                    target = outer / f"target with spaces {package_id}"
                    target.mkdir()
                    if package_id == "workspace-coordination":
                        (target / "child-alpha").mkdir()
                        (target / "child-alpha" / "AGENTS.md").write_text(
                            "# Alpha owner\n", encoding="utf-8"
                        )
                    elif package_id == "cross-project":
                        (target / "projects" / "alpha").mkdir(parents=True)

                    installer = str(bundle / "installer.py")
                    common = [package_id, "--target", str(target), "--json"]
                    doctor = run(installer, "doctor", *common, cwd=bundle)
                    self.assertEqual("downloaded", json.loads(doctor.stdout)["phase"])
                    dry_run = run(
                        installer,
                        "install",
                        package_id,
                        "--target",
                        str(target),
                        "--dry-run",
                        "--json",
                        cwd=bundle,
                    )
                    self.assertFalse(json.loads(dry_run.stdout)["ready"])
                    applied = run(
                        installer,
                        "install",
                        package_id,
                        "--target",
                        str(target),
                        "--apply",
                        "--json",
                        cwd=bundle,
                    )
                    self.assertEqual("installed", json.loads(applied.stdout)["phase"])
                    before_init = subprocess.run(
                        [sys.executable, "-B", installer, "verify", *common],
                        cwd=bundle,
                        env=environment,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(2, before_init.returncode)
                    self.assertEqual("E_NOT_READY", json.loads(before_init.stdout)["code"])

                    runtime = (
                        target
                        / ".agent-harnesses"
                        / "runtime"
                        / package_id
                        / value["release"]["version"]
                    )
                    for relative in build_release.CORE_OPERATION_FILES:
                        self.assertTrue((runtime / relative).is_file())
                    if package_id == "project-harness":
                        executable = str(runtime / "project_harness.py")
                        run(executable, "init", "--root", str(target), "--dry-run", cwd=runtime)
                        run(executable, "init", "--root", str(target), cwd=runtime)
                        run(executable, "verify", "--root", str(target), cwd=runtime)
                    elif package_id == "workspace-coordination":
                        executable = str(runtime / "workspace_coordination.py")
                        prefix = [executable, "--root", str(target)]
                        run(*prefix, "init", "--dry-run", cwd=runtime)
                        run(*prefix, "init", "--apply", cwd=runtime)
                        child = [
                            "--id",
                            "alpha",
                            "--path",
                            "child-alpha",
                            "--owner",
                            "AGENTS.md",
                        ]
                        run(*prefix, "add", *child, "--dry-run", cwd=runtime)
                        run(*prefix, "add", *child, "--apply", cwd=runtime)
                        run(*prefix, "verify", cwd=runtime)
                    elif package_id == "cross-project":
                        executable = str(runtime / "scripts" / "cross_project.py")
                        registration = [
                            "--front",
                            "alpha",
                            "--name",
                            "Alpha",
                            "--path",
                            "projects/alpha",
                            "--role",
                            "Produces one synthetic component",
                            "--next",
                            "Validate the first slice",
                        ]
                        run(
                            executable,
                            "hq-init",
                            "--root",
                            str(target),
                            "--dry-run",
                            *registration,
                            cwd=runtime,
                        )
                        run(
                            executable,
                            "hq-init",
                            "--root",
                            str(target),
                            *registration,
                            cwd=runtime,
                        )
                        run(executable, "hq-sync", "--root", str(target), cwd=runtime)
                    else:
                        executable = str(runtime / "hq.py")
                        prefix = [executable, "--root", str(target), "--json"]
                        registration = [
                            "--id",
                            "alpha",
                            "--name",
                            "Alpha",
                            "--path",
                            "fronts/alpha",
                        ]
                        run(*prefix, "init", *registration, "--dry-run", cwd=runtime)
                        run(*prefix, "init", *registration, "--apply", cwd=runtime)
                        run(*prefix, "hq-sync", cwd=runtime)

                    verified = run(installer, "verify", *common, cwd=bundle)
                    result = json.loads(verified.stdout)
                    self.assertEqual("ready", result["phase"])
                    self.assertTrue(result["ready"])

    def test_existing_output_is_never_reused_or_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_bytes(b"keep\n")

            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.build_release(
                    output,
                    source_commit=SYNTHETIC_COMMIT,
                    repository_root=REPOSITORY_ROOT,
                )

            self.assertEqual(b"keep\n", sentinel.read_bytes())
            self.assertEqual(["sentinel.txt"], [path.name for path in output.iterdir()])

    def test_tampered_asset_and_wrong_commit_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            output = self._build(parent, "tampered")
            first_zip = next(output.glob("*.zip"))
            first_zip.write_bytes(first_zip.read_bytes() + b"tampered")

            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.verify_release(
                    output,
                    source_commit=SYNTHETIC_COMMIT,
                    repository_root=REPOSITORY_ROOT,
                )
            clean = self._build(parent, "clean")
            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.verify_release(
                    clean,
                    source_commit="2" * 40,
                    repository_root=REPOSITORY_ROOT,
                )


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (
            REPOSITORY_ROOT / ".github/workflows/release.yml"
        ).read_text(encoding="utf-8")

    def test_workflow_is_manual_and_actions_are_sha_pinned(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("tags:", self.workflow)
        self.assertIn('"v*"', self.workflow)
        self.assertNotIn("pull_request_target", self.workflow)
        action_lines = [
            line.strip() for line in self.workflow.splitlines() if "uses:" in line
        ]
        self.assertTrue(action_lines)
        for line in action_lines:
            self.assertRegex(line, r"uses: [^@\s]+@[0-9a-f]{40}(?:\s+#.*)?$")

    def test_write_permission_exists_only_on_release_job(self) -> None:
        self.assertEqual(1, self.workflow.count("contents: write"))
        self.assertGreaterEqual(self.workflow.count("contents: read"), 2)
        release_job = self.workflow.index("  release:")
        write_permission = self.workflow.index("contents: write")
        self.assertGreater(write_permission, release_job)

    def test_workflow_builds_once_and_tests_the_same_bytes(self) -> None:
        self.assertEqual(1, self.workflow.count("build_release.py build"))
        self.assertGreaterEqual(self.workflow.count("build_release.py verify"), 2)
        self.assertIn("actions/upload-artifact", self.workflow)
        self.assertIn("actions/download-artifact", self.workflow)

    def test_workflow_refuses_overwrite_and_leaves_a_verified_draft(self) -> None:
        self.assertNotIn("--clobber", self.workflow)
        self.assertNotIn("--latest", self.workflow)
        self.assertNotIn("gh release edit", self.workflow)
        guard = self.workflow.index("gh release view")
        create = self.workflow.index("gh release create")
        download = self.workflow.index("gh release download")
        final_verify = self.workflow.rindex("build_release.py verify")
        self.assertLess(guard, create)
        self.assertLess(create, download)
        self.assertLess(download, final_verify)
        self.assertIn("--draft", self.workflow[create:download])

    def test_tag_push_rebuilds_without_recreating_the_release(self) -> None:
        release_job = self.workflow.index("  release:")
        release_guard = self.workflow.index(
            "if: github.event_name == 'workflow_dispatch'",
            release_job,
        )
        release_needs = self.workflow.index("needs: build", release_job)
        self.assertLess(release_guard, release_needs)

    def test_run_blocks_do_not_interpolate_dispatch_inputs_directly(self) -> None:
        in_run = False
        for line in self.workflow.splitlines():
            stripped = line.strip()
            if stripped.startswith("run:"):
                in_run = True
                continue
            if in_run and re.match(r"^\s{6}-\s+name:", line):
                in_run = False
            if in_run:
                self.assertNotIn("${{ inputs.", line)


if __name__ == "__main__":
    unittest.main()
