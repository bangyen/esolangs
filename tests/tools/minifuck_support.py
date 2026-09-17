"""The Minifuck suites' shared harness: run a program, fill a template."""

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.minifuck_sim import PAIR


def run_count(template: str, n: int) -> int:
    """How many input runs ``template`` carries, expecting ``n``.

    The k-th run *is* input k, so this is what the text can still show
    about the embedding: a run short, a run over, or a fill character in
    the program proper refuses (a ``ValueError`` from :func:`runs`).
    """
    return len(runs(template, TEMPLATE_CHAR, (PAIR,) * n))


class _MinifuckCase:
    """Input-by-substitution boolean generator for Minifuck.

    Minifuck's only read is ``.`` pulling a byte when the eight-cell pool is
    zero, which a boolean program cannot use without destroying the pool it
    is about to print -- so the inputs are embedded instead.  The generator
    simulates every row as it emits and raises rather than returning a
    program it has not seen print the table, so these tests are checking the
    *interpreter* agrees with that simulation.

    Split out of TestParameterizedMinifuck when that class became four, so
    the four do not each carry a copy of the harness.
    """

    def run_minifuck(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import _fill_minifuck

        return _fill_minifuck(tpl, bits)


# --- The separation gadget and the pool oracles.  Nothing shipped builds
# through these: the mux is the preloaded-strip lookup.  They stay as the
# fixtures and the exhaustive checks the pool tests drive.
from esolangs.tools.minifuck_mux import (  # noqa: E402
    _MUX_GUARD,
    _mux_start,
    _mux_weight,
    _mux_weights,
)
from esolangs.tools.minifuck_pool import (  # noqa: E402
    _POOL,
    _POOL_WIDTH,
    _READS,
    _endgame,
    _find_pool,
)
from esolangs.tools.minifuck_sim import _Joint, _walk_to  # noqa: E402

# One separation per arity, forked out.  A dict: the value is a mutable ``_Joint``.
_MUX_SEPARATED: dict[int, _Joint] = {}


def _mux_reference(n: int) -> _Joint:
    """Return a joint walked to the embed's start with nothing embedded yet.

    The tape :func:`_mux_separate` must leave untouched left of :data:`_MUX_GUARD`.
    """
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    """Whether every cell left of the guard survived, on every row."""
    return all(
        m.cells(_MUX_GUARD) == m0.cells(_MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight.

    Clears the ``k - 3`` reach and keeps the deepest rewind above cell 0;
    ``2**(n-2) - 1`` is sharp (n=4: pad 3 separates all 16; n=5: pad 7 closes
    it; below, rows clamp at the floor).  A shift, since mypy widens ``2 **``.
    """
    return max((1 << (n - 2)) - 1, 1)


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers.

    Setter, :func:`_mux_weight` on the fresh bit, then a pad, so the pointer
    ends at ``c0 - sum(2**(n-1-i) * x_i)``: affine with binary weights,
    hence injective.  Table-independent, cached per arity.  No right-pad:
    ``min(q) = start + (n-1) * (pad + 1) - 1`` clears the span by 30, 28, 28,
    39, 71, 151 cells at n=2..7 and grows.
    """
    if n in _MUX_SEPARATED:
        return _MUX_SEPARATED[n].fork()
    weights = _mux_weights(n)
    pad = _mux_pad(n)
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    for i, k in enumerate(weights):
        j.emit_setter(i)
        j.emit_weight(_mux_weight(k), k)
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # Checked before caching: a lost row would otherwise surface as an
    # unfixable table.  Neither fires at any arity (argued uniformly in the
    # generator tests); they guard against a future weighting.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None  # pragma: no cover - the construction separates by design
    if not _mux_intact(_mux_reference(n), j):
        return None  # pragma: no cover - the construction separates by design
    _MUX_SEPARATED[n] = j.fork()
    return j


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out.

    Judged *after* the walk to the accumulator, which crosses the pool.
    """
    target = (*_POOL, cell7)
    probe = [m.copy() for m in j.ms]
    for char in code:
        for m in probe:
            m.exec(char)
    if any(m.dead or m.skip for m in probe):
        return False
    if len({m.ptr for m in probe}) != 1:
        return False
    steps = walk_out - probe[0].ptr
    if steps < 0:
        return False
    for _ in range(steps):
        for char in "[x":
            for m in probe:
                m.exec(char)
    for cell in range(_POOL_WIDTH):
        col = {m.cell(cell) for m in probe}
        if len(col) != 1 or probe[0].cell(cell) != target[cell]:
            return False
    return True


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)


# Keyed by ``(template, accumulator, orientation)``; a dict since ``None``
# is a real answer.  ``_derived_plans.cache_clear`` empties it too (tests
# count ``_find_pool`` sites, which a warm cache cuts to seventeen).
_PRINTED_COLUMNS: dict[tuple[str, int, int], tuple[int, ...] | None] = {}


_MISSING = object()


def _printed_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return what the ``'[x<[<'`` read prints here, without printing it.

    After the pool code and walk to ``acc - 1`` the read reports ``ptr + 1``,
    complemented for ``'[<'``.  Checked against :func:`_endgame` over 15600
    columns; ``None`` on the two conditions it raises on.  Memoised on the
    template: 12612 distinct triples at n=3 however many tables are asked.
    """
    key = (j.template(), acc, cell7)
    hit = _PRINTED_COLUMNS.get(key, _MISSING)
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    column = _derive_column(j, acc, cell7)
    _PRINTED_COLUMNS[key] = column
    return column


def _derive_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return the column :func:`_printed_column` memoises, derived fresh.

    For :func:`_try_print`, whose fresh template per sculpted build would
    never hit the memo.
    """
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        return None
    probe = j.fork()
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed, not unreachable
        # ``_find_pool`` ignores ``walk_out``; 1740 real stagings, no failure.
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1))


def _try_print(j: _Joint, truth_table: str, acc: int) -> _Joint | None:
    """Emit the endgame that prints the table at ``acc``, or None.

    Read and orientation are computed from :func:`_derive_column` (the reads
    differ only in polarity), in the old trial order; the output is still
    compared against the table (15600 columns checked, corpus byte-identical).
    """
    if acc < _POOL_WIDTH:
        # Mirrors ``_endgame``'s floor.  Not a dead guard: ``_degenerate``
        # probes every cell and the constant-one column sits at cell 1.
        return None
    want = list(truth_table)
    derived: dict[int, tuple[int, ...] | None] = {}
    for read in _READS:
        for cell7 in (0, 1):
            if cell7 not in derived:
                derived[cell7] = _derive_column(j, acc, cell7)
            column = derived[cell7]
            if column is None:
                continue
            digits = column if read == _READS[1] else _complement(column)
            if list(map(str, digits)) != want:
                continue
            probe = j.fork()
            try:
                _endgame(probe, acc, read, cell7)
            except ValueError:  # pragma: no cover - not observed
                # The endgame refuses on the same two conditions the
                # derivation declined on; a raise here is a derivation bug.
                continue
            if probe.printed() != want:  # pragma: no cover - the acceptance
                # Never observed, but "seen to print" is the standard.
                continue
            return probe
    return None
