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
    n=10 random 1847: 13,340 chars, shared through n=11. Nonconstants
    use 15,127 at n=12 and 13, 21,641 at n=14, 52,480 at n=15,
    and 59,049 from n=16. Constants use 88/86 chars for zero/one.

Raises:
    GeneratorCapError: past seventeen inputs, or seventeen in neither family.

Decisions:
    Constants read every input before building and printing ASCII 48/49.
"""

from __future__ import annotations

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.malbolge.descriptor import check_arity, input_cap_error
from esolangs.runtime._program import Program

from .constant import _constant_program
from .digits import _DIGITS_N, _digits_program, _seventeen_program
from .symmetric import _symmetric_program


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    Seventeen inputs only when the table ignores an input or is
    constant on Hamming-weight classes; else ``n`` <= 16.
    """
    n = _validate_truth_table(truth_table)
    check_arity(n)
    if (constant := constant_output(truth_table)) is not None:
        return _constant_program(n, int(constant))
    if n > _DIGITS_N:
        if program := _seventeen_program(truth_table) or _symmetric_program(
            truth_table
        ):
            return program
        raise input_cap_error(n)
    return _digits_program(truth_table, n)


def malbolge_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return malbolge(request.table)
