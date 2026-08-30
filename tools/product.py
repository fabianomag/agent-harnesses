"""Load and render the canonical Agent Harnesses product definition."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PRODUCT_PATH = Path("product/harnesses.json")
SITE_SNAPSHOT_PATH = Path("catalog/site-harnesses.v0.2.2.json")
PACKAGE_IDS = (
    "project-harness",
    "workspace-coordination",
    "cross-project",
    "orchestration",
)
EXPECTED_OPERATIONS = {
    "project-harness": (
        "init",
        "verify",
        "status",
        "open",
        "digest",
        "checkpoint",
        "close",
    ),
    "workspace-coordination": (
        "init",
        "add",
        "remove",
        "open",
        "digest",
        "record",
        "reflect",
        "verify",
        "recover",
    ),
    "cross-project": (
        "bom-dia",
        "hq-init",
        "hq-sync",
        "digere",
        "registra",
        "encerra",
    ),
    "orchestration": (
        "bom-dia",
        "foco",
        "init",
        "hq-sync",
        "digere",
        "registra",
        "encerra",
        "repair-panel",
        "recover",
    ),
}
WORKFLOW_IDS = ("firstUse", "daily", "closeResume", "verifyRecover")
OPERATION_KINDS = frozenset(("read", "write", "repair"))
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
VERSION_TOKEN = re.compile(r"(?<![0-9])v?([0-9]+\.[0-9]+\.[0-9]+)(?![0-9])")
ASSET_TOKEN = re.compile(r"[a-z][a-z0-9-]*-[0-9]+\.[0-9]+\.[0-9]+\.zip")
PLACEHOLDER = re.compile(r"<[^<>\n]+>")
FORBIDDEN_PUBLIC_NAMES = re.compile(r"\b(?:alpha|beta)\b", re.IGNORECASE)


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


def _string_list(value: Any, label: str, *, minimum: int = 1) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or len(value) != len(set(value))
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ProductContractError(f"{label} must be a unique non-empty string list")
    return value


def _public_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _public_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _public_strings(item)


def load_product(repository_root: Path) -> dict[str, Any]:
    path = repository_root / PRODUCT_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductContractError("product source is not readable strict JSON") from error
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "release",
        "compatibility",
        "support",
        "tutorial",
        "promptInstructions",
        "executionModeInstruction",
        "ptBrEnglishTerms",
        "packages",
    }:
        raise ProductContractError("product source fields do not match the contract")
    if value["schemaVersion"] != 2:
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
    if (
        version != "0.2.2"
        or SEMVER.fullmatch(version) is None
        or release["tag"] != f"v{version}"
    ):
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

    compatibility = value["compatibility"]
    if not isinstance(compatibility, dict) or set(compatibility) != {
        "primary",
        "smoke",
    }:
        raise ProductContractError("compatibility fields do not match the contract")
    for key, expected_agent, expected_level in (
        ("primary", "Codex", "primary"),
        ("smoke", "Claude Code Desktop", "smoke"),
    ):
        entry = compatibility[key]
        if not isinstance(entry, dict) or set(entry) != {
            "agent",
            "level",
            "description",
        }:
            raise ProductContractError("compatibility entry is invalid")
        if entry["agent"] != expected_agent or entry["level"] != expected_level:
            raise ProductContractError("compatibility identity is invalid")
        _localized(entry["description"], f"compatibility.{key}.description")

    support = value["support"]
    if not isinstance(support, dict) or support != {
        "linkedin": "https://www.linkedin.com/in/fabianomag/",
        "email": "fm@fabianomag.com",
    }:
        raise ProductContractError("support contacts are outside the public contract")

    tutorial = value["tutorial"]
    if not isinstance(tutorial, dict) or set(tutorial) != {
        "requiredAfterReady",
        "delivery",
        "sources",
        "mustCover",
        "packageLifecycle",
        "constraints",
    }:
        raise ProductContractError("tutorial fields do not match the contract")
    if tutorial["requiredAfterReady"] is not True or tutorial["delivery"] != "conversation":
        raise ProductContractError("tutorial must be required in the conversation")
    if tutorial["sources"] != {
        "operations": "operations.json",
        "operatorGuide": {
            "en": "OPERATOR_GUIDE.md",
            "ptBr": "OPERATOR_GUIDE.pt-BR.md",
        },
    }:
        raise ProductContractError("tutorial sources are invalid")
    must_cover = tutorial["mustCover"]
    if not isinstance(must_cover, dict) or set(must_cover) != {"en", "ptBr"}:
        raise ProductContractError("tutorial coverage locales are invalid")
    for language in ("en", "ptBr"):
        _string_list(must_cover[language], f"tutorial.mustCover.{language}", minimum=7)
    package_lifecycle = tutorial["packageLifecycle"]
    if not isinstance(package_lifecycle, dict) or set(package_lifecycle) != {
        "en",
        "ptBr",
    }:
        raise ProductContractError("tutorial package lifecycle locales are invalid")
    for language in ("en", "ptBr"):
        entries = _string_list(
            package_lifecycle[language],
            f"tutorial.packageLifecycle.{language}",
            minimum=5,
        )
        if any("<id>" not in entry for entry in entries[:2]):
            raise ProductContractError(
                "tutorial package lifecycle must bind the selected package"
            )
        if "<version>" not in entries[0] or "<version>" not in entries[1]:
            raise ProductContractError(
                "tutorial package lifecycle must bind the selected version"
            )
    _localized(tutorial["constraints"], "tutorial.constraints")

    prompt_instructions = _localized(
        value["promptInstructions"], "promptInstructions"
    )
    execution_mode = _localized(
        value["executionModeInstruction"], "executionModeInstruction"
    )
    if (
        "execution-capable mode" not in execution_mode["en"]
        or "modo capaz de executar" not in execution_mode["ptBr"]
    ):
        raise ProductContractError("execution mode instruction is incomplete")
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
    prompt_requirements = {
        "en": (
            "native Plan mode",
            "structured questions",
            "otherwise present the same plan",
            "plan first",
            "Before any write",
            "four separate checklists",
            "ask the user to confirm",
            "Do not organize",
            "zero target writes",
            "fails after the first apply",
            "rollback or recovery",
            "operations.json",
            "OPERATOR_GUIDE.md",
            "tutorial",
            "ready=true",
            "https://www.linkedin.com/in/fabianomag/",
            "fm@fabianomag.com",
        ),
        "ptBr": (
            "Plan mode nativo",
            "structured questions",
            "caso contrário, apresente o mesmo plano",
            "primeiro o plano",
            "Antes de qualquer escrita",
            "quatro checklists separados",
            "confirme esse plano",
            "Não organize",
            "zero writes no target",
            "falhar depois do primeiro apply",
            "rollback ou recovery",
            "operations.json",
            "OPERATOR_GUIDE.pt-BR.md",
            "tutorial",
            "ready=true",
            "https://www.linkedin.com/in/fabianomag/",
            "fm@fabianomag.com",
        ),
    }
    for language, required in prompt_requirements.items():
        if any(token not in prompt_instructions[language] for token in required):
            raise ProductContractError(
                f"promptInstructions.{language} omits a guided-install requirement"
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
            "operator",
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

        operator = item["operator"]
        if not isinstance(operator, dict) or set(operator) != {
            "entrypoint",
            "memory",
            "installationReadiness",
            "readiness",
            "operations",
            "workflows",
        }:
            raise ProductContractError("package operator fields are invalid")
        entrypoint = _nonempty(operator["entrypoint"], f"{package_id}.operator.entrypoint")
        if entrypoint.startswith(("/", "\\")) or ".." in Path(entrypoint).parts:
            raise ProductContractError("operator entrypoint must be a relative safe path")
        memory = operator["memory"]
        if not isinstance(memory, dict) or set(memory) != {
            "canonical",
            "projections",
            "description",
        }:
            raise ProductContractError("operator memory fields are invalid")
        _string_list(memory["canonical"], f"{package_id}.operator.memory.canonical")
        _string_list(memory["projections"], f"{package_id}.operator.memory.projections")
        _localized(memory["description"], f"{package_id}.operator.memory.description")
        installation_readiness = operator["installationReadiness"]
        if not isinstance(installation_readiness, dict) or set(
            installation_readiness
        ) != {"en", "ptBr"}:
            raise ProductContractError(
                "operator installation readiness locales are invalid"
            )
        for language in ("en", "ptBr"):
            _string_list(
                installation_readiness[language],
                f"{package_id}.operator.installationReadiness.{language}",
                minimum=3,
            )
        _localized(operator["readiness"], f"{package_id}.operator.readiness")
        operations = operator["operations"]
        expected_commands = EXPECTED_OPERATIONS[package_id]
        if not isinstance(operations, list) or tuple(
            operation.get("command") if isinstance(operation, dict) else None
            for operation in operations
        ) != expected_commands:
            raise ProductContractError("operator command inventory is incomplete or reordered")
        for operation in operations:
            if set(operation) != {
                "command",
                "kind",
                "purpose",
                "inputs",
                "effects",
                "example",
            }:
                raise ProductContractError("operator operation fields are invalid")
            command = operation["command"]
            if operation["kind"] not in OPERATION_KINDS:
                raise ProductContractError("operator operation kind is invalid")
            _localized(operation["purpose"], f"{package_id}.{command}.purpose")
            _string_list(operation["inputs"], f"{package_id}.{command}.inputs")
            _localized(operation["effects"], f"{package_id}.{command}.effects")
            example = _nonempty(operation["example"], f"{package_id}.{command}.example")
            if command not in example or "<python>" not in example or PLACEHOLDER.search(example) is None:
                raise ProductContractError("operator example must use its command and placeholders")

        workflows = operator["workflows"]
        if not isinstance(workflows, dict) or tuple(workflows) != WORKFLOW_IDS:
            raise ProductContractError("operator workflows are incomplete or reordered")
        commands = set(expected_commands)
        for workflow_id in WORKFLOW_IDS:
            workflow = workflows[workflow_id]
            if not isinstance(workflow, dict) or set(workflow) != {"purpose", "steps"}:
                raise ProductContractError("operator workflow fields are invalid")
            _localized(
                workflow["purpose"],
                f"{package_id}.operator.workflows.{workflow_id}.purpose",
            )
            steps = workflow["steps"]
            if not isinstance(steps, list) or not steps or any(
                step not in commands for step in steps
            ):
                raise ProductContractError("operator workflow references an unknown command")

    if any(FORBIDDEN_PUBLIC_NAMES.search(text) for text in _public_strings(value)):
        raise ProductContractError("public product content contains a forbidden fixture name")

    for item in packages:
        prompt_ids: set[str] = set()
        prompt_assets: set[str] = set()
        prompt_versions: set[str] = set()
        for language in ("en", "ptBr"):
            rendered = install_prompt(value, item, language)
            prompt_ids.update(
                package_id for package_id in PACKAGE_IDS if package_id in rendered
            )
            prompt_assets.update(ASSET_TOKEN.findall(rendered))
            prompt_versions.update(match.group(1) for match in VERSION_TOKEN.finditer(rendered))
        if prompt_ids != {item["id"]}:
            raise ProductContractError("install prompt contains another package ID")
        if prompt_assets != {item["asset"]}:
            raise ProductContractError("install prompt contains another release asset")
        if prompt_versions != {version}:
            raise ProductContractError("install prompt contains another release version")
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
    readiness_items = package["operator"]["installationReadiness"][language]
    if language == "en":
        readiness = "\n".join(
            [
                "Before proposing execution, confirm every selected-harness "
                "readiness fact:",
                *(f"- {item}" for item in readiness_items),
                "If any fact is unknown or false, stop before downloads or target "
                "writes, explain what must be organized first, and offer the support "
                "contacts below.",
            ]
        )
    else:
        readiness = "\n".join(
            [
                "Antes de propor a execução, confirme cada fato de readiness do "
                "harness selecionado:",
                *(f"- {item}" for item in readiness_items),
                "Se algum fato for desconhecido ou falso, pare antes de downloads ou "
                "writes no target, explique o que precisa ser organizado primeiro e "
                "ofereça os contatos de suporte abaixo.",
            ]
        )
    instructions = value["promptInstructions"][language].replace(
        "<selector>", package["id"]
    )
    separator = "" if instructions.startswith("\n") else " "
    return (
        opening
        + "\n\n"
        + readiness
        + "\n\n"
        + value["executionModeInstruction"][language]
        + "\n\n"
        + instructions.lstrip()
        + "\n\n"
        + value["tutorial"]["constraints"][language]
    )


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
            f"Requirements: Python {release['minimumPython']} or newer, an explicit existing target directory, and one exact `{release['tag']}` ZIP with its matching checksum sidecar. Each ZIP installs the complete Python-standard-library runtime, command inventory, and agent-agnostic operator guide for one harness. It does not change `PATH`, edit `.gitignore`, or require a global Skill.",
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
            f"Requisitos: Python {release['minimumPython']} ou mais recente, um diretório-alvo existente e explícito e um único ZIP da release `{release['tag']}` com seu checksum sidecar correspondente. Cada ZIP instala o runtime completo baseado apenas na biblioteca padrão do Python, o inventário de comandos e o guia operacional agent-agnostic de um harness. O instalador não altera `PATH`, não edita `.gitignore` e não exige uma Skill global.",
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
    if language == "en":
        lines.extend(
            [
                "",
                "## Agent compatibility",
                "",
                "Codex is the primary guided-install experience. Claude Code Desktop is the agent-agnostic smoke target; neither path requires a global Skill.",
                "",
                "## Support",
                "",
                f"LinkedIn: {value['support']['linkedin']} · Email: {value['support']['email']}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Compatibilidade com agentes",
                "",
                "Codex é a experiência principal de instalação guiada. Claude Code Desktop é o alvo agent-agnostic de smoke; nenhum dos dois fluxos exige uma Skill global.",
                "",
                "## Suporte",
                "",
                f"LinkedIn: {value['support']['linkedin']} · Email: {value['support']['email']}",
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
            "readiness": "Ready means",
            "installReadiness": "Before installation, confirm",
            "installation": "Installation",
            "copy": "Copy only this prompt:",
            "operator": "The installed runtime includes `operations.json` plus `OPERATOR_GUIDE.md`; after `ready=true`, the coding agent must read both and teach the user the complete operating cycle in the conversation.",
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
            "readiness": "Readiness significa",
            "installReadiness": "Antes da instalação, confirme",
            "installation": "Instalação",
            "copy": "Copie somente este prompt:",
            "operator": "O runtime instalado inclui `operations.json` e `OPERATOR_GUIDE.pt-BR.md`; após `ready=true`, o coding agent deve ler ambos e ensinar ao usuário, na conversa, o ciclo operacional completo.",
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
            f"**{labels['readiness']}:** {package['operator']['readiness'][language]}",
            "",
            f"**{labels['installReadiness']}:**",
            "",
            *(
                f"- {item}"
                for item in package["operator"]["installationReadiness"][language]
            ),
            "",
            f"## {labels['installation']}",
            "",
            labels["copy"],
            "",
            "```text",
            install_prompt(value, package, language),
            "```",
            "",
            labels["operator"],
        ]
    )


def operations_document(
    value: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    """Render the neutral machine-readable operator contract for one package."""
    operator = package["operator"]
    return {
        "schemaVersion": 1,
        "package": {
            "id": package["id"],
            "displayName": package["displayName"],
            "version": value["release"]["version"],
            "entrypoint": operator["entrypoint"],
        },
        "readiness": operator["readiness"],
        "installationReadiness": operator["installationReadiness"],
        "memory": operator["memory"],
        "operations": operator["operations"],
        "workflows": operator["workflows"],
        "tutorial": value["tutorial"],
        "compatibility": value["compatibility"],
        "support": value["support"],
    }


def _markdown_cell(value: str) -> str:
    return value.replace("|", "&#124;").replace("\n", " ")


def operator_guide(
    value: dict[str, Any], package: dict[str, Any], language: str
) -> str:
    """Render one human-readable, agent-agnostic operator guide."""
    if language not in {"en", "ptBr"}:
        raise ProductContractError("operator guide language is invalid")
    operator = package["operator"]
    tutorial = value["tutorial"]
    support = value["support"]
    if language == "en":
        labels = {
            "title": "operator guide",
            "neutral": (
                "This is the complete, agent-agnostic operating contract for the "
                "installed runtime. It does not require a formal Skill or an "
                "agent-specific API. Use one public Python 3.10+ executable and "
                "the target-local entrypoint shown below."
            ),
            "entrypoint": "Entrypoint",
            "memory": "Operational memory",
            "canonical": "Canonical state",
            "projections": "Readable projections",
            "ready": "Ready means",
            "installReady": "Installation readiness",
            "plan": "Before a write",
            "planBody": (
                "Inspect read-only, state the intended command, inputs, paths, and "
                "effects, then obtain explicit confirmation. Never infer, reorganize, "
                "or summarize project data for a mutation. Retain placeholders until "
                "the user supplies the corresponding values."
            ),
            "inventory": "Command inventory",
            "command": "Command",
            "kind": "Kind",
            "purpose": "Purpose",
            "inputs": "Inputs",
            "effects": "Effects",
            "examples": "Placeholder examples",
            "workflows": "Workflows",
            "lifecycle": "Installation receipt, rollback, update, and uninstall",
            "tutorial": "Required tutorial after readiness",
            "tutorialBody": (
                "After installer verification returns `ready=true`, read this guide "
                "and `operations.json`, then teach the user the installed harness in "
                "the conversation. Do not create a tutorial file. Cover:"
            ),
            "support": "Support",
            "workflowTitles": {
                "firstUse": "First use",
                "daily": "Daily use",
                "closeResume": "Close and resume",
                "verifyRecover": "Verify or recover",
            },
        }
    else:
        labels = {
            "title": "guia operacional",
            "neutral": (
                "Este é o contrato operacional completo e agent-agnostic do runtime "
                "instalado. Ele não exige uma Skill formal nem uma API específica de "
                "agente. Use um único executável público do Python 3.10+ e o "
                "entrypoint local ao target indicado abaixo."
            ),
            "entrypoint": "Entrypoint",
            "memory": "Memória operacional",
            "canonical": "Estado canônico",
            "projections": "Projeções legíveis",
            "ready": "Readiness significa",
            "installReady": "Readiness de instalação",
            "plan": "Antes de um write",
            "planBody": (
                "Inspecione em modo read-only, informe o comando pretendido, os inputs, "
                "os paths e os efeitos e então obtenha confirmação explícita. Nunca "
                "infira, reorganize nem resuma dados do projeto para uma mutação. "
                "Mantenha placeholders até o usuário fornecer os valores correspondentes."
            ),
            "inventory": "Inventário de comandos",
            "command": "Comando",
            "kind": "Categoria",
            "purpose": "Finalidade",
            "inputs": "Inputs",
            "effects": "Efeitos",
            "examples": "Exemplos com placeholders",
            "workflows": "Workflows",
            "lifecycle": "Receipt de instalação, rollback, update e uninstall",
            "tutorial": "Tutorial obrigatório após readiness",
            "tutorialBody": (
                "Depois que a verificação do instalador retornar `ready=true`, leia este "
                "guia e `operations.json` e ensine ao usuário, na conversa, o harness "
                "instalado. Não crie um arquivo de tutorial. Cubra:"
            ),
            "support": "Suporte",
            "workflowTitles": {
                "firstUse": "Primeiro uso",
                "daily": "Uso diário",
                "closeResume": "Closeout e retomada",
                "verifyRecover": "Verify ou recovery",
            },
        }

    lines = [
        f"# {package['displayName']} — {labels['title']}",
        "",
        labels["neutral"],
        "",
        f"- {labels['entrypoint']}: `{operator['entrypoint']}`",
        f"- Package: `{package['id']}` v`{value['release']['version']}`",
        "",
        f"## {labels['memory']}",
        "",
        operator["memory"]["description"][language],
        "",
        f"- {labels['canonical']}: "
        + ", ".join(f"`{path}`" for path in operator["memory"]["canonical"]),
        f"- {labels['projections']}: "
        + ", ".join(f"`{path}`" for path in operator["memory"]["projections"]),
        "",
        f"## {labels['installReady']}",
        "",
        *(
            f"- {item}"
            for item in operator["installationReadiness"][language]
        ),
        "",
        f"## {labels['ready']}",
        "",
        operator["readiness"][language],
        "",
        f"## {labels['plan']}",
        "",
        labels["planBody"],
        "",
        f"## {labels['inventory']}",
        "",
        (
            f"| {labels['command']} | {labels['kind']} | {labels['purpose']} | "
            f"{labels['inputs']} | {labels['effects']} |"
        ),
        "| --- | --- | --- | --- | --- |",
    ]
    for operation in operator["operations"]:
        inputs = ", ".join(
            f"`{_markdown_cell(item)}`" for item in operation["inputs"]
        )
        lines.append(
            f"| `{operation['command']}` | `{operation['kind']}` | "
            f"{_markdown_cell(operation['purpose'][language])} | {inputs} | "
            f"{_markdown_cell(operation['effects'][language])} |"
        )

    lines.extend(["", f"## {labels['examples']}"])
    for operation in operator["operations"]:
        lines.extend(
            [
                "",
                f"### `{operation['command']}`",
                "",
                "```text",
                operation["example"],
                "```",
            ]
        )

    lines.extend(["", f"## {labels['workflows']}"])
    for workflow_id in WORKFLOW_IDS:
        workflow = operator["workflows"][workflow_id]
        sequence = " → ".join(f"`{step}`" for step in workflow["steps"])
        lines.extend(
            [
                "",
                f"### {labels['workflowTitles'][workflow_id]}",
                "",
                workflow["purpose"][language],
                "",
                sequence,
            ]
        )

    lifecycle_items = (
        item.replace("<id>", package["id"]).replace(
            "<version>", value["release"]["version"]
        )
        for item in tutorial["packageLifecycle"][language]
    )
    lines.extend(
        [
            "",
            f"## {labels['lifecycle']}",
            "",
            *(f"- {item}" for item in lifecycle_items),
        ]
    )

    lines.extend(
        [
            "",
            f"## {labels['tutorial']}",
            "",
            labels["tutorialBody"],
            "",
            *(f"- {item}" for item in tutorial["mustCover"][language]),
            "",
            tutorial["constraints"][language],
            "",
            f"## {labels['support']}",
            "",
            f"- LinkedIn: {support['linkedin']}",
            f"- Email: {support['email']}",
        ]
    )
    return "\n".join(lines)


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
                "operator": item["operator"],
                "installPrompt": {
                    "en": install_prompt(value, item, "en"),
                    "ptBr": install_prompt(value, item, "ptBr"),
                },
            }
        )
    return {
        "schemaVersion": 2,
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
        "compatibility": value["compatibility"],
        "support": value["support"],
        "tutorial": value["tutorial"],
        "executionModeInstruction": value["executionModeInstruction"],
        "ptBrEnglishTerms": value["ptBrEnglishTerms"],
        "packages": packages,
    }
