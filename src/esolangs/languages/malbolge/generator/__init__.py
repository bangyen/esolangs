"""Malbolge Boolean program generator: one source cell per row pair.

``malbolge(truth_table)`` reads one ``0``/``1`` line per input.  The first
``n - 1`` inputs are folded positionally into a readout word, three bits per
two-trit digit (:mod:`esolangs.languages.malbolge.generator.digits`), so
every row pair owns a distinct table cell; that cell holds a source
character naming the answer as a function of the last input, which the
answer stub reads.  The whole fixed-size source is the program: constants,
labels and stubs are all source characters, so there is no initializer.
Fewer than sixteen inputs hold the unused reads at ``'0'``, so every
arity's cells are a subset of sixteen's and one placement serves all.
Seventeen inputs are built only when the table ignores one: the sixteen
build over the projection, kept aligned by one discarded read.

Size:
    Constant: the fixed 59049-cell memory at every arity; n=10 random 1847:
    59,049 chars, n=16 and: 59,049 chars.

Raises:
    GeneratorCapError: past seventeen inputs, or seventeen using every input.

Decisions:
    Folding or sharing stubs cannot shrink the fixed store.
"""

from __future__ import annotations

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.malbolge.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.runtime.source_hints import with_hint

from .digits import _DIGITS_N, _digits_program, _seventeen_program

MAX_INPUTS = _DIGITS_N


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    Seventeen inputs only when the table ignores an input; else ``n`` <= 16.
    """
    n = _validate_truth_table(truth_table)
    if n > _DIGITS_N:
        if n == _DIGITS_N + 1 and (program := _seventeen_program(truth_table)):
            return program
        detail = (
            "seventeen is built only for a table that ignores an input, and "
            "this one uses all seventeen; every row pair owns a cell, and "
            "seventeen inputs would need 65,536 of the store's 59,049"
            if n == _DIGITS_N + 1
            else "every row pair owns a cell, and seventeen inputs would need "
            "65,536 of the store's 59,049"
        )
        raise with_hint(
            GeneratorCapError(
                f"Malbolge builds at most {_DIGITS_N} inputs, got {n}: {detail}"
            ),
            (
                "use fewer inputs or check another generator's "
                "limits; width cannot enlarge Malbolge's store"
            ),
        )
    return _digits_program(truth_table, n)


LANGUAGE = Language(
    "Malbolge",
    "malbolge",
    category="program_based",
    # Every source loads into the fixed store, so every program -- this
    # generator's or any other -- is bounded by a constant.
    size_bound=lambda _n: 59_049,
    generator_max_inputs=MAX_INPUTS + 1,
    generator_restrictions="seventeen inputs only for a table that ignores an input",
    boolean=malbolge,
    # Not a tree: straight-line code into the fixed store.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
    # Loader whitespace is discarded before assigning memory addresses.
    wrap=wrap_chars,
    eof="an exhausted read is the value 59048, not an error",
    proof_execution=(execution, True, (2, 3, 6)),
    proof_workspace=(workspace, False, (2, 3)),
)
