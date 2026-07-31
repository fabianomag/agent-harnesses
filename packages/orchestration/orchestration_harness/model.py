"""Strict state model and portable identifier/path contracts."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable

from .errors import CollisionError, ValidationError


SCHEMA_VERSION = 1
MANIFEST_KIND = "orchestration-control-plane"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TRANSACTION_PATTERN = re.compile(r"^[0-9a-f]{32}$")
STAGES = frozenset(("registered", "digested", "recorded", "closed"))
MAX_FRONTS = 500
MAX_ALIASES = 20
MAX_NAME_LENGTH = 80
MAX_TEXT_LENGTH = 2_000
MAX_PENDING_LENGTH = 240
MAX_JSON_INTEGER = (1 << 63) - 1
MAX_STATE_COUNTER = 999_999_999

_MANIFEST_KEYS = frozenset(
    (
        "schemaVersion",
        "kind",
        "revision",
        "lastTransaction",
        "activeFocus",
        "fronts",
    )
)
_FRONT_KEYS = frozenset(
    (
        "id",
        "displayName",
        "path",
        "aliases",
        "stage",
        "pending",
        "lastDigest",
        "reflectionCount",
        "recordCount",
        "sessionCount",
    )
)
_RESERVED_FIRST_COMPONENTS = frozenset(
    (
        ".orchestration",
        ".orchestration-journal.json",
        "agents.md",
        "architecture.md",
        "fronts.md",
        "next.md",
    )
)
_WINDOWS_RESERVED_NAMES = frozenset(
    (
        "aux",
        "clock$",
        "con",
        "nul",
        "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    )
)


def _closed_object(
    value: Any,
    expected_keys: frozenset[str],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    observed = frozenset(value)
    missing = sorted(expected_keys - observed)
    extra = sorted(observed - expected_keys)
    if missing:
        raise ValidationError(f"{label} is missing required fields")
    if extra:
        raise ValidationError(f"{label} contains unsupported fields")
    return value


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValidationError("JSON contains a duplicate object key")
        value[key] = child
    return value


def _parse_integer(value: str) -> int:
    if len(value.lstrip("-")) > 19:
        raise ValidationError("JSON integer exceeds the supported range")
    parsed = int(value)
    if abs(parsed) > MAX_JSON_INTEGER:
        raise ValidationError("JSON integer exceeds the supported range")
    return parsed


def _reject_constant(_value: str) -> None:
    raise ValidationError("JSON non-finite numbers are not supported")


def loads_strict_json(text: str) -> Any:
    """Load a closed UTF-8 JSON document without ambiguous constructs."""

    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_pairs,
            parse_int=_parse_integer,
            parse_constant=_reject_constant,
        )
    except ValidationError:
        raise
    except (json.JSONDecodeError, UnicodeError, ValueError) as error:
        raise ValidationError("state is not valid JSON") from error


def dumps_canonical_json(value: Any) -> str:
    """Render deterministic UTF-8 JSON with a final newline."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def validate_identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        raise ValidationError(f"{label} must be a portable lowercase identifier")
    return value


def validate_display_text(
    value: Any,
    *,
    label: str,
    maximum: int = MAX_TEXT_LENGTH,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        raise ValidationError(f"{label} must use Unicode NFC")
    if value != value.strip():
        raise ValidationError(f"{label} must not have surrounding whitespace")
    if not value and not allow_empty:
        raise ValidationError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValidationError(f"{label} is too long")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValidationError(f"{label} must be a single safe line")
    if any(ord(character) < 32 for character in value):
        raise ValidationError(f"{label} contains a control character")
    return value


def validate_relative_path(
    value: Any,
    *,
    label: str = "path",
    allow_reserved: bool = False,
) -> str:
    """Require a canonical forward-slash path valid across major platforms."""

    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty relative path")
    if value != unicodedata.normalize("NFC", value):
        raise ValidationError(f"{label} must use Unicode NFC")
    if "\x00" in value or "\\" in value or value.startswith("~"):
        raise ValidationError(f"{label} is not a portable relative path")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValidationError(f"{label} must be relative")
    if posix.as_posix() != value:
        raise ValidationError(f"{label} must be canonical")
    if not posix.parts or any(part in ("", ".", "..") for part in posix.parts):
        raise ValidationError(f"{label} contains an unsafe component")

    for part in posix.parts:
        if part.endswith((" ", ".")) or ":" in part:
            raise ValidationError(f"{label} contains a non-portable component")
        stem = part.split(".", 1)[0].casefold()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise ValidationError(f"{label} contains a reserved component")

    first = posix.parts[0].casefold()
    if not allow_reserved and (
        first in _RESERVED_FIRST_COMPONENTS
        or first.startswith(".orchestration-")
    ):
        raise ValidationError(f"{label} uses a reserved root component")
    return value


def _nonnegative_integer(value: Any, *, label: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > MAX_STATE_COUNTER
    ):
        raise ValidationError(f"{label} must be a supported non-negative integer")
    return value


@dataclass(frozen=True)
class Front:
    """One registered front and its explicit workflow state."""

    id: str
    display_name: str
    path: str
    aliases: tuple[str, ...]
    stage: str
    pending: str
    last_digest: str
    reflection_count: int
    record_count: int
    session_count: int

    @classmethod
    def create(
        cls,
        *,
        front_id: str,
        display_name: str,
        path: str,
        aliases: Iterable[str] = (),
    ) -> "Front":
        observed_aliases = tuple(
            validate_identifier(alias, label="alias") for alias in aliases
        )
        if len(set(observed_aliases)) != len(observed_aliases):
            raise CollisionError("front contains a duplicate alias")
        alias_values = tuple(sorted(observed_aliases))
        if len(alias_values) > MAX_ALIASES:
            raise ValidationError("front has too many aliases")
        identifier = validate_identifier(front_id, label="front ID")
        if identifier in alias_values:
            raise CollisionError("front ID collides with one of its aliases")
        return cls(
            id=identifier,
            display_name=validate_display_text(
                display_name,
                label="display name",
                maximum=MAX_NAME_LENGTH,
            ),
            path=validate_relative_path(path),
            aliases=alias_values,
            stage="registered",
            pending="Run the first reflection",
            last_digest="",
            reflection_count=0,
            record_count=0,
            session_count=0,
        )

    @classmethod
    def from_dict(cls, value: Any) -> "Front":
        data = _closed_object(value, _FRONT_KEYS, label="front")
        aliases_value = data["aliases"]
        if not isinstance(aliases_value, list):
            raise ValidationError("front aliases must be a JSON array")
        if len(aliases_value) > MAX_ALIASES:
            raise ValidationError("front has too many aliases")
        aliases = tuple(
            validate_identifier(alias, label="alias") for alias in aliases_value
        )
        if len(set(aliases)) != len(aliases):
            raise ValidationError("front aliases must be unique")
        if aliases != tuple(sorted(aliases)):
            raise ValidationError("front aliases must use canonical order")

        stage = data["stage"]
        if not isinstance(stage, str) or stage not in STAGES:
            raise ValidationError("front stage is unsupported")
        front = cls(
            id=validate_identifier(data["id"], label="front ID"),
            display_name=validate_display_text(
                data["displayName"],
                label="display name",
                maximum=MAX_NAME_LENGTH,
            ),
            path=validate_relative_path(data["path"]),
            aliases=aliases,
            stage=stage,
            pending=validate_display_text(
                data["pending"],
                label="pending action",
                maximum=MAX_PENDING_LENGTH,
            ),
            last_digest=validate_display_text(
                data["lastDigest"],
                label="last digest",
                allow_empty=True,
            ),
            reflection_count=_nonnegative_integer(
                data["reflectionCount"],
                label="reflection count",
            ),
            record_count=_nonnegative_integer(
                data["recordCount"],
                label="record count",
            ),
            session_count=_nonnegative_integer(
                data["sessionCount"],
                label="session count",
            ),
        )
        if front.id in front.aliases:
            raise ValidationError("front ID collides with an alias")
        _validate_front_state(front)
        return front

    def to_dict(self) -> dict[str, Any]:
        return {
            "aliases": list(self.aliases),
            "displayName": self.display_name,
            "id": self.id,
            "lastDigest": self.last_digest,
            "path": self.path,
            "pending": self.pending,
            "recordCount": self.record_count,
            "reflectionCount": self.reflection_count,
            "sessionCount": self.session_count,
            "stage": self.stage,
        }


@dataclass(frozen=True)
class Manifest:
    """The only authority for registry, focus, and pending state."""

    revision: int
    last_transaction: str
    active_focus: str | None
    fronts: tuple[Front, ...]

    @classmethod
    def create(
        cls,
        front: Front,
        *,
        transaction_id: str,
    ) -> "Manifest":
        validate_transaction_id(transaction_id)
        _validate_front_state(front)
        return cls(
            revision=1,
            last_transaction=transaction_id,
            active_focus=front.id,
            fronts=(front,),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "Manifest":
        data = _closed_object(value, _MANIFEST_KEYS, label="manifest")
        if data["schemaVersion"] != SCHEMA_VERSION:
            raise ValidationError("manifest schema version is unsupported")
        if data["kind"] != MANIFEST_KIND:
            raise ValidationError("manifest kind is unsupported")
        revision = _nonnegative_integer(data["revision"], label="revision")
        if revision < 1:
            raise ValidationError("manifest revision must start at one")
        transaction_id = validate_transaction_id(data["lastTransaction"])

        fronts_value = data["fronts"]
        if not isinstance(fronts_value, list) or not fronts_value:
            raise ValidationError("manifest must contain at least one front")
        if len(fronts_value) > MAX_FRONTS:
            raise ValidationError("manifest contains too many fronts")
        fronts = tuple(Front.from_dict(front) for front in fronts_value)
        if tuple(front.id for front in fronts) != tuple(
            sorted(front.id for front in fronts)
        ):
            raise ValidationError("manifest fronts must use canonical order")
        _validate_front_collisions(fronts)

        focus = data["activeFocus"]
        if focus is not None:
            focus = validate_identifier(focus, label="active focus")
            if focus not in {front.id for front in fronts}:
                raise ValidationError("active focus does not identify a front")

        return cls(
            revision=revision,
            last_transaction=transaction_id,
            active_focus=focus,
            fronts=tuple(sorted(fronts, key=lambda front: front.id)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "activeFocus": self.active_focus,
            "fronts": [front.to_dict() for front in self.fronts],
            "kind": MANIFEST_KIND,
            "lastTransaction": self.last_transaction,
            "revision": self.revision,
            "schemaVersion": SCHEMA_VERSION,
        }

    def resolve(self, selector: str | None) -> Front:
        if selector is None:
            if self.active_focus is not None:
                selector = self.active_focus
            elif len(self.fronts) == 1:
                return self.fronts[0]
            else:
                raise ValidationError("a front selector is required")
        normalized = validate_identifier(selector, label="front selector")
        for front in self.fronts:
            if normalized == front.id or normalized in front.aliases:
                return front
        raise ValidationError("front selector is not registered")

    def with_front(
        self,
        front: Front,
        *,
        transaction_id: str,
        active_focus: str | None = None,
        preserve_focus: bool = False,
    ) -> "Manifest":
        validate_transaction_id(transaction_id)
        replaced = False
        values: list[Front] = []
        for current in self.fronts:
            if current.id == front.id:
                values.append(front)
                replaced = True
            else:
                values.append(current)
        if not replaced:
            values.append(front)
        _validate_front_collisions(tuple(values))
        focus = self.active_focus if preserve_focus else active_focus
        return Manifest(
            revision=self.revision + 1,
            last_transaction=transaction_id,
            active_focus=focus,
            fronts=tuple(sorted(values, key=lambda value: value.id)),
        )

    def with_focus(self, front_id: str | None, *, transaction_id: str) -> "Manifest":
        if front_id is not None and front_id not in {front.id for front in self.fronts}:
            raise ValidationError("focus does not identify a registered front")
        validate_transaction_id(transaction_id)
        return replace(
            self,
            revision=self.revision + 1,
            last_transaction=transaction_id,
            active_focus=front_id,
        )


def validate_transaction_id(value: Any) -> str:
    if not isinstance(value, str) or TRANSACTION_PATTERN.fullmatch(value) is None:
        raise ValidationError("transaction ID is invalid")
    return value


def _path_parts_casefold(value: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in PurePosixPath(value).parts)


def _paths_overlap(first: str, second: str) -> bool:
    first_parts = _path_parts_casefold(first)
    second_parts = _path_parts_casefold(second)
    length = min(len(first_parts), len(second_parts))
    return first_parts[:length] == second_parts[:length]


def _validate_front_collisions(fronts: tuple[Front, ...]) -> None:
    names: dict[str, str] = {}
    paths: list[tuple[str, str]] = []
    for front in fronts:
        _validate_front_state(front)
        for name in (front.id, *front.aliases):
            folded = name.casefold()
            if folded in names:
                raise CollisionError("front ID or alias collision")
            names[folded] = front.id
        for registered_id, registered_path in paths:
            if _paths_overlap(front.path, registered_path):
                raise CollisionError(
                    f"front path collides with registered front {registered_id}"
                )
        paths.append((front.id, front.path))


def _validate_front_state(front: Front) -> None:
    counts = (
        front.reflection_count,
        front.record_count,
        front.session_count,
    )
    if front.stage == "registered":
        if counts != (0, 0, 0) or front.last_digest:
            raise ValidationError("registered front counters are inconsistent")
        return
    if not front.last_digest:
        raise ValidationError("active front state requires an explicit digest")
    if front.stage == "digested":
        valid = (
            front.reflection_count == front.record_count + 1
            and front.record_count == front.session_count
        )
    elif front.stage == "recorded":
        valid = (
            front.reflection_count == front.record_count
            and front.record_count == front.session_count + 1
        )
    else:
        valid = (
            front.reflection_count == front.record_count
            and front.record_count == front.session_count
            and front.session_count >= 1
        )
    if not valid:
        raise ValidationError("front lifecycle counters are inconsistent")


def parse_manifest(text: str) -> Manifest:
    return Manifest.from_dict(loads_strict_json(text))


def render_manifest(manifest: Manifest) -> str:
    return dumps_canonical_json(manifest.to_dict())
