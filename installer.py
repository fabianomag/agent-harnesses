#!/usr/bin/env python3
"""Dependency-free, target-local installer for Agent Harnesses."""

import argparse
import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path


PRODUCT = json.loads(r'''{
  "packages": [
    {
      "aliases": [
        "project",
        "single-project",
        "project-harness"
      ],
      "asset": "project-harness-0.2.0.zip",
      "complexity": {
        "en": "Low",
        "level": "low",
        "ptBr": "Baixa"
      },
      "content": {
        "en": {
          "bestFor": "One explicit project that needs checkpoints, closeout, and reliable resumption.",
          "notFor": "Coordination across workspace children or independent project roots.",
          "scenario": "I need one project to remember context between work sessions.",
          "summary": "A small project-local lifecycle for durable context and the next action.",
          "whatItChanges": "Creates a bounded project state directory and managed context blocks inside the selected project."
        },
        "ptBr": {
          "bestFor": "Um projeto explícito que precisa de checkpoints, closeout e retomada confiável.",
          "notFor": "Coordenação entre projetos filhos de um workspace ou raízes de projetos independentes.",
          "scenario": "Preciso que um único projeto preserve contexto entre sessões de trabalho.",
          "summary": "Um pequeno ciclo local ao projeto para contexto durável e a próxima ação.",
          "whatItChanges": "Cria um diretório limitado de estado e blocos gerenciados de contexto dentro do projeto selecionado."
        }
      },
      "displayName": "Project Harness",
      "id": "project-harness",
      "strengths": {
        "en": [
          "Checkpoints",
          "Close and resume",
          "Fast setup"
        ],
        "ptBr": [
          "Checkpoints",
          "Close e resume",
          "Setup rápido"
        ]
      }
    },
    {
      "aliases": [
        "workspace",
        "workspace-harness",
        "workspace-coordination"
      ],
      "asset": "workspace-coordination-0.2.0.zip",
      "complexity": {
        "en": "Medium",
        "level": "medium",
        "ptBr": "Média"
      },
      "content": {
        "en": {
          "bestFor": "Contained child projects that share one workspace boundary and a small shared index.",
          "notFor": "Independent repositories or a single project with no child coordination.",
          "scenario": "I have autonomous child folders inside one containing workspace.",
          "summary": "A coordinator index that preserves child-local ownership.",
          "whatItChanges": "Creates a workspace control directory and child-local coordination records."
        },
        "ptBr": {
          "bestFor": "Projetos filhos contidos que compartilham o limite de um workspace e um pequeno índice compartilhado.",
          "notFor": "Repositórios independentes ou um único projeto sem coordenação de projetos filhos.",
          "scenario": "Tenho pastas de projetos filhos autônomos dentro de um único workspace.",
          "summary": "Um índice de coordenação que preserva o ownership local de cada projeto filho.",
          "whatItChanges": "Cria um diretório de controle do workspace e registros locais de coordenação de cada projeto filho."
        }
      },
      "displayName": "Workspace Harness",
      "id": "workspace-coordination",
      "strengths": {
        "en": [
          "Child index",
          "Ownership boundaries",
          "Shared workspace view"
        ],
        "ptBr": [
          "Índice de projetos filhos",
          "Limites de ownership",
          "Visão compartilhada do workspace"
        ]
      }
    },
    {
      "aliases": [
        "multi-project",
        "cross-project",
        "cross"
      ],
      "asset": "cross-project-0.2.0.zip",
      "complexity": {
        "en": "Medium",
        "level": "medium",
        "ptBr": "Média"
      },
      "content": {
        "en": {
          "bestFor": "Existing independent project roots that need explicit handoffs and transversal coordination.",
          "notFor": "A contained child index or a new strict registry with journaled recovery.",
          "scenario": "I need handoffs and shared state across existing independent projects.",
          "summary": "A canonical cross-project manifest with bounded reflection and structural sync.",
          "whatItChanges": "Creates a canonical coordination manifest and managed root projections without taking ownership of project-local details."
        },
        "ptBr": {
          "bestFor": "Raízes de projetos independentes existentes que precisam de handoffs explícitos e coordenação transversal.",
          "notFor": "Um índice de projetos filhos contidos ou um registry novo e estrito com recovery por journal.",
          "scenario": "Preciso de handoffs e estado compartilhado entre projetos independentes que já existem.",
          "summary": "Um manifest canônico entre projetos, com reflexão limitada e sincronização estrutural.",
          "whatItChanges": "Cria um manifest canônico de coordenação e projeções gerenciadas na raiz, sem assumir o ownership dos detalhes locais de cada projeto."
        }
      },
      "displayName": "Multi-Project Harness",
      "id": "cross-project",
      "strengths": {
        "en": [
          "Independent projects",
          "Handoffs",
          "Structural sync"
        ],
        "ptBr": [
          "Projetos independentes",
          "Handoffs",
          "Sincronização estrutural"
        ]
      }
    },
    {
      "aliases": [
        "control-plane",
        "control-plane-harness",
        "orchestration"
      ],
      "asset": "orchestration-0.2.0.zip",
      "complexity": {
        "en": "High",
        "level": "high",
        "ptBr": "Alta"
      },
      "content": {
        "en": {
          "bestFor": "A new control plane whose registry and lifecycle mutations justify transactions and recovery.",
          "notFor": "Adopting an existing project layout, dispatching agents, or executing project work.",
          "scenario": "I am creating a new structure that needs a strict registry, transactions, and recovery.",
          "summary": "A transactional local control plane for a deliberate new Master structure.",
          "whatItChanges": "Creates a strict Master registry and managed front structure through validated transactional mutations. It does not call models or dispatch agents."
        },
        "ptBr": {
          "bestFor": "Um control plane novo cujo registry e cujas alterações de ciclo de vida justificam transactions e recovery.",
          "notFor": "Adotar um layout de projetos existente, despachar agents ou executar o trabalho dos projetos.",
          "scenario": "Estou criando uma estrutura nova que precisa de registry estrito, transactions e recovery.",
          "summary": "Um control plane local e transacional para uma estrutura Master deliberadamente nova.",
          "whatItChanges": "Cria um Master registry estrito e uma estrutura gerenciada de frentes por alterações transacionais validadas. Não chama models nem despacha agents."
        }
      },
      "displayName": "Control Plane Harness",
      "id": "orchestration",
      "strengths": {
        "en": [
          "Strict registry",
          "Transactions",
          "Recovery"
        ],
        "ptBr": [
          "Registry estrito",
          "Transactions",
          "Recovery"
        ]
      }
    }
  ],
  "promptInstructions": {
    "en": "Before any write, confirm the explicit target and use a public Python 3.10+ executable; never use a private Codex runtime. Download the ZIP and its adjacent .sha256 sidecar into an isolated temporary directory, verify the checksum before extraction or execution, then extract it. Run installer.py doctor first. Stop without writes on a mismatch and only recommend a better fit; never silently substitute another harness. Run install with --dry-run and then --apply, follow the selected package README to initialize the target, and run verify. Report success only when verify returns ready=true. Clean up temporary files and report the receipt plus uninstall/rollback instructions. Do not edit unrelated documentation, PATH, or .gitignore, and do not install a global Skill.",
    "ptBr": "Antes de qualquer escrita, confirme o diretório-alvo explícito e use um executável público do Python 3.10+; nunca use um runtime privado do Codex. Baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide o checksum antes de extrair ou executar e só então extraia. Execute primeiro `installer.py doctor`. Em caso de incompatibilidade, pare sem escrever nada e apenas recomende a melhor adequação; nunca substitua silenciosamente por outro harness. Execute `install` com `--dry-run` e depois `--apply`, siga o README do package selecionado para inicializar o diretório-alvo e execute `verify`. Só reporte sucesso quando `verify` retornar `ready=true`. Limpe os arquivos temporários e informe o comprovante e as instruções de `uninstall`/rollback. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global."
  },
  "ptBrEnglishTerms": [
    "harness",
    "coding agent",
    "workspace",
    "prompt",
    "Skill",
    "CLI",
    "dry-run",
    "apply",
    "rollback",
    "runtime",
    "manifest",
    "checkpoint",
    "closeout",
    "single writer",
    "control plane",
    "guardrails",
    "release",
    "commit",
    "handoff"
  ],
  "release": {
    "minimumPython": "3.10",
    "repository": "https://github.com/fabianomag/agent-harnesses",
    "site": {
      "en": "https://fabianomag.com/artifacts/agent-harnesses",
      "ptBr": "https://fabianomag.com/pt-br/artefatos/agent-harnesses"
    },
    "tag": "v0.2.0",
    "version": "0.2.0"
  },
  "schemaVersion": 1
}''')
VERSION = PRODUCT["release"]["version"]
MARKERS = {
    "project-harness": Path(".project-harness/state.json"),
    "workspace-coordination": Path(".workspace-coordination/workspace.json"),
    "cross-project": Path("harness.config.json"),
    "orchestration": Path(".orchestration/manifest.json"),
}
RUNTIME_RELATIVE = Path(".agent-harnesses/runtime")
RECEIPT_NAME = ".agent-harness-receipt.json"


class InstallerFailure(RuntimeError):
    def __init__(self, code, phase, message, remediation, ready=False):
        RuntimeError.__init__(self, message)
        self.result = {
            "code": code,
            "phase": phase,
            "message": message,
            "remediation": remediation,
            "ready": bool(ready),
        }


def _result(code, phase, message, remediation="", ready=False):
    return {
        "code": code,
        "phase": phase,
        "message": message,
        "remediation": remediation,
        "ready": bool(ready),
    }


def _is_link_like(path):
    try:
        metadata = path.lstat()
    except OSError as error:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "Path metadata cannot be read safely.",
            "Choose one existing real directory with no linked components.",
        ) from error
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and attributes & reparse)


def _lexists(path):
    return os.path.lexists(os.fspath(path))


def _safe_existing_directory(value):
    if not value or not str(value).strip():
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "The target must be explicit.",
            "Pass --target with one existing project or workspace directory.",
        )
    requested = Path(value)
    lexical = requested if requested.is_absolute() else Path.cwd() / requested
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        if _lexists(current) and _is_link_like(current):
            raise InstallerFailure(
                "E_TARGET_AMBIGUOUS",
                "preflight",
                "The target contains a linked path component.",
                "Choose one existing real directory with no symlinks or reparse points.",
            )
    try:
        target = lexical.resolve(strict=True)
    except OSError as error:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "The target does not resolve to an existing directory.",
            "Create or select the exact project or workspace directory first.",
        ) from error
    if not target.is_dir() or _is_link_like(target):
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "The target is not a real directory.",
            "Choose one existing real project or workspace directory.",
        )
    forbidden = {Path(target.anchor), Path.home().resolve()}
    if target in forbidden or target.name.casefold() == ".git" or ".git" in target.parts:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "The selected target is too broad or is Git metadata.",
            "Choose the exact project or workspace root, never a home, filesystem, or .git directory.",
        )
    return target


def _package_for_selector(selector):
    normalized = selector.strip().lower()
    for package in PRODUCT["packages"]:
        if normalized in package["aliases"]:
            return package
    raise InstallerFailure(
        "E_HARNESS_MISMATCH",
        "preflight",
        "The selector does not identify one public harness.",
        "Use project-harness, workspace-coordination, cross-project, or orchestration.",
    )


def _marker_ids(target):
    return [package_id for package_id, relative in MARKERS.items() if _lexists(target / relative)]


def _recommend(package_id):
    names = {item["id"]: item["displayName"] for item in PRODUCT["packages"]}
    return "%s (`%s`)" % (names[package_id], package_id)


def _doctor(package, target):
    marker_ids = _marker_ids(target)
    if len(marker_ids) > 1:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "preflight",
            "The target contains markers for more than one harness.",
            "Resolve the existing harness ownership before installing another runtime.",
        )
    if marker_ids and marker_ids[0] != package["id"]:
        observed = marker_ids[0]
        raise InstallerFailure(
            "E_HARNESS_MISMATCH",
            "preflight",
            "The target is already initialized for a different harness.",
            "Keep the target unchanged and use %s." % _recommend(observed),
        )
    runtime_root = target / ".agent-harnesses"
    if _lexists(runtime_root) and (_is_link_like(runtime_root) or not runtime_root.is_dir()):
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "preflight",
            "The target-local runtime boundary is not a real directory.",
            "Resolve the .agent-harnesses collision without overwriting it.",
        )
    if package["id"] == "orchestration" and not marker_ids:
        master_like = any(
            _lexists(target / name)
            for name in ("AGENTS.md", "ARCHITECTURE.md", "NEXT.md", "FRONTS.md", "harness.config.json")
        )
        project_directories = [
            child
            for child in target.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
        if master_like or project_directories:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "preflight",
                "Control Plane Harness cannot safely adopt this existing project structure.",
                "Keep the target unchanged and evaluate %s for existing independent projects."
                % _recommend("cross-project"),
            )
    initialized = bool(marker_ids and marker_ids[0] == package["id"])
    message = "Preflight passed for the selected harness."
    if initialized:
        message = "Preflight passed; the target already has the selected harness marker."
    return _result("OK", "initialized" if initialized else "preflight", message, ready=False)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path):
    def reject_duplicate(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate property")
            value[key] = item
        return value

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate)
    except (OSError, UnicodeError, ValueError) as error:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The package manifest is unreadable or invalid.",
            "Discard the download and fetch the immutable release assets again.",
        ) from error


def _source_from_bundle(root, expected_id):
    manifest_path = root / "bundle-manifest.json"
    package_root = root / "package"
    if not manifest_path.is_file() or not package_root.is_dir():
        return None
    manifest = _load_json(manifest_path)
    if manifest.get("package", {}).get("id") != expected_id or manifest.get("package", {}).get("version") != VERSION:
        raise InstallerFailure(
            "E_HARNESS_MISMATCH",
            "downloaded",
            "The extracted bundle does not match the selected harness.",
            "Discard it and download the exact selected asset.",
        )
    return package_root, manifest.get("files")


def _source_from_repository(root, expected_id):
    catalog_path = root / "catalog/harnesses.json"
    package_root = root / "packages" / expected_id
    if not catalog_path.is_file() or not package_root.is_dir():
        return None
    catalog = _load_json(catalog_path)
    for entry in catalog.get("packages", []):
        if entry.get("id") == expected_id and entry.get("version") == VERSION:
            return package_root, entry.get("files")
    raise InstallerFailure(
        "E_HARNESS_MISMATCH",
        "downloaded",
        "The source tree does not contain the selected v%s package." % VERSION,
        "Use the matching immutable release bundle.",
    )


def _validate_inventory(package_root, inventory):
    if not isinstance(inventory, list) or not inventory:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The package inventory is missing.",
            "Discard the source and fetch the immutable release assets again.",
        )
    expected = {}
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The package inventory is invalid.", "Discard the source and fetch it again.")
        relative = Path(entry["path"])
        if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The package inventory contains an unsafe path.", "Discard the source and fetch it again.")
        expected[relative.as_posix()] = entry["sha256"]
    observed = {}
    for path in sorted(package_root.rglob("*")):
        if _is_link_like(path):
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The package contains a linked entry.", "Discard the source and fetch it again.")
        if path.is_file():
            observed[path.relative_to(package_root).as_posix()] = _sha256(path)
    if observed != expected:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The package bytes do not match the signed inventory.",
            "Discard the source and fetch the immutable release assets again.",
        )
    return expected


def _safe_extract(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members:
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive is empty.", "Fetch the asset again.")
        for member in members:
            relative = Path(member.filename)
            mode = member.external_attr >> 16
            if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts) or stat.S_ISLNK(mode):
                raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive contains an unsafe entry.", "Discard the archive.")
            candidate = (destination / relative).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive escapes its extraction boundary.", "Discard the archive.")
        bundle.extractall(destination)


def _download_source(package, temporary):
    repository = PRODUCT["release"]["repository"]
    tag = PRODUCT["release"]["tag"]
    asset = package["asset"]
    url = "%s/releases/download/%s/%s" % (repository, tag, asset)
    archive = temporary / asset
    sidecar = temporary / (asset + ".sha256")
    try:
        urllib.request.urlretrieve(url, archive)
        urllib.request.urlretrieve(url + ".sha256", sidecar)
    except Exception as error:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The immutable release asset or checksum could not be downloaded.",
            "Check connectivity and the v%s release, then retry." % VERSION,
        ) from error
    try:
        fields = sidecar.read_text(encoding="ascii").strip().split()
    except (OSError, UnicodeError) as error:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The checksum sidecar is unreadable.", "Download both assets again.") from error
    if len(fields) != 2 or fields[1].lstrip("*") != asset or fields[0] != _sha256(archive):
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The release archive checksum does not match its sidecar.",
            "Discard both files and do not extract or execute the archive.",
        )
    extracted = temporary / "extracted"
    extracted.mkdir()
    _safe_extract(archive, extracted)
    roots = [path.parent for path in extracted.rglob("bundle-manifest.json") if (path.parent / "package").is_dir()]
    if len(roots) != 1:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release bundle layout is invalid.", "Discard the archive and report the immutable asset.")
    source = _source_from_bundle(roots[0], package["id"])
    if source is None:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release bundle is incomplete.", "Discard the archive and report the immutable asset.")
    return source


def _local_source(package_id):
    base = Path(__file__).resolve().parent
    for root in (base, base.parent):
        source = _source_from_bundle(root, package_id)
        if source is not None:
            return source
        source = _source_from_repository(root, package_id)
        if source is not None:
            return source
    return None


def _runtime_destination(target, package_id):
    return target / RUNTIME_RELATIVE / package_id / VERSION


def _receipt(package_id, inventory):
    return {
        "schemaVersion": 1,
        "package": {"id": package_id, "version": VERSION},
        "files": [{"path": path, "sha256": inventory[path]} for path in sorted(inventory)],
    }


def _canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _verify_runtime_files(destination, package_id):
    if not destination.is_dir() or _is_link_like(destination):
        raise InstallerFailure("E_NOT_READY", "downloaded", "The selected runtime is not installed.", "Run install --dry-run and install --apply first.")
    receipt_path = destination / RECEIPT_NAME
    receipt = _load_json(receipt_path)
    if receipt.get("schemaVersion") != 1 or receipt.get("package") != {"id": package_id, "version": VERSION}:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installation receipt is invalid.", "Do not overwrite it; use uninstall only after restoring receipt-owned bytes.")
    inventory = receipt.get("files")
    if not isinstance(inventory, list):
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installation receipt has no valid inventory.", "Restore the exact installed package before retrying.")
    expected = {entry.get("path"): entry.get("sha256") for entry in inventory if isinstance(entry, dict)}
    observed = {}
    for path in sorted(destination.rglob("*")):
        if _is_link_like(path):
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installed runtime contains a linked entry.", "Inspect it without following links.")
        if path.is_file() and path.name != RECEIPT_NAME:
            observed[path.relative_to(destination).as_posix()] = _sha256(path)
    if None in expected or observed != expected or receipt_path.read_bytes() != _canonical_bytes(receipt):
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "Installed runtime bytes differ from the receipt.", "Do not overwrite or uninstall changed bytes; inspect the target-local runtime.")
    return receipt


def _publish_no_replace(source, destination):
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        if function(os.fsencode(source), os.fsencode(destination), 0x00000004) != 0:
            number = ctypes.get_errno()
            if number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(number, os.strerror(number), os.fspath(destination))
            raise OSError(number or errno.EIO, os.strerror(number or errno.EIO))
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        function = getattr(libc, "renameat2", None)
        if function is None:
            raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "Atomic no-overwrite publication is unavailable.", "Use a supported macOS, Linux, or Windows runtime.")
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        if function(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
            number = ctypes.get_errno()
            if number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(number, os.strerror(number), os.fspath(destination))
            raise OSError(number or errno.EIO, os.strerror(number or errno.EIO))
        return
    if os.name == "nt":
        os.rename(source, destination)
        return
    raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "Atomic no-overwrite publication is unavailable.", "Use a supported macOS, Linux, or Windows runtime.")


def _copy_install(source_root, inventory, destination, package_id):
    expected = _validate_inventory(source_root, inventory)
    if _lexists(destination):
        _verify_runtime_files(destination, package_id)
        return "unchanged"
    runtime_root = destination.parents[2]
    created = []
    current = runtime_root
    missing = []
    while not _lexists(current):
        missing.append(current)
        current = current.parent
    if _is_link_like(current):
        raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "The runtime boundary contains a linked component.", "Resolve the collision without overwriting it.")
    for path in reversed(missing):
        path.mkdir()
        created.append(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for parent in (runtime_root, runtime_root / package_id, destination.parent):
        if parent not in created and parent.exists() and _is_link_like(parent):
            raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "The runtime boundary contains a linked component.", "Resolve the collision without overwriting it.")
    stage = runtime_root / (".install-%s-%s" % (package_id, uuid.uuid4().hex))
    try:
        stage.mkdir()
        for relative_text in sorted(expected):
            relative = Path(relative_text)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with (source_root / relative).open("rb") as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
        (stage / RECEIPT_NAME).write_bytes(_canonical_bytes(_receipt(package_id, expected)))
        _verify_runtime_files(stage, package_id)
        try:
            _publish_no_replace(stage, destination)
        except FileExistsError:
            _verify_runtime_files(destination, package_id)
            shutil.rmtree(stage)
            return "unchanged"
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        for path in reversed(created):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    return "installed"


def _runtime_command(package_id, destination, target):
    python = sys.executable
    if package_id == "project-harness":
        return [python, "-B", str(destination / "project_harness.py"), "verify", "--root", str(target)]
    if package_id == "workspace-coordination":
        return [python, "-B", str(destination / "workspace_coordination.py"), "--root", str(target), "verify"]
    if package_id == "cross-project":
        return [python, "-B", str(destination / "scripts/cross_project.py"), "hq-sync", "--root", str(target)]
    return [python, "-B", str(destination / "hq.py"), "--root", str(target), "--json", "hq-sync"]


def _verify_ready(package, target):
    destination = _runtime_destination(target, package["id"])
    _verify_runtime_files(destination, package["id"])
    marker_ids = _marker_ids(target)
    if not marker_ids:
        raise InstallerFailure(
            "E_NOT_READY",
            "installed",
            "The runtime is installed, but the target is uninitialized.",
            "Follow the selected package README initialization dry-run/apply steps, then run verify again.",
        )
    if marker_ids != [package["id"]]:
        raise InstallerFailure("E_HARNESS_MISMATCH", "initialized", "The target marker does not match the installed runtime.", "Keep the target unchanged and select its existing harness.")
    environment = os.environ.copy()
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    process = subprocess.run(_runtime_command(package["id"], destination, target), check=False, capture_output=True, env=environment)
    if process.returncode != 0:
        raise InstallerFailure(
            "E_NOT_READY",
            "initialized",
            "The target is initialized, but operational verification failed.",
            "Run the selected runtime verifier directly and resolve its bounded findings; do not claim installation success.",
        )
    return _result("OK", "ready", "The runtime is installed and the initialized target passed operational verification.", ready=True)


def _uninstall(package, target, apply):
    destination = _runtime_destination(target, package["id"])
    _verify_runtime_files(destination, package["id"])
    if not apply:
        return _result("OK", "installed", "Uninstall dry-run passed; only receipt-owned unchanged runtime bytes would be removed.", ready=False)
    quarantine = destination.parent / (".remove-%s-%s" % (VERSION, uuid.uuid4().hex))
    os.rename(destination, quarantine)
    try:
        shutil.rmtree(quarantine)
    except BaseException:
        if not _lexists(destination) and _lexists(quarantine):
            os.rename(quarantine, destination)
        raise
    for parent in (destination.parent, destination.parents[1], destination.parents[2]):
        try:
            parent.rmdir()
        except OSError:
            break
    return _result("OK", "downloaded", "The receipt-owned runtime was removed; initialized target files were left untouched.", ready=False)


def _parser():
    parser = argparse.ArgumentParser(description="Install one Agent Harness runtime into one explicit target.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "verify"):
        command = commands.add_parser(name)
        command.add_argument("selector")
        command.add_argument("--target", required=True)
        command.add_argument("--json", action="store_true")
    install = commands.add_parser("install")
    install.add_argument("selector")
    install.add_argument("--target", required=True)
    mode = install.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    install.add_argument("--json", action="store_true")
    uninstall = commands.add_parser("uninstall")
    uninstall.add_argument("selector")
    uninstall.add_argument("--target", required=True)
    mode = uninstall.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    uninstall.add_argument("--json", action="store_true")
    return parser


def _render(result, as_json):
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    prefix = "READY" if result["ready"] else ("PASS" if result["code"] == "OK" else "STOP")
    text = "%s [%s] %s" % (prefix, result["code"], result["message"])
    if result["remediation"]:
        text += " " + result["remediation"]
    return text


def main(argv=None):
    arguments_list = list(sys.argv[1:] if argv is None else argv)
    wants_json = "--json" in arguments_list
    if sys.version_info < (3, 10):
        result = _result("E_PYTHON_UNSUPPORTED", "downloaded", "Python 3.10 or newer is required.", "Install a public Python 3.10+ executable; do not use a private Codex runtime.")
        print(_render(result, wants_json))
        return 2
    arguments = _parser().parse_args(arguments_list)
    try:
        package = _package_for_selector(arguments.selector)
        target = _safe_existing_directory(arguments.target)
        doctor = _doctor(package, target)
        if arguments.command == "doctor":
            result = doctor
        elif arguments.command == "verify":
            result = _verify_ready(package, target)
        elif arguments.command == "uninstall":
            result = _uninstall(package, target, arguments.apply)
        elif not arguments.apply:
            destination = _runtime_destination(target, package["id"])
            if _lexists(destination):
                _verify_runtime_files(destination, package["id"])
                message = "Install dry-run passed; the exact runtime is already installed."
            else:
                message = "Install dry-run passed; the selected runtime can be installed without initializing the target."
            result = _result("OK", "downloaded", message, ready=False)
        else:
            source = _local_source(package["id"])
            if source is None:
                with tempfile.TemporaryDirectory(prefix="agent-harnesses-") as directory:
                    source = _download_source(package, Path(directory))
                    action = _copy_install(source[0], source[1], _runtime_destination(target, package["id"]), package["id"])
            else:
                action = _copy_install(source[0], source[1], _runtime_destination(target, package["id"]), package["id"])
            result = _result("OK", "installed", "The selected runtime is %s; the target still requires operational initialization and verify." % action, "Follow the selected package README. Do not report ready until verify returns ready=true.", ready=False)
    except InstallerFailure as error:
        result = error.result
    except (OSError, ValueError, zipfile.BadZipFile):
        result = _result("E_INITIALIZATION_CONFLICT", "downloaded", "The operation failed safely without overwriting target content.", "Inspect the target-local runtime boundary and retry from a clean immutable bundle.")
    print(_render(result, arguments.json))
    return 0 if result["code"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
