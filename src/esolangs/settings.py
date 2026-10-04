"""Immutable specification choices for generation and execution."""

import inspect
from dataclasses import dataclass
from typing import Any, TypedDict, cast

from esolangs._brainfuck import EOF_POLICIES, BrainfuckDialect
from esolangs._dialects import (
    DEQUE_CURSORS,
    EXPRESSION_SYNTAXES,
    INDEX_BASES,
    LITERAL_POLICIES,
    SCHEDULINGS,
    TAPE_BOUNDARIES,
    UNKNOWN_POLICIES,
    UNSET_POLICIES,
    FalseDialect,
    FlowchartDialect,
    LineDialect,
    PacklangLiterals,
    expression_syntax,
    index_base,
)
from esolangs._framing import INPUT_FRAMINGS, InputFraming
from esolangs._grapheme import INTEGER_CONVERSIONS, GraphemeDialect
from esolangs._jaune import UNDEFINED_TARGETS, JauneDialect
from esolangs._laserfuck import LaserfuckDialect
from esolangs._mammalian import MODULI, MammalianModuli
from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, resolve

_VALIDATORS: dict[str, Any] = {
    "brainfuck": BrainfuckDialect,
    "factor": BrainfuckDialect,
    "unary": BrainfuckDialect,
    "line": LineDialect,
    "jaune": JauneDialect,
    "laserfuck": LaserfuckDialect,
    "grapheme": GraphemeDialect,
    "unsquare": InputFraming,
    "decleq": InputFraming,
    "addsubjump": InputFraming,
    "minifuck": InputFraming,
    "false": FalseDialect,
    "flowchart": FlowchartDialect,
    "slow_acv_mammalian": MammalianModuli,
}


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
            "undefined_targets",
            "integer_conversion",
            "input_framing",
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
    # Dependent overrides (wrap + retained tape_size) validate only after merging.
    merged = DialectSettings(**(dict(retained._items) | dict(settings._items)))  # noqa: SLF001
    dialect_options(language, merged)
    return merged


def _single(values: dict[str, Any], key: str, validator: Any, default: Any) -> None:
    if values.keys() - {key}:
        raise TypeError(f"supported dialect setting: {key}")
    validator(values.get(key, default))


class DialectOption(TypedDict):
    """Runtime choices with non-null dependencies; generation may need more storage."""

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
    singles = {
        "bitdeque": "index_base",
        "alight": "expression_syntax",
        "packlang": "literal_policy",
    }
    if language_id in singles:
        keys = [singles[language_id]]
    elif language_id in _VALIDATORS:
        keys = list(inspect.signature(_VALIDATORS[language_id]).parameters)
    else:
        return {}
    choices: dict[str, tuple[int | str, ...]] = {
        "index_base": INDEX_BASES,
        "pick_base": INDEX_BASES,
        "expression_syntax": EXPRESSION_SYNTAXES,
        "literal_policy": LITERAL_POLICIES,
        "unset_variables": UNSET_POLICIES,
        "unknown_commands": UNKNOWN_POLICIES,
        "boundary": TAPE_BOUNDARIES,
        "eof": EOF_POLICIES,
        "scheduling": SCHEDULINGS,
        "deque_cursor": DEQUE_CURSORS,
        "undefined_targets": UNDEFINED_TARGETS,
        "integer_conversion": INTEGER_CONVERSIONS,
        "input_framing": INPUT_FRAMINGS,
    }
    if language_id == "slow_acv_mammalian":
        choices.update(cell_modulus=MODULI, io_modulus=MODULI)
    machine = interpreter_module(name)._Machine  # noqa: SLF001 - interpreter adapter
    parameters = inspect.signature(machine).parameters
    result: dict[str, DialectOption] = {}
    for key in keys:
        dependencies: dict[str, tuple[str, ...]] = {}
        if key == "boundary":
            dependencies["wrap"] = ("tape_size",)
            if language_id == "line":
                dependencies["clamp"] = ("tape_size",)
        result[key] = {
            "default": cast("int | str | None", parameters[key].default),
            "choices": choices.get(key),
            "minimum": None if key in choices else 2 if key == "cell_modulus" else 1,
            "nullable": key not in choices,
            "requires": dependencies,
        }
    return result
