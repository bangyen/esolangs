"""Covers :mod:`esolangs.tools.minifuck` and :mod:`esolangs.tools.minifuck.mux`."""

import importlib
from unittest.mock import patch

import pytest

from esolangs.tools.helpers import essential_inputs
from esolangs.tools.minifuck import _solve
from esolangs.tools.minifuck.mux import _MUX_MIN_ARITY, _mux, _mux_lookup
from esolangs.tools.minifuck.sim import _MINIFUCK_INPUT, PAIR
from tests.tools.minifuck_support import _MinifuckCase, _mux_separate, run_count


class TestParameterizedMinifuck(_MinifuckCase):
    """The generator end to end, and the routes before the lookup."""

    @pytest.mark.slow  # the four-input separation derivation, ~15s once
    def test_sculpted_route_computes_and_is_row_addressable(self) -> None:
        """``_mux`` builds a fully-essential table and every row is run."""

        separated = _mux_separate(4)
        positions = separated.ptrs()
        assert len(set(positions)) == 16, positions
        assert run_count(separated.template(), 4) == 4

        table = "0110100110010110"
        template = _mux(table, 4)
        assert template is not None
        assert run_count(template, 4) == 4
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.slow  # the six-input build, tens of seconds
    def test_no_arity_is_gated(self) -> None:
        """A fully-essential six-input table builds and prints all 64 rows."""

        module = importlib.import_module("esolangs.tools.minifuck")
        assert _MUX_MIN_ARITY == 2

        n = 6
        # Fixed table rather than a sampled one: a test that picks its own
        # table cannot fail reproducibly.
        table = "0110100110010110100101100110100101101001011010011100101101001010"
        assert len(table) == 2**n
        assert len(essential_inputs(table, n)) == n, "the table must be fully essential"

        template = module._solve(table)  # noqa: SLF001
        assert run_count(template, n) == n
        widths = set()
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.parametrize(
        ("table", "tier"),
        [
            ("0001", "scan"),  # AND: the embed's carry chain already holds it
            ("0110", "column search"),  # XOR: found by searching for a column
        ],
    )
    def test_the_search_tiers_still_build_when_the_cheap_routes_miss(
        self, table: str, tier: str
    ) -> None:
        """With the degenerate route stubbed off, ``_mux`` builds the table."""

        module = importlib.import_module("esolangs.tools.minifuck")

        with patch.object(module, "_degenerate", lambda *_a, **_k: None):
            _solve.cache_clear()
            try:
                template = _solve.__wrapped__(table)
            finally:
                _solve.cache_clear()

        assert template, f"the {tier} tier returned nothing"
        for combo in range(4):
            bits = [(combo >> 1) & 1, combo & 1]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], (tier, bits)

    def test_the_mux_uses_the_preloaded_strip_rule(self) -> None:
        """``_mux`` is exactly the named linear lookup construction."""

        table = "1010000110011011"
        built = _mux(table, 4)
        assert built is not None

        assert built == _mux_lookup(table, 4)

    def test_template_is_input_independent_and_equal_length(self) -> None:
        """The template has placeholders and every fill has the same length."""
        from esolangs import tools as generators

        template = generators.minifuck("0110")
        assert "{X" not in template
        assert run_count(template, 2) == 2
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"

    def test_ignored_inputs_wrap_the_inner_program(self) -> None:
        """An inert block before it per leading input, a run after per trailing one."""
        from esolangs.interpreters.tape_based.minifuck import _step

        module = importlib.import_module("esolangs.tools.minifuck")
        inert = module._INERT  # noqa: SLF001
        for fill in PAIR:
            code, tape, ptr, at = inert.replace(_MINIFUCK_INPUT, fill), 0, 0, 0
            while at < len(code):
                tape, _length, ptr, skipped, char, reads = _step(code[at], tape, 8, ptr)
                assert (char, reads) == (None, False)
                at += 2 if skipped else 1
            assert (tape, ptr, at) == (0, 0, len(code)), fill

        inner = module._solve("01")  # noqa: SLF001
        for table, template in (
            ("0101", inert + inner),
            ("0011", inner + _MINIFUCK_INPUT),
        ):
            assert module._solve(table) == template  # noqa: SLF001
            for row, expected in enumerate(table):
                bits = [row >> 1, row & 1]
                assert self.run_minifuck(self.instantiate(template, bits)) == expected

    def test_an_ignored_input_between_two_is_a_pad_step(self) -> None:
        """Input 1 of four, ignored, costs a pad step, not the full-arity mux."""
        inner = "01101001"  # inputs 0, 2 and 3
        table = "".join(inner[(row >> 3 << 2) | (row & 3)] for row in range(16))
        template = _solve(table)
        assert len(template) < 0.7 * len(_mux(table, 4))
        for row, expected in enumerate(table):
            bits = [(row >> shift) & 1 for shift in (3, 2, 1, 0)]
            assert self.run_minifuck(self.instantiate(template, bits)) == expected
