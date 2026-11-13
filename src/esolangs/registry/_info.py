"""Public catalog result schema without runtime or compiler imports."""

from dataclasses import dataclass

from esolangs.registry._contracts import (
    AnswerMode,
    GeneratorShape,
    InputShape,
    SourceForm,
    StateModel,
    WidthEffect,
)
from esolangs.settings import DialectOption


@dataclass(frozen=True, slots=True)
class LanguageInfo:
    """What :func:`describe` returns.

    Every field is always set, and a scalar that does not apply is None, never
    ``""`` -- so a caller tests ``is None`` and iterates the registry without
    branching.  ``dataclasses.asdict`` gives the JSON the CLI prints.
    """

    name: str
    dialect_settings: dict[str, DialectOption]
    spec: str
    id: str
    source_kind: SourceForm
    state_model: StateModel
    generator_shape: GeneratorShape | None
    boolean_generator: bool
    generator_scaling: str | None
    generator_max_inputs: int | None
    generator_restrictions: str | None
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
    examples: tuple[str, ...]
    wiki_url: str
