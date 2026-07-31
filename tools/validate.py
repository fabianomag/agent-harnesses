"""Validate the public repository contracts with Python's standard library."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

try:
    from tools import catalog as common_catalog
except ModuleNotFoundError:  # Direct execution from the tools directory.
    import catalog as common_catalog  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_PACKAGES = common_catalog.EXPECTED_PACKAGES

REQUIRED_PATHS = (
    Path(".gitignore"),
    Path("AGENTS.md"),
    Path("assets/harnesses.svg"),
    *(Path(f"assets/{package_id}.svg") for package_id in EXPECTED_PACKAGES),
    Path("catalog/harnesses.json"),
    Path("CONTRIBUTING.md"),
    Path("graphs/harnesses.graph.json"),
    *(
        Path(f"graphs/{package_id}.graph.json")
        for package_id in EXPECTED_PACKAGES
    ),
    Path("LICENSE"),
    Path("README.md"),
    Path("SECURITY.md"),
    Path("schemas/harness-catalog.schema.json"),
    Path("schemas/harness-package.schema.json"),
    Path("tools/build_common.py"),
    Path("tools/catalog.py"),
    Path("tools/package_manager.py"),
    Path("tools/run_checks.py"),
    Path("tools/validate.py"),
    Path("tests/test_common.py"),
    Path("tests/test_validate.py"),
)

IGNORED_DIRECTORY_NAMES = {".git"}
MAX_TEXT_FILE_BYTES = 1_000_000
MAX_PRIVATE_PATTERN_FILE_BYTES = 256_000
MAX_PRIVATE_PATTERNS = 1_000


@dataclass(frozen=True, order=True)
class Issue:
    """A validation finding that never contains matched source text."""

    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        location = self.path if self.line <= 0 else f"{self.path}:{self.line}"
        return f"ERROR [{self.code}] {location}: {self.message}"


class ContractError(ValueError):
    """Raised when an external validation input violates its contract."""


def _relative_display(path: Path, repository_root: Path) -> str:
    try:
        return path.relative_to(repository_root).as_posix()
    except ValueError:
        return "<external>"


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema_instance(
    value: Any,
    schema: dict[str, Any],
    *,
    artifact: str,
    location: str = "$",
    _root_schema: dict[str, Any] | None = None,
) -> list[Issue]:
    """Validate the JSON Schema subset used by the package contract."""

    root_schema = schema if _root_schema is None else _root_schema
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/"):
            return [
                Issue(
                    artifact,
                    0,
                    "SCHEMA_REFERENCE",
                    f"{location} uses an unsupported schema reference",
                )
            ]
        resolved: Any = root_schema
        try:
            for token in reference[2:].split("/"):
                key = token.replace("~1", "/").replace("~0", "~")
                resolved = resolved[key]
        except (KeyError, TypeError):
            return [
                Issue(
                    artifact,
                    0,
                    "SCHEMA_REFERENCE",
                    f"{location} uses an unresolved schema reference",
                )
            ]
        if not isinstance(resolved, dict):
            return [
                Issue(
                    artifact,
                    0,
                    "SCHEMA_REFERENCE",
                    f"{location} uses a non-object schema reference",
                )
            ]
        return validate_schema_instance(
            value,
            resolved,
            artifact=artifact,
            location=location,
            _root_schema=root_schema,
        )

    issues: list[Issue] = []
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for child_schema in all_of:
            if isinstance(child_schema, dict):
                issues.extend(
                    validate_schema_instance(
                        value,
                        child_schema,
                        artifact=artifact,
                        location=location,
                        _root_schema=root_schema,
                    )
                )

    expected_type = schema.get("type")
    if expected_type is not None and not _json_type_matches(value, expected_type):
        return [
            Issue(
                artifact,
                0,
                "SCHEMA_TYPE",
                f"{location} must have JSON type {expected_type}",
            )
        ]

    if "const" in schema and value != schema["const"]:
        issues.append(
            Issue(artifact, 0, "SCHEMA_CONST", f"{location} violates a constant")
        )

    if "enum" in schema and value not in schema["enum"]:
        issues.append(
            Issue(artifact, 0, "SCHEMA_ENUM", f"{location} is outside its enum")
        )

    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(
                Issue(
                    artifact,
                    0,
                    "SCHEMA_MIN_LENGTH",
                    f"{location} is shorter than allowed",
                )
            )
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            issues.append(
                Issue(
                    artifact,
                    0,
                    "SCHEMA_PATTERN",
                    f"{location} does not match its required format",
                )
            )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                issues.append(
                    Issue(
                        artifact,
                        0,
                        "SCHEMA_REQUIRED",
                        f"{location} is missing a required property",
                    )
                )

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    issues.append(
                        Issue(
                            artifact,
                            0,
                            "SCHEMA_ADDITIONAL_PROPERTY",
                            f"{location} contains an unsupported property",
                        )
                    )

        for key, child_schema in properties.items():
            if key in value:
                issues.extend(
                    validate_schema_instance(
                        value[key],
                        child_schema,
                        artifact=artifact,
                        location=f"{location}.{key}",
                        _root_schema=root_schema,
                    )
                )

    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(
                Issue(
                    artifact,
                    0,
                    "SCHEMA_MIN_ITEMS",
                    f"{location} contains too few items",
                )
            )
        maximum = schema.get("maxItems")
        if isinstance(maximum, int) and len(value) > maximum:
            issues.append(
                Issue(
                    artifact,
                    0,
                    "SCHEMA_MAX_ITEMS",
                    f"{location} contains too many items",
                )
            )
        prefix_items = schema.get("prefixItems")
        prefix_count = 0
        if isinstance(prefix_items, list):
            prefix_count = len(prefix_items)
            for index, child_schema in enumerate(prefix_items[: len(value)]):
                if isinstance(child_schema, dict):
                    issues.extend(
                        validate_schema_instance(
                            value[index],
                            child_schema,
                            artifact=artifact,
                            location=f"{location}[{index}]",
                            _root_schema=root_schema,
                        )
                    )

        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            start = prefix_count if isinstance(prefix_items, list) else 0
            for index, item in enumerate(value[start:], start=start):
                issues.extend(
                    validate_schema_instance(
                        item,
                        item_schema,
                        artifact=artifact,
                        location=f"{location}[{index}]",
                        _root_schema=root_schema,
                    )
                )
        elif item_schema is False and len(value) > prefix_count:
            issues.append(
                Issue(
                    artifact,
                    0,
                    "SCHEMA_ITEMS",
                    f"{location} contains unsupported trailing items",
                )
            )

    return issues


def _load_json(path: Path, repository_root: Path) -> tuple[Any | None, list[Issue]]:
    display = _relative_display(path, repository_root)
    try:
        return common_catalog.load_json_strict(path), []
    except common_catalog.CommonContractError:
        return None, [
            Issue(display, 0, "INVALID_JSON", "file is not readable UTF-8 JSON")
        ]


def _is_absolute_reference(reference: str) -> bool:
    parsed = urlsplit(reference)
    windows_path = PureWindowsPath(reference)
    return (
        Path(reference).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or bool(parsed.scheme)
        or bool(parsed.netloc)
        or reference.startswith("~")
    )


def validate_reference(
    repository_root: Path,
    declaring_file: Path,
    reference: Any,
    *,
    field_name: str,
) -> list[Issue]:
    """Require a relative file reference that resolves inside the repository."""

    display = _relative_display(declaring_file, repository_root)
    if not isinstance(reference, str) or not reference:
        return [
            Issue(
                display,
                0,
                "REFERENCE_TYPE",
                f"{field_name} must be a non-empty string",
            )
        ]
    try:
        is_absolute = _is_absolute_reference(reference)
    except (OSError, ValueError):
        return [
            Issue(
                display,
                0,
                "REFERENCE_INVALID",
                f"{field_name} is not a valid file reference",
            )
        ]
    if is_absolute:
        return [
            Issue(
                display,
                0,
                "ABSOLUTE_REFERENCE",
                f"{field_name} must be repository-relative",
            )
        ]

    root = repository_root.resolve()
    try:
        candidate = (declaring_file.parent / reference).resolve(strict=False)
    except (OSError, ValueError):
        return [
            Issue(
                display,
                0,
                "REFERENCE_INVALID",
                f"{field_name} is not a valid file reference",
            )
        ]
    try:
        candidate.relative_to(root)
    except ValueError:
        return [
            Issue(
                display,
                0,
                "REFERENCE_ESCAPE",
                f"{field_name} resolves outside the repository",
            )
        ]

    if not candidate.is_file():
        return [
            Issue(
                display,
                0,
                "REFERENCE_MISSING",
                f"{field_name} does not resolve to a regular file",
            )
        ]
    return []


def _walk_repository(repository_root: Path) -> Iterable[tuple[Path, list[str], list[str]]]:
    for current, directory_names, file_names in os.walk(
        repository_root, followlinks=False
    ):
        directory_names[:] = [
            name for name in directory_names if name not in IGNORED_DIRECTORY_NAMES
        ]
        yield Path(current), directory_names, file_names


def find_symlink_issues(repository_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for current, directory_names, file_names in _walk_repository(repository_root):
        for name in (*directory_names, *file_names):
            path = current / name
            if path.is_symlink():
                issues.append(
                    Issue(
                        _relative_display(path, repository_root),
                        0,
                        "SYMLINK",
                        "symbolic links are not allowed",
                    )
                )
    return issues


def _repository_files(repository_root: Path) -> Iterable[Path]:
    for current, _directory_names, file_names in _walk_repository(repository_root):
        for name in file_names:
            if current == repository_root and name == ".git":
                # A linked worktree records its Git administrative directory in
                # this root marker. It is not part of the public repository.
                continue
            path = current / name
            if not path.is_symlink():
                yield path


def _built_in_safety_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    email_pattern = re.compile(
        r"\b[A-Z0-9._%+-]+" + "@" + r"[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )
    private_key_header = re.compile(
        re.escape("-----BEGIN ")
        + r"(?:RSA |EC |OPENSSH )?"
        + re.escape("PRIVATE KEY-----")
    )
    credential_assignment = re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
        r"password|private[_-]?key)\b['\"]?\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9_./+=-]{12,}",
        re.IGNORECASE,
    )
    bearer_token = re.compile(
        r"\b" + "Bearer" + r"\s+[A-Za-z0-9._~+/-]{12,}",
        re.IGNORECASE,
    )
    return (
        (
            "ABSOLUTE_PATH",
            re.compile(
                r"(?:^|[\s\"'(=\[])"
                r"/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~+-]+)*",
                re.MULTILINE,
            ),
        ),
        (
            "WINDOWS_ABSOLUTE_PATH",
            re.compile(
                r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]"
                r"(?:[^\\/\r\n]+[\\/])*[^\\/\r\n]+"
            ),
        ),
        (
            "UNC_PATH",
            re.compile(
                r"(?<![\\A-Za-z0-9_])\\\\"
                r"[^\\/\r\n]+\\[^\\/\r\n]+(?:\\[^\\/\r\n]+)*"
            ),
        ),
        ("HOME_PATH", re.compile(r"(?<![A-Za-z0-9_])~[\\/][^\s'\"`]+")),
        ("EMAIL", email_pattern),
        (
            "PHONE",
            re.compile(r"(?<!\w)\+\d(?:[\s().-]*\d){9,14}(?!\w)"),
        ),
        ("PRIVATE_KEY", private_key_header),
        ("CREDENTIAL_ASSIGNMENT", credential_assignment),
        ("BEARER_TOKEN", bearer_token),
        ("AWS_ACCESS_KEY", re.compile(r"\b" + "AKIA" + r"[0-9A-Z]{16}\b")),
        (
            "GITHUB_TOKEN",
            re.compile(r"\b" + "ghp_" + r"[A-Za-z0-9]{30,}\b"),
        ),
        (
            "OPENAI_TOKEN",
            re.compile(r"\b" + "sk-" + r"[A-Za-z0-9_-]{20,}\b"),
        ),
        (
            "JWT",
            re.compile(
                r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
                r"\.[A-Za-z0-9_-]{8,}\b"
            ),
        ),
    )


def scan_text(
    path: str,
    text: str,
    *,
    private_patterns: Sequence[str] = (),
) -> list[Issue]:
    """Scan text without including a match or excerpt in findings."""

    issues: list[Issue] = []
    seen: set[tuple[str, int]] = set()
    for code, pattern in _built_in_safety_patterns():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            key = (code, line)
            if key not in seen:
                issues.append(
                    Issue(path, line, code, "public-safety pattern matched")
                )
                seen.add(key)

    folded_text = text.casefold()
    for private_pattern in private_patterns:
        start = folded_text.find(private_pattern.casefold())
        while start >= 0:
            line = text.count("\n", 0, start) + 1
            key = ("PRIVATE_PATTERN", line)
            if key not in seen:
                issues.append(
                    Issue(
                        path,
                        line,
                        "PRIVATE_PATTERN",
                        "external private pattern matched",
                    )
                )
                seen.add(key)
            start = folded_text.find(private_pattern.casefold(), start + 1)
    return issues


def load_private_patterns(path: Path, repository_root: Path) -> tuple[str, ...]:
    """Load literal patterns from outside the repository without logging them."""

    if path.is_symlink():
        raise ContractError("private pattern input must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ContractError("private pattern input is not a readable file") from error

    root = repository_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        pass
    else:
        raise ContractError("private pattern input must remain outside the repository")

    if not resolved.is_file():
        raise ContractError("private pattern input is not a regular file")
    if resolved.stat().st_size > MAX_PRIVATE_PATTERN_FILE_BYTES:
        raise ContractError("private pattern input exceeds the size limit")

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ContractError("private pattern input is not readable UTF-8") from error

    patterns = tuple(line.strip() for line in text.splitlines() if line.strip())
    if not patterns:
        raise ContractError("private pattern input contains no usable patterns")
    if len(patterns) > MAX_PRIVATE_PATTERNS:
        raise ContractError("private pattern input contains too many patterns")
    if any(len(pattern) < 3 for pattern in patterns):
        raise ContractError("private patterns must contain at least three characters")
    return patterns


def scan_repository_text(
    repository_root: Path,
    *,
    private_patterns: Sequence[str] = (),
) -> list[Issue]:
    issues: list[Issue] = []
    for path in _repository_files(repository_root):
        display = _relative_display(path, repository_root)
        try:
            size = path.stat().st_size
        except OSError:
            issues.append(
                Issue(display, 0, "UNREADABLE_FILE", "file metadata is unreadable")
            )
            continue
        if size > MAX_TEXT_FILE_BYTES:
            issues.append(
                Issue(display, 0, "FILE_TOO_LARGE", "file exceeds the baseline limit")
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            issues.append(
                Issue(display, 0, "NON_TEXT_FILE", "file is not readable UTF-8 text")
            )
            continue
        issues.extend(
            scan_text(display, text, private_patterns=private_patterns)
        )
    return issues


def _validate_package_set(
    repository_root: Path, schema: dict[str, Any]
) -> list[Issue]:
    issues: list[Issue] = []
    packages_root = repository_root / "packages"
    if not packages_root.is_dir():
        return [
            Issue("packages", 0, "PACKAGES_MISSING", "package directory is missing")
        ]

    actual_entries = {path.name for path in packages_root.iterdir()}
    expected_entries = set(EXPECTED_PACKAGES)
    for missing in sorted(expected_entries - actual_entries):
        issues.append(
            Issue(
                f"packages/{missing}",
                0,
                "PACKAGE_MISSING",
                "required package directory is missing",
            )
        )
    for unexpected in sorted(actual_entries - expected_entries):
        issues.append(
            Issue(
                f"packages/{unexpected}",
                0,
                "PACKAGE_UNEXPECTED",
                "unexpected package-root entry",
            )
        )

    observed_ids: list[str] = []
    for package_id, display_name in EXPECTED_PACKAGES.items():
        package_root = packages_root / package_id
        if not package_root.is_dir():
            if package_root.exists():
                issues.append(
                    Issue(
                        f"packages/{package_id}",
                        0,
                        "PACKAGE_TYPE",
                        "required package entry must be a directory",
                    )
                )
            continue
        manifest_path = package_root / "harness.package.json"
        manifest, load_issues = _load_json(manifest_path, repository_root)
        issues.extend(load_issues)
        if not isinstance(manifest, dict):
            continue

        manifest_display = _relative_display(manifest_path, repository_root)
        issues.extend(
            validate_schema_instance(
                manifest,
                schema,
                artifact=manifest_display,
            )
        )

        observed_id = manifest.get("id")
        if isinstance(observed_id, str):
            observed_ids.append(observed_id)
        if observed_id != package_id:
            issues.append(
                Issue(
                    manifest_display,
                    0,
                    "PACKAGE_ID_MISMATCH",
                    "manifest ID does not match its package directory",
                )
            )
        if manifest.get("displayName") != display_name:
            issues.append(
                Issue(
                    manifest_display,
                    0,
                    "PACKAGE_NAME_MISMATCH",
                    "manifest display name does not match the package contract",
                )
            )

        issues.extend(
            validate_reference(
                repository_root,
                manifest_path,
                manifest.get("$schema"),
                field_name="$schema",
            )
        )
        issues.extend(
            validate_reference(
                repository_root,
                manifest_path,
                manifest.get("readme"),
                field_name="readme",
            )
        )

    if len(set(observed_ids)) != len(observed_ids):
        issues.append(
            Issue(
                "packages",
                0,
                "DUPLICATE_PACKAGE_ID",
                "package IDs must be unique",
            )
        )
    return issues


def validate_repository(
    repository_root: Path = REPOSITORY_ROOT,
    *,
    private_pattern_file: Path | None = None,
) -> list[Issue]:
    """Validate repository shape, package contracts, references, and safety."""

    repository_root = repository_root.resolve()
    issues: list[Issue] = []

    for relative_path in REQUIRED_PATHS:
        candidate = repository_root / relative_path
        if not candidate.is_file():
            issues.append(
                Issue(
                    relative_path.as_posix(),
                    0,
                    "REQUIRED_FILE",
                    "required baseline file is missing",
                )
            )

    license_path = repository_root / "LICENSE"
    try:
        license_text = license_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        license_text = ""
    if not license_text.startswith("MIT License\n"):
        issues.append(
            Issue(
                "LICENSE",
                0,
                "LICENSE_CONTRACT",
                "license must use the MIT license text",
            )
        )
    public_holder = "Copyright (c) 2026 " + "Fabiano Magalhães"
    if public_holder not in license_text:
        issues.append(
            Issue(
                "LICENSE",
                0,
                "LICENSE_HOLDER",
                "license must document the approved public holder",
            )
        )

    issues.extend(find_symlink_issues(repository_root))

    schema_path = repository_root / "schemas/harness-package.schema.json"
    schema, schema_issues = _load_json(schema_path, repository_root)
    issues.extend(schema_issues)
    if isinstance(schema, dict):
        issues.extend(_validate_package_set(repository_root, schema))

    catalog_schema_path = repository_root / "schemas/harness-catalog.schema.json"
    catalog_schema, catalog_schema_issues = _load_json(
        catalog_schema_path, repository_root
    )
    issues.extend(catalog_schema_issues)
    catalog_path = repository_root / common_catalog.CATALOG_PATH
    catalog_value, catalog_issues = _load_json(catalog_path, repository_root)
    issues.extend(catalog_issues)
    if isinstance(catalog_schema, dict) and isinstance(catalog_value, dict):
        issues.extend(
            validate_schema_instance(
                catalog_value,
                catalog_schema,
                artifact=common_catalog.CATALOG_PATH.as_posix(),
            )
        )

    try:
        expected_artifacts = common_catalog.generated_artifacts(repository_root)
    except common_catalog.CommonContractError:
        issues.append(
            Issue(
                ".",
                0,
                "COMMON_CONTRACT",
                "common artifacts cannot be derived from package contracts",
            )
        )
    else:
        for relative_path, expected_bytes in expected_artifacts.items():
            try:
                actual_bytes = (repository_root / relative_path).read_bytes()
            except OSError:
                actual_bytes = None
            if actual_bytes != expected_bytes:
                issues.append(
                    Issue(
                        relative_path.as_posix(),
                        0,
                        "GENERATED_DRIFT",
                        "generated artifact differs from package contracts",
                    )
                )

    for path in _repository_files(repository_root):
        if path.suffix == ".json":
            _value, json_issues = _load_json(path, repository_root)
            issues.extend(json_issues)

    private_patterns: tuple[str, ...] = ()
    if private_pattern_file is not None:
        try:
            private_patterns = load_private_patterns(
                private_pattern_file, repository_root
            )
        except ContractError:
            issues.append(
                Issue(
                    ".",
                    0,
                    "PRIVATE_PATTERN_INPUT",
                    "external private pattern input violates its contract",
                )
            )

    issues.extend(
        scan_repository_text(
            repository_root,
            private_patterns=private_patterns,
        )
    )
    return sorted(set(issues))


def _git_paths(
    repository_root: Path, arguments: Sequence[str]
) -> tuple[set[str], Issue | None]:
    process = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False,
        capture_output=True,
        text=False,
    )
    if process.returncode != 0:
        return set(), Issue(
            ".",
            0,
            "GIT_SCOPE",
            "Git could not evaluate the requested scope",
        )
    try:
        paths = {
            value.decode("utf-8", errors="strict")
            for value in process.stdout.split(b"\0")
            if value
        }
    except UnicodeDecodeError:
        return set(), Issue(
            ".",
            0,
            "GIT_SCOPE",
            "Git returned a path that is not UTF-8",
        )
    return paths, None


def validate_git_scope(
    repository_root: Path,
    *,
    package_id: str,
    baseline: str,
) -> list[Issue]:
    """Require every path changed since a baseline to remain in one package."""

    if package_id not in EXPECTED_PACKAGES:
        return [
            Issue(
                ".",
                0,
                "SCOPE_PACKAGE",
                "scope package is not part of the repository contract",
            )
        ]

    if re.fullmatch(r"[0-9a-fA-F]{7,64}", baseline) is None:
        return [
            Issue(
                ".",
                0,
                "SCOPE_BASELINE",
                "baseline must be an abbreviated or full commit object ID",
            )
        ]

    verification = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{baseline}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=False,
    )
    if verification.returncode != 0:
        return [
            Issue(
                ".",
                0,
                "SCOPE_BASELINE",
                "baseline does not resolve to a local commit",
            )
        ]

    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "merge-base",
            "--is-ancestor",
            baseline,
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=False,
    )
    if ancestry.returncode != 0:
        return [
            Issue(
                ".",
                0,
                "SCOPE_BASELINE",
                "baseline must be an ancestor of HEAD",
            )
        ]

    revision_process = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "rev-list",
            f"{baseline}..HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if revision_process.returncode != 0:
        return [
            Issue(
                ".",
                0,
                "GIT_SCOPE",
                "Git could not enumerate commits after the baseline",
            )
        ]

    committed_commands = tuple(
        (
            "diff-tree",
            "--root",
            "-m",
            "--no-commit-id",
            "--name-only",
            "--no-renames",
            "-r",
            "-z",
            commit,
        )
        for commit in revision_process.stdout.splitlines()
        if commit
    )
    commands = (
        *committed_commands,
        ("diff", "--cached", "--name-only", "--no-renames", "-z"),
        ("diff", "--name-only", "--no-renames", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
        ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
    )
    changed_paths: set[str] = set()
    issues: list[Issue] = []
    for command in commands:
        paths, issue = _git_paths(repository_root, command)
        changed_paths.update(paths)
        if issue is not None:
            issues.append(issue)

    allowed_prefix = f"packages/{package_id}/"
    for changed_path in sorted(changed_paths):
        if not changed_path.startswith(allowed_prefix):
            issues.append(
                Issue(
                    changed_path,
                    0,
                    "SCOPE_VIOLATION",
                    "changed path is outside the assigned package",
                )
            )
    return issues


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate package contracts and public-safety boundaries."
    )
    parser.add_argument(
        "--private-pattern-file",
        type=Path,
        help="literal deny patterns from a file outside the repository",
    )
    parser.add_argument(
        "--scope",
        choices=sorted(EXPECTED_PACKAGES),
        help="package ID whose Git write scope should be checked",
    )
    parser.add_argument(
        "--base",
        help="local baseline commit used with --scope",
    )
    arguments = parser.parse_args(argv)
    if bool(arguments.scope) != bool(arguments.base):
        parser.error("--scope and --base must be supplied together")
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    issues = validate_repository(
        REPOSITORY_ROOT,
        private_pattern_file=arguments.private_pattern_file,
    )
    if arguments.scope and arguments.base:
        issues.extend(
            validate_git_scope(
                REPOSITORY_ROOT,
                package_id=arguments.scope,
                baseline=arguments.base,
            )
        )

    if issues:
        for issue in sorted(set(issues)):
            print(issue.render())
        print(f"FAIL: {len(set(issues))} validation issue(s)")
        return 1

    scope_suffix = " with package scope" if arguments.scope else ""
    print(
        "PASS: repository baseline validated "
        f"({len(EXPECTED_PACKAGES)} package contracts){scope_suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
