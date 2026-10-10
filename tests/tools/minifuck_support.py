"""The Minifuck suites' shared harness: run a program, fill a template."""

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.minifuck.pool import _BASE, _SEP
from esolangs.tools.minifuck.sim import PAIR, _clamp, _Joint, _Sim, _walk_to


def _copy(sim: _Sim) -> _Sim:
    """Return an independent copy of ``sim``."""
    clone = _Sim.__new__(_Sim)
    clone.tape, clone.length, clone.ptr = sim.tape, sim.length, sim.ptr
    clone.out, clone.dead, clone.skip = list(sim.out), sim.dead, sim.skip
    return clone


def _fork(j: _Joint) -> _Joint:
    """Return a copy of ``j``, for trying a continuation without committing."""
    clone = _Joint.__new__(_Joint)
    clone.n, clone.rows, clone.parts = j.n, j.rows, list(j.parts)
    clone.ms = [_copy(m) for m in j.ms]
    return clone


def _cells(sim: _Sim, stop: int) -> tuple[int, ...]:
    """Return cells ``0..stop-1`` of ``sim``."""
    return tuple(sim.cell(i) for i in range(stop))


def _exec(sim: _Sim, ins: str) -> None:
    """Execute one instruction, the single-character case of the laws."""
    if ins == "<":
        sim.run_left(1)
    elif ins == "[":
        sim.run_brackets(1)
    elif ins == ".":
        sim.run_dot()
    else:
        sim.run_comment(1)


# Complements the bit a setter just wrote.  The ``x`` absorbs the cascade's
# skip flag, or the gadget eats the template's next instruction: ``<[``
# passed a tape+pointer probe and printed 0 of 12 on the real interpreter.
_FLIP = "<[x"


def _embed(n: int, settle: int = 0, sep: str = _SEP, flips: int = 0) -> _Joint:
    """The shipped embed plus ``settle`` re-crossings and ``flips`` complements."""
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        if (flips >> i) & 1:
            j.emit(_FLIP)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


def run_count(template: str, n: int) -> int:
    """How many input runs ``template`` carries, expecting ``n``."""
    return len(runs(template, TEMPLATE_CHAR, (PAIR,) * n))


class _MinifuckCase:
    """Input-by-substitution boolean generator for Minifuck."""

    def run_minifuck(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import fill

        _fill_minifuck = fill("Minifuck")

        return _fill_minifuck(tpl, bits)


# --- The separation gadget and the pool oracles.  Nothing shipped builds
# through these: the mux is the preloaded-strip lookup.  They stay as the
# fixtures and the exhaustive checks the pool tests drive.
from esolangs.tools.minifuck.mux import (  # noqa: E402
    _MUX_GUARD,
    _mux_start,
    _mux_weight,
    _mux_weights,
)
from esolangs.tools.minifuck.pool import _POOL, _POOL_WIDTH  # noqa: E402

# One separation per arity, forked out.  A dict: the value is a mutable ``_Joint``.
_MUX_SEPARATED: dict[int, _Joint] = {}


def _mux_reference(n: int) -> _Joint:
    """Return a joint walked to the embed's start with nothing embedded yet."""
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    """Whether every cell left of the guard survived, on every row."""
    return all(
        _cells(m, _MUX_GUARD) == _cells(m0, _MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight."""
    return max((1 << (n - 2)) - 1, 1)


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers."""
    if n in _MUX_SEPARATED:
        return _fork(_MUX_SEPARATED[n])
    weights = _mux_weights(n)
    pad = _mux_pad(n)
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    for i, k in enumerate(weights):
        j.emit_setter(i)
        j.emit(_mux_weight(k))
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # Checked before caching: a lost row would otherwise surface as an
    # unfixable table.  Neither fires at any arity (argued uniformly in the
    # generator tests); they guard against a future weighting.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None  # pragma: no cover - the construction separates by design
    if not _mux_intact(_mux_reference(n), j):
        return None  # pragma: no cover - the construction separates by design
    _MUX_SEPARATED[n] = _fork(j)
    return j


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out."""
    target = (*_POOL, cell7)
    probe = [_copy(m) for m in j.ms]
    for char in code:
        for m in probe:
            _exec(m, char)
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
                _exec(m, char)
    for cell in range(_POOL_WIDTH):
        col = {m.cell(cell) for m in probe}
        if len(col) != 1 or probe[0].cell(cell) != target[cell]:
            return False
    return True


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)
