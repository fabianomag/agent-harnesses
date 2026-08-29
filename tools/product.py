"""Load and render the canonical Agent Harnesses product definition."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PRODUCT_PATH = Path("product/harnesses.json")
SITE_SNAPSHOT_PATH = Path("catalog/site-harnesses.v0.2.0.json")
PACKAGE_IDS = (
    "project-harness",
    "workspace-coordination",
    "cross-project",
    "orchestration",
)
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class ProductContractError(ValueError):
    """The checked-in product source violates its public contract."""


def _reject_duplicate(keys: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in keys:
        if key in value:
            raise ProductContractError("product JSON contains a duplicate property")
        value[key] = item
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductContractError(f"{label} must be a non-empty string")
    return value


def _localized(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"en", "ptBr"}:
        raise ProductContractError(f"{label} must contain en and ptBr")
    return {key: _nonempty(value[key], f"{label}.{key}") for key in ("en", "ptBr")}


def load_product(repository_root: Path) -> dict[str, Any]:
    path = repository_root / PRODUCT_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductContractError("product source is not readable strict JSON") from error
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "release",
        "promptInstructions",
        "ptBrEnglishTerms",
        "packages",
    }:
        raise ProductContractError("product source fields do not match the contract")
    if value["schemaVersion"] != 1:
        raise ProductContractError("product schema version is unsupported")

    release = value["release"]
    if not isinstance(release, dict) or set(release) != {
        "version",
        "tag",
        "minimumPython",
        "repository",
        "site",
    }:
        raise ProductContractError("release fields do not match the contract")
    version = _nonempty(release["version"], "release.version")
    if SEMVER.fullmatch(version) is None or release["tag"] != f"v{version}":
        raise ProductContractError("release version and tag must be aligned")
    if release["minimumPython"] != "3.10":
        raise ProductContractError("minimum Python must be 3.10")
    repository = _nonempty(release["repository"], "release.repository")
    if repository != "https://github.com/fabianomag/agent-harnesses":
        raise ProductContractError("repository URL is outside the public contract")
    sites = _localized(release["site"], "release.site")
    if sites != {
        "en": "https://fabianomag.com/artifacts/agent-harnesses",
        "ptBr": "https://fabianomag.com/pt-br/artefatos/agent-harnesses",
    }:
        raise ProductContractError("site URLs are outside the public contract")
    _localized(value["promptInstructions"], "promptInstructions")

    terms = value["ptBrEnglishTerms"]
    if not isinstance(terms, list) or len(terms) != len(set(terms)) or any(
        not isinstance(term, str) or not term.strip() for term in terms
    ):
        raise ProductContractError("PT-BR terminology list is invalid")

    packages = value["packages"]
    if not isinstance(packages, list) or tuple(
        item.get("id") if isinstance(item, dict) else None for item in packages
    ) != PACKAGE_IDS:
        raise ProductContractError("product package order or IDs are invalid")
    aliases: set[str] = set()
    for item in packages:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "displayName",
            "aliases",
            "asset",
            "complexity",
            "strengths",
            "content",
        }:
            raise ProductContractError("package product fields are invalid")
        package_id = item["id"]
        if IDENTIFIER.fullmatch(package_id) is None:
            raise ProductContractError("package ID is invalid")
        _nonempty(item["displayName"], f"{package_id}.displayName")
        expected_asset = f"{package_id}-{version}.zip"
        if item["asset"] != expected_asset:
            raise ProductContractError("package asset does not match the release")
        package_aliases = item["aliases"]
        if not isinstance(package_aliases, list) or package_id not in package_aliases:
            raise ProductContractError("package aliases must include the stable ID")
        for alias in package_aliases:
            if not isinstance(alias, str) or IDENTIFIER.fullmatch(alias) is None or alias in aliases:
                raise ProductContractError("package aliases must be unique identifiers")
            aliases.add(alias)
        complexity = item["complexity"]
        if not isinstance(complexity, dict) or set(complexity) != {"level", "en", "ptBr"}:
            raise ProductContractError("package complexity is invalid")
        if complexity["level"] not in {"low", "medium", "high"}:
            raise ProductContractError("package complexity level is invalid")
        _nonempty(complexity["en"], "complexity.en")
        _nonempty(complexity["ptBr"], "complexity.ptBr")
        strengths = item["strengths"]
        if not isinstance(strengths, dict) or set(strengths) != {"en", "ptBr"}:
            raise ProductContractError("package strengths are invalid")
        for language in ("en", "ptBr"):
            entries = strengths[language]
            if not isinstance(entries, list) or len(entries) != 3 or any(
                not isinstance(entry, str) or not entry.strip() for entry in entries
            ):
                raise ProductContractError("each package needs three strengths")
        content = item["content"]
        if not isinstance(content, dict) or set(content) != {"en", "ptBr"}:
            raise ProductContractError("package content locales are invalid")
        content_keys = {"scenario", "summary", "bestFor", "notFor", "whatItChanges"}
        for language in ("en", "ptBr"):
            localized = content[language]
            if not isinstance(localized, dict) or set(localized) != content_keys:
                raise ProductContractError("package localized content is invalid")
            for key in content_keys:
                _nonempty(localized[key], f"{package_id}.{language}.{key}")
    return value


def package_map(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in value["packages"]}


def resolve_selector(value: dict[str, Any], selector: str) -> dict[str, Any]:
    normalized = selector.strip().lower()
    for item in value["packages"]:
        if normalized in item["aliases"]:
            return item
    raise ProductContractError("selector does not identify one harness")


def asset_url(value: dict[str, Any], package: dict[str, Any]) -> str:
    release = value["release"]
    return (
        f"{release['repository']}/releases/download/{release['tag']}/"
        f"{package['asset']}"
    )


def install_prompt(value: dict[str, Any], package: dict[str, Any], language: str) -> str:
    if language not in {"en", "ptBr"}:
        raise ProductContractError("prompt language is invalid")
    release = value["release"]
    if language == "en":
        opening = (
            f"Install {package['displayName']} (`{package['id']}`) "
            f"v{release['version']} from {asset_url(value, package)}."
        )
    else:
        opening = (
            f"Instale {package['displayName']} (`{package['id']}`) "
            f"v{release['version']} a partir de {asset_url(value, package)}."
        )
    return opening + " " + value["promptInstructions"][language]


def site_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    release = value["release"]
    packages: list[dict[str, Any]] = []
    for item in value["packages"]:
        packages.append(
            {
                "id": item["id"],
                "displayName": item["displayName"],
                "version": release["version"],
                "aliases": item["aliases"],
                "asset": {
                    "name": item["asset"],
                    "url": asset_url(value, item),
                    "checksumUrl": asset_url(value, item) + ".sha256",
                },
                "complexity": item["complexity"],
                "strengths": item["strengths"],
                "content": item["content"],
                "installPrompt": {
                    "en": install_prompt(value, item, "en"),
                    "ptBr": install_prompt(value, item, "ptBr"),
                },
            }
        )
    return {
        "schemaVersion": 1,
        "release": release,
        "ptBrEnglishTerms": value["ptBrEnglishTerms"],
        "packages": packages,
    }
