"""Deterministic release packaging and workflow safety tests."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

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
            self.assertNotIn("SHA256SUMS", verified)

    def test_manifest_binds_commit_tag_sizes_and_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self._build(Path(directory))
            files = _files(output)
            manifest = json.loads(files[build_release.RELEASE_MANIFEST_NAME])
            value = product.load_product(REPOSITORY_ROOT)

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
            expected = (
                "https://github.com/fabianomag/agent-harnesses/releases/"
                "download/v0.2.0/release-manifest.json"
            )
            self.assertEqual(expected, snapshot["releaseManifest"]["url"])

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
