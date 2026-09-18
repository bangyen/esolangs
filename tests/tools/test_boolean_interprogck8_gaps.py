"""Interprogck8's corridor machinery that no shipped arity reaches.

Two pieces are load-bearing but dormant at buildable sizes: the stride
classes past the first (the mod-30 pool of fourteen residues serves
fourteen inputs, past the contract's ceiling) and the validator's refusal
(the assembler plans the flights it validates, so a live build never
trips it).  Each is reached by construction -- shrinking the pool,
corrupting the corridor -- rather than by finding a table that defeats
the real constants.
"""

import hashlib
import importlib

import pytest

from esolangs.tools import interprogck8
from esolangs.tools.interprogck8 import _RUNG, _assemble, _Layout, _validate
from tests.tools.boolean_runners import run_interprogck8


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


class TestDormantMachinery:
    def test_deep_stride_classes_route_and_execute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Adjusted strides work, proved by shrinking the pool to reach them.

        Two residues per class force a five-input tree through three
        stride classes (30, 32, 34), so the ``@nd`` adjusters and the
        cross-class stop avoidance -- dead code below depth 14 otherwise
        -- carry real flights, and every row still executes.
        """
        module = importlib.import_module("esolangs.tools.interprogck8")
        table = _parity_table(5)
        with monkeypatch.context() as patch:
            patch.setattr(module, "_PHASES_PER_CLASS", 2)
            lines, flights = _assemble(table, 5)
        assert {stride for _, stride, _ in flights} >= {30, 32, 34}, (
            "the shrunken pool must actually reach three stride classes"
        )
        _validate(lines, flights)
        program = "\n".join(lines)
        for row in range(32):
            bits = list(bin(row)[2:].zfill(5))
            assert run_interprogck8(program, bits) == table[row], f"row {row}"

    def test_a_corrupted_corridor_is_refused_not_emitted(self) -> None:
        """A non-rung straying onto an open channel fails validation.

        That is the corridor's one failure mode -- the chain would
        dismount mid-flight and compute the wrong row -- so the check
        must catch a single blanked rung on any multi-hop flight.
        """
        lines, flights = _assemble(_dense_table(6), 6)
        launch, stride, _stop = next(f for f in flights if f[2] - f[0] > f[1])
        assert lines[launch + stride] == _RUNG
        lines[launch + stride] = "x"
        with pytest.raises(AssertionError, match="dismounts"):
            _validate(lines, flights)

    def test_the_placer_walks_over_an_occupied_line(self) -> None:
        """A placement scan skips occupied lines rather than reusing them.

        The tree's own scans mostly start past the frontier where every
        line is free, so the skip is pinned directly: a line already
        holding an instruction is passed over for the next fit.
        """
        layout = _Layout()
        layout.put(4, "x")
        assert layout.place(4, 0, ()) == 6

    def test_the_shipped_constants_still_build_the_table(self) -> None:
        """The positive control: neither backstop fires by default."""
        assert interprogck8(_parity_table(6))

    def test_the_pool_thins_when_a_second_class_opens(self) -> None:
        """Residues per class come from probing the placer, not a table.

        Fourteen inputs ride one full class; a fifteenth needs a second,
        whose two-odd-line read never fits under a full first, so the
        pool thins to thirteen.  The arity where it runs out is the next
        test: the probe past 15 is what costs, and it costs on the placer
        rather than on anything this repository can make cheaper.
        """
        from esolangs.tools.interprogck8 import _phases

        assert _phases(14) == 14
        assert _phases(15) == 13

    # 0.8s local, 3.4s on a CI runner against the fast band's scaled 3s:
    # `_phases` walks the pool down from fourteen and replays the whole
    # placement stack per candidate, and the two high arities are most of
    # that.  The probe is the documented method, not a shortcut to replace.
    @pytest.mark.medium
    def test_the_pool_ends_at_forty(self) -> None:
        """Past forty no pool places every depth under a fully open stack.

        Forty is the last arity the probe places, at nine residues; a
        forty-first has no pool at all and the generator refuses.
        """
        from esolangs.exceptions import TruthTableError
        from esolangs.tools.interprogck8 import _phases

        assert _phases(40) == 9
        with pytest.raises(TruthTableError, match="at most 40"):
            _phases(41)
