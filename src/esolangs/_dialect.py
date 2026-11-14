"""Immutable dialect schemas and choices, independent of the catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from keyword import iskeyword
from typing import cast, overload
from unicodedata import normalize

from esolangs.exceptions import ArgumentError
from esolangs.runtime._validate import _argument_repr

type Scalar = int | str


@dataclass(frozen=True, slots=True, init=False)
class DialectSchema:
    """A language's enumerated choices and defaults, frozen at declaration."""

    language: str
    _choices: tuple[tuple[str, tuple[Scalar, ...]], ...]
    _defaults: tuple[tuple[str, Scalar], ...]

    def __init__(
        self,
        language: str,
        choices: Mapping[str, tuple[Scalar, ...]],
        defaults: Mapping[str, Scalar],
    ) -> None:
        """Freeze the schema and require a typed default for every choice."""
        if not isinstance(language, str) or not str.__str__(language).strip():
            raise ArgumentError("a dialect schema requires a language")
        if not isinstance(choices, Mapping) or not isinstance(defaults, Mapping):
            raise ArgumentError("dialect choices and defaults must be mappings")
        if choices.keys() != defaults.keys():
            raise ArgumentError("dialect defaults must match declared choices")
        frozen = {}
        frozen_defaults = {}
        for key, declared in choices.items():
            if not isinstance(key, str):
                raise ArgumentError("dialect names must be identifiers")
            name = str.__str__(key)
            if not name.isidentifier() or iskeyword(name) or name in frozen:
                raise ArgumentError("dialect names must be distinct identifiers")
            if not isinstance(declared, tuple):
                raise ArgumentError("dialect enums must be tuples")
            values = tuple(declared)
            if not values or any(type(value) not in (int, str) for value in values):
                raise ArgumentError(
                    "dialect choices must be nonempty integer/string enums"
                )
            if any(type(value) is not type(values[0]) for value in values):
                raise ArgumentError("each dialect choice requires one value type")
            if len(set(values)) != len(values):
                raise ArgumentError("dialect choices must be distinct")
            default = defaults[key]
            if type(default) is not type(values[0]) or default not in values:
                raise ArgumentError(
                    f"default for {key} must be a declared dialect choice"
                )
            frozen[name] = values
            frozen_defaults[name] = default
        object.__setattr__(self, "language", str.__str__(language))
        object.__setattr__(self, "_choices", tuple(sorted(frozen.items())))
        object.__setattr__(self, "_defaults", tuple(sorted(frozen_defaults.items())))

    @property
    def choices(self) -> dict[str, tuple[Scalar, ...]]:
        """Return fresh enumerations; callers cannot mutate the declaration."""
        return dict(self._choices)

    @property
    def defaults(self) -> dict[str, Scalar]:
        """Return fresh defaults."""
        return dict(self._defaults)

    def validate(self, choices: Mapping[str, Scalar]) -> dict[str, Scalar]:
        """Copy overrides after validating them within this language's scope."""
        if not isinstance(choices, Mapping):
            raise ArgumentError("dialect overrides must be a mapping")
        known = self.choices
        checked: dict[str, Scalar] = {}
        for given, value in choices.items():
            if not isinstance(given, str):
                raise ArgumentError("dialect override names must be strings")
            key = str.__str__(given)
            if key in checked:
                raise ArgumentError(f"duplicate dialect override: {key}")
            if key not in known:
                names = sorted(known)
                close = get_close_matches(key, names, n=1, cutoff=0.6)
                suggestion = f" (did you mean {close[0]}?)" if close else ""
                known_names = (
                    f"known settings: {', '.join(names)}" if names else "it has none"
                )
                raise ArgumentError(
                    f"unknown dialect setting for {self.language}: {key}{suggestion}; "
                    f"{known_names}"
                )
            values = known[key]
            if type(value) is not type(values[0]) or value not in values:
                available = ", ".join(
                    choice if isinstance(choice, str) else _argument_repr(choice)
                    for choice in values
                )
                raise ArgumentError(
                    f"invalid value for dialect setting {key}: "
                    f"{_argument_repr(value)}; "
                    f"choices: {available}"
                )
            checked[key] = value
        return checked


@dataclass(frozen=True, slots=True, init=False, repr=False)
class DialectSettings:
    """Validated overrides bound to one language schema."""

    _schema: DialectSchema
    _items: tuple[tuple[str, Scalar], ...]

    @overload
    def __init__(self, schema: DialectSchema, /, **choices: Scalar) -> None: ...

    @overload
    def __init__(self, /, *, schema: DialectSchema, **choices: Scalar) -> None: ...

    def __init__(
        self,
        schema: DialectSchema | None = None,
        /,
        **choices: Scalar | DialectSchema,
    ) -> None:
        """Freeze choices against an explicit schema; use Language.settings."""
        # Keep the keyword constructor working when no positional schema was supplied.
        declared = choices.pop("schema", None) if schema is None else schema
        if not isinstance(declared, DialectSchema):
            raise ArgumentError("dialect settings require a language schema")
        checked = declared.validate(cast("dict[str, Scalar]", choices))
        object.__setattr__(self, "_schema", declared)
        object.__setattr__(self, "_items", tuple(sorted(checked.items())))

    @property
    def language(self) -> str:
        """Return the canonical owner of these choices."""
        return self._schema.language

    def __repr__(self) -> str:
        """Spell the public factory that reconstructs these choices."""

        def literal(value: Scalar) -> str:
            try:
                return repr(value)
            except ValueError:
                assert isinstance(value, int)
                return hex(value)

        if any(normalize("NFKC", key) != key for key, _ in self._items):
            # Python normalizes identifiers in call syntax, but preserves dict keys.
            items = ", ".join(
                f"{key!r}: {literal(value)}" for key, value in self._items
            )
            choices = f"**{{{items}}}"
        else:
            choices = ", ".join(f"{key}={literal(value)}" for key, value in self._items)
        return f"Language({self.language!r}).settings({choices})"

    def options(self) -> dict[str, Scalar]:
        """Return the validated overrides as a new dict."""
        return self._schema.validate(dict(self._items))
