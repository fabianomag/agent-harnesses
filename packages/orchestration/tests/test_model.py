"""Strict schema and portable naming tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap

from orchestration_harness.errors import CollisionError, ValidationError
from orchestration_harness.model import (
    Front,
    Manifest,
    dumps_canonical_json,
    loads_strict_json,
    parse_manifest,
    render_manifest,
    validate_relative_path,
)
from orchestration_harness.paths import safe_path


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_key_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            loads_strict_json('{"value":1,"value":2}')

    def test_nonfinite_number_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            loads_strict_json('{"value":NaN}')

    def test_large_integer_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            loads_strict_json('{"value":10000000000000000000}')

    def test_canonical_json_is_utf8_and_deterministic(self) -> None:
        value = {"z": "ação", "a": 1}
        rendered = dumps_canonical_json(value)
        self.assertEqual(rendered, dumps_canonical_json(value))
        self.assertTrue(rendered.endswith("\n"))
        self.assertIn("ação", rendered)


class PortablePathTests(unittest.TestCase):
    def test_valid_nested_path_passes(self) -> None:
        self.assertEqual(
            "fronts/sample-front",
            validate_relative_path("fronts/sample-front"),
        )

    def test_unsafe_path_families_are_rejected(self) -> None:
        separator = chr(47)
        reverse = chr(92)
        values = (
            separator + "outside",
            "C" + ":" + reverse + "outside",
            reverse + reverse + "host" + reverse + "share",
            "~" + separator + "outside",
            "fronts/../outside",
            "fronts" + reverse + "sample",
            "fronts/con",
            "fronts/trailing.",
        )
        for value in values:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValidationError):
                    validate_relative_path(value)

    @unittest.skipUnless(hasattr(__import__("os"), "symlink"), "symlinks unavailable")
    def test_existing_symlink_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / (root.name + "-outside")
            outside.mkdir()
            try:
                (root / "fronts").symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValidationError):
                    safe_path(root, "fronts/sample")
            finally:
                outside.rmdir()


class ManifestTests(unittest.TestCase):
    def _front(
        self,
        front_id: str = "sample-front",
        path: str = "fronts/sample-front",
        aliases: tuple[str, ...] = ("sample",),
    ) -> Front:
        return Front.create(
            front_id=front_id,
            display_name="Sample Front",
            path=path,
            aliases=aliases,
        )

    def test_manifest_round_trip(self) -> None:
        manifest = Manifest.create(self._front(), transaction_id="a" * 32)
        parsed = parse_manifest(render_manifest(manifest))
        self.assertEqual(manifest, parsed)

    def test_schema_one_keeps_semantic_boundary_out_of_manifest(self) -> None:
        manifest = Manifest.create(self._front(), transaction_id="a" * 32)
        value = manifest.to_dict()

        self.assertEqual(1, value["schemaVersion"])
        self.assertNotIn("responsibilityBoundary", value["fronts"][0])
        self.assertEqual(manifest, parse_manifest(json.dumps(value)))

        value["fronts"][0]["responsibilityBoundary"] = "Synthetic API only"
        with self.assertRaises(ValidationError):
            parse_manifest(json.dumps(value))

    def test_manifest_rejects_extra_field(self) -> None:
        manifest = Manifest.create(self._front(), transaction_id="b" * 32)
        value = manifest.to_dict()
        value["unsupported"] = True
        with self.assertRaises(ValidationError):
            parse_manifest(json.dumps(value))

    def test_manifest_rejects_noncanonical_alias_order(self) -> None:
        manifest = Manifest.create(
            self._front(aliases=("alpha", "zeta")),
            transaction_id="3" * 32,
        )
        value = manifest.to_dict()
        value["fronts"][0]["aliases"] = ["zeta", "alpha"]
        with self.assertRaises(ValidationError):
            parse_manifest(json.dumps(value))

    def test_manifest_rejects_inconsistent_lifecycle_counters(self) -> None:
        manifest = Manifest.create(self._front(), transaction_id="4" * 32)
        value = manifest.to_dict()
        value["fronts"][0]["stage"] = "closed"
        with self.assertRaises(ValidationError):
            parse_manifest(json.dumps(value))

    def test_alias_to_id_collision_is_rejected(self) -> None:
        first = self._front()
        second = self._front(
            front_id="second-front",
            path="fronts/second-front",
            aliases=("sample-front",),
        )
        manifest = Manifest.create(first, transaction_id="c" * 32)
        with self.assertRaises(CollisionError):
            manifest.with_front(second, transaction_id="d" * 32)

    def test_casefolded_path_collision_is_rejected(self) -> None:
        first = self._front(path="Fronts/Sample")
        second = self._front(
            front_id="second-front",
            path="fronts/sample",
            aliases=("second",),
        )
        manifest = Manifest.create(first, transaction_id="e" * 32)
        with self.assertRaises(CollisionError):
            manifest.with_front(second, transaction_id="f" * 32)

    def test_nested_path_collision_is_rejected(self) -> None:
        first = self._front(path="fronts/sample")
        second = self._front(
            front_id="nested-front",
            path="fronts/sample/nested",
            aliases=("nested",),
        )
        manifest = Manifest.create(first, transaction_id="1" * 32)
        with self.assertRaises(CollisionError):
            manifest.with_front(second, transaction_id="2" * 32)

    def test_non_nfc_display_text_is_rejected(self) -> None:
        decomposed = "Cafe" + "\u0301"
        with self.assertRaises(ValidationError):
            Front.create(
                front_id="sample-front",
                display_name=decomposed,
                path="fronts/sample-front",
            )
