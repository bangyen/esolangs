r"""Build parameterized Boolean programs for %^2^-1.

Programs that read their own inputs cannot compute a two-input function, so
this module embeds each input once.  Every input is spelled by the one pair
``s``/``i`` -- a run leaves ``-(2 + bit)`` behind -- and the template around
the runs carries everything else: the weight, as doublings between runs; a
complement, as a ``p`` pair around one; and the table itself, as the fold's
sequence of relocations, replayed on every row before it is emitted.
"""

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)
from esolangs.tools.pct_codes import (
    _DECL_RE,
    _HEADER_END,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.pct_codes import (
    _LIMIT as _LIMIT,
)
from esolangs.tools.pct_codes import (
    _apply as _apply,
)
from esolangs.tools.pct_codes import (
    _sub_code as _sub_code,
)
from esolangs.tools.pct_fold import (
    _DEEP_DOUBLINGS as _DEEP_DOUBLINGS,
)
from esolangs.tools.pct_fold import (
    _ENDGAME as _ENDGAME,
)
from esolangs.tools.pct_fold import (
    _LAY as _LAY,
)
from esolangs.tools.pct_fold import (
    _LAY_COMPLEMENT as _LAY_COMPLEMENT,
)
from esolangs.tools.pct_fold import (
    _MASK_SWEEP as _MASK_SWEEP,
)
from esolangs.tools.pct_fold import (
    _PAIR,
    _fold,
    _interleaved_fold,
)
from esolangs.tools.pct_fold import (
    _centred_setter as _centred_setter,
)
from esolangs.tools.pct_fold import (
    _fold_at as _fold_at,
)
from esolangs.tools.pct_fold import (
    _fold_ladders as _fold_ladders,
)
from esolangs.tools.pct_fold import (
    _fold_positions as _fold_positions,
)
from esolangs.tools.pct_fold import (
    _fold_setters as _fold_setters,
)
from esolangs.tools.pct_fold import (
    _fold_subset_weights as _fold_subset_weights,
)
from esolangs.tools.pct_fold import (
    _fold_to_cofactors as _fold_to_cofactors,
)
from esolangs.tools.pct_fold import (
    _fold_uniform as _fold_uniform,
)
from esolangs.tools.pct_fold import (
    _FoldEmitter as _FoldEmitter,
)
from esolangs.tools.pct_fold import (
    _interleaved_final_pair as _interleaved_final_pair,
)
from esolangs.tools.pct_fold import (
    _ladder_legal as _ladder_legal,
)
from esolangs.tools.pct_fold import (
    _ladder_prefix as _ladder_prefix,
)
from esolangs.tools.pct_fold import (
    _ladder_values as _ladder_values,
)
from esolangs.tools.pct_fold import (
    _split_setter as _split_setter,
)
from esolangs.tools.pct_fold_plan import (
    _COFACTOR_BRIDGE_POINTS as _COFACTOR_BRIDGE_POINTS,
)
from esolangs.tools.pct_fold_plan import (
    _FOLD_NARROW_STEP as _FOLD_NARROW_STEP,
)
from esolangs.tools.pct_fold_plan import (
    _FOLD_STEP as _FOLD_STEP,
)
from esolangs.tools.pct_fold_plan import (
    _cofactor_done as _cofactor_done,
)
from esolangs.tools.pct_fold_plan import (
    _fold_construct as _fold_construct,
)
from esolangs.tools.pct_fold_plan import (
    _fold_done as _fold_done,
)
from esolangs.tools.pct_fold_plan import (
    _fold_geometry as _fold_geometry,
)
from esolangs.tools.pct_fold_plan import (
    _fold_merge as _fold_merge,
)
from esolangs.tools.pct_fold_plan import (
    _fold_moves as _fold_moves,
)
from esolangs.tools.pct_fold_plan import (
    _fold_norm as _fold_norm,
)
from esolangs.tools.pct_fold_plan import (
    _fold_plan as _fold_plan,
)
from esolangs.tools.pct_fold_plan import (
    _fold_reduce as _fold_reduce,
)
from esolangs.tools.pct_fold_plan import (
    _fold_resolve as _fold_resolve,
)
from esolangs.tools.pct_fold_plan import (
    _fold_served as _fold_served,
)
from esolangs.tools.pct_fold_plan import (
    _fold_skeleton as _fold_skeleton,
)
from esolangs.tools.pct_ladder import (
    _header,
    _runs,
)

__all__ = ["pct_squared_minus_one"]


#: Tails for a table that is one input or its complement.  After the run and
#: its ``psp`` the accumulator is ``-bit``; ``ps`` alone (the run's own
#: ``p``, then the drop) leaves ``bit``, and ``pip`` leaves ``1 - bit``:
#: ``p`` to ``2 + bit``, ``i`` to ``bit - 1``, ``p`` to ``1 - bit``.  ``l``
#: prints the accumulator in decimal, so those are the digits.
_ONE_INPUT_TAILS = {False: "ps", True: "pip"}

#: A constant table prints from a zero accumulator: ``l`` prints ``0`` as it
#: stands, and ``ips`` first lifts it to 1 (``i`` to -3, ``p`` to 3, ``s``).
_CONSTANT_TAILS = {"0": "l", "1": "ipsl"}


def _one_input(truth_table: str, n: int) -> str | None:
    """Build a table affine in its inputs, or ``None`` if it is not one.

    Every run is a translation, so a template with no reset is affine in
    the bits, and an affine function into ``{0, 1}`` depends on at most one
    input.  Those tables need no fold: the answer is printed with ``l`` as
    soon as it is in the accumulator, and the runs after the print are
    executed but print nothing.  The runs before the deciding input are
    erased by one ``'``.

    Every table that is not one of these needs the reset and goes to the
    fold; the check here is a read of the table, not a search.
    """
    if len(set(truth_table)) == 1:
        return (
            _header([_PAIR] * n) + _CONSTANT_TAILS[truth_table[0]] + _runs([_PAIR] * n)
        )
    size = 2**n
    for k in range(n):
        bit = 1 << (n - 1 - k)
        for negate in (False, True):
            if all(
                (truth_table[r] == "1") == (bool(r & bit) != negate)
                for r in range(size)
            ):
                before = TEMPLATE_CHAR * k + ("'" if k else "")
                after = TEMPLATE_CHAR * (n - 1 - k)
                tail = _ONE_INPUT_TAILS[negate]
                return (
                    _header([_PAIR] * n) + before + TEMPLATE_CHAR + tail + "l" + after
                )
    return None


def pct_squared_minus_one(truth_table: str) -> str:
    """Build a %^2^-1 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, indexed by the
    inputs (most significant first); the table length implies ``n``.

    %^2^-1 has no usable branch -- ``t`` only ever jumps to position 0 -- so
    this generator computes the answer arithmetically instead of routing a
    decision tree.  Every input is the one pair ``s``/``i``; the template
    weights the runs by doubling between them and lays every row on a
    ladder below zero, and the fold then plans a sequence of relocations
    through the over-3003 reset that lands each class on its digit.

    A table that depends on at most one input is printed straight off its
    run (:func:`_one_input`).  Everything else goes to :func:`_fold`, which
    tries the popcount ladder under every complementation that keeps its
    collisions inside a class -- the symmetric tables open there as a
    handful of points -- and then the distinct ladders, which close every
    table through eleven inputs.  Past that the staged
    :func:`_interleaved_fold` lays two inputs after a compaction, with its
    own pairs; a table none of them covers raises
    :class:`~esolangs.exceptions.GeneratorCapError`, because emitting
    nothing is better than emitting a program that computes the wrong
    function.
    """
    n = _validate_truth_table(truth_table)
    built = _one_input(truth_table, n)
    if built is not None:
        return built
    built = _fold(truth_table, n)
    if built is None:
        # The staged route is after the ladders: at the arities they serve
        # it is a much longer program, while beyond them it is the only
        # construction that can release equal suffix cofactors before every
        # row has been laid.
        built = _interleaved_fold(truth_table, n)
    if built is None:
        raise GeneratorCapError(
            f"%^2^-1 builds every table at one through four inputs, every "
            f"table tried from five through thirteen, and any table "
            f"symmetric under a complementation of its inputs; beyond those "
            f"the tables the all-row fold can plan and the compactable "
            f"suffix-cofactor stages the interleaved fold can plan; "
            f"got {n} inputs ({truth_table!r})"
        )
    return built


def fill(template: str, bits: list[int]) -> str:
    """Instantiate ``template`` for ``bits``, returning a runnable program.

    The header names each setter's two branches; this strips it and replaces
    each input's run with the branch its bit selects.  The branches are
    equal width, so every instantiation has the same length whatever the
    inputs.

    The header's own newlines are discarded before it is read, which is what
    lets the wrapper fold a header at all -- and lets it fold *inside* a
    declaration rather than only between two.  Stripping here rather than
    substituting the rows as they come keeps the filled program
    byte-identical however the header was folded, so the two branches stay
    equal width in text as well as in commands.
    """
    return fill_runs(body(template), TEMPLATE_CHAR, setters(template), bits)


def body(template: str) -> str:
    """Return the template past its header: the text the runs are filled in."""
    return template.partition(_HEADER_END)[2]


def setters(template: str, _n: int = 0) -> Setters:
    """Return the ``(zero, one)`` branch per input, read off the header."""
    header = template.partition(_HEADER_END)[0].replace("\n", "")
    branches = {
        int(m.group(1)): (m.group(2), m.group(3)) for m in _DECL_RE.finditer(header)
    }
    return tuple(branches[i] for i in range(len(branches)))
