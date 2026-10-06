"""Immutable specification choices for generation and execution."""

import inspect
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any, TypedDict, cast

from esolangs._dialects import (
    EXPRESSION_SYNTAXES,
    LITERAL_POLICIES,
    PacklangLiterals,
    expression_syntax,
)
from esolangs._grapheme import INTEGER_CONVERSIONS, GraphemeDialect
from esolangs._mammalian import MODULI, MammalianModuli
from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, resolve

_VALIDATORS: dict[str, Any] = {
    "grapheme": GraphemeDialect,
    "slow_acv_mammalian": MammalianModuli,
}


@dataclass(frozen=True, init=False)
class DialectSettings:
    """Explicit overrides; omitted choices retain each language's defaults."""

    _items: tuple[tuple[str, int | str | None], ...]

    def __init__(self, **choices: int | str | None) -> None:
        """Copy typed overrides; language-specific validation precedes use."""
        integer = {"cell_modulus", "io_modulus"}
        text = {"expression_syntax", "literal_policy", "integer_conversion"}
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
        language_id = LANGUAGES[name].id
        values: dict[str, Any] = dict(self._items)
        try:
            if language_id == "alight":
                _single(values, "expression_syntax", expression_syntax, "infix")
            elif language_id == "packlang":
                PacklangLiterals(
                    **{
                        "policy" if key == "literal_policy" else key: value
                        for key, value in values.items()
                    }
                )
            elif language_id in _VALIDATORS:
                _VALIDATORS[language_id](**values)
            elif values:
                raise ArgumentError(f"{name} supports no dialect settings")
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


def _single(values: dict[str, Any], key: str, validator: Any, default: Any) -> None:
    if values.keys() - {key}:
        raise TypeError(f"supported dialect setting: {key}")
    validator(values.get(key, default))


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
    language_id = LANGUAGES[name].id
    singles = {"alight": "expression_syntax", "packlang": "literal_policy"}
    if language_id in singles:
        keys = [singles[language_id]]
    elif language_id in _VALIDATORS:
        keys = list(inspect.signature(_VALIDATORS[language_id]).parameters)
    else:
        return {}
    choices: dict[str, tuple[int | str, ...]] = {
        "expression_syntax": EXPRESSION_SYNTAXES,
        "literal_policy": LITERAL_POLICIES,
        "integer_conversion": INTEGER_CONVERSIONS,
        "cell_modulus": MODULI,
        "io_modulus": MODULI,
    }
    machine = interpreter_module(name)._Machine  # noqa: SLF001 - interpreter adapter
    parameters = inspect.signature(machine).parameters
    return {
        key: {
            "default": cast("int | str | None", parameters[key].default),
            "choices": choices[key],
            "minimum": None,
            "nullable": False,
            "requires": {},
        }
        for key in keys
    }
