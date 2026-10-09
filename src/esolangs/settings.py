"""Immutable specification choices for generation and execution."""

import inspect
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any, TypedDict, cast

from esolangs._dialects import (
    EXPRESSION_SYNTAXES,
    LIST_UPDATES,
    LITERAL_POLICIES,
    ROTATIONS,
)
from esolangs._grapheme import INTEGER_CONVERSIONS
from esolangs._mammalian import MODULI
from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, resolve

#: Every setting a language's ``dialect=`` may take, and its values.
_CHOICES: dict[str, tuple[int | str, ...]] = {
    "expression_syntax": EXPRESSION_SYNTAXES,
    "list_update": LIST_UPDATES,
    "literal_policy": LITERAL_POLICIES,
    "rotation": ROTATIONS,
    "integer_conversion": INTEGER_CONVERSIONS,
    "cell_modulus": MODULI,
    "io_modulus": MODULI,
}


@dataclass(frozen=True, init=False)
class DialectSettings:
    """Explicit overrides; omitted choices retain each language's defaults."""

    _items: tuple[tuple[str, int | str | None], ...]

    def __init__(self, **choices: int | str | None) -> None:
        """Copy typed overrides; language-specific validation precedes use."""
        integer = {key for key, values in _CHOICES.items() if type(values[0]) is int}
        text = set(_CHOICES) - integer
        for key, value in choices.items():
            if key not in integer | text:
                known = sorted(integer | text)
                close = get_close_matches(key, known, n=1, cutoff=0.6)
                suggestion = f" (did you mean {close[0]}?)" if close else ""
                raise ArgumentError(
                    f"unknown dialect setting: {key}{suggestion}; "
                    f"known settings: {', '.join(known)}"
                )
            valid = (
                (type(value) is int or value is None)
                if key in integer
                else isinstance(value, str)
            )
            if not valid:
                raise ArgumentError(f"invalid value for dialect setting {key}")
        object.__setattr__(self, "_items", tuple(sorted(choices.items())))

    def options(self, language: str) -> dict[str, Any]:
        """Return validated overrides supported by ``language``."""
        name = resolve(language)
        values: dict[str, Any] = dict(self._items)
        dialect = LANGUAGES[name].dialect
        try:
            if dialect is None:
                if values:
                    raise ArgumentError(f"{name} supports no dialect settings")
            else:
                keys = list(inspect.signature(dialect).parameters)
                if values.keys() - set(keys):
                    raise TypeError(f"supported dialect settings: {', '.join(keys)}")
                dialect(**values)
        except (TypeError, ValueError) as error:
            raise ArgumentError(
                f"invalid dialect settings for {name}: {error}"
            ) from error
        return values


def dialect_options(language: str, settings: DialectSettings | None) -> dict[str, Any]:
    """Validate the public settings object before source or input acquisition."""
    if settings is None:
        return {}
    if not isinstance(settings, DialectSettings):
        raise ArgumentError("settings must be a DialectSettings object")
    return settings.options(language)


def effective_settings(
    language: str, program: object, settings: DialectSettings | None
) -> DialectSettings | None:
    """Merge explicit choices over retained same-language source provenance."""
    from esolangs.raster import Raster
    from esolangs.tagged import _Tagged

    if settings is not None and not isinstance(settings, DialectSettings):
        raise ArgumentError("settings must be a DialectSettings object")
    if not isinstance(program, (_Tagged, Raster)) or program.language != resolve(
        language
    ):
        return settings
    retained = program.settings
    dialect_options(language, retained)
    if retained is None:
        return settings
    if settings is None:
        return retained
    # Validate the combined choices after explicit fields replace retained fields.
    merged = DialectSettings(**(dict(retained._items) | dict(settings._items)))  # noqa: SLF001
    dialect_options(language, merged)
    return merged


class DialectOption(TypedDict):
    """Supported resolutions of conflicting rules within one specification."""

    default: int | str | None
    choices: tuple[int | str, ...] | None
    minimum: int | None
    nullable: bool
    requires: dict[str, tuple[str, ...]]


def dialect_choices(language: str) -> dict[str, DialectOption]:
    """Return fresh choices and defaults drawn from the interpreter signature."""
    from esolangs._execution import interpreter_module

    name = resolve(language)
    dialect = LANGUAGES[name].dialect
    if dialect is None:
        return {}
    keys = list(inspect.signature(dialect).parameters)
    machine = interpreter_module(name)._Machine  # noqa: SLF001 - interpreter adapter
    parameters = inspect.signature(machine).parameters
    return {
        key: {
            "default": cast("int | str | None", parameters[key].default),
            "choices": _CHOICES[key],
            "minimum": None,
            "nullable": False,
            "requires": {},
        }
        for key in keys
    }
