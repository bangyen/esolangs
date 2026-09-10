"""Interprogck8's two routing backstops, each pinned to its own message.

The shipped constants are sized so neither fires -- the settle and the
repair budget are both measured, not argued -- so each is reached by
shrinking the budget it guards rather than by finding a table that
defeats the real one.  The express test module accepts whichever
refusal a starved meadow happens to reach; these separate them.
"""

import hashlib
import importlib

import pytest

from esolangs.tools.boolean import interprogck8


def _parity_table(n: int) -> str:
    """A table whose every row differs from its neighbours."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**n))


def _dense_table(n: int) -> str:
    """The contract suite's dense pseudo-random table."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


class TestRoutingBackstops:
    def test_widths_that_run_out_of_passes_are_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One pass cannot settle a program whose widths still move."""
        module = importlib.import_module("esolangs.tools.boolean.interprogck8")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_PASSES", 1)
            with pytest.raises(ValueError, match="did not converge"):
                interprogck8(_parity_table(6))

    def test_a_shortfall_given_no_repairs_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no meadows to add, a routing shortfall names its window.

        Dense at n=8 needs a couple of repair meadows under the shipped
        placement, so a budget below zero turns its first shortfall into
        the refusal -- which must name the stranded window rather than
        emit a program that jumps into the middle of a subtree.
        """
        module = importlib.import_module("esolangs.tools.boolean.interprogck8")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_REPAIRS", -1)
            with pytest.raises(ValueError, match="no rung slot"):
                interprogck8(_dense_table(8))

    def test_the_shipped_constants_still_build_the_table(self) -> None:
        """The positive control: neither backstop fires by default."""
        assert interprogck8(_parity_table(6))
