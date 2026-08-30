"""Tests for deterministic common artifacts and package installation."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from tools import build_common, catalog, package_manager, product, run_checks, validate


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE_DIAGRAM_URL = product.load_product(REPOSITORY_ROOT)["release"]["site"][
    "en"
]


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    snapshot: list[tuple[str, str, int, str]] = []
    for path in sorted(
        root.rglob("*"),
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    ):
        kind = "directory" if path.is_dir() else "file"
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        snapshot.append(
            (
                path.relative_to(root).as_posix(),
                kind,
                path.stat().st_mtime_ns,
                digest,
            )
        )
    return tuple(snapshot)


def _run_success(
    *arguments: str,
    cwd: Path = REPOSITORY_ROOT,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    process = subprocess.run(
        [sys.executable, "-B", *arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise AssertionError(process.stdout + process.stderr)
    return process


def _assert_documented(installed_package: Path, literal: str) -> None:
    readme = (installed_package / "README.md").read_text(encoding="utf-8")
    if literal not in readme:
        raise AssertionError(
            "installed first-use command is not documented: "
            f"{installed_package.name}"
        )


def _load_test_module(name: str, path: Path):
    """Load one package CLI without relying on repository-wide import paths."""

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load CLI module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CatalogIntegrationTests(unittest.TestCase):
    def test_catalog_is_canonical_and_matches_all_manifests(self) -> None:
        checked_path = REPOSITORY_ROOT / catalog.CATALOG_PATH
        checked = catalog.load_json_strict(checked_path)
        expected = catalog.expected_catalog(REPOSITORY_ROOT)

        self.assertEqual(expected, checked)
        self.assertEqual(
            catalog.canonical_json_bytes(expected),
            checked_path.read_bytes(),
        )
        self.assertEqual(
            list(catalog.PACKAGE_ORDER),
            [entry["id"] for entry in checked["packages"]],
        )
        self.assertEqual(
            ["0.2.2", "0.2.2", "0.2.2", "0.2.2"],
            [entry["version"] for entry in checked["packages"]],
        )
        self.assertEqual(
            ["implemented"] * 4,
            [
                entry["artifactStatus"]["implementation"]
                for entry in checked["packages"]
            ],
        )
        self.assertEqual(
            ["published"] * 4,
            [
                entry["artifactStatus"]["publication"]
                for entry in checked["packages"]
            ],
        )
        license_bytes = (REPOSITORY_ROOT / "LICENSE").read_bytes()
        self.assertEqual(
            hashlib.sha256(license_bytes).hexdigest(),
            checked["licenseFile"]["sha256"],
        )

    def test_catalog_profiles_are_complete_evidence_bound_and_non_ranking(
        self,
    ) -> None:
        checked = catalog.load_json_strict(REPOSITORY_ROOT / catalog.CATALOG_PATH)
        self.assertEqual(2, checked["schemaVersion"])
        self.assertEqual(
            list(catalog.BADGE_LEVELS),
            checked["badgeScale"]["levels"],
        )
        self.assertFalse(checked["badgeScale"]["packageRanking"])
        self.assertFalse(checked["evolutionModel"]["ranking"])
        compatibility = checked["agentCompatibility"]
        self.assertEqual("compatible", compatibility["codex"]["status"])
        self.assertEqual("pending", compatibility["codex"]["verification"])
        self.assertFalse(compatibility["codex"]["verifiedEligible"])
        self.assertEqual(
            "compatible",
            compatibility["otherAgents"]["status"],
        )
        self.assertEqual(
            "unverified",
            compatibility["otherAgents"]["verification"],
        )
        self.assertFalse(compatibility["otherAgents"]["verifiedEligible"])

        for entry in checked["packages"]:
            self.assertTrue(entry["purpose"])
            self.assertTrue(entry["complexity"]["description"])
            self.assertFalse(entry["evolutionaryPosition"]["ranking"])
            self.assertTrue(entry["audience"]["description"])
            self.assertTrue(entry["limitations"])
            self.assertEqual(
                list(catalog.BADGE_NAMES),
                list(entry["badges"]),
            )
            for badge in entry["badges"].values():
                self.assertIn(badge["level"], catalog.BADGE_LEVELS)
                self.assertNotEqual("verified", badge["level"])
                self.assertTrue(badge["evidence"])
                for evidence in badge["evidence"]:
                    self.assertIn(
                        evidence["method"],
                        {"automated", "structural"},
                    )
                    self.assertTrue(
                        (REPOSITORY_ROOT / evidence["path"]).is_file()
                    )
                    self.assertTrue(evidence["claim"])

            self.assertEqual(
                ("automated", "defined"),
                (
                    entry["evidence"]["automated"]["method"],
                    entry["evidence"]["automated"]["status"],
                ),
            )
            self.assertEqual(
                ("structural", "defined"),
                (
                    entry["evidence"]["structural"]["method"],
                    entry["evidence"]["structural"]["status"],
                ),
            )
            self.assertEqual(
                ("manual-codex", "pending"),
                (
                    entry["evidence"]["manualCodex"]["method"],
                    entry["evidence"]["manualCodex"]["status"],
                ),
            )
            self.assertNotIn("publication", entry["evidence"]["manualCodex"])
            skill_claims = [
                item["claim"] for item in entry["badges"]["Skill"]["evidence"]
            ]
            self.assertFalse(
                any("pending" in claim.lower() for claim in skill_claims)
            )
            self.assertTrue(
                any(
                    "optional" in claim.lower()
                    and "outside" in claim.lower()
                    and (
                        "not installed" in claim.lower()
                        or "no adapter is installed" in claim.lower()
                    )
                    for claim in skill_claims
                )
            )
            self.assertFalse(any("is published" in claim.lower() for claim in skill_claims))

    def test_published_links_are_complete_https_urls(self) -> None:
        checked = catalog.load_json_strict(REPOSITORY_ROOT / catalog.CATALOG_PATH)
        expected_kinds = {
            "documentation",
            "prompt",
            "source",
            "release",
            "interactiveDiagram",
        }
        for entry in checked["packages"]:
            self.assertEqual(expected_kinds, set(entry["immutableLinks"]))
            for link_name, link in entry["immutableLinks"].items():
                if link_name == "interactiveDiagram":
                    self.assertEqual("planned", link["status"])
                    continue
                self.assertEqual("published", link["status"])
                self.assertTrue(link["url"].startswith("https://"))
            self.assertTrue(
                entry["immutableLinks"]["interactiveDiagram"]["url"].startswith(
                    "https://"
                )
            )
            self.assertEqual(
                INTERACTIVE_DIAGRAM_URL,
                entry["immutableLinks"]["interactiveDiagram"]["url"],
            )
            prompt_url = entry["immutableLinks"]["prompt"]["url"]
            self.assertIn(entry["id"], prompt_url)
            self.assertIn(entry["version"], prompt_url)
            self.assertTrue(prompt_url.endswith(".zip"))

    def test_catalog_schema_enforces_exact_packages_badges_and_link_state(
        self,
    ) -> None:
        schema = catalog.load_json_strict(
            REPOSITORY_ROOT / "schemas" / "harness-catalog.schema.json"
        )
        checked = catalog.load_json_strict(REPOSITORY_ROOT / catalog.CATALOG_PATH)
        self.assertEqual(
            [],
            validate.validate_schema_instance(
                checked,
                schema,
                artifact=catalog.CATALOG_PATH.as_posix(),
            ),
        )
        self.assertEqual(4, len(schema["properties"]["packages"]["prefixItems"]))
        self.assertFalse(schema["properties"]["packages"]["items"])
        self.assertEqual(
            list(catalog.BADGE_LEVELS),
            [
                item["const"]
                for item in schema["properties"]["badgeScale"]["properties"][
                    "levels"
                ]["prefixItems"]
            ],
        )
        self.assertEqual(
            list(catalog.BADGE_NAMES),
            schema["$defs"]["package"]["properties"]["badges"]["required"],
        )

        wrong_order = json.loads(json.dumps(checked))
        wrong_order["packages"][0], wrong_order["packages"][1] = (
            wrong_order["packages"][1],
            wrong_order["packages"][0],
        )
        wrong_order_issues = validate.validate_schema_instance(
            wrong_order,
            schema,
            artifact="synthetic-catalog.json",
        )
        self.assertIn(
            "SCHEMA_CONST",
            {issue.code for issue in wrong_order_issues},
        )

        mutable_urls = {
            "documentation": (
                "https://github.com/fabianomag/agent-harnesses/blob/main/"
                "packages/project-harness/README.md"
            ),
            "prompt": (
                "https://github.com/fabianomag/agent-harnesses/releases/"
                "latest/download/project-harness-0.2.2.zip"
            ),
            "source": (
                "https://github.com/fabianomag/agent-harnesses/tree/main/"
                "packages/project-harness"
            ),
            "release": (
                "https://github.com/fabianomag/agent-harnesses/releases/latest"
            ),
            "interactiveDiagram": "https://example.invalid/latest",
        }
        for link_name, mutable_url in mutable_urls.items():
            with self.subTest(link_name=link_name):
                mutant = json.loads(json.dumps(checked))
                mutant["packages"][0]["immutableLinks"][link_name][
                    "url"
                ] = mutable_url
                url_issues = validate.validate_schema_instance(
                    mutant,
                    schema,
                    artifact="synthetic-catalog.json",
                )
                self.assertTrue(
                    {"SCHEMA_PATTERN", "SCHEMA_CONST"}
                    & {issue.code for issue in url_issues},
                )

        mismatched = json.loads(json.dumps(checked))
        mismatched["packages"][0]["immutableLinks"]["prompt"]["url"] = (
            checked["packages"][1]["immutableLinks"]["prompt"]["url"]
        )
        mismatch_issues = validate.validate_schema_instance(
            mismatched,
            schema,
            artifact="synthetic-catalog.json",
        )
        self.assertIn(
            "SCHEMA_CONST",
            {issue.code for issue in mismatch_issues},
        )

        mutable_evidence = json.loads(json.dumps(checked))
        mutable_evidence["packages"][0]["evidence"]["manualCodex"][
            "status"
        ] = "verified"
        evidence_issues = validate.validate_schema_instance(
            mutable_evidence,
            schema,
            artifact="synthetic-catalog.json",
        )
        self.assertTrue(
            {"SCHEMA_CONST"}
            & {issue.code for issue in evidence_issues},
        )

    def test_generated_graph_expresses_membership_without_package_edges(self) -> None:
        graph = json.loads(
            (REPOSITORY_ROOT / catalog.GRAPH_SPEC_PATH).read_text(
                encoding="utf-8"
            )
        )
        package_ids = set(catalog.PACKAGE_ORDER)
        self.assertEqual(
            INTERACTIVE_DIAGRAM_URL,
            graph["interactiveDiagram"],
        )
        self.assertEqual(
            {
                ("agent-harnesses", package_id, "contains")
                for package_id in catalog.PACKAGE_ORDER
            },
            {
                (edge["from"], edge["to"], edge["kind"])
                for edge in graph["edges"]
            },
        )
        self.assertFalse(
            any(
                edge["from"] in package_ids and edge["to"] in package_ids
                for edge in graph["edges"]
            )
        )

    def test_four_package_graphs_and_assets_are_distinct(self) -> None:
        checked = catalog.load_json_strict(REPOSITORY_ROOT / catalog.CATALOG_PATH)
        expected_labels = {
            "project-harness": [
                "Skill trigger",
                "Initializer",
                "Local context",
                "Work cycle",
                "Finalizer",
                "Durable next",
            ],
            "workspace-coordination": [
                "Workspace coordinator",
                "Child index",
                "Shared boundary / governance",
                "Child-local owner",
                "Reflection",
            ],
            "cross-project": [
                "Named target",
                "Manifest",
                "Structural sync",
                "Front state",
                "Local owner",
                "Transversal reflection",
            ],
            "orchestration": [
                "Strategic opening",
                "Registry validation",
                "Dry-run",
                "Transactional apply / rollback",
                "Pending reflection",
                "Verified sync",
            ],
        }
        graph_bytes: set[bytes] = set()
        asset_bytes: set[bytes] = set()
        observed_specs: set[str] = set()
        observed_assets: set[str] = set()

        for entry in checked["packages"]:
            graph_reference = entry["graph"]
            observed_specs.add(graph_reference["spec"])
            observed_assets.add(graph_reference["staticAsset"])
            graph_content = (
                REPOSITORY_ROOT / graph_reference["spec"]
            ).read_bytes()
            asset_content = (
                REPOSITORY_ROOT / graph_reference["staticAsset"]
            ).read_bytes()
            graph_bytes.add(graph_content)
            asset_bytes.add(asset_content)
            graph = json.loads(graph_content)

            self.assertEqual(graph_reference["id"], graph["id"])
            self.assertEqual(entry["id"], graph["package"]["id"])
            self.assertEqual(entry["version"], graph["package"]["version"])
            self.assertEqual(
                entry["artifactStatus"],
                graph["package"]["artifactStatus"],
            )
            self.assertEqual(
                INTERACTIVE_DIAGRAM_URL,
                graph["source"]["interactiveDiagram"],
            )
            self.assertEqual(
                expected_labels[entry["id"]],
                [node["label"] for node in graph["nodes"]],
            )
            self.assertEqual(
                [
                    (current["id"], following["id"], "next")
                    for current, following in zip(
                        graph["nodes"],
                        graph["nodes"][1:],
                    )
                ],
                [
                    (edge["from"], edge["to"], edge["kind"])
                    for edge in graph["edges"]
                ],
            )

            root = ET.fromstring(asset_content)
            self.assertEqual(graph_reference["id"], root.attrib["data-graph-id"])
            self.assertEqual(entry["id"], root.attrib["data-package-id"])
            self.assertFalse(
                any(element.tag.endswith("image") for element in root.iter())
            )
            asset_text = asset_content.decode("utf-8")
            for label in expected_labels[entry["id"]]:
                for label_part in catalog._svg_label_lines(label):
                    self.assertIn(label_part, asset_text)

        self.assertEqual(4, len(observed_specs))
        self.assertEqual(4, len(observed_assets))
        self.assertEqual(4, len(graph_bytes))
        self.assertEqual(4, len(asset_bytes))

    def test_generated_artifact_bytes_are_hash_seed_independent(self) -> None:
        script = (
            "import hashlib,json;"
            "from pathlib import Path;"
            "from tools import catalog;"
            "root=Path('.').resolve();"
            "print(json.dumps({p.as_posix():hashlib.sha256(b).hexdigest() "
            "for p,b in catalog.generated_artifacts(root).items()},sort_keys=True))"
        )
        outputs: list[str] = []
        for seed in ("1", "987654"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            process = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=REPOSITORY_ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_generated_check_rejects_stale_managed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            (root / "graphs").mkdir()
            (root / "assets").mkdir()
            expected = {catalog.CATALOG_PATH: b"{}\n"}
            (root / catalog.CATALOG_PATH).write_bytes(b"{}\n")
            (root / "graphs" / "stale.graph.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (root / "assets" / "stale.svg").write_text(
                "<svg/>\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                catalog,
                "generated_artifacts",
                return_value=expected,
            ):
                drift = build_common.check(root)
            self.assertEqual(
                ["assets/stale.svg", "graphs/stale.graph.json"],
                drift,
            )

    def test_all_generated_artifacts_match_expected_bytes(self) -> None:
        self.assertEqual([], build_common.check(REPOSITORY_ROOT))

    def test_duplicate_json_properties_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"value": 1, "value": 2}\n', encoding="utf-8")
            with self.assertRaises(catalog.CommonContractError):
                catalog.load_json_strict(path)

    def test_optional_skill_adapters_are_valid_and_outside_packages(self) -> None:
        checked = catalog.load_json_strict(REPOSITORY_ROOT / catalog.CATALOG_PATH)
        observed: dict[str, str] = {}
        for entry in checked["packages"]:
            packaged_skill_paths = [
                item["path"]
                for item in entry["files"]
                if item["path"].endswith("SKILL.md")
            ]
            self.assertEqual([], packaged_skill_paths)
            skill_path = catalog.SKILL_PATHS[entry["id"]]
            self.assertTrue(skill_path.startswith("adapters/openai/"))
            skill_text = (
                REPOSITORY_ROOT
                / skill_path
            ).read_text(encoding="utf-8")
            frontmatter = catalog.parse_skill_frontmatter(
                skill_text,
                package_id=entry["id"],
            )
            observed[entry["id"]] = frontmatter["description"]
        self.assertEqual(set(catalog.PACKAGE_ORDER), set(observed))

    def test_invalid_optional_skill_frontmatter_is_rejected(self) -> None:
        invalid = (
            "# Missing frontmatter\n",
            "---\nname: wrong\ndescription: Synthetic.\n---\n# Body\n",
            (
                "---\nname: project-harness\nname: project-harness\n"
                "description: Synthetic.\n---\n# Body\n"
            ),
            (
                "---\nname: project-harness\ndescription: Synthetic.\n"
                "unknown: value\n---\n# Body\n"
            ),
        )
        for text in invalid:
            with self.subTest(text=text):
                with self.assertRaises(catalog.CommonContractError):
                    catalog.parse_skill_frontmatter(
                        text,
                        package_id="project-harness",
                    )

    def test_root_and_package_readmes_cover_the_public_contract(self) -> None:
        root_readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        pt_readme = (REPOSITORY_ROOT / "README.pt-BR.md").read_text(encoding="utf-8")
        product_value = product.load_product(REPOSITORY_ROOT)
        for phrase in (
            "## What do you need to coordinate?",
            "## Copy one install prompt",
            "## Manual install",
            "Technical evidence",
            INTERACTIVE_DIAGRAM_URL,
        ):
            self.assertIn(phrase, root_readme)
        self.assertIn("## O que você precisa coordenar?", pt_readme)
        self.assertIn("## Copie um único prompt de instalação", pt_readme)

        for definition in product_value["packages"]:
            package_id = definition["id"]
            english_prompt = product.install_prompt(product_value, definition, "en")
            portuguese_prompt = product.install_prompt(product_value, definition, "ptBr")
            self.assertEqual(1, root_readme.count(f"```text\n{english_prompt}\n```"))
            self.assertEqual(1, pt_readme.count(f"```text\n{portuguese_prompt}\n```"))
            readme = (
                REPOSITORY_ROOT / "packages" / package_id / "README.md"
            ).read_text(encoding="utf-8")
            localized = (
                REPOSITORY_ROOT / "packages" / package_id / "README.pt-BR.md"
            ).read_text(encoding="utf-8")
            for decision in ("**Best for:**", "**Not for:**", "**What it changes:**"):
                self.assertIn(decision, readme)
                self.assertLess(readme.index(decision), readme.index("## Installation"))
            self.assertIn(english_prompt, readme)
            self.assertIn(portuguese_prompt, localized)
            self.assertTrue((REPOSITORY_ROOT / "packages" / package_id / "docs/REFERENCE.md").is_file())

        self.assertNotIn("releases/latest/download", root_readme)
        self.assertIn("ready", root_readme)
        self.assertIn("private Codex runtime", root_readme)
        self.assertIn("ZIP with its matching checksum sidecar", root_readme)
        self.assertIn("ZIP da release", pt_readme)
        self.assertIn("checksum sidecar correspondente", pt_readme)

        issue_form = (
            REPOSITORY_ROOT
            / ".github"
            / "ISSUE_TEMPLATE"
            / "installation-report.yml"
        ).read_text(encoding="utf-8")
        for package_id in catalog.PACKAGE_ORDER:
            self.assertIn(f"- {package_id}", issue_form)
        for safe_phrase in (
            "private identifiers",
            "private paths and absolute local paths",
            "full logs",
            "synthetic, minimal reproduction details",
        ):
            self.assertIn(safe_phrase, issue_form)

        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")
        for os_label in ("ubuntu-latest", "macos-latest", "windows-latest"):
            self.assertIn(f"- {os_label}", workflow)
        for package_id in catalog.PACKAGE_ORDER:
            self.assertIn(f"- {package_id}", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("manual_walkthrough", workflow)
        self.assertIn("persist-credentials: false", workflow)

        attributes = (REPOSITORY_ROOT / ".gitattributes").read_text(
            encoding="utf-8"
        )
        self.assertIn("* text=auto eol=lf", attributes)

    def test_pt_br_readmes_preserve_essential_operational_limits(self) -> None:
        expected = {
            "project-harness": {
                "en": (
                    "Package version and state schema are independent.",
                    "never coordinates sibling roots or external services",
                    "uninstall removes only unchanged",
                ),
                "ptBr": (
                    "Package version e state schema são independentes.",
                    "não coordena roots irmãs nem serviços externos",
                    "uninstall remove somente bytes inalterados",
                ),
            },
            "workspace-coordination": {
                "en": (
                    'open --child "<child-id>"',
                    "one mutating writer per coordinator root",
                    "serialize writers",
                ),
                "ptBr": (
                    'open --child "<id-do-projeto-filho>"',
                    "single writer",
                    "serialize os writers",
                ),
            },
            "cross-project": {
                "en": (
                    "Rollback covers catchable cooperative failures",
                    "not power loss or adversarial root replacement",
                ),
                "ptBr": (
                    "rollback cobre falhas capturáveis entre processos cooperativos",
                    "não power loss nem substituição adversarial da raiz",
                ),
            },
            "orchestration": {
                "en": (
                    "Mutations use a journal and explicit recovery",
                    "never executes registered projects",
                ),
                "ptBr": (
                    "As mutações usam journal e recovery explícito",
                    "nunca executa os projetos cadastrados",
                ),
            },
        }
        for package_id, locales in expected.items():
            for language, required in locales.items():
                name = "README.md" if language == "en" else "README.pt-BR.md"
                readme = (
                    REPOSITORY_ROOT / "packages" / package_id / name
                ).read_text(encoding="utf-8")
                normalized_readme = " ".join(readme.split())
                with self.subTest(package_id=package_id, language=language):
                    for phrase in required:
                        self.assertIn(phrase, normalized_readme)

        workspace_pt = (
            REPOSITORY_ROOT
            / "packages/workspace-coordination/README.pt-BR.md"
        ).read_text(encoding="utf-8")
        project_pt = (
            REPOSITORY_ROOT / "packages/project-harness/README.pt-BR.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "todos os projetos filhos e owner paths registrados são",
            " ".join(workspace_pt.split()),
        )
        self.assertNotIn("A\n[guia operacional]", project_pt)

    def test_operator_contracts_are_generated_from_one_schema_two_source(self) -> None:
        value = product.load_product(REPOSITORY_ROOT)
        snapshot = product.site_snapshot(value)
        self.assertEqual(2, value["schemaVersion"])
        self.assertEqual(2, snapshot["schemaVersion"])
        snapshot_packages = {item["id"]: item for item in snapshot["packages"]}

        public_text: list[str] = [json.dumps(snapshot, ensure_ascii=False)]
        readiness_sets: set[tuple[str, ...]] = set()
        for definition in value["packages"]:
            package_id = definition["id"]
            package_root = REPOSITORY_ROOT / "packages" / package_id
            operations_path = package_root / "operations.json"
            operations = json.loads(operations_path.read_text(encoding="utf-8"))
            self.assertEqual(product.operations_document(value, definition), operations)
            self.assertEqual(
                product.EXPECTED_OPERATIONS[package_id],
                tuple(item["command"] for item in operations["operations"]),
            )
            self.assertEqual(definition["operator"], snapshot_packages[package_id]["operator"])
            self.assertEqual(definition["operator"]["memory"], operations["memory"])

            readiness = tuple(definition["operator"]["installationReadiness"]["en"])
            self.assertGreaterEqual(len(readiness), 3)
            readiness_sets.add(readiness)
            for language, guide_name in (
                ("en", "OPERATOR_GUIDE.md"),
                ("ptBr", "OPERATOR_GUIDE.pt-BR.md"),
            ):
                guide = (package_root / guide_name).read_text(encoding="utf-8")
                self.assertEqual(
                    product.operator_guide(value, definition, language).rstrip() + "\n",
                    guide,
                )
                prompt = product.install_prompt(value, definition, language)
                for item in definition["operator"]["installationReadiness"][language]:
                    self.assertIn(item, guide)
                    self.assertIn(item, prompt)
                public_text.extend((guide, prompt))
            public_text.extend(
                (
                    (package_root / "README.md").read_text(encoding="utf-8"),
                    (package_root / "README.pt-BR.md").read_text(encoding="utf-8"),
                )
            )

        self.assertEqual(4, len(readiness_sets))
        rendered_public = "\n".join(public_text)
        self.assertIsNone(re.search(r"\b(?:alpha|beta)\b", rendered_public, re.IGNORECASE))
        self.assertTrue(value["tutorial"]["requiredAfterReady"])
        self.assertEqual("conversation", value["tutorial"]["delivery"])
        smoke_en = value["compatibility"]["smoke"]["description"]["en"]
        smoke_pt = value["compatibility"]["smoke"]["description"]["ptBr"]
        self.assertIn("release acceptance requires", smoke_en)
        self.assertIn("does not claim complete agent equivalence", smoke_en)
        self.assertIn("a aceitação da release exige", smoke_pt)
        self.assertIn("não afirma equivalência completa", smoke_pt)
        self.assertNotIn("validated by a copied-prompt smoke", rendered_public)

    def test_operator_guides_teach_safe_package_lifecycle_in_both_languages(
        self,
    ) -> None:
        value = product.load_product(REPOSITORY_ROOT)
        for definition in value["packages"]:
            package_id = definition["id"]
            receipt = (
                f".agent-harnesses/runtime/{package_id}/"
                f"{value['release']['version']}/"
                ".agent-harness-receipt.json"
            )
            dry_run = (
                f'<python> -B installer.py uninstall {package_id} '
                '--target "<target>" --dry-run --json'
            )
            apply = (
                f'<python> -B installer.py uninstall {package_id} '
                '--target "<target>" --apply --json'
            )
            for language, guide_name in (
                ("en", "OPERATOR_GUIDE.md"),
                ("ptBr", "OPERATOR_GUIDE.pt-BR.md"),
            ):
                guide = (
                    REPOSITORY_ROOT / "packages" / package_id / guide_name
                ).read_text(encoding="utf-8")
                normalized_guide = " ".join(guide.split())
                prompt = product.install_prompt(value, definition, language)
                with self.subTest(package_id=package_id, language=language):
                    self.assertIn(receipt, normalized_guide)
                    self.assertIn(dry_run, normalized_guide)
                    self.assertIn(apply, normalized_guide)
                    self.assertIn("ready=true", normalized_guide)
                    if language == "en":
                        required = (
                            "Uninstall removes only the receipt-owned runtime",
                            "never removes initialized operational state",
                            "first run this package's verify-or-recover workflow",
                            "Preserve and report any residual initialized state",
                            "matching checksum sidecar",
                            "read its migration notes",
                            "Do not edit a versioned runtime in place",
                            "keep the old version until the new one reaches ready=true",
                            "in the user's language",
                            "any global agent adapter",
                        )
                    else:
                        required = (
                            "Uninstall remove somente o runtime pertencente ao receipt",
                            "nunca remove o estado operacional inicializado",
                            "primeiro execute o workflow de verify ou recovery",
                            "Preserve e informe qualquer estado inicializado residual",
                            "checksum sidecar correspondentes",
                            "leia as migration notes",
                            "Não edite um runtime versionado in-place",
                            "mantenha a versão anterior até a nova chegar a ready=true",
                            "no idioma do usuário",
                            "qualquer adapter global de agente",
                        )
                    for phrase in required:
                        self.assertIn(phrase, normalized_guide)
                    self.assertIn(value["tutorial"]["constraints"][language], prompt)

    def test_every_operator_example_parses_with_the_real_cli(self) -> None:
        project_cli = _load_test_module(
            "_operator_example_project_harness",
            REPOSITORY_ROOT / "packages/project-harness/project_harness.py",
        )
        workspace_cli = _load_test_module(
            "_operator_example_workspace_coordination",
            REPOSITORY_ROOT
            / "packages/workspace-coordination/workspace_coordination.py",
        )
        cross_project_cli = _load_test_module(
            "_operator_example_cross_project",
            REPOSITORY_ROOT / "packages/cross-project/scripts/cross_project.py",
        )
        orchestration_root = REPOSITORY_ROOT / "packages/orchestration"
        with mock.patch.object(
            sys,
            "path",
            [str(orchestration_root), *sys.path],
        ):
            orchestration_cli = importlib.import_module("orchestration_harness.cli")

        parsers = {
            "project-harness": project_cli._parse_args,
            "workspace-coordination": workspace_cli._build_parser().parse_args,
            "cross-project": cross_project_cli.parser().parse_args,
            "orchestration": orchestration_cli._parser().parse_args,
        }
        value = product.load_product(REPOSITORY_ROOT)
        for definition in value["packages"]:
            package_id = definition["id"]
            observed_commands: list[str] = []
            for operation in definition["operator"]["operations"]:
                with self.subTest(
                    package_id=package_id,
                    command=operation["command"],
                ):
                    rendered = re.sub(
                        r"<([^<>]+)>",
                        lambda match: (
                            match.group(1).split("|", maxsplit=1)[0]
                            if "|" in match.group(1)
                            else "value"
                        ),
                        operation["example"],
                    )
                    arguments = shlex.split(rendered)
                    self.assertEqual("value", arguments[0])
                    self.assertEqual("-B", arguments[1])
                    self.assertEqual(
                        definition["operator"]["entrypoint"],
                        arguments[2],
                    )
                    errors = io.StringIO()
                    try:
                        with contextlib.redirect_stderr(errors):
                            parsed = parsers[package_id](arguments[3:])
                    except SystemExit as error:
                        self.fail(
                            "operator example does not parse with its real CLI: "
                            f"{error}; {errors.getvalue().strip()}"
                        )
                    self.assertEqual(operation["command"], parsed.command)
                    observed_commands.append(parsed.command)
            self.assertEqual(
                product.EXPECTED_OPERATIONS[package_id],
                tuple(observed_commands),
            )

    def test_security_policy_matches_standalone_installer_contract(self) -> None:
        policy = (REPOSITORY_ROOT / "SECURITY.md").read_text(encoding="utf-8")
        local_heading = "## Local safety boundary"
        next_heading = "## Public-safety validation"
        self.assertIn(local_heading, policy)
        self.assertIn(next_heading, policy)
        local_boundary = policy.split(local_heading, maxsplit=1)[1].split(
            next_heading,
            maxsplit=1,
        )[0]
        normalized = " ".join(local_boundary.split())
        required_claims = (
            "`doctor` is read-only.",
            "`install --dry-run` verifies the selected bundle inventory and "
            "target compatibility without writing.",
            "It does not change `PATH`, install a global Skill, edit "
            "`.gitignore`, initialize the target, or edit unrelated "
            "documentation.",
            "A failed or interrupted installer-owned download, extraction, "
            "or pre-publication stage is cleaned up.",
            "`uninstall` removes only unchanged receipt-owned runtime bytes",
            "returns `ready: true` only after the selected runtime verifies "
            "an initialized target.",
            "Installed but uninitialized targets fail with `E_NOT_READY`.",
        )
        for claim in required_claims:
            self.assertIn(claim, normalized)

        obsolete_claims = (
            "root-local lock serializes cooperating installers",
            "unchanged-residual",
            "never removes residual stages automatically",
            "common package manager requires",
        )
        for claim in obsolete_claims:
            self.assertNotIn(claim, normalized)

        reporting = " ".join(policy.split("## Reporting", maxsplit=1)[1].split())
        self.assertIn("private vulnerability reporting", reporting)
        self.assertIn("before any tag or release", reporting)
        self.assertIn("Report a vulnerability", reporting)
        self.assertIn(
            "Installation Report Issue Form is not a security channel",
            reporting,
        )

    def test_root_readme_keeps_install_state_clear_and_internals_advanced(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        normalized = " ".join(readme.split())
        self.assertIn(
            "`downloaded → installed → initialized → verified → ready`",
            normalized,
        )
        self.assertIn('Only a successful `verify` result with `"ready": true`', normalized)
        self.assertIn("receipt-owned runtime bytes", normalized)
        self.assertNotIn("unique root-local name", normalized)
        self.assertNotIn("unchanged-residual", normalized)
        value = product.load_product(REPOSITORY_ROOT)
        for definition in value["packages"]:
            self.assertEqual(
                1,
                readme.count(product.install_prompt(value, definition, "en")),
            )


class RunnerEvidenceTests(unittest.TestCase):
    def test_runner_success_does_not_claim_manual_evidence(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = run_checks.run(checks=())
        rendered = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn("MANUAL CODEX: not executed by this runner", rendered)
        self.assertIn(
            "release manifest or evidence asset bound to the exact published "
            "package version and commit",
            rendered,
        )
        self.assertIn("no manual evidence claimed", rendered)
        self.assertNotIn("MANUAL: pending", rendered)


class PackageManagerIntegrationTests(unittest.TestCase):
    def test_dry_run_apply_verify_and_idempotent_reapply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            planned = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=False,
            )
            destination = root / planned.destination_name
            self.assertEqual("planned", planned.action)
            self.assertEqual([], list(root.iterdir()))

            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            installed_license = destination / "LICENSE"
            self.assertIn(
                "Fabiano Magalhães",
                installed_license.read_text(encoding="utf-8"),
            )
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)

            before = _tree_snapshot(destination)
            unchanged = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            after = _tree_snapshot(destination)
            self.assertEqual("unchanged", unchanged.action)
            self.assertEqual(before, after)

    def test_all_four_exact_package_versions_install_and_verify(self) -> None:
        versions = {
            "project-harness": "0.2.2",
            "workspace-coordination": "0.2.2",
            "cross-project": "0.2.2",
            "orchestration": "0.2.2",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            for package_id in catalog.PACKAGE_ORDER:
                result = package_manager.install_package(
                    root=root,
                    package_id=package_id,
                    version=versions[package_id],
                    apply=True,
                )
                self.assertEqual("installed", result.action)
                verified = package_manager.verify_package(
                    root=root,
                    package_id=package_id,
                    version=versions[package_id],
                )
                self.assertEqual("verified", verified.action)
            self.assertEqual(4, len(list(root.iterdir())))

    def test_changed_installation_is_refused_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            readme = root / installed.destination_name / "README.md"
            changed = b"synthetic local change\n"
            readme.write_bytes(changed)

            with self.assertRaises(package_manager.PackageManagerError):
                package_manager.install_package(
                    root=root,
                    package_id="project-harness",
                    version="0.2.2",
                    apply=True,
                )
            self.assertEqual(changed, readme.read_bytes())

    def test_extra_installation_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            destination = root / installed.destination_name
            (destination / "unexpected.txt").write_text(
                "synthetic",
                encoding="utf-8",
            )
            with self.assertRaises(package_manager.PackageManagerError):
                package_manager.verify_package(
                    root=root,
                    package_id="project-harness",
                    version="0.2.2",
                )

    def test_extra_installation_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            destination = root / installed.destination_name
            (destination / "unexpected-empty-directory").mkdir()
            with self.assertRaises(package_manager.PackageManagerError):
                package_manager.verify_package(
                    root=root,
                    package_id="project-harness",
                    version="0.2.2",
                )

    def test_failed_atomic_rename_preserves_stage_for_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            with mock.patch.object(
                package_manager,
                "_publish_no_replace",
                side_effect=OSError("synthetic rename failure"),
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )
            stages = sorted(root.glob(".project-harness-0.2.2.stage-*"))
            self.assertEqual(1, len(stages))
            residual_before = _tree_snapshot(stages[0])
            self.assertTrue((stages[0] / "README.md").is_file())
            self.assertFalse((root / "project-harness-0.2.2").exists())

            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stages[0]))

    def test_interrupt_after_stage_creation_preserves_ambiguous_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            stage_token = "1" * 32
            stage = root / f".project-harness-0.2.2.stage-{stage_token}"
            original_mkdir = Path.mkdir

            def create_stage_then_interrupt(
                path: Path,
                mode: int = 0o777,
                parents: bool = False,
                exist_ok: bool = False,
            ) -> None:
                original_mkdir(
                    path,
                    mode=mode,
                    parents=parents,
                    exist_ok=exist_ok,
                )
                if path == stage:
                    raise KeyboardInterrupt()

            token = mock.Mock(hex=stage_token)
            with (
                mock.patch.object(
                    package_manager.uuid,
                    "uuid4",
                    return_value=token,
                ),
                mock.patch.object(
                    package_manager.Path,
                    "mkdir",
                    new=create_stage_then_interrupt,
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual([stage], list(root.iterdir()))
            self.assertEqual([], list(stage.iterdir()))
            residual_before = _tree_snapshot(stage)
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stage))

    def test_ambiguous_stage_creation_error_is_preserved_and_retry_succeeds(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            stage_token = "3" * 32
            stage = root / f".project-harness-0.2.2.stage-{stage_token}"
            original_mkdir = Path.mkdir

            def create_stage_then_fail(
                path: Path,
                mode: int = 0o777,
                parents: bool = False,
                exist_ok: bool = False,
            ) -> None:
                original_mkdir(
                    path,
                    mode=mode,
                    parents=parents,
                    exist_ok=exist_ok,
                )
                if path == stage:
                    raise OSError("synthetic ambiguous stage creation result")

            token = mock.Mock(hex=stage_token)
            with (
                mock.patch.object(
                    package_manager.uuid,
                    "uuid4",
                    return_value=token,
                ),
                mock.patch.object(
                    package_manager.Path,
                    "mkdir",
                    new=create_stage_then_fail,
                ),
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual([stage], list(root.iterdir()))
            self.assertEqual([], list(stage.iterdir()))
            residual_before = _tree_snapshot(stage)
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stage))

    def test_stage_name_collision_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            stage_token = "2" * 32
            stage = root / f".project-harness-0.2.2.stage-{stage_token}"
            stage.mkdir(mode=0o711)
            sentinel = stage / "sentinel.txt"
            sentinel.write_bytes(b"synthetic existing stage\n")
            before = _tree_snapshot(root)
            before_metadata = stage.stat()

            token = mock.Mock(hex=stage_token)
            with mock.patch.object(
                package_manager.uuid,
                "uuid4",
                return_value=token,
            ):
                with self.assertRaises(package_manager.PackageManagerError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual(before, _tree_snapshot(root))
            after_metadata = stage.stat()
            self.assertEqual(before_metadata.st_dev, after_metadata.st_dev)
            self.assertEqual(before_metadata.st_ino, after_metadata.st_ino)
            self.assertEqual(before_metadata.st_mode, after_metadata.st_mode)
            self.assertEqual(
                before_metadata.st_mtime_ns,
                after_metadata.st_mtime_ns,
            )
            self.assertEqual(b"synthetic existing stage\n", sentinel.read_bytes())
            self.assertFalse((root / "project-harness-0.2.2").exists())

    def test_replaced_stage_is_never_auto_deleted(self) -> None:
        failures = (
            OSError("synthetic failure after stage replacement"),
            KeyboardInterrupt(),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory).resolve(strict=True)
                    replacement: Path | None = None
                    before_metadata: os.stat_result | None = None

                    def replace_stage_then_fail(
                        stage: Path,
                        **_arguments: object,
                    ) -> None:
                        nonlocal replacement, before_metadata
                        shutil.rmtree(stage)
                        stage.mkdir(mode=0o711)
                        (stage / "sentinel.txt").write_bytes(
                            b"synthetic replacement\n"
                        )
                        replacement = stage
                        before_metadata = stage.stat()
                        raise failure

                    with mock.patch.object(
                        package_manager,
                        "_stage_installation",
                        side_effect=replace_stage_then_fail,
                    ):
                        expected_error = type(failure)
                        with self.assertRaises(expected_error):
                            package_manager.install_package(
                                root=root,
                                package_id="project-harness",
                                version="0.2.2",
                                apply=True,
                            )

                    self.assertIsNotNone(replacement)
                    self.assertIsNotNone(before_metadata)
                    assert replacement is not None
                    assert before_metadata is not None
                    after_metadata = replacement.stat()
                    self.assertEqual(before_metadata.st_dev, after_metadata.st_dev)
                    self.assertEqual(before_metadata.st_ino, after_metadata.st_ino)
                    self.assertEqual(before_metadata.st_mode, after_metadata.st_mode)
                    self.assertEqual(
                        before_metadata.st_mtime_ns,
                        after_metadata.st_mtime_ns,
                    )
                    self.assertEqual(
                        b"synthetic replacement\n",
                        (replacement / "sentinel.txt").read_bytes(),
                    )
                    self.assertFalse(
                        (root / "project-harness-0.2.2").exists()
                    )

    def test_publish_refuses_destination_created_at_atomic_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            destination = root / "project-harness-0.2.2"
            original_publish = package_manager._publish_no_replace
            created_metadata: os.stat_result | None = None
            contender_stage: Path | None = None

            def create_empty_destination_then_publish(
                source: Path,
                target: Path,
            ) -> None:
                nonlocal contender_stage, created_metadata
                contender_stage = source
                target.mkdir(mode=0o711)
                created_metadata = target.stat()
                original_publish(source, target)

            with mock.patch.object(
                package_manager,
                "_publish_no_replace",
                side_effect=create_empty_destination_then_publish,
            ):
                with self.assertRaises(package_manager.PackageManagerError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertIsNotNone(created_metadata)
            self.assertIsNotNone(contender_stage)
            assert created_metadata is not None
            assert contender_stage is not None
            preserved_metadata = destination.stat()
            self.assertEqual(created_metadata.st_dev, preserved_metadata.st_dev)
            self.assertEqual(created_metadata.st_ino, preserved_metadata.st_ino)
            self.assertEqual(created_metadata.st_mode, preserved_metadata.st_mode)
            self.assertEqual(
                created_metadata.st_mtime_ns,
                preserved_metadata.st_mtime_ns,
            )
            self.assertEqual([], list(destination.iterdir()))
            self.assertTrue(contender_stage.is_dir())
            self.assertEqual(
                sorted((contender_stage, destination)),
                sorted(root.iterdir()),
            )

    def test_concurrent_identical_publish_converges_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            destination = root / "project-harness-0.2.2"
            concurrent_stage = root / ".synthetic-concurrent-stage"
            original_publish = package_manager._publish_no_replace
            contender_stage: Path | None = None

            def publish_identical_winner_then_contender(
                source: Path,
                target: Path,
            ) -> None:
                nonlocal contender_stage
                contender_stage = source
                self.assertEqual([source], list(root.iterdir()))
                shutil.copytree(source, concurrent_stage)
                original_publish(concurrent_stage, target)
                original_publish(source, target)

            with mock.patch.object(
                package_manager,
                "_publish_no_replace",
                side_effect=publish_identical_winner_then_contender,
            ):
                result = package_manager.install_package(
                    root=root,
                    package_id="project-harness",
                    version="0.2.2",
                    apply=True,
                )

            self.assertEqual("unchanged-residual", result.action)
            self.assertIsNotNone(contender_stage)
            assert contender_stage is not None
            self.assertTrue(contender_stage.is_dir())
            self.assertEqual(
                sorted((contender_stage, destination)),
                sorted(root.iterdir()),
            )
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)

    def test_ambiguous_publish_error_leaves_verified_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            destination = root / "project-harness-0.2.2"
            original_publish = package_manager._publish_no_replace

            def publish_then_fail(source: Path, target: Path) -> None:
                original_publish(source, target)
                raise OSError("synthetic ambiguous publish result")

            with mock.patch.object(
                package_manager,
                "_publish_no_replace",
                side_effect=publish_then_fail,
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual([destination], list(root.iterdir()))
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)
            unchanged = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("unchanged", unchanged.action)

    def test_interrupt_after_publish_leaves_verified_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            destination = root / "project-harness-0.2.2"
            original_publish = package_manager._publish_no_replace

            def publish_then_interrupt(source: Path, target: Path) -> None:
                original_publish(source, target)
                raise KeyboardInterrupt()

            with mock.patch.object(
                package_manager,
                "_publish_no_replace",
                side_effect=publish_then_interrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual([destination], list(root.iterdir()))
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)

    def test_unavailable_publish_primitive_preserves_stage_and_allows_retry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            with (
                mock.patch.object(package_manager.sys, "platform", "darwin"),
                mock.patch.object(
                    package_manager.ctypes,
                    "CDLL",
                    side_effect=OSError("synthetic unavailable primitive"),
                ),
            ):
                with self.assertRaises(package_manager.PackageManagerError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            stages = sorted(root.glob(".project-harness-0.2.2.stage-*"))
            self.assertEqual(1, len(stages))
            residual_before = _tree_snapshot(stages[0])
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stages[0]))

    def test_publish_fails_closed_on_an_unsupported_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()

            with mock.patch.object(
                package_manager.sys,
                "platform",
                "synthetic-unsupported",
            ):
                with self.assertRaises(package_manager.PackageManagerError):
                    package_manager._publish_no_replace(source, destination)

            self.assertTrue(source.is_dir())
            self.assertFalse(destination.exists())

    def test_initial_root_sync_failure_preserves_stage_and_allows_retry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            original_sync = catalog.fsync_directory
            root_syncs = 0

            def fail_first_root_sync(path: Path) -> None:
                nonlocal root_syncs
                if path == root:
                    root_syncs += 1
                    if root_syncs == 1:
                        raise OSError("synthetic initial root sync failure")
                original_sync(path)

            with mock.patch.object(
                catalog,
                "fsync_directory",
                side_effect=fail_first_root_sync,
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )
            stages = sorted(root.glob(".project-harness-0.2.2.stage-*"))
            self.assertEqual(1, len(stages))
            self.assertEqual([], list(stages[0].iterdir()))
            residual_before = _tree_snapshot(stages[0])

            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stages[0]))
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)

    def test_staging_sync_failure_preserves_stage_and_allows_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            original_sync = catalog.fsync_directory
            failed = False

            def fail_one_staging_sync(path: Path) -> None:
                nonlocal failed
                if path != root and ".stage-" in path.as_posix() and not failed:
                    failed = True
                    raise OSError("synthetic staging sync failure")
                original_sync(path)

            with mock.patch.object(
                catalog,
                "fsync_directory",
                side_effect=fail_one_staging_sync,
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertTrue(failed)
            stages = sorted(root.glob(".project-harness-0.2.2.stage-*"))
            self.assertEqual(1, len(stages))
            residual_before = _tree_snapshot(stages[0])
            installed = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("installed", installed.action)
            self.assertEqual(residual_before, _tree_snapshot(stages[0]))

    def test_post_rename_sync_failure_leaves_verified_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            original_sync = catalog.fsync_directory
            root_syncs = 0

            def fail_second_root_sync(path: Path) -> None:
                nonlocal root_syncs
                if path == root:
                    root_syncs += 1
                    if root_syncs == 2:
                        raise OSError("synthetic post-rename root sync failure")
                original_sync(path)

            with mock.patch.object(
                catalog,
                "fsync_directory",
                side_effect=fail_second_root_sync,
            ):
                with self.assertRaises(OSError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual(
                ["project-harness-0.2.2"],
                sorted(path.name for path in root.iterdir()),
            )
            verified = package_manager.verify_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
            )
            self.assertEqual("verified", verified.action)
            unchanged = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("unchanged", unchanged.action)

    def test_final_sync_failure_leaves_verified_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            original_sync = catalog.fsync_directory
            root_syncs = 0

            def fail_third_root_sync(path: Path) -> None:
                nonlocal root_syncs
                if path == root:
                    root_syncs += 1
                    if root_syncs == 3:
                        raise OSError("synthetic final root sync failure")
                original_sync(path)

            with mock.patch.object(
                catalog,
                "fsync_directory",
                side_effect=fail_third_root_sync,
            ):
                with self.assertRaises(package_manager.PackageManagerError):
                    package_manager.install_package(
                        root=root,
                        package_id="project-harness",
                        version="0.2.2",
                        apply=True,
                    )

            self.assertEqual(
                ["project-harness-0.2.2"],
                sorted(path.name for path in root.iterdir()),
            )
            unchanged = package_manager.install_package(
                root=root,
                package_id="project-harness",
                version="0.2.2",
                apply=True,
            )
            self.assertEqual("unchanged", unchanged.action)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_install_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve(strict=True)
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            os.symlink(real.name, linked)
            with self.assertRaises(package_manager.PackageManagerError):
                package_manager.install_package(
                    root=linked,
                    package_id="project-harness",
                    version="0.2.2",
                    apply=False,
                )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_install_root_component_is_rejected_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve(strict=True)
            physical_parent = parent / "physical"
            physical_root = physical_parent / "install-root"
            physical_root.mkdir(parents=True)
            alias_parent = parent / "alias"
            os.symlink(physical_parent.name, alias_parent)
            alias_root = alias_parent / physical_root.name
            before = _tree_snapshot(physical_parent)

            for apply in (False, True):
                with self.subTest(apply=apply):
                    with self.assertRaises(package_manager.PackageManagerError):
                        package_manager.install_package(
                            root=alias_root,
                            package_id="project-harness",
                            version="0.2.2",
                            apply=apply,
                        )
                    self.assertEqual(before, _tree_snapshot(physical_parent))

            accepted = package_manager.install_package(
                root=physical_root,
                package_id="project-harness",
                version="0.2.2",
                apply=False,
            )
            self.assertEqual("planned", accepted.action)
            self.assertEqual(before, _tree_snapshot(physical_parent))

    def test_wrong_version_is_rejected_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            with self.assertRaises(package_manager.PackageManagerError):
                package_manager.install_package(
                    root=root,
                    package_id="cross-project",
                    version="0.1.9",
                    apply=False,
                )
            self.assertEqual([], list(root.iterdir()))

    def test_cli_dry_run_is_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(strict=True)
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPOSITORY_ROOT / "tools" / "package_manager.py"),
                    "install",
                    "--package",
                    "orchestration",
                    "--version",
                    "0.2.2",
                    "--root",
                    str(root),
                    "--dry-run",
                ],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process.returncode, process.stdout + process.stderr)
            self.assertEqual([], list(root.iterdir()))

    def test_installed_packages_execute_documented_first_use(self) -> None:
        versions = {
            "project-harness": "0.2.2",
            "workspace-coordination": "0.2.2",
            "cross-project": "0.2.2",
            "orchestration": "0.2.2",
        }
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory).resolve(strict=True)
            install_root = outer / "installed"
            install_root.mkdir()
            destinations: dict[str, Path] = {}
            for package_id, version in versions.items():
                result = package_manager.install_package(
                    root=install_root,
                    package_id=package_id,
                    version=version,
                    apply=True,
                )
                destinations[package_id] = install_root / result.destination_name
            installed_snapshots = {
                package_id: _tree_snapshot(destination)
                for package_id, destination in destinations.items()
            }

            project_root = outer / "project"
            project_root.mkdir()
            project_cwd = destinations["project-harness"]
            _assert_documented(
                project_cwd,
                '<python> -B project_harness.py init --root "<project-root>" --dry-run',
            )
            _run_success(
                "project_harness.py",
                "init",
                "--root",
                str(project_root),
                "--dry-run",
                cwd=project_cwd,
            )
            _run_success(
                "project_harness.py",
                "init",
                "--root",
                str(project_root),
                cwd=project_cwd,
            )
            _run_success(
                "project_harness.py",
                "verify",
                "--root",
                str(project_root),
                cwd=project_cwd,
            )
            _run_success(
                "project_harness.py",
                "open",
                "--root",
                str(project_root),
                cwd=project_cwd,
            )

            workspace_root = outer / "workspace"
            workspace_root.mkdir()
            (workspace_root / "child-alpha").mkdir()
            (workspace_root / "child-beta").mkdir()
            (workspace_root / "child-alpha" / "AGENTS.md").write_text(
                "# Alpha owner\n",
                encoding="utf-8",
            )
            (workspace_root / "child-beta" / "OWNER.md").write_text(
                "# Beta owner\n",
                encoding="utf-8",
            )
            workspace_cwd = destinations["workspace-coordination"]
            _assert_documented(
                workspace_cwd,
                (
                    '<python> -B workspace_coordination.py --root '
                    '"<coordinator-root>" init --dry-run'
                ),
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "init",
                "--dry-run",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "init",
                "--apply",
                cwd=workspace_cwd,
            )
            for child_id, child_path, owner in (
                ("alpha", "child-alpha", "AGENTS.md"),
                ("beta", "child-beta", "OWNER.md"),
            ):
                child_arguments = (
                    "--id",
                    child_id,
                    "--path",
                    child_path,
                    "--owner",
                    owner,
                )
                _run_success(
                    "workspace_coordination.py",
                    "--root",
                    str(workspace_root),
                    "add",
                    *child_arguments,
                    "--dry-run",
                    cwd=workspace_cwd,
                )
                _run_success(
                    "workspace_coordination.py",
                    "--root",
                    str(workspace_root),
                    "add",
                    *child_arguments,
                    "--apply",
                    cwd=workspace_cwd,
                )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "open",
                "--child",
                "alpha",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "digest",
                "--child",
                "alpha",
                cwd=workspace_cwd,
            )
            record_arguments = (
                "--child",
                "alpha",
                "--key",
                "cycle-001",
                "--kind",
                "decision",
                "--summary",
                "Keep this implementation local to alpha.",
                "--next",
                "Run the local fixture.",
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "record",
                *record_arguments,
                "--dry-run",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "record",
                *record_arguments,
                "--apply",
                cwd=workspace_cwd,
            )
            reflect_arguments = (
                "--child",
                "alpha",
                "--key",
                "shared-001",
                "--summary",
                "Both children share one fixture naming boundary.",
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "reflect",
                *reflect_arguments,
                "--dry-run",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "reflect",
                *reflect_arguments,
                "--apply",
                cwd=workspace_cwd,
            )
            close_arguments = (
                "--child",
                "alpha",
                "--key",
                "cycle-002",
                "--kind",
                "close",
                "--summary",
                "The local cycle is closed.",
                "--next",
                "Reopen alpha from its recorded next action.",
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "record",
                *close_arguments,
                "--dry-run",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "record",
                *close_arguments,
                "--apply",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "verify",
                cwd=workspace_cwd,
            )
            _run_success(
                "workspace_coordination.py",
                "--root",
                str(workspace_root),
                "open",
                "--child",
                "alpha",
                cwd=workspace_cwd,
            )

            cross_root = outer / "cross"
            (cross_root / "projects" / "alpha").mkdir(parents=True)
            cross_cwd = destinations["cross-project"]
            _assert_documented(
                cross_cwd,
                (
                    "<python> -B scripts/cross_project.py bom-dia "
                    '--root "<coordination-root>"'
                ),
            )
            _run_success(
                "scripts/cross_project.py",
                "bom-dia",
                "--root",
                str(cross_root),
                cwd=cross_cwd,
            )
            cross_registration = (
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
            )
            _run_success(
                "scripts/cross_project.py",
                "hq-init",
                "--root",
                str(cross_root),
                "--dry-run",
                *cross_registration,
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "hq-init",
                "--root",
                str(cross_root),
                *cross_registration,
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "hq-sync",
                "--root",
                str(cross_root),
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "digere",
                "--root",
                str(cross_root),
                "--front",
                "alpha",
                "--scope",
                "coordination",
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "registra",
                "--root",
                str(cross_root),
                "--front",
                "alpha",
                "--state",
                "active",
                "--next",
                "Validate the first slice",
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "encerra",
                "--root",
                str(cross_root),
                "--front",
                "alpha",
                "--role",
                "Produces one synthetic component",
                "--state",
                "ready",
                "--next",
                "Hand off the component",
                "--summary",
                "First slice validated",
                "--reflect-when",
                "The shared interface changes",
                cwd=cross_cwd,
            )
            _run_success(
                "scripts/cross_project.py",
                "bom-dia",
                "--root",
                str(cross_root),
                "--front",
                "alpha",
                cwd=cross_cwd,
            )

            orchestration_root = outer / "orchestration"
            orchestration_root.mkdir()
            orchestration_cwd = destinations["orchestration"]
            _assert_documented(
                orchestration_cwd,
                '<python> -B hq.py --root "<workspace>" --json bom-dia',
            )
            orchestration_prefix = (
                "hq.py",
                "--root",
                str(orchestration_root),
                "--json",
            )
            _run_success(
                *orchestration_prefix,
                "bom-dia",
                cwd=orchestration_cwd,
            )
            orchestration_registration = (
                "--id",
                "alpha",
                "--name",
                "Alpha",
                "--path",
                "fronts/alpha",
            )
            _run_success(
                *orchestration_prefix,
                "init",
                *orchestration_registration,
                "--dry-run",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "init",
                *orchestration_registration,
                "--apply",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "hq-sync",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "foco",
                "alpha",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "digere",
                "--summary",
                "Validated the current slice",
                "--pending",
                "Register the validated delta",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "registra",
                "--note",
                "Evidence recorded",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "encerra",
                "--summary",
                "Closed the work block",
                "--next",
                "Review the next bounded slice",
                cwd=orchestration_cwd,
            )
            _run_success(
                *orchestration_prefix,
                "bom-dia",
                cwd=orchestration_cwd,
            )

            for package_id, version in versions.items():
                verified = package_manager.verify_package(
                    root=install_root,
                    package_id=package_id,
                    version=version,
                )
                self.assertEqual("verified", verified.action)
                self.assertEqual(
                    installed_snapshots[package_id],
                    _tree_snapshot(destinations[package_id]),
                )


if __name__ == "__main__":
    unittest.main()
