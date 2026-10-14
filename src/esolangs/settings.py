"""Immutable specification choices for generation and execution."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any, TypedDict, cast

from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, resolve

#: Every setting a language's ``dialect=`` may take, and its values.
_CHOICES: dict[str, tuple[int | str, ...]] = {
    key: values
    for language in LANGUAGES.values()
    for key, values in (language.dialect_values or {}).items()
}


@dataclass(frozen=True, init=False)
class DialectSettings:
    """Explicit overrides; omitted choices retain each language's defaults."""

    _items: tuple[tuple[str, int | str | None], ...]

    def __init__(self, **choices: int | str | None) -> None:
        """Copy typed overrides; language-specific validation precedes use."""
        integer = {key for key, values in _CHOICES.items() if type(values[0]) is int}
        for key, value in choices.items():
            if key not in _CHOICES:
                known = sorted(_CHOICES)
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
        if dialect is None:
            if values:
                raise ArgumentError(f"{name} supports no dialect settings")
        else:
            keys = _dialect_keys(dialect)
            unknown = values.keys() - set(keys)
            if unknown:
                raise ArgumentError(
                    f"invalid dialect settings for {name}: "
                    f"unknown setting(s): {', '.join(sorted(unknown))}; "
                    f"supported dialect settings: {', '.join(keys)}"
                )
            try:
                dialect(**values)
            except (TypeError, ValueError) as error:
                raise ArgumentError(
                    f"invalid dialect settings for {name}: {error}"
                ) from error
        return values


def _dialect_keys(dialect: Callable[..., Any]) -> list[str]:
    """Return the setting names a dialect validator accepts."""
    return list(inspect.signature(dialect).parameters)


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
    from esolangs.compressed import CompressedText
    from esolangs.raster import Raster
    from esolangs.tagged import _Tagged

    if settings is not None and not isinstance(settings, DialectSettings):
        raise ArgumentError("settings must be a DialectSettings object")
    if not isinstance(
        program, (_Tagged, Raster, CompressedText)
    ) or program.language != resolve(language):
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
    """A dialect setting's default and its accepted choices."""

    default: int | str | None
    choices: tuple[int | str, ...]


def dialect_choices(language: str) -> dict[str, DialectOption]:
    """Return fresh choices and defaults drawn from the interpreter signature."""
    from esolangs.runtime._execution import interpreter_module

    name = resolve(language)
    dialect = LANGUAGES[name].dialect
    if dialect is None:
        return {}
    keys = _dialect_keys(dialect)
    machine = interpreter_module(name)._Machine  # noqa: SLF001 - interpreter adapter
    parameters = inspect.signature(machine).parameters
    return {
        key: {
            "default": cast("int | str | None", parameters[key].default),
            "choices": _CHOICES[key],
        }
        for key in keys
    }
