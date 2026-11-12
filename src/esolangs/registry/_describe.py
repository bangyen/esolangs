"""Registry facts as data: :func:`describe`, :func:`_spec`, :func:`list_languages`."""

import json
import pathlib
import re
from typing import cast, get_args

from esolangs.exceptions import ProgramError
from esolangs.registry import (
    Language,
    example_stems,
    wiki_url,
)
from esolangs.registry._catalog import Catalog
from esolangs.registry._contracts import (
    GeneratorShape,
    ProofStatus,
    StateModel,
    WidthEffect,
)
from esolangs.registry._info import LanguageInfo as _LanguageInfo
from esolangs.runtime._execution import interpreter_module
from esolangs.runtime._json import unique_object
from esolangs.settings import dialect_choices
from esolangs.vm import machine_traits

#: Generated from the language-owned proof ledger by ``just docs``.
_SCALING: dict[str, str] = json.loads(
    pathlib.Path(__file__).with_name("scaling.json").read_text(encoding="utf-8"),
    object_pairs_hook=unique_object,
)

#: The committed examples, inside the package so the wheel ships them.
_LANGUAGES_DIR = pathlib.Path(__file__).resolve().parents[1] / "languages"

# Registry category -> state model name.
_STATE_MODELS: dict[str, StateModel] = {
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

#: The ``state_model`` labels (the language's category) and generator shapes.
STATE_MODELS: tuple[str, ...] = tuple(_STATE_MODELS.values())
SHAPES: tuple[str, ...] = get_args(GeneratorShape.__value__)
#: The ``width_effect`` labels.
WIDTH_EFFECTS: tuple[str, ...] = get_args(WidthEffect.__value__)
#: A Sphinx role; ``~`` keeps only the last dotted component.
_ROLE = re.compile(r":(?:class|func|meth|mod|attr|exc|data|obj):`(~?)([^`]+)`")


def describe(language: str, *, catalog: "Catalog | None" = None) -> _LanguageInfo:
    """Return a structured description of ``language``.

    Returns:
        A :class:`~esolangs.registry._info.LanguageInfo` dict with these keys:

        - Identity: ``name``, ``id``, ``source_kind``, ``state_model`` (the
          registry's category), ``wiki_url``, ``spec`` (the interpreter
          docstring), ``dialect_settings`` (runtime defaults and choices).
        - Generation: ``boolean_generator``; ``generator_max_inputs``, an
          explicit arity cap (None: none declared, or no generator);
          ``generator_restrictions``, further table-dependent budgets (None:
          none); ``generator_shape``, the construction growth class ``"tree"``,
          ``"reducing"`` or ``"lookup"`` (None without a generator);
          ``parameterized``, a template filled by :func:`instantiate`
          (``reads_input`` false).
        - Proof: ``generator_scaling`` is the ledger statement;
          ``proof_status`` is its category (None without a recorded proof).
          Linear refers to size and generation time, not totality.
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
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    lang = catalog.languages[name]
    stem = example_stems(catalog=catalog).get(lang.id, lang.id)
    # Package-relative: repository-relative paths broke after a ``chdir`` and
    # when installed; absolute ones froze the install location into output.
    examples = sorted(
        f"languages/{lang.id}/{p.name}"
        for p in (_LANGUAGES_DIR / lang.id).glob(f"{stem}{lang.source_suffix}")
    )
    traits = machine_traits(name, catalog=catalog)
    parameterized = lang.parameterized
    contract = lang.contract
    width_effect = _width_effect(lang)
    packaged = get_catalog().languages.get(name)
    scaling = _SCALING.get(lang.id) if lang == packaged else None
    backend = lang.backend
    generates = backend is not None
    reads_input = generates and not parameterized
    return {
        "name": name,
        "dialect_settings": dialect_choices(name, catalog=catalog),
        "spec": _spec(name, catalog=catalog),
        "id": lang.id,
        "source_kind": lang.runtime.source_kind.value,
        "state_model": _STATE_MODELS[lang.runtime.category],
        "generator_shape": backend.shape.value if backend is not None else None,
        "boolean_generator": generates,
        "generator_scaling": scaling,
        "proof_status": _proof_status(scaling) if scaling is not None else None,
        "generator_max_inputs": backend.max_inputs if backend is not None else None,
        "generator_restrictions": (backend.restrictions or None)
        if backend is not None
        else None,
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
        "random": lang.runtime.random,
        "examples": examples,
        "wiki_url": wiki_url(name),
    }


def _width_effect(lang: Language) -> WidthEffect:
    """Return ``"layout"`` (a shape built to fit), ``"wrap"`` or ``"none"``."""
    backend = lang.backend
    if backend is None:
        return "none"
    if backend.layout_width:
        return "layout"
    return "wrap" if backend.wrap is not None else "none"


def _spec(language: str, *, catalog: "Catalog | None" = None) -> str:
    """Return the interpreter's own description of ``language``.

    The module docstring: the command table and where this implementation
    differs from the wiki -- the documentation for *writing* a program.
    Sphinx roles print as literals.  Raises under ``-OO``, which strips
    docstrings.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    interpreter = interpreter_module(name, catalog=catalog)
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


def list_languages(*, catalog: "Catalog | None" = None) -> list[str]:
    """Return the supported language names, sorted."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return sorted(catalog.languages)


def _proof_status(scaling: str) -> ProofStatus:
    """Return the ledger category without its argument."""
    return cast(
        ProofStatus,
        scaling.partition(":")[0].replace(", ", "-").replace(" ", "-"),
    )
