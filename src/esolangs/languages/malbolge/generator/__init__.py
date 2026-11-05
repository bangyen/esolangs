"""Malbolge Boolean program generator: one source cell per row pair.

``malbolge(truth_table)`` reads one ``0``/``1`` character per input.  The first
``n - 1`` inputs are folded positionally into a readout word, three bits per
two-trit digit (:mod:`esolangs.languages.malbolge.generator.digits`), so
every row pair owns a distinct table cell; that cell holds a source
character naming the answer as a function of the last input, which the
answer stub reads. For nonconstants the whole source is the program: constants,
labels and stubs are all source characters, so there is no initializer.
Fewer than sixteen inputs hold the unused reads at ``'0'``, so every
arity's cells are a subset of sixteen's and one placement serves all; up to
fifteen the tables sit low enough that the source stops at its highest live
cell.
Seventeen inputs are built only when the table ignores an input or is
constant on Hamming-weight classes: the sixteen build over the
projection, kept aligned by one discarded read, or the popcount build,
whose first group folds four inputs into their weight.

Size:
    Nonconstants end at the highest live cell; n=10 random 1847:
    13,340 chars to n=13, 19,683 at n=14, 52,480 at n=15, and the whole
    59,049-cell memory from n=16. Constants use 618..639 chars over
    n=1..17; n=8 zero/one: 632/625 chars.

Raises:
    GeneratorCapError: past seventeen inputs, or seventeen in neither family.

Decisions:
    Constants read every input before building and printing ASCII 48/49.
"""

from __future__ import annotations

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.malbolge.proof_formulas import execution, workspace
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime.source_hints import with_hint

from .constant import _constant_program
from .digits import _DIGITS_N, _digits_program, _seventeen_program
from .symmetric import _symmetric_program

MAX_INPUTS = _DIGITS_N


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    Seventeen inputs only when the table ignores an input or is
    constant on Hamming-weight classes; else ``n`` <= 16.
    """
    n = _validate_truth_table(truth_table)
    if n <= _DIGITS_N + 1 and truth_table.count(truth_table[0]) == len(truth_table):
        return _constant_program(n, int(truth_table[0]))
    if n > _DIGITS_N:
        if n == _DIGITS_N + 1 and (
            program := _seventeen_program(truth_table)
            or _symmetric_program(truth_table)
        ):
            return program
        detail = (
            "seventeen is built only for a table that ignores an input or "
            "is constant on Hamming-weight classes, and this one does "
            "neither; every row pair owns a cell, and seventeen inputs "
            "would need 65,536 of the store's 59,049"
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
    RuntimeSpec(
        "malbolge",
        category="program_based",
        eof="an exhausted read is the value 59048, not an error",
    ),
    certification=CertificationSpec(
        # Every source loads into the fixed store, so every program -- this
        # generator's or any other -- is bounded by a constant.
        size_bound=lambda _n: 59_049,
    ),
    backend=BooleanBackend(
        max_inputs=MAX_INPUTS + 1,
        restrictions=(
            "seventeen inputs only for a table that ignores an input "
            "or is constant on Hamming-weight classes"
        ),
        generate=malbolge,
        # Not a tree: straight-line code into the fixed store.
        shape=Shape.LOOKUP,
        # Loader whitespace is discarded before assigning memory addresses.
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
)
