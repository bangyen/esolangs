"""The Minifuck suites' shared harness: run a program, fill a template."""

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.minifuck.sim import PAIR


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
        from tests.tools.fills import _fill_minifuck

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
from esolangs.tools.minifuck.sim import _Joint, _walk_to  # noqa: E402

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
        m.cells(_MUX_GUARD) == m0.cells(_MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight."""
    return max((1 << (n - 2)) - 1, 1)


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers."""
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
    """Whether ``code`` leaves the pool correct once walked out."""
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
