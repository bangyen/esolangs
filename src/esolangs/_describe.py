"""Registry facts as data: :func:`describe`, :func:`_spec`, :func:`list_languages`."""

import pathlib
from typing import TypedDict

from esolangs._execution import interpreter_module
from esolangs.exceptions import ProgramError
from esolangs.registry import (
    LANGUAGES,
    Language,
    example_stems,
    parameterized_ids,
    resolve,
    wiki_url,
)
from esolangs.registry._contracts import AnswerMode, InputShape, WidthEffect
from esolangs.settings import DialectOption, dialect_choices
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.vm import machine_traits

#: The committed examples, inside the package so the wheel ships them.
_EXAMPLES = pathlib.Path(__file__).resolve().parent / "examples"

# Interpreter module family -> state model name.
_STATE_MODELS = {
    "register_based": "register",
    "tape_based": "tape",
    "stack_based": "stack",
    "grid_based": "grid",
    "queue_based": "queue",
    "other": "other",
}


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
    generator_max_inputs: int | None
    generator_restrictions: str | None
    boolean_generator: bool
    parameterized: bool
    reads_input: bool
    width_aware: bool
    width_effect: WidthEffect
    input_encoding: tuple[str, str]
    input_shape: InputShape
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

    ``spec`` contains the interpreter docstring; missing docstrings raise.
    ``dialect_settings`` gives runtime defaults, choices, bounds and dependencies.
    Identity: ``name``, ``id``, ``source_kind``, ``state_model``, ``wiki_url``.
    Generation: ``generator_max_inputs`` is an explicit arity cap (None means
    none declared, or no generator); ``generator_restrictions`` names additional
    table-dependent budgets, None when there are none.  ``boolean_generator``;
    ``parameterized`` (a template, filled by :func:`instantiate`,
    ``reads_input`` false).  Width: ``width_effect`` is
    ``"layout"`` (a shape built to fit; a hint), ``"wrap"`` (reflowed between
    tokens) or ``"none"`` (newlines are semantic); ``width_aware`` is the
    narrower ``== "layout"``.  Input: ``input_shape`` and ``input_encoding``,
    the ``(zero, one)`` pair -- the wrong
    alphabet is a wrong answer.  Answer: ``answer_mode`` is ``"output"``
    (last non-whitespace character), ``"dump"`` (a fixed place in the final
    state) or ``"termination"`` (a proven halt or divergence);
    ``answer_pattern`` is the regex whose first group holds it (None: no regex);
    ``answer_encoding`` the ``(zero, one)`` or ``("halts", "diverges")``;
    ``answer_convention`` prose or None.  These describe raw output (a mark's
    ``("o", "@")`` is a grid mark); :func:`read_answer` returns ``"0"``/``"1"``.
    Machine traits (``self_halts``, ``dumps_on_the_post_halt_step``,
    ``steppable_to_answer``, ``eof_is_a_value``) are documented on
    :func:`~esolangs.vm.machine_traits`.  ``random``: the interpreter has
    instructions that draw at random (``run(seed=...)`` fixes them).
    ``examples`` lists the committed programs as POSIX paths relative to
    the package
    (``importlib.resources.files("esolangs") / path``);
    ``examples/MANIFEST.md`` says what each computes.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    family = lang.interpreter.split(".")[0] if lang.interpreter else None
    stem = example_stems().get(lang.id, lang.id)
    # Package-relative: repository-relative paths broke a ``chdir`` away and
    # under any install, and absolute ones froze the install location into
    # the public output.  ``importlib.resources.files("esolangs")`` resolves.
    suffix = ".png" if lang.source_kind.value == "raster" else ".txt"
    examples = sorted(f"examples/{p.name}" for p in _EXAMPLES.glob(f"{stem}{suffix}"))
    traits = machine_traits(name)
    parameterized = lang.id in parameterized_ids()
    contract = lang.contract
    return {
        "name": name,
        "dialect_settings": dialect_choices(name),
        "spec": _spec(name),
        "id": lang.id,
        "source_kind": lang.source_kind.value,
        "state_model": _STATE_MODELS.get(family) if family else None,
        "boolean_generator": lang.boolean is not None,
        "generator_max_inputs": lang.generator_max_inputs,
        "generator_restrictions": lang.generator_restrictions or None,
        "parameterized": parameterized,
        "reads_input": (lang.boolean is not None) and not parameterized,
        # Derived, not recomputed: this was a second copy of the very
        # expression _width_effect() evaluates, so the two could drift into
        # disagreeing about the same language.
        "width_aware": _width_effect(lang) == "layout",
        "width_effect": _width_effect(lang),
        "input_encoding": contract.alphabet,
        "input_shape": contract.input_shape,
        "answer_mode": contract.answer_mode,
        "answer_pattern": contract.answer_pattern or None,
        "answer_encoding": contract.answer_values,
        "answer_convention": contract.note or None,
        # Spelled out rather than ``**machine_traits(name)``: that returns
        # a ``dict[str, bool]``, which a TypedDict cannot verify a
        # ``**``-expansion of, so the merge would have silently accepted a
        # renamed or dropped trait.  ``test_describe_agrees_with_the_machine``
        # keeps the four in step with what the VM reports.
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
    Raises under ``-OO``, which strips docstrings.
    """
    name = resolve(language)
    interpreter = interpreter_module(name)
    text = (interpreter.__doc__ or "").strip()
    if not text:
        # ``-OO`` strips docstrings, so this returned ``""`` for every one --
        # a silent wrong answer from the function whose whole promise is
        # "read rather than stored, so it cannot drift".  Nothing to say is
        # worth an abort, not an empty string that looks like an answer.
        raise ProgramError(
            f"{name}'s spec is its interpreter's docstring, and this "
            f"interpreter has none -- Python was started with -OO (or "
            f"PYTHONOPTIMIZE=2), which strips them"
        )
    return text


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
