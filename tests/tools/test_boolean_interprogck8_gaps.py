"""Interprogck8's two routing backstops, each pinned to its own message.

The shipped constants are sized so neither fires -- the settle is
measured, not argued -- so each is reached by shrinking the budget it
guards rather than by finding a table that defeats the real one.  The
existing relay test accepts whichever backstop a narrowed spacing
happens to reach; these separate them.
"""

import importlib

import pytest

from esolangs.tools.boolean import interprogck8


def _dense_table(n: int) -> str:
    """A table whose every row differs from its neighbours."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**n))


class TestRoutingBackstops:
    def test_widths_that_run_out_of_passes_are_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One pass cannot settle a program whose widths still move."""
        module = importlib.import_module("esolangs.tools.boolean.interprogck8")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_PASSES", 1)
            with pytest.raises(ValueError, match="did not converge"):
                interprogck8(_dense_table(6))

    def test_a_relay_given_no_patience_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no rounds to spare, a relay that must route gives up.

        Parity at n=7 needs several rounds -- it gets worse before it gets
        better -- so a patience of zero refuses it on the first round that
        does not improve, naming the count it gave up on.
        """
        module = importlib.import_module("esolangs.tools.boolean.interprogck8")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_PATIENCE", 0)
            with pytest.raises(ValueError, match="jump routing gave up"):
                interprogck8(_dense_table(7))

    def test_the_shipped_constants_still_build_the_table(self) -> None:
        """The positive control: neither backstop fires by default."""
        assert interprogck8(_dense_table(6))
