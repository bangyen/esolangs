"""Immutable specification choices for generation and execution."""

from dataclasses import dataclass
from typing import Any

from esolangs._brainfuck import BrainfuckDialect
from esolangs._dialects import (
    FalseDialect,
    FlowchartDialect,
    LineDialect,
    PacklangLiterals,
    expression_syntax,
    index_base,
)
from esolangs._mammalian import MammalianModuli
from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, resolve


@dataclass(frozen=True, init=False)
class DialectSettings:
    """Explicit overrides; omitted choices retain each language's defaults."""

    _items: tuple[tuple[str, int | str | None], ...]

    def __init__(self, **choices: int | str | None) -> None:
        """Copy typed overrides; language-specific validation precedes use."""
        integer = {"cell_modulus", "io_modulus", "tape_size", "index_base", "pick_base"}
        text = {
            "boundary",
            "eof",
            "expression_syntax",
            "literal_policy",
            "unset_variables",
            "unknown_commands",
            "scheduling",
            "deque_cursor",
        }
        for key, value in choices.items():
            if key not in integer | text:
                raise ArgumentError(f"unknown dialect setting: {key}")
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
        validators: dict[str, Any] = {
            "brainfuck": BrainfuckDialect,
            "factor": BrainfuckDialect,
            "unary": BrainfuckDialect,
            "line": LineDialect,
            "false": FalseDialect,
            "flowchart": FlowchartDialect,
            "slow_acv_mammalian": MammalianModuli,
        }
        values: dict[str, Any] = dict(self._items)
        try:
            if language_id == "bitdeque":
                _single(values, "index_base", index_base, 0)
            elif language_id == "alight":
                _single(values, "expression_syntax", expression_syntax, "infix")
            elif language_id == "packlang":
                PacklangLiterals(
                    **{
                        "policy" if key == "literal_policy" else key: value
                        for key, value in values.items()
                    }
                )
            elif language_id in validators:
                validators[language_id](**values)
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


def _single(values: dict[str, Any], key: str, validator: Any, default: Any) -> None:
    if values.keys() - {key}:
        raise TypeError(f"supported dialect setting: {key}")
    validator(values.get(key, default))
