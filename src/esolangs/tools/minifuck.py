"""Build Minifuck Boolean templates by input substitution.

Each input is embedded once at equal width; every row is verified with
the joint simulator and an unverified program raises.  The simulator laws
are pinned differentially against the interpreter.
"""

from functools import cache
from inspect import signature

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    mark_runs,
    read_at,
    unmark,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.minifuck_mux import (
    _MUX_BASE as _MUX_BASE,
)
from esolangs.tools.minifuck_mux import (
    _MUX_MIN_ARITY,
    _canonical_endgame,
    _mux,
    _mux_lookup,
)
from esolangs.tools.minifuck_mux import (
    _MUX_PRESERVE_RIGHT as _MUX_PRESERVE_RIGHT,
)
from esolangs.tools.minifuck_mux import (
    _SCULPT_POOL_CODE as _SCULPT_POOL_CODE,
)
from esolangs.tools.minifuck_mux import (
    _mux_start as _mux_start,
)
from esolangs.tools.minifuck_mux import (
    _mux_weight as _mux_weight,
)
from esolangs.tools.minifuck_mux import (
    _probe_frame as _probe_frame,
)
from esolangs.tools.minifuck_pool import (
    _BASE,
    _SEP,
    _embed,
)
from esolangs.tools.minifuck_pool import (
    _FLIP as _FLIP,
)
from esolangs.tools.minifuck_pool import (
    _PLANS as _PLANS,
)
from esolangs.tools.minifuck_pool import (
    _POOL_CODES as _POOL_CODES,
)
from esolangs.tools.minifuck_pool import (
    _POOL_MASK as _POOL_MASK,
)
from esolangs.tools.minifuck_pool import (
    _POOL_PTR_MAX as _POOL_PTR_MAX,
)
from esolangs.tools.minifuck_pool import (
    _POOL_WIDTH as _POOL_WIDTH,
)
from esolangs.tools.minifuck_pool import (
    _PROBE_WALK_OUT as _PROBE_WALK_OUT,
)
from esolangs.tools.minifuck_pool import (
    _READS as _READS,
)
from esolangs.tools.minifuck_pool import (
    _endgame as _endgame,
)
from esolangs.tools.minifuck_pool import (
    _find_pool as _find_pool,
)
from esolangs.tools.minifuck_pool import (
    _pool_code_for_row as _pool_code_for_row,
)
from esolangs.tools.minifuck_pool import (
    _pool_slice as _pool_slice,
)
from esolangs.tools.minifuck_pool import (
    _step as _step,
)

# The machine the construction below emits against.  ``_Sim`` and ``_Joint``
# are re-exported rather than referenced through the module because the test
# suite imports them from here by name, and because every use in this file
# reads as part of the construction rather than as a call into a simulator.
from esolangs.tools.minifuck_sim import (
    _MINIFUCK_INPUT,
    PAIR,
)
from esolangs.tools.minifuck_sim import (
    _clamp as _clamp,
)
from esolangs.tools.minifuck_sim import (
    _Joint as _Joint,
)
from esolangs.tools.minifuck_sim import (
    _runs as _runs,
)
from esolangs.tools.minifuck_sim import (
    _Sim as _Sim,
)
from esolangs.tools.minifuck_sim import (
    _walk_to as _walk_to,
)

__all__ = ["minifuck"]


def _degenerate(truth_table: str, n: int) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    A constant, projection or negated projection already stands as a
    column: cell 16 prints ``b0``, cell 19 ``~b1``, a constant at 16
    (nullary) or 17.  A table with ``k`` essential inputs is a ``k``-input
    problem, so four of the fourteen three-input orbits land here.  Later
    projections decline to :func:`_mux`.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) > 1:
        return None
    if not essential:
        acc = _BASE if n == 0 else _BASE + 1
        direct = truth_table[0] == ("1" if n == 0 else "0")
    elif essential[0] == 0:
        acc = _BASE
        direct = truth_table[0] == "0"
    elif essential[0] == 1:
        acc = _BASE + 3
        direct = truth_table[0] == "1"
    else:
        return None

    base = _embed(n, sep=_SEP)
    _clamp(base)
    _canonical_endgame(base, acc, direct=direct)
    if base.printed() != list(truth_table):  # pragma: no cover - the law is exact
        raise AssertionError("the degenerate rule printed the wrong column")
    return base.template()


def _project(truth_table: str, essential: list[int], n: int) -> str:
    """Rewrite the table over its essential inputs only.

    :func:`read_at`, shared with :func:`permute_truth_table`.
    """
    return read_at(truth_table, essential, n)


def _lift_leaves_name_order(essential: list[int], n: int) -> bool:
    """Whether lifting would put the ignored inputs' runs out of name order.

    Correct only when every ignored index is above every essential one.
    """
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    """Widen a smaller table's template back onto the wider arity.

    Ignored inputs' runs go on the end: two characters either bit, after
    the ``.`` has printed.  An order the append would misname is refused.
    """
    if _lift_leaves_name_order(essential, n):
        raise ValueError(f"lifting {essential} onto {n} inputs misnames a run")
    return template + _MINIFUCK_INPUT * (n - len(essential))


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Runs become ``[<`` for a one and
    ``xx`` for a zero.  The program embeds each input once, computes past
    the pool, relays the answer into the *pointer*, and prints one digit;
    every emission is tracked against all rows by
    :mod:`esolangs.tools.minifuck_sim` and :class:`ValueError` is raised
    otherwise.  Cached; no route enumerates candidates.
    """
    n = _validate_shape(truth_table)

    # Dependency discovery compares every row at every input and is
    # O(T log T).  Keep the compact legacy routes only below the strip's
    # crossover; the direct lookup is O(T) for every wider table, folded or
    # not, so no preliminary analysis may dominate it.
    if n >= 5:
        return _mux_lookup(truth_table, n)

    # Below the strip crossover, a table that ignores inputs is a smaller
    # table wearing extra ones; solve it there and append the ignored runs.
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projection is cheaper, but appending ignored inputs after the print
        # disorders their names when one lies below an essential input.  The
        # full-arity mux embeds every slot in order, so that case uses it.
        if _lift_leaves_name_order(essential, n):
            return _mux(truth_table, n)
        inner = _solve(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # Nullary and unary inner solves use the embed's named standing column.
    if n < _MUX_MIN_ARITY:
        degenerate = _degenerate(truth_table, n)
        if degenerate is None:  # pragma: no cover - nullary/unary column rule
            raise ValueError(
                f"the Minifuck boolean generator could not build {truth_table!r}"
            )
        return degenerate

    return _mux(truth_table, n)


def minifuck(truth_table: str, width: int | None = None) -> str:
    """Build a Minifuck template for the given truth table.

    :func:`_solve` plus the arity check: ``_solve`` accepts a nullary table
    while recursing (six such calls building the 276 tables up to three
    inputs), but the API refuses it.  Narrow layouts pair fresh walks with
    comments so skip chains no longer bind the padding into one long line.
    """
    n = _validate_truth_table(truth_table)
    natural = _solve(truth_table)
    if width is None or width <= 0:
        return natural
    wrapped = _wrap_template(natural, n, width)
    if max(map(len, wrapped.splitlines())) <= width:
        return wrapped
    if width < 4 and all(
        int(bit) == ((row.bit_count() ^ int(truth_table[0])) & 1)
        for row, bit in enumerate(truth_table)
    ):
        return _parity_columns(n, int(truth_table[0]))
    if n == 1:
        # The lookup requires two inputs: duplicate each leaf and fix its
        # second setter to zero, leaving the first as the sole named input.
        narrow = _mux_lookup("".join(bit * 2 for bit in truth_table), 2, paired=True)
        at = narrow.rindex(_MINIFUCK_INPUT)
        narrow = narrow[:at] + PAIR[0] + narrow[at + len(PAIR[0]) :]
    else:
        narrow = _mux_lookup(truth_table, n, paired=True)
    narrow = _wrap_template(narrow, n, width)
    return (
        narrow
        if max(map(len, narrow.splitlines())) < max(map(len, wrapped.splitlines()))
        else wrapped
    )


def _parity_columns(n: int, complement: int) -> str:
    """Toggle output bit 7 with each input; every skip absorbs only LF."""
    bits = [0] * 10
    pointer = 0
    parts = ["q"]

    def emit(command: str) -> None:
        nonlocal pointer
        parts.append(command)
        if command == "<":
            pointer = max(0, pointer - 1)
        else:
            pointer += 1
            bits[pointer] ^= 1
            if not bits[pointer]:
                bits[pointer + 1] ^= 1

    for _ in range(n):
        for _ in range(6):
            emit("[")
        parts.append(TEMPLATE_CHAR)
        # Either input ends at 6 or 7; clamping seven left steps returns to 0.
        for _ in range(7):
            emit("<")
    for cell in range(1, 7):
        emit("[")
        if bits[cell] != int(cell in (2, 3)):
            emit("<")
            emit("[")
    if bits[7] != (complement ^ 1):
        emit("[")
        emit("<")
    parts.append(".")
    return "\n".join(parts)


def minifuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Recognize the parity layout's inert q prefix; retain legacy two-cell bits."""
    return (("x", "[") if template.startswith("q\n") else PAIR,) * n


def _wrap_template(template: str, n: int, width: int) -> str:
    """Wrap a template with each two-character input run kept atomic."""
    from esolangs.tools.wrap import wrap_program

    marked = mark_runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return unmark(wrap_program(marked, "minifuck", width), TEMPLATE_CHAR, n)


# The construction's cache and its undecorated body live on ``_solve`` now,
# but tests and callers reach for them through the public name: keep
# ``cache_clear``/``cache_info`` and ``__wrapped__`` here so splitting the
# arity check off did not move the surface.
minifuck.cache_clear = _solve.cache_clear  # type: ignore[attr-defined]
minifuck.cache_info = _solve.cache_info  # type: ignore[attr-defined]
# Keep the public width parameter visible despite the legacy raw-solver link.
minifuck.__signature__ = signature(minifuck)  # type: ignore[attr-defined]
minifuck.__wrapped__ = _solve.__wrapped__  # type: ignore[attr-defined]
