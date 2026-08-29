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
        "en": "https://fabianomag.com/projects/agent-harnesses",
        "ptBr": "https://fabianomag.com/pt-br/projetos/agent-harnesses",
    }:
        raise ProductContractError("site URLs are outside the public contract")
    prompt_instructions = _localized(
        value["promptInstructions"], "promptInstructions"
    )
    if any(
        instructions.count("<selector>") != 4
        for instructions in prompt_instructions.values()
    ):
        raise ProductContractError(
            "each prompt locale must contain four selector command tokens"
        )
    if any(
        instructions.count("<python> -B installer.py") != 4
        for instructions in prompt_instructions.values()
    ):
        raise ProductContractError(
            "each prompt locale must contain four public Python command tokens"
        )

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
    instructions = value["promptInstructions"][language].replace(
        "<selector>", package["id"]
    )
    separator = "" if instructions.startswith("\n") else " "
    return opening + separator + instructions


def root_readme_block(value: dict[str, Any], language: str) -> str:
    """Render the product-owned root README block for one locale."""
    if language not in {"en", "ptBr"}:
        raise ProductContractError("README language is invalid")
    release = value["release"]
    if language == "en":
        lines = [
            "# Agent Harnesses",
            "",
            "[Português do Brasil](README.pt-BR.md)",
            "",
            "Four local harnesses for four different coordination boundaries. Choose the smallest boundary that matches your actual work; the packages are siblings, not levels in a maturity ladder.",
            "",
            f"Interactive guide: {release['site']['en']}",
            "",
            f"Requirements: Python {release['minimumPython']} or newer, an explicit existing target directory, and one exact `{release['tag']}` release asset. The runtimes use only the Python standard library. The installer does not change `PATH`, edit `.gitignore`, or install a global Skill.",
            "",
            "## What do you need to coordinate?",
            "",
            "| Harness | Choose it when | Not for | Strengths | Complexity |",
            "| --- | --- | --- | --- | --- |",
        ]
    else:
        lines = [
            "# Agent Harnesses",
            "",
            "[English](README.md)",
            "",
            "Quatro harnesses locais para quatro limites de coordenação diferentes. Escolha o menor limite que corresponda ao trabalho real; os pacotes são alternativas paralelas, não degraus de maturidade.",
            "",
            f"Guia interativo: {release['site']['ptBr']}",
            "",
            f"Requisitos: Python {release['minimumPython']} ou mais recente, um diretório-alvo existente e explícito e um único arquivo da release `{release['tag']}`. Os runtimes usam apenas a biblioteca padrão do Python. O instalador não altera `PATH`, não edita `.gitignore` e não instala uma Skill global.",
            "",
            "## O que você precisa coordenar?",
            "",
            "| Harness | Escolha quando | Não serve para | Pontos fortes | Complexidade |",
            "| --- | --- | --- | --- | --- |",
        ]
    for item in value["packages"]:
        content = item["content"][language]
        strengths = " · ".join(item["strengths"][language])
        readme = "README.md" if language == "en" else "README.pt-BR.md"
        lines.append(
            f"| [{item['displayName']}](packages/{item['id']}/{readme}) (`{item['id']}`) "
            f"| {content['scenario']} | {content['notFor']} | {strengths} | "
            f"{item['complexity'][language]} |"
        )
    if language == "en":
        lines.extend(
            [
                "",
                "Control Plane Harness is a local control plane. It does not call models, dispatch agents, or execute projects, and it intentionally refuses to adopt an existing Master-like structure when ownership would be ambiguous.",
                "",
                "## Copy one install prompt",
                "",
                "Copy only the block for the harness you chose. Each block names one package, one version, and one ZIP.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Control Plane Harness é um control plane local. Ele não chama modelos, não aciona coding agents e não executa projetos. Por segurança, também se recusa a adotar automaticamente uma estrutura de coordenação existente cuja responsabilidade seja ambígua.",
                "",
                "## Copie um único prompt de instalação",
                "",
                "Cada bloco abaixo contém somente um harness, uma versão e um ZIP. Copie apenas o bloco escolhido.",
            ]
        )
    for item in value["packages"]:
        lines.extend(
            [
                "",
                f"### {item['displayName']}",
                "",
                "```text",
                install_prompt(value, item, language),
                "```",
            ]
        )
    return "\n".join(lines)


def package_readme_block(
    value: dict[str, Any], package: dict[str, Any], language: str
) -> str:
    """Render the product-owned package decision and installation block."""
    if language not in {"en", "ptBr"}:
        raise ProductContractError("README language is invalid")
    release = value["release"]
    content = package["content"][language]
    strengths = " · ".join(package["strengths"][language])
    if language == "en":
        labels = {
            "language": "[Português do Brasil](README.pt-BR.md)",
            "version": "Version",
            "best": "Best for",
            "not": "Not for",
            "changes": "What it changes",
            "strengths": "Strengths",
            "complexity": "Complexity",
            "installation": "Installation",
            "copy": "Copy only this prompt:",
        }
    else:
        labels = {
            "language": "[English](README.md)",
            "version": "Versão",
            "best": "Melhor opção para",
            "not": "Não serve para",
            "changes": "O que muda",
            "strengths": "Pontos fortes",
            "complexity": "Complexidade",
            "installation": "Instalação",
            "copy": "Copie somente este prompt:",
        }
    return "\n".join(
        [
            f"# {package['displayName']}",
            "",
            f"{labels['language']} · {labels['version']} `{release['version']}`",
            "",
            f"**{labels['best']}:** {content['bestFor']}",
            "",
            f"**{labels['not']}:** {content['notFor']}",
            "",
            f"**{labels['changes']}:** {content['whatItChanges']}",
            "",
            f"{labels['strengths']}: **{strengths}**. {labels['complexity']}: {package['complexity'][language].lower()}.",
            "",
            f"## {labels['installation']}",
            "",
            labels["copy"],
            "",
            "```text",
            install_prompt(value, package, language),
            "```",
        ]
    )


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
        "releaseManifest": {
            "url": (
                f"{release['repository']}/releases/download/{release['tag']}/"
                "release-manifest.json"
            ),
            "checksumUrl": (
                f"{release['repository']}/releases/download/{release['tag']}/"
                "release-manifest.json.sha256"
            ),
        },
        "ptBrEnglishTerms": value["ptBrEnglishTerms"],
        "packages": packages,
    }
