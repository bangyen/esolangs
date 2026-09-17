"""Registry facts as data: :func:`describe`, :func:`spec`, :func:`list_languages`.

Nothing here runs a program; the run layer (:mod:`esolangs`) and the answer
layer (:mod:`esolangs._answers`) both read these facts.
"""

import importlib
import pathlib
from typing import Any, TypedDict

from esolangs.exceptions import ProgramError
from esolangs.registry import (
    LANGUAGES,
    RUNNERS,
    example_stems,
    parameterized_ids,
    resolve,
    wiki_url,
)
from esolangs.tools.wrap import WRAPPERS
from esolangs.tools.wrap import takes_width as _takes_width
from esolangs.vm import machine_traits

#: The committed examples, inside the package so the wheel ships them
#: (at the repo root, ``parents[2]`` from an install was above ``site-packages``).
_EXAMPLES = pathlib.Path(__file__).resolve().parent / "examples"

# An unfilled input slot in a parameterized generator's template.  Matched
# only for the languages whose generator emits one: ``{`` is a live command
# in several of the others, so a blanket search would refuse real programs.

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
    in an ordinary consumer).  ``total=True``: a field that does not apply is
    a documented empty value, so a caller iterates the registry without branching.
    """

    name: str
    id: str
    state_model: str | None
    interpreter: str | None
    boolean_generator: bool
    parameterized: bool
    reads_input: bool
    width_aware: bool
    width_effect: str
    input_encoding: tuple[str, str]
    input_shape: str
    answer_mode: str
    answer_pattern: str
    answer_encoding: tuple[str, str]
    answer_convention: str | None
    self_halts: bool
    dumps_on_the_post_halt_step: bool
    steppable_to_answer: bool
    eof_is_a_value: bool
    examples: list[str]
    wiki_url: str


def describe(language: str) -> LanguageInfo:
    """Return a structured description of ``language``.

    Identity: ``name``, ``id``, ``state_model``, ``interpreter``, ``wiki_url``.
    Generation: ``boolean_generator``; ``parameterized`` (a template, filled by
    :func:`instantiate`, ``reads_input`` false).  Width: ``width_effect`` is
    ``"layout"`` (a shape built to fit; a hint), ``"wrap"`` (reflowed between
    tokens) or ``"none"`` (newlines are semantic); ``width_aware`` is the
    narrower ``== "layout"``.  Input: ``input_shape`` and ``input_encoding``,
    the ``(zero, one)`` pair (``("%", "A")`` for Grapheme) -- the wrong
    alphabet is a wrong answer.  Answer: ``answer_mode`` is ``"output"``
    (last non-whitespace character), ``"dump"`` (a fixed place in the final
    state) or ``"termination"`` (a timeout *is* an answer);
    ``answer_pattern`` is the regex whose first group holds it;
    ``answer_encoding`` the ``(zero, one)`` or ``("halts", "diverges")``;
    ``answer_convention`` prose.  These describe raw output (A Painter Ant's
    ``("o", "@")`` is a grid mark); :func:`read_answer` returns ``"0"``/``"1"``.
    Machine traits (``self_halts``, ``dumps_on_the_post_halt_step``,
    ``steppable_to_answer``, ``eof_is_a_value``) are documented on
    :func:`~esolangs.vm.machine_traits`.  ``examples`` lists the committed
    programs; ``examples/MANIFEST.md`` says what each computes.
    """
    name = resolve(language)
    lang = LANGUAGES[name]
    module = RUNNERS.get(name)
    family = module[0].split(".")[0] if module else None
    stem = example_stems().get(lang.id, lang.id)
    # Absolute.  These were relative to the repository root, which made the
    # recipe this package advertises -- ``run(lang, Path(describe(lang)
    # ["examples"][0]))`` -- work from one directory and nowhere else: a
    # ``chdir`` away it is ``cannot read examples/brainfuck.txt``,
    # and for anyone who pip-installed there is no such directory at all.
    examples = sorted(str(p) for p in _EXAMPLES.glob(f"{stem}.txt"))
    traits = machine_traits(name)
    parameterized = lang.id in parameterized_ids()
    example = _example_for(lang.id)
    return {
        "name": name,
        "id": lang.id,
        "state_model": _STATE_MODELS.get(family) if family else None,
        "interpreter": lang.interpreter,
        "boolean_generator": lang.boolean is not None,
        "parameterized": parameterized,
        "reads_input": lang.boolean is not None and not parameterized,
        # Derived, not recomputed: this was a second copy of the very
        # expression _width_effect() evaluates, so the two could drift into
        # disagreeing about the same language.
        "width_aware": _width_effect(lang) == "layout",
        "width_effect": _width_effect(lang),
        "input_encoding": example.alphabet if example else ("0", "1"),
        "input_shape": example.input_shape if example else "line_per_bit",
        "answer_mode": example.answer_mode if example else "output",
        "answer_pattern": example.answer_pattern if example else "",
        "answer_encoding": example.answer_values if example else ("0", "1"),
        "answer_convention": (example.note or None) if example else None,
        # Spelled out rather than ``**machine_traits(name)``: that returns
        # a ``dict[str, bool]``, which a TypedDict cannot verify a
        # ``**``-expansion of, so the merge would have silently accepted a
        # renamed or dropped trait.  ``test_describe_agrees_with_the_machine``
        # keeps the four in step with what the VM reports.
        "self_halts": traits["self_halts"],
        "dumps_on_the_post_halt_step": traits["dumps_on_the_post_halt_step"],
        "steppable_to_answer": traits["steppable_to_answer"],
        "eof_is_a_value": traits["eof_is_a_value"],
        "examples": examples,
        "wiki_url": wiki_url(name),
    }


def _width_effect(lang: Any) -> str:
    """Return what ``width`` actually does to this language's program.

    ``width_aware`` was ``False`` for both Sophie (reflowed afterwards) and
    Clockwise (ignores it).  ``"layout"``: a shape built to fit, a hint
    (LaserFuck asked for 10 gives 18, for 200 gives 56); ``"wrap"``:
    reflowed between tokens; ``"none"``: ignored, newlines semantic.
    """
    # One expression rather than an early return for the generator-less
    # case: every registered language has a generator, so that return was a
    # line no input could reach.
    if lang.boolean is not None and _takes_width(lang.boolean):
        return "layout"
    return "wrap" if lang.id in WRAPPERS else "none"


def spec(language: str) -> str:
    """Return the interpreter's own description of ``language``.

    The module docstring: the command table and where this implementation
    differs from the wiki -- the documentation for *writing* a program.
    Raises under ``-OO``, which strips docstrings.
    """
    name = resolve(language)
    module = RUNNERS[name][0]
    interpreter = importlib.import_module("esolangs.interpreters." + module)
    text = (interpreter.__doc__ or "").strip()
    if not text:
        # ``-OO`` strips docstrings, so this returned ``""`` for all 65 --
        # a silent wrong answer from the function whose whole promise is
        # "read rather than stored, so it cannot drift".  Nothing to say is
        # worth an abort, not an empty string that looks like an answer.
        raise ProgramError(
            f"{name}'s spec is its interpreter's docstring, and this "
            f"interpreter has none -- Python was started with -OO (or "
            f"PYTHONOPTIMIZE=2), which strips them"
        )
    return text


def _example_for(language_id: str) -> Any:
    """Return the committed boolean example for ``language_id``, or None.

    Deferred: ``examples`` imports the registry.
    """
    from esolangs.tools.examples import BOOLEAN_EXAMPLES

    stem = example_stems().get(language_id)
    return BOOLEAN_EXAMPLES.get(stem) if stem is not None else None


def list_languages() -> list[str]:
    """Return the supported language names, sorted."""
    return sorted(LANGUAGES)
