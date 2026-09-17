"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

from tests.tools.minifuck_support import _mux_separate


def _scout_setup(module: object, n: int) -> tuple[object, range]:
    """The separation ``_mux`` scouts at ``n``, with the accumulators it tries."""
    base = _mux_separate(n)
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    accs = range(highest - lowest + module._POOL_WIDTH + 1, lowest - 1)  # noqa: SLF001
    return base, accs


class TestMuxUsesOneRule:
    """The production mux uses one direct preloaded-strip rule."""

    def test_the_rule_matches_the_named_lookup(self) -> None:
        """The named strip construction is the production spelling."""
        module = importlib.import_module("esolangs.tools.minifuck")
        for n, table in ((2, "0110"), (2, "0001"), (3, "01101001")):
            built = module._mux(table, n)  # noqa: SLF001
            assert built == module._mux_lookup(table, n)  # noqa: SLF001

    def test_the_start_displacement_sets_the_baseline_phase(self) -> None:
        """Crossing an odd extra prefix flips the zero-control column."""
        module = importlib.import_module("esolangs.tools.minifuck")
        phases = [
            (n ^ (module._mux_start(n) - module._MUX_BASE) ^ 1)  # noqa: SLF001
            & 1
            for n in range(2, 9)
        ]
        assert phases == [1, 0, 1, 1, 0, 1, 0]


class TestProbeFrameAndColumns:
    """The summaries' own refusals, reached by constructed keys.

    Each is a guard on the frame being a function of the pool byte alone.
    The construction never offers these states, so every one is built here
    rather than waited for.
    """

    def test_a_code_that_writes_above_the_pool_has_no_frame(self) -> None:
        """The frame summarises the low byte, so a carry out of it refuses.

        Found by enumerating the ``<[.x`` alphabet: ``.[[...[<`` from byte
        242 leaves the region's cells alone but changes what sits above it,
        which the frame cannot describe.
        """
        module = importlib.import_module("esolangs.tools.minifuck")
        assert module._probe_frame(".[[...[<", 242) is None  # noqa: SLF001
