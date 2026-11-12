"""Public catalog result schema without runtime or compiler imports."""

from typing import TypedDict

from esolangs.registry._contracts import (
    AnswerMode,
    GeneratorShape,
    InputShape,
    SourceForm,
    StateModel,
    WidthEffect,
)
from esolangs.settings import DialectOption


class LanguageInfo(TypedDict):
    """What :func:`describe` returns, as a type a caller can annotate with.

    ``dict[str, object]`` cost a cast per field (five ``mypy --strict`` errors
    in an ordinary consumer).  ``total=True``: every key is always present, and
    a scalar field that does not apply is None, never ``""`` -- so a caller
    tests ``is None`` and iterates the registry without branching.
    """

    name: str
    spec: str
    id: str
    source_kind: SourceForm
    state_model: StateModel
    generator_shape: GeneratorShape | None
    generator_max_inputs: int | None
    generator_restrictions: str | None
    generator_scaling: str | None
    boolean_generator: bool
    parameterized: bool
    reads_input: bool
    width_effect: WidthEffect
    input_encoding: tuple[str, str] | None
    input_shape: InputShape | None
    answer_mode: AnswerMode
    answer_pattern: str | None
    answer_encoding: tuple[str, str]
    answer_convention: str | None
    self_halts: bool
    dumps_on_the_post_halt_step: bool
    steppable_to_answer: bool
    eof_is_a_value: bool
    random: bool
    examples: list[str]
    wiki_url: str
    dialect_settings: dict[str, DialectOption]
