r"""Unit tests for the Circuit Diagram interpreter."""

import pytest

from esolangs.interpreters.grid_based.circuit_diagram import (
    _OUTPUT,
    _Connections,
    _Grid,
    _Machine,
    _merge,
    _Parser,
    run,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle

# The wiki's 4-bit prime.
# OR gates have an input no.
# ``PRIME_TESTER`` for the.
# how the repair is derived.
PRIME_TESTER_AS_DRAWN = [
    "       .~..",
    "      /    ..         .-.",
    "     <.----=-----    .   o.",
    "    / .~. /.   .---.    .  >.",
    "-4-<     =  >.=--.  o.-=--.  \\",
    "    \\ . . ..      ..  /       .",
    "     < =    = .------=-----.   >.",
    "      = .~..-=--.~.-.       .-.  a.-:",
    "     / \\    / \\                 .",
    "    .   .===.  .               /",
    "     \\   o.  \\  o.------------.",
    "      .-.     ..",
]

# The same circuit with the two.
# gap on the third line, and.
# already draws.
PRIME_TESTER = [
    "       .~..",
    "      /    ..         .-.",
    "     <.----=---------.   o.",
    "    / .~. /.   .---.    .  >.",
    "-4-<     =  >.=--.  o.-=--.  \\",
    "    \\ . . .. /    ..  /       .",
    "     < =    = .------=-----.   >.",
    "      = .~..-=--.~.-.       .-.  a.-:",
    "     / \\    / \\                 .",
    "    .   .===.  .               /",
    "     \\   o.  \\  o.------------.",
    "      .-.     ..",
]

# The wiki's flip-flop: two.
# The page states its output as.
FLIP_FLOP = [
    "--.~.",
    "   =",
    "  .~.--",
]

# The wiki's "it is possible to.
CONSTANT = [
    "     .",
    "--.-. a.----.--.~.",
    "   \\ .     /    =",
    "    \\     /    .~.-----",
    "     .~.~.",
]

PRIMES = frozenset({2, 3, 5, 7, 11, 13})


def output_for(code: list[str], stdin: str) -> str:
    r"""Run ``code`` on ``stdin`` and return everything it printed."""
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def bits_of(value: int) -> str:
    r"""Return ``value`` as four input lines, most significant bit first."""
    return "\n".join(format(value, "04b")) + "\n"


class TestPrimeTester:
    r"""The page's only worked example, replayed over its whole input space."""

    @pytest.mark.parametrize("value", range(16))
    def test_detects_exactly_the_primes(self, value: int) -> None:
        expected = "1" if value in PRIMES else "0"
        assert output_for(PRIME_TESTER, bits_of(value)) == expected

    def test_the_whole_truth_table_is_primality(self) -> None:
        r"""Guard the replay as a set, not just value by value."""
        detected = {n for n in range(16) if output_for(PRIME_TESTER, bits_of(n)) == "1"}
        assert detected == PRIMES

    def test_it_halts_rather_than_looping(self) -> None:
        machine = _Machine(PRIME_TESTER, ScriptedIO(bits_of(7)))
        assert run_until_halt_or_cycle(machine) is True

    def test_missing_input_bits_read_as_zero(self) -> None:
        r"""An exhausted stdin fills the remaining wires with zero bits."""
        assert output_for(PRIME_TESTER, "") == "0"

    def test_an_exhausted_one_bit_input_is_zero(self) -> None:
        r"""A direct wire distinguishes the zero fallback from a one bit."""
        assert output_for(["-:"], "") == "0"

    def test_as_drawn_the_page_prints_nothing(self) -> None:
        r"""The unrepaired diagram is silent, for every input."""
        for value in range(16):
            assert output_for(PRIME_TESTER_AS_DRAWN, bits_of(value)) == ""


class TestFlipFlop:
    r"""Feedback: the page states this alternates rather than settling."""

    def test_it_alternates_one_and_null(self) -> None:
        r"""The page gives this circuit's output as ``1N1N1N...``."""
        machine = _Machine(FLIP_FLOP, ScriptedIO("1\n"))
        seen = []
        for _ in range(6):
            value = machine.values[0]
            seen.append("N" if value is None else str(value[0]))
            machine.step()
        assert "".join(seen) == "1N1N1N"

    def test_it_is_a_provable_cycle(self) -> None:
        machine = _Machine(FLIP_FLOP, ScriptedIO("1\n"))
        assert run_until_halt_or_cycle(machine) is False

    def test_a_zero_input_alternates_too(self) -> None:
        machine = _Machine(FLIP_FLOP, ScriptedIO("0\n"))
        seen = []
        for _ in range(4):
            value = machine.values[0]
            seen.append("N" if value is None else str(value[0]))
            machine.step()
        assert "".join(seen) == "0N0N"


class TestConstantOutput:
    r"""The page's constant-output circuit holds a value indefinitely."""

    def test_it_never_quiesces(self) -> None:
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        assert run_until_halt_or_cycle(machine) is False

    def test_one_wiring_holds_a_steady_one(self) -> None:
        r"""The circuit re-drives its own wiring every generation."""
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        for _ in range(3):
            machine.step()
        held = [v for v in machine.values if v == (1,)]
        assert held, "no wiring is holding a 1"

    def test_a_wiring_may_feed_both_sides_of_a_gate(self) -> None:
        r"""Its ``a`` takes both inputs from one wiring; ports are per cell."""
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        gate = next(g for g in machine.gates if g.kind == "a")
        assert len(gate.inputs) == 2
        assert gate.inputs[0] is gate.inputs[1]


class TestGates:
    r"""Each gate's truth table, driven through a two-input harness."""

    @staticmethod
    def circuit(kind: str) -> list[str]:
        r"""Return a diagram feeding two input bits into ``kind``."""
        return [
            "-.",
            f"  {kind}.-:",
            "-.",
        ]

    @pytest.mark.parametrize(
        ("kind", "expected"),
        [
            ("a", "0001"),
            ("A", "1110"),
            ("o", "0111"),
            ("O", "1000"),
            ("x", "0110"),
            ("X", "1001"),
        ],
    )
    def test_truth_table(self, kind: str, expected: str) -> None:
        got = "".join(
            output_for(self.circuit(kind), f"{a}\n{b}\n")
            for a in (0, 1)
            for b in (0, 1)
        )
        assert got == expected

    @pytest.mark.parametrize(("bit", "expected"), [("0", "1"), ("1", "0")])
    def test_not_inverts(self, bit: str, expected: str) -> None:
        assert output_for(["-.~.-:"], f"{bit}\n") == expected


class TestMultiWire:
    r"""Widths, splitting, combining, and the multi-input gate readings."""

    def test_a_label_widens_its_wiring(self) -> None:
        machine = _Machine(["-3-:"], ScriptedIO("1\n0\n1\n"))
        assert machine.wirings[0].width == 3

    def test_output_prints_every_wire(self) -> None:
        assert output_for(["-3-:"], "1\n0\n1\n") == "101"

    def test_a_summed_label_totals_its_parts(self) -> None:
        machine = _Machine(["-1+2-:"], ScriptedIO("1\n1\n0\n"))
        assert machine.wirings[0].width == 3

    def test_and_over_many_wires_needs_them_all(self) -> None:
        r"""Multi-input AND is 1 iff every wire is 1."""
        circuit = [
            "-2-.",
            "    a.-:",
            "-2-.",
        ]
        assert output_for(circuit, "1\n1\n1\n1\n") == "1"
        assert output_for(circuit, "1\n1\n1\n0\n") == "0"

    def test_or_over_many_wires_needs_only_one(self) -> None:
        circuit = [
            "-2-.",
            "    o.-:",
            "-2-.",
        ]
        assert output_for(circuit, "0\n0\n0\n0\n") == "0"
        assert output_for(circuit, "0\n0\n0\n1\n") == "1"

    def test_xor_over_many_wires_needs_exactly_one(self) -> None:
        circuit = [
            "-2-.",
            "    x.-:",
            "-2-.",
        ]
        assert output_for(circuit, "0\n1\n0\n0\n") == "1"
        assert output_for(circuit, "1\n1\n0\n0\n") == "0"

    def test_not_preserves_width(self) -> None:
        assert output_for(["-3-~.-:"], "1\n0\n1\n") == "010"

    def test_a_splitter_halves_rounding_down(self) -> None:
        r"""``<`` sends floor(n/2) wires up and the rest down."""
        circuit = [
            "    .-:",
            "-3-<",
            "    .-:",
        ]
        machine = _Machine(circuit, ScriptedIO("1\n0\n1\n"))
        split = next(g for g in machine.gates if g.kind == "<")
        assert [w.width for w in split.outputs] == [1, 2]

    def test_a_splitter_sends_the_first_wires_up(self) -> None:
        r"""The upper output takes the low-numbered wires, in order."""
        circuit = [
            "    .-:",
            "-3-<",
            "    .-:",
        ]
        assert output_for(circuit, "1\n0\n1\n") == "101"

    def test_a_splitter_keeps_unequal_outputs_separate(self) -> None:
        r"""The two output wires are independently 1 and 2 bits wide."""
        circuit = [
            "    .-:",
            "-3-<",
            "    .-:",
        ]
        machine = _Machine(circuit, ScriptedIO("1\n0\n1\n"))
        machine.step()
        split = next(g for g in machine.gates if g.kind == "<")
        upper, lower = (machine.values[machine.index[id(w)]] for w in split.outputs)
        assert (upper, lower) == ((1,), (0, 1))

    def test_a_combine_totals_its_two_input_widths(self) -> None:
        r"""``>`` is the splitter's inverse: its output is the sum."""
        circuit = [
            "-1-.",
            "    >-:",
            "-2-.",
        ]
        machine = _Machine(circuit, ScriptedIO("1\n0\n0\n"))
        combine = next(g for g in machine.gates if g.kind == ">")
        assert [w.width for w in combine.inputs] == [1, 2]
        assert combine.outputs[0].width == 3

    def test_a_combine_concatenates_upper_then_lower(self) -> None:
        r"""The upper input's wires lead, in order, as ``<`` splits them."""
        circuit = [
            "-1-.",
            "    >-:",
            "-2-.",
        ]
        assert output_for(circuit, "1\n0\n0\n") == "100"
        assert output_for(circuit, "0\n1\n1\n") == "011"
        assert output_for(circuit, "0\n1\n0\n") == "010"


class TestWiring:
    r"""The connection rules that turn ASCII into a graph."""

    def test_a_crossover_chain_off_any_edge_connects_to_nothing(self) -> None:
        r"""``through`` rejects the cell it lands on, off *any* of the four."""
        conn = _Connections(_Grid(["-=", "  "]))
        assert conn.through(0, 0, (0, 1)) is None, "off the right edge"
        assert conn.through(0, 0, (0, -1)) is None, "off the left edge"
        assert conn.through(0, 0, (-1, 0)) is None, "off the top"
        assert conn.through(1, 0, (1, 0)) is None, "off the bottom"
        # A step that stays on the grid.
        assert conn.through(0, 0, (1, 0)) == (1, 0)

    def test_a_crossover_joins_opposite_sides(self) -> None:
        assert output_for(["-=-~.-:"], "1\n") == "0"

    def test_a_crossover_chain_is_walked_through(self) -> None:
        r"""The prime tester's ``.===.`` spans three crossovers at once."""
        assert output_for(["-===-~.-:"], "1\n") == "0"

    def test_crossing_wires_do_not_mix(self) -> None:
        r"""A ``=`` carries each direction through independently."""
        circuit = [
            "  |",
            "-=-~.-:",
            "  |",
        ]
        assert output_for(circuit, "1\n") == "0"
        assert output_for(circuit, "0\n") == "1"

    def test_a_connection_must_be_mutual(self) -> None:
        r"""``-`` and ``|`` never join: neither reaches toward the other."""
        circuit = [
            "-|",
            "-.~.-:",
        ]
        assert output_for(circuit, "1\n0\n") == "1"

    def test_multiple_drivers_are_xored(self) -> None:
        r"""One wiring driven twice takes the XOR of its drivers."""
        circuit = [
            "-.~.",
            "    .-:",
            "-.~.",
        ]
        assert output_for(circuit, "1\n1\n") == "0"
        assert output_for(circuit, "1\n0\n") == "1"

    def test_overlapping_driver_vectors_are_xored_bit_by_bit(self) -> None:
        r"""Each position merges independently, not by last driver wins."""
        assert _merge([(1, 0), (1, 1)]) == (0, 1)


class TestParseErrors:
    r"""Malformed and out-of-scope programs are rejected, not guessed at."""

    def test_unknown_character_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown character"):
            run(["-.#.-:"], ScriptedIO(""))

    @pytest.mark.parametrize("prefix", ["   ", "-  ", ".  "])
    def test_a_bad_character_after_a_valid_one_is_still_rejected(
        self, prefix: str
    ) -> None:
        r"""Validation scans the whole grid, not up to the first legal cell."""
        with pytest.raises(ValueError, match="out of scope"):
            run([f"{prefix}%"], ScriptedIO(""))

    def test_a_bad_character_after_a_gate_is_still_rejected(self) -> None:
        r"""Character validation cannot stop after seeing a gate."""
        with pytest.raises(ValueError, match="out of scope"):
            run(["~%"], ScriptedIO(""))

    @pytest.mark.parametrize(
        ("code", "name"),
        [
            (["{f", "-.~.-:", "}"], "user-defined functions"),
            ([")-2-:"], "constant-1"),
            (["(-2-:"], "constant-0"),
            (["-t-:"], "clock"),
        ],
    )
    def test_out_of_scope_constructs_are_named(
        self, code: list[str], name: str
    ) -> None:
        with pytest.raises(ValueError, match=name):
            run(code, ScriptedIO(""))

    def test_letter_labelled_wires_are_rejected(self) -> None:
        r"""The whole message is asserted, not a substring of it."""
        with pytest.raises(ValueError, match="letter-labelled") as caught:
            run(["-width-:"], ScriptedIO(""))
        assert (
            str(caught.value)
            == "letter-labelled multi-wires are out of scope: 'w' at (1, 0)"
        )

    def test_a_gate_missing_an_input_is_rejected(self) -> None:
        r"""The position is asserted too: it is the only reader of a gate's."""
        with pytest.raises(ValueError, match="input") as caught:
            run(["-.a.-:"], ScriptedIO("1\n"))
        assert str(caught.value) == "'a' at (2, 0) takes 2 input(s), found 1"

    def test_an_empty_program_has_nothing_to_run(self) -> None:
        assert output_for([], "") == ""

    def test_an_output_is_exempt_from_the_out_port_count(self) -> None:
        r"""An output sinks its wire and drives nothing, so arity skips its."""
        parser = _Parser(_Grid(["-.~.-:"]))
        outputs = [g for g in parser.gates if g.kind == _OUTPUT]
        assert outputs, "the program has an output gate"
        assert [(len(g.inputs), len(g.outputs)) for g in outputs] == [(1, 0)]
        assert output_for(["-.~.-:"], "1\n") == "0"


class TestGrid:
    r"""The padded character grid the parser reads through."""

    def test_only_the_newline_is_stripped(self) -> None:
        r"""Trailing spaces are part of the row, since columns are positions."""
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        grid = _Grid(["ab   \n"])
        assert grid.rows == ["ab   "]
        assert grid.width == 5

    def test_an_empty_program_has_zero_width(self) -> None:
        r"""With no rows there is no width, and the maximum has no default."""
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        assert _Grid([]).width == 0
        assert _Grid([]).rows == []

    def test_outside_the_grid_reads_as_one_blank(self) -> None:
        r"""A position off the grid is a single space, not a longer string."""
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        grid = _Grid(["ab"])
        assert grid.at(0, 0) == "a"
        assert grid.at(9, 9) == " "


class TestWireLabelErrors:
    r"""A wire label has to name a width, and the widths have to agree."""

    def test_a_non_numeric_label_is_rejected(self) -> None:
        r"""``3+x`` is not a sum of widths, so the label means nothing."""
        with pytest.raises(ValueError, match="malformed wire label") as caught:
            run(["-3+x-:"], ScriptedIO(""))
        assert str(caught.value) == "malformed wire label '3+' at (1, 0)"

    def test_a_zero_width_label_is_rejected(self) -> None:
        r"""A wire carrying no bits cannot be read or driven."""
        with pytest.raises(ValueError, match="must be positive") as caught:
            run(["-0-:"], ScriptedIO(""))
        assert str(caught.value) == "wire label '0' at (1, 0) must be positive"

    def test_a_label_touching_no_wire_is_rejected(self) -> None:
        r"""A width written beside nothing annotates nothing."""
        with pytest.raises(ValueError, match="annotates no wire"):
            run([" 3 "], ScriptedIO(""))

    def test_two_labels_disagreeing_on_a_wire_are_rejected(self) -> None:
        r"""One wire cannot be two widths at once."""
        with pytest.raises(ValueError, match="inconsistent wire labels"):
            run(["-2-3-:"], ScriptedIO(""))

    def test_a_splitter_needs_both_its_outputs(self) -> None:
        r"""``<`` drives two wires; with one the circuit is malformed."""
        with pytest.raises(ValueError, match="output") as caught:
            run(["-2-<-:"], ScriptedIO(""))
        assert str(caught.value) == "'<' at (3, 0) drives 2 output(s), found 0"


def test_a_crossover_running_off_the_grid_connects_nothing() -> None:
    r"""A ``=`` chain walked to the edge has no cell on the far side."""
    io = ScriptedIO("1\n")
    run(["-1-="], io)
    assert io.getvalue() == ""


def test_a_gate_contradicting_an_explicit_label_is_rejected() -> None:
    r"""``~`` preserves width, so the labels either side must agree."""
    with pytest.raises(ValueError, match="implies 2 wire"):
        run(["-2-~-3-:"], ScriptedIO(""))


class TestCircuitDiagramMutationSurvivors:
    r"""Two conditions a mutation survived, both about *when* the machine."""

    def test_the_prime_tester_settles_in_ten_generations(self) -> None:
        r"""Quiescence needs *both* halves: nothing fired and no wire is live."""
        for value in range(16):
            machine = _Machine(PRIME_TESTER, ScriptedIO(bits_of(value)))
            generations = 0
            while not machine.halted and generations < 500:
                machine.step()
                generations += 1
            assert machine.halted
            assert generations == 10

    def test_a_not_gate_settles_in_three_generations(self) -> None:
        r"""The smallest circuit pins the same rule without the replay."""
        scripted = ScriptedIO("0\n")
        machine = _Machine(["-.~.-:"], scripted)
        generations = 0
        while not machine.halted and generations < 500:
            machine.step()
            generations += 1
        assert generations == 3
        assert scripted.getvalue() == "1"

    def test_halted_starts_as_the_boolean_false(self) -> None:
        r"""``halted`` is a bool, not merely something falsy."""
        machine = _Machine(["-.~.-:"], ScriptedIO("0\n"))
        assert machine.halted is False


def test_a_not_fed_only_diagonally_is_still_rejected() -> None:
    r"""The level-input rescue needs a level input to find."""
    with pytest.raises(ValueError, match="takes 1 input"):
        run(["-\\  ", "  ~-:", "-/  "], ScriptedIO("1\n0\n"))
