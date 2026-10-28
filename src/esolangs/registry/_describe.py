"""Registry facts as data: :func:`describe`, :func:`_spec`, :func:`list_languages`."""

import pathlib
import re
from typing import TypedDict, get_args

from esolangs.exceptions import ProgramError
from esolangs.generation.wrap import takes_width as _takes_width
from esolangs.registry import (
    LANGUAGES,
    Language,
    example_stems,
    resolve,
    wiki_url,
)
from esolangs.registry._contracts import AnswerMode, InputShape, WidthEffect
from esolangs.registry._language import Shape
from esolangs.runtime._execution import interpreter_module
from esolangs.settings import DialectOption, dialect_choices
from esolangs.vm import machine_traits

#: The committed examples, inside the package so the wheel ships them.
_LANGUAGES_DIR = pathlib.Path(__file__).resolve().parents[1] / "languages"

# Registry category -> state model name.
_STATE_MODELS = {
    "register_based": "register",
    "tape_based": "tape",
    "stack_based": "stack",
    "grid_based": "grid",
    "queue_based": "queue",
    # The run's data is the program itself: rewritten text, instructions
    # writing into each other, or code sharing one memory with data.
    "program_based": "program",
    # A store of named variables the program declares.
    "variable_based": "variables",
    "other": "other",
}

#: The ``state_model`` labels (the language's category) and generator shapes;
#: the CLI's ``--state-model`` and ``--shape`` filters accept exactly these.
STATE_MODELS: tuple[str, ...] = tuple(_STATE_MODELS.values())
SHAPES: tuple[str, ...] = tuple(shape.value for shape in Shape)
#: The ``input_shape`` and ``width_effect`` labels, for the CLI's filters.
INPUT_SHAPES: tuple[str, ...] = get_args(InputShape.__value__)
WIDTH_EFFECTS: tuple[str, ...] = get_args(WidthEffect.__value__)
#: A Sphinx role; ``~`` keeps only the last dotted component.
_ROLE = re.compile(r":(?:class|func|meth|mod|attr|exc|data|obj):`(~?)([^`]+)`")


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
    source_kind: str
    state_model: str | None
    shape: str | None
    generator_max_inputs: int | None
    generator_restrictions: str | None
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


def describe(language: str) -> LanguageInfo:
    """Return a structured description of ``language``.

    Returns:
        A :class:`LanguageInfo` dict with these keys:

        - Identity: ``name``, ``id``, ``source_kind``, ``state_model`` (the
          registry's category), ``wiki_url``, ``spec`` (the interpreter
          docstring), ``dialect_settings`` (runtime defaults and choices).
        - Generation: ``boolean_generator``; ``generator_max_inputs``, an
          explicit arity cap (None: none declared, or no generator);
          ``generator_restrictions``, further table-dependent budgets (None:
          none); ``shape``, the construction growth class ``"tree"``,
          ``"reducing"`` or ``"lookup"`` (None without a generator);
          ``parameterized``, a template filled by :func:`instantiate`
          (``reads_input`` false).
        - Width: ``width_effect`` is ``"layout"`` (a shape built to fit; a
          hint), ``"wrap"`` (reflowed between tokens) or ``"none"`` (newlines
          are semantic).
        - Input: ``reads_input``; ``input_shape`` and ``input_encoding``, the
          ``(zero, one)`` pair (the wrong alphabet is a wrong answer), both
          None unless ``reads_input``.
        - Answer: ``answer_mode`` is ``"output"`` (last non-whitespace
          character), ``"dump"`` (a fixed place in the final state) or
          ``"termination"`` (a proven halt or divergence); ``answer_pattern``,
          the regex whose first group holds it (None: no regex);
          ``answer_encoding``, ``(zero, one)`` or ``("halts", "diverges")``;
          ``answer_convention``, prose or None.  These describe raw output (a
          mark's ``("o", "@")`` is a grid mark); :func:`read_answer` returns
          ``"0"``/``"1"``.
        - Machine traits (:func:`~esolangs.vm.machine_traits`): ``self_halts``,
          ``dumps_on_the_post_halt_step``, ``steppable_to_answer``,
          ``eof_is_a_value``; ``random`` (fixed by ``run(seed=...)``).
        - ``examples``: the committed programs as POSIX paths relative to the
          package (``importlib.resources.files("esolangs") / path``);
          ``languages/EXAMPLES.md`` says what each computes.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ProgramError: The interpreter has no docstring for ``spec`` (Python
            run with ``-OO``).
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    family = lang.category if lang.interpreter else None
    stem = example_stems().get(lang.id, lang.id)
    # Package-relative: repository-relative paths broke after a ``chdir`` and
    # when installed; absolute ones froze the install location into output.
    examples = sorted(
        f"languages/{lang.id}/{p.name}"
        for p in (_LANGUAGES_DIR / lang.id).glob(f"{stem}{lang.source_suffix}")
    )
    traits = machine_traits(name)
    parameterized = lang.parameterized
    contract = lang.contract
    width_effect = _width_effect(lang)
    generates = lang.boolean is not None
    reads_input = generates and not parameterized
    return {
        "name": name,
        "dialect_settings": dialect_choices(name),
        "spec": _spec(name),
        "id": lang.id,
        "source_kind": lang.source_kind.value,
        "state_model": _STATE_MODELS.get(family) if family else None,
        "shape": lang.shape.value if generates else None,
        "boolean_generator": generates,
        "generator_max_inputs": lang.generator_max_inputs,
        "generator_restrictions": lang.generator_restrictions or None,
        "parameterized": parameterized,
        "reads_input": reads_input,
        "width_effect": width_effect,
        # Defaults leaked here as facts: Deadfish "read" ``line_per_bit``.
        "input_encoding": contract.alphabet if reads_input else None,
        "input_shape": contract.input_shape if reads_input else None,
        "answer_mode": contract.answer_mode,
        "answer_pattern": contract.answer_pattern or None,
        "answer_encoding": contract.answer_values,
        "answer_convention": contract.note or None,
        # Not ``**machine_traits(name)``: a TypedDict cannot check a
        # ``dict[str, bool]`` expansion, so a renamed trait would pass.
        # ``test_describe_agrees_with_the_machine`` keeps the four in step.
        "self_halts": traits["self_halts"],
        "dumps_on_the_post_halt_step": traits["dumps_on_the_post_halt_step"],
        "steppable_to_answer": traits["steppable_to_answer"],
        "eof_is_a_value": traits["eof_is_a_value"],
        "random": lang.random,
        "examples": examples,
        "wiki_url": wiki_url(name),
    }


def _width_effect(lang: Language) -> WidthEffect:
    """Return ``"layout"`` (a shape built to fit), ``"wrap"`` or ``"none"``."""
    generator = lang.boolean
    if generator is not None and _takes_width(generator):
        return "layout"
    return "wrap" if lang.wrap is not None else "none"


def _spec(language: str) -> str:
    """Return the interpreter's own description of ``language``.

    The module docstring: the command table and where this implementation
    differs from the wiki -- the documentation for *writing* a program.
    Sphinx roles print as literals.  Raises under ``-OO``, which strips
    docstrings.
    """
    name = resolve(language)
    interpreter = interpreter_module(name)
    text = (interpreter.__doc__ or "").strip()
    text = _ROLE.sub(lambda m: f"``{m[2].rsplit('.', 1)[-1] if m[1] else m[2]}``", text)
    if not text:
        # Abort: under ``-OO`` an empty string would look like an answer from
        # a function promising "read rather than stored, so it cannot drift".
        raise ProgramError(
            f"{name}'s spec is its interpreter's docstring, and this "
            f"interpreter has none -- Python was started with -OO (or "
            f"PYTHONOPTIMIZE=2), which strips them"
        )
    return text


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
