r"""Unit tests for the Circuit Diagram interpreter."""

import time
from collections import OrderedDict
from functools import partial

import pytest

from esolangs.interpreters.grid_based.circuit_diagram import (
    _compile,
    _functions,
    _Machine,
    _merge,
    _seconds_since_2000,
    run,
)
from esolangs.interpreters.grid_based.circuit_diagram._functions import _remember_width
from esolangs.interpreters.grid_based.circuit_diagram._parse import (
    _OUTPUT,
    _Connections,
    _Grid,
    _Parser,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.fixtures import grid
from tests.interpreters.runner import run_program

# The wiki's 4-bit prime tester, exactly as the page draws it.  Two of its
# OR gates have an input no gate ever drives, so it prints nothing; see
# ``PRIME_TESTER`` for the repaired circuit and the module docstring for
# how the repair is derived.
PRIME_TESTER_AS_DRAWN = grid("circuit_diagram/prime_tester_as_drawn.txt")

# The same circuit with the two omissions repaired: four ``-`` closing the
# gap on the third line, and the ``/`` whose two ``=`` crossings the page
# already draws.  This computes primality of a 4-bit input, MSB first.
PRIME_TESTER = grid("circuit_diagram/prime_tester.txt")

# The wiki's flip-flop: two NOTs wired into each other through a crossover.
# The page states its output as ``1N1N1N...``.
FLIP_FLOP = grid("circuit_diagram/flip_flop.txt")

# The wiki's "it is possible to produce a constant output" circuit.
CONSTANT = grid("circuit_diagram/constant.txt")

PRIMES = frozenset({2, 3, 5, 7, 11, 13})


output_for = partial(run_program, run, suppress_eof=False)


def bits_of(value: int) -> str:
    """Return ``value`` as four input lines, most significant bit first."""
    return "\n".join(format(value, "04b")) + "\n"


class TestPrimeTester:
    """The page's only worked example, replayed over its whole input space."""

    def test_the_whole_truth_table_is_primality(self) -> None:
        """Guard the replay as a set, not just value by value."""
        detected = {n for n in range(16) if output_for(PRIME_TESTER, bits_of(n)) == "1"}
        assert detected == PRIMES

    def test_cached_topology_keeps_run_state_isolated(self) -> None:
        _compile.cache_clear()
        assert output_for(PRIME_TESTER, bits_of(2)) == "1"
        assert output_for(PRIME_TESTER, bits_of(4)) == "0"
        assert _compile.cache_info().hits == 1

    def test_cached_topology_keeps_debugger_state_isolated(self) -> None:
        _compile.cache_clear()
        first = _Machine(PRIME_TESTER, ScriptedIO(bits_of(2)))
        second = _Machine(PRIME_TESTER, ScriptedIO(bits_of(4)))
        initial = second.snapshot()
        assert run_until_halt_or_cycle(first) is True
        assert second.snapshot() == initial
        assert run_until_halt_or_cycle(second) is True
        assert first.io.getvalue() == "1"
        assert second.io.getvalue() == "0"
        assert _compile.cache_info().hits == 1

    def test_it_halts_rather_than_looping(self) -> None:
        machine = _Machine(PRIME_TESTER, ScriptedIO(bits_of(7)))
        assert run_until_halt_or_cycle(machine) is True

    def test_missing_input_bits_read_as_zero(self) -> None:
        """An exhausted stdin fills the remaining wires with zero bits."""
        assert output_for(PRIME_TESTER, "") == "0"

    def test_as_drawn_the_page_prints_nothing(self) -> None:
        """The unrepaired diagram is silent, for every input."""
        for value in range(16):
            assert output_for(PRIME_TESTER_AS_DRAWN, bits_of(value)) == ""


class TestFlipFlop:
    """Feedback: the page states this alternates rather than settling."""

    def test_it_alternates_one_and_null(self) -> None:
        """The page gives this circuit's output as ``1N1N1N...``."""
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
    """The page's constant-output circuit holds a value indefinitely."""

    def test_it_never_quiesces(self) -> None:
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        assert run_until_halt_or_cycle(machine) is False

    def test_one_wiring_holds_a_steady_one(self) -> None:
        """The circuit re-drives its own wiring every generation."""
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        for _ in range(3):
            machine.step()
        held = [v for v in machine.values if v == (1,)]
        assert held, "no wiring is holding a 1"

    def test_a_wiring_may_feed_both_sides_of_a_gate(self) -> None:
        """Its ``a`` takes both inputs from one wiring; ports are per cell."""
        machine = _Machine(CONSTANT, ScriptedIO("1\n"))
        gate = next(g for g in machine.gates if g.kind == "a")
        assert len(gate.inputs) == 2
        assert gate.inputs[0] is gate.inputs[1]


class TestGates:
    """Each gate's truth table, driven through a two-input harness."""

    @staticmethod
    def circuit(kind: str) -> list[str]:
        """Return a diagram feeding two input bits into ``kind``."""
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
    """Widths, splitting, combining, and the multi-input gate readings."""

    def test_a_label_widens_its_wiring(self) -> None:
        machine = _Machine(["-3-:"], ScriptedIO("1\n0\n1\n"))
        assert machine.wirings[0].width == 3

    def test_a_summed_label_totals_its_parts(self) -> None:
        machine = _Machine(["-1+2-:"], ScriptedIO("1\n1\n0\n"))
        assert machine.wirings[0].width == 3

    @pytest.mark.parametrize(
        ("kind", "ones"),
        [("A", {0, 1, 2, 3}), ("O", {0}), ("X", {0, 2, 3, 4})],
    )
    def test_the_negated_gates_read_many_wires_as_the_wiki_says(
        self, kind: str, ones: set[int]
    ) -> None:
        """NAND: not all 1; NOR: no 1; XNOR: only 0s or more than one 1."""
        circuit = ["-2-.", f"    {kind}.-:", "-2-."]
        for row in range(16):
            bits = f"{row:04b}"
            want = "1" if bits.count("1") in ones else "0"
            assert output_for(circuit, "\n".join(bits) + "\n") == want, bits

    def test_a_splitter_halves_rounding_down(self) -> None:
        """``<`` sends floor(n/2) wires up and the rest down."""
        circuit = _SPLIT3
        machine = _Machine(circuit, ScriptedIO("1\n0\n1\n"))
        split = next(g for g in machine.gates if g.kind == "<")
        assert [w.width for w in split.outputs] == [1, 2]

    def test_a_splitter_keeps_unequal_outputs_separate(self) -> None:
        """The two output wires are independently 1 and 2 bits wide."""
        circuit = _SPLIT3
        machine = _Machine(circuit, ScriptedIO("1\n0\n1\n"))
        machine.step()
        split = next(g for g in machine.gates if g.kind == "<")
        upper, lower = (machine.values[machine.index[id(w)]] for w in split.outputs)
        assert (upper, lower) == ((1,), (0, 1))

    def test_a_combine_totals_its_two_input_widths(self) -> None:
        """``>`` is the splitter's inverse: its output is the sum."""
        circuit = _COMBINE
        machine = _Machine(circuit, ScriptedIO("1\n0\n0\n"))
        combine = next(g for g in machine.gates if g.kind == ">")
        assert [w.width for w in combine.inputs] == [1, 2]
        assert combine.outputs[0].width == 3


@pytest.mark.parametrize(
    "source", [["-.", "  \\", "   :"], ["   :", "  /", "-."], ["-.:"], ["-=:"], [":"]]
)
def test_output_requires_a_horizontal_dash_directly_left(source: list[str]) -> None:
    with pytest.raises(ValueError, match="requires '-' directly to its left"):
        output_for(source, "1\n")


class TestSpecifiedSourcesAndRemoval:
    """The built-in functions outside the page's worked circuits."""

    def test_clock_is_a_32_bit_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "esolangs.interpreters.grid_based.circuit_diagram._seconds_since_2000",
            lambda: 5,
        )
        assert output_for(["t-32-:"], "") == f"{5:032b}"

    def test_the_real_clock_counts_seconds_since_2000(self) -> None:
        # 946684800 is the Unix time of 2000-01-01T00:00:00Z.
        assert abs(_seconds_since_2000() - (int(time.time()) - 946684800)) <= 2


class TestWiring:
    """The connection rules that turn ASCII into a graph."""

    def test_a_crossover_chain_off_any_edge_connects_to_nothing(self) -> None:
        """``through`` rejects the cell it lands on, off *any* of the four."""
        conn = _Connections(_Grid(["-=", "  "]))
        assert conn.through(0, 0, (0, 1)) is None, "off the right edge"
        assert conn.through(0, 0, (0, -1)) is None, "off the left edge"
        assert conn.through(0, 0, (-1, 0)) is None, "off the top"
        assert conn.through(1, 0, (1, 0)) is None, "off the bottom"
        # A step that stays on the grid still returns the cell it reaches.
        assert conn.through(0, 0, (1, 0)) == (1, 0)

    def test_overlapping_driver_vectors_are_xored_bit_by_bit(self) -> None:
        """Each position merges independently, not by last driver wins."""
        assert _merge([(1, 0), (1, 1)]) == (0, 1)


class TestParseErrors:
    """Malformed and out-of-scope programs are rejected, not guessed at."""

    def test_a_gate_missing_an_input_is_rejected(self) -> None:
        """The position is asserted too: it is the only reader of a gate's
        ``row`` and ``col``, which nothing else on a valid program looks at.
        """
        with pytest.raises(ValueError, match="input") as caught:
            run(["-.a.-:"], ScriptedIO("1\n"))
        assert str(caught.value) == "'a' at (2, 0) takes 2 input(s), found 1"

    def test_an_output_is_exempt_from_the_out_port_count(self) -> None:
        """An output sinks its wire and drives nothing, so arity skips its ports."""
        parser = _Parser(_Grid(["-.~.-:"]))
        outputs = [g for g in parser.gates if g.kind == _OUTPUT]
        assert outputs, "the program has an output gate"
        assert [(len(g.inputs), len(g.outputs)) for g in outputs] == [(1, 0)]
        assert output_for(["-.~.-:"], "1\n") == "0"


class TestWireLabelErrors:
    """A wire label has to name a width, and the widths have to agree."""

    def test_a_zero_width_label_is_rejected(self) -> None:
        """A wire carrying no bits cannot be read or driven."""
        with pytest.raises(ValueError, match="must be positive") as caught:
            run(["-0-:"], ScriptedIO(""))
        assert str(caught.value) == "wire label '0' at (1, 0) must be positive"

    def test_a_fixed_width_may_propagate_to_another_symbol_use(self) -> None:
        machine = _Machine(["-2-n-:", "-n-:"], ScriptedIO("1\n0\n1\n0\n"))
        assert sorted(wiring.width for wiring in machine.wirings) == [2, 2]

    def test_a_splitter_needs_both_its_outputs(self) -> None:
        """``<`` drives two wires; with one the circuit is malformed."""
        with pytest.raises(ValueError, match="output") as caught:
            run(["-2-<-:"], ScriptedIO(""))
        assert str(caught.value) == "'<' at (3, 0) drives 2 output(s), found 0"


class TestCircuitDiagramMutationSurvivors:
    """Two conditions a mutation survived, both about *when* the machine stops."""

    def test_the_prime_tester_settles_in_ten_generations(self) -> None:
        """Quiescence needs *both* halves: nothing fired and no wire is live."""
        for value in range(16):
            machine = _Machine(PRIME_TESTER, ScriptedIO(bits_of(value)))
            generations = 0
            while not machine.halted and generations < 500:
                machine.step()
                generations += 1
            assert machine.halted
            assert generations == 10

    def test_a_not_gate_settles_in_three_generations(self) -> None:
        """The smallest circuit pins the same rule without the replay."""
        scripted = ScriptedIO("0\n")
        machine = _Machine(["-.~.-:"], scripted)
        generations = 0
        while not machine.halted and generations < 500:
            machine.step()
            generations += 1
        assert generations == 3
        assert scripted.getvalue() == "1"


class TestSpecRepairs:
    """One pin per spec repair the independent model found."""

    def test_a_clock_read_inside_a_call_is_in_the_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The call's one clock read advances the caller's cursor, so a
        # changing clock cannot fake a cycle.
        monkeypatch.setattr(
            "esolangs.interpreters.grid_based.circuit_diagram._seconds_since_2000",
            lambda: 5,
        )
        code = ["{stamp", "-.~.-:", "t-32-:", "}", "-stamp-:"]
        machine = _Machine(code, ScriptedIO("1\n"))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == f"{5:032b}0"
        assert machine.snapshot()[3] == 1

    def test_a_clock_read_before_a_nested_call_is_replayed_not_reread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads = iter(range(1, 10))
        monkeypatch.setattr(
            "esolangs.interpreters.grid_based.circuit_diagram._seconds_since_2000",
            lambda: next(reads),
        )
        code = ["{inv", "-.~.-:", "}", "{stamp", "t-32-:", "-inv-:", "}", "-stamp-:"]
        assert output_for(code, "1\n") == f"{1:032b}0"

    def test_the_width_cache_forgets_its_oldest_entry_past_256(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        widths = OrderedDict((((), str(i), None, ()), 1) for i in range(256))
        monkeypatch.setattr(_functions, "_FUNCTION_WIDTHS", widths)
        _remember_width(((), "new", None, ()), 2)
        assert len(widths) == 256
        assert ((), "0", None, ()) not in widths
        assert widths[((), "new", None, ())] == 2

    def test_a_function_runtime_error_keeps_its_hint(self) -> None:
        code = ["{loop", *FLIP_FLOP, "}", "-loop-:"]
        with pytest.raises(ValueError, match="does not settle") as error:
            run(code, ScriptedIO("1\n"))
        assert error.value.__notes__ == [
            "hint: remove oscillating feedback from the function so it "
            "reaches a settled output"
        ]


_SPLIT3 = ["    .-:", "-3-<", "    .-:"]
_COMBINE = ["-1-.", "    >-:", "-2-."]
_BOTH = ["{both", "-.", "  a.-:", "-.", "}", "-.", "  both.-:", "-."]


def _MANY(kind: str) -> list[str]:
    """Two two-wire inputs into one multi-input ``kind`` gate."""
    return ["-2-.", f"    {kind}.-:", "-2-."]


@pytest.mark.parametrize(
    ("circuit", "stdin", "expected"),
    [
        # A direct wire distinguishes the zero fallback from a one bit.
        pytest.param(["-:"], "", "0", id="an_exhausted_one_bit_input_is_zero"),
        pytest.param(["-3-:"], "1\n0\n1\n", "101", id="output_prints_every_wire"),
        pytest.param(["-3-~.-:"], "1\n0\n1\n", "010", id="not_preserves_width"),
        # The upper output of ``<`` takes the low-numbered wires, in order.
        pytest.param(
            _SPLIT3, "1\n0\n1\n", "101", id="a_splitter_sends_the_first_wires_up"
        ),
        pytest.param([")-3-:"], "", "111", id="one_source_fills_its_output_width"),
        pytest.param(["(-3-:"], "", "000", id="zero_source_fills_its_output_width"),
        pytest.param(
            ["-2-.", "    %-:", "-4-."],
            "1\n0\n0\n1\n1\n0\n",
            "10",
            id="remove_drops_the_first_input_width_from_the_second",
        ),
        pytest.param(
            ["-2-n-.", "      >-n+n-:", "-2-n-."],
            "1\n0\n0\n1\n",
            "1001",
            id="repeated_symbolic_labels_share_a_width",
        ),
        pytest.param(
            ["{invert", "-.~.-:", "}", "-invert-:"], "1\n", "0", id="one_input_function"
        ),
        pytest.param(
            ["{invert", "-n-~-n-:", "}", "-3-invert-:"],
            "1\n0\n1\n",
            "010",
            id="function_labels_bind_to_the_call_width",
        ),
        pytest.param(
            ["{invert", "-2-~-2-:", "}", "-2-invert-:"],
            "1\n0\n",
            "01",
            id="function_may_fix_its_input_width_numerically",
        ),
        pytest.param(
            ["{%", "-n-.", "    ?.-:", "-m-.", "}", "(-2-:"],
            "",
            "00",
            id="builtin_definition_may_be_spelled_out",
        ),
        pytest.param(["-=-~.-:"], "1\n", "0", id="a_crossover_joins_opposite_sides"),
        # The prime tester's ``.===.`` spans three crossovers at once.
        pytest.param(
            ["-===-~.-:"], "1\n", "0", id="a_crossover_chain_is_walked_through"
        ),
        # ``-`` and ``|`` never join: neither reaches toward the other.
        pytest.param(["-|", "-.~.-:"], "1\n0\n", "1", id="a_connection_must_be_mutual"),
        pytest.param(
            ["-width-:"], "1\n", "1", id="letter_labelled_wires_are_supported"
        ),
        pytest.param([], "", "", id="an_empty_program_has_nothing_to_run"),
        pytest.param(
            ["-3+x-:"], "1\n0\n1\n0\n", "1010", id="a_symbolic_sum_label_is_supported"
        ),
        # A ``=`` chain walked to the edge has no cell on the far side.
        pytest.param(
            ["-1-="], "1\n", "", id="a_crossover_running_off_the_grid_connects_nothing"
        ),
        # Each leading '-' reads its own bit; drivers of one wiring XOR (wiki).
        pytest.param(
            ["-.", " |", "-.-:"],
            "1\n1\n",
            "0",
            id="two_input_rows_on_one_wiring_are_xored",
        ),
        # '-inv-' in a body is a call, not a symbolic width label.
        pytest.param(
            ["{inv", "-.~.-:", "}", "{wrap", "-inv-:", "}", "-wrap-:"],
            "1\n",
            "0",
            id="a_function_body_may_call_another_function",
        ),
        # 5001 digits, value 2: beyond int()'s default 4300-digit cap.
        pytest.param(
            ["-" + "0" * 5000 + "2-:"],
            "1\n0\n",
            "10",
            id="a_width_label_past_the_int_digit_limit_parses",
        ),
        pytest.param(
            _MANY("a"), "1\n1\n1\n1\n", "1", id="and_over_many_wires_needs_them_all_0"
        ),
        pytest.param(
            _MANY("a"), "1\n1\n1\n0\n", "0", id="and_over_many_wires_needs_them_all_1"
        ),
        pytest.param(
            _MANY("o"), "0\n0\n0\n0\n", "0", id="or_over_many_wires_needs_only_one_0"
        ),
        pytest.param(
            _MANY("o"), "0\n0\n0\n1\n", "1", id="or_over_many_wires_needs_only_one_1"
        ),
        pytest.param(
            _MANY("x"),
            "0\n1\n0\n0\n",
            "1",
            id="xor_over_many_wires_needs_exactly_one_0",
        ),
        pytest.param(
            _MANY("x"),
            "1\n1\n0\n0\n",
            "0",
            id="xor_over_many_wires_needs_exactly_one_1",
        ),
        pytest.param(
            _COMBINE, "1\n0\n0\n", "100", id="a_combine_concatenates_upper_then_lower_0"
        ),
        pytest.param(
            _COMBINE, "0\n1\n1\n", "011", id="a_combine_concatenates_upper_then_lower_1"
        ),
        pytest.param(
            _COMBINE, "0\n1\n0\n", "010", id="a_combine_concatenates_upper_then_lower_2"
        ),
        pytest.param(
            ["-:"], "1\n", "1", id="output_with_a_direct_left_dash_executes_0"
        ),
        pytest.param(
            ["-:"], "0\n", "0", id="output_with_a_direct_left_dash_executes_1"
        ),
        pytest.param(_BOTH, "1\n1\n", "1", id="two_input_function_0"),
        pytest.param(_BOTH, "1\n0\n", "0", id="two_input_function_1"),
        pytest.param(
            ["  |", "-=-~.-:", "  |"], "1\n", "0", id="crossing_wires_do_not_mix_0"
        ),
        pytest.param(
            ["  |", "-=-~.-:", "  |"], "0\n", "1", id="crossing_wires_do_not_mix_1"
        ),
        pytest.param(
            ["-.~.", "    .-:", "-.~."],
            "1\n1\n",
            "0",
            id="multiple_drivers_are_xored_0",
        ),
        pytest.param(
            ["-.~.", "    .-:", "-.~."],
            "1\n0\n",
            "1",
            id="multiple_drivers_are_xored_1",
        ),
    ],
)
def test_output(circuit: list[str], stdin: str, expected: str) -> None:
    assert output_for(circuit, stdin) == expected


@pytest.mark.parametrize(
    ("circuit", "stdin", "match"),
    [
        pytest.param(
            ["{invert", "-2-~-2-:", "}", "-3-invert-:"],
            "1\n0\n1\n",
            "expects 2 input wires",
            id="fixed_function_input_width_is_checked",
        ),
        pytest.param(
            ["{invert", "-n+m-~-n+m-:", "}", "-2-invert-:"],
            "1\n0\n",
            "number or one name",
            id="function_input_cannot_be_a_symbolic_sum",
        ),
        pytest.param(
            ["{foo", "-.~.-:", "}", "{foo", "-.~.-:", "}"],
            "",
            "duplicate function",
            id="duplicate_function_is_rejected",
        ),
        pytest.param(
            ["{foo", "-.~.-:"],
            "",
            "unterminated function",
            id="unterminated_function_is_rejected",
        ),
        pytest.param(
            ["{a", "-.~.-:", "}"],
            "",
            "reserved",
            id="reserved_function_name_is_rejected",
        ),
        pytest.param(
            ["{invert", "-.~.-:", "}", "-2-invert-:"],
            "1\n0\n",
            "one-wire input",
            id="unlabelled_function_input_requires_one_wire",
        ),
        pytest.param(
            ["{same", "-n-.", "    a.-:", "-n-.", "}", "-2-.", "    same.-:", "-3-."],
            "1\n0\n1\n0\n1\n",
            "binds 'n'",
            id="one_symbol_cannot_bind_to_two_input_widths",
        ),
        pytest.param(
            ["{loop", *FLIP_FLOP, "}", "-loop-:"],
            "1\n",
            "does not settle",
            id="function_that_does_not_settle_is_rejected",
        ),
        pytest.param(
            ["{silent", "-.~.-", "}", "-silent-:"],
            "1\n",
            "did not return bits",
            id="function_without_a_return_is_rejected",
        ),
        pytest.param(
            ["-.#.-:"], "", "unknown character", id="unknown_character_is_rejected"
        ),
        pytest.param(
            ["~?"],
            "",
            "out of scope",
            id="a_bad_character_after_a_gate_is_still_rejected",
        ),
        pytest.param(
            [" 3 "], "", "annotates no wire", id="a_label_touching_no_wire_is_rejected"
        ),
        pytest.param(
            ["-3 "],
            "",
            "annotates no wire",
            id="a_label_missing_its_right_wire_is_rejected",
        ),
        pytest.param(
            ["-2-3-:"],
            "",
            "inconsistent wire labels",
            id="two_labels_disagreeing_on_a_wire_are_rejected",
        ),
        pytest.param(
            ["-2-n-:", "-3-n-:"],
            "",
            "inconsistent widths",
            id="repeated_symbol_cannot_have_two_fixed_widths",
        ),
        pytest.param(
            ["-3-n+n-:"],
            "",
            "symbolic wire label implies",
            id="symbolic_sum_must_agree_with_a_fixed_width",
        ),
        pytest.param(
            ["-2-.", "    %-:", "-2-."],
            "",
            "removes every output wire",
            id="remove_must_leave_an_output_wire",
        ),
        pytest.param(
            ["-2-~-3-:"],
            "",
            "implies 2 wire",
            id="a_gate_contradicting_an_explicit_label_is_rejected",
        ),
        pytest.param(
            ["-.", "  \\", "---:"],
            "1\n",
            r"takes 1 input\(s\), found 2",
            id="output_rejects_an_additional_diagonal_input",
        ),
        pytest.param(
            ["-\\  ", "  ~-:", "-/  "],
            "1\n0\n",
            r"takes 1 input\(s\), found 2",
            id="a_not_fed_only_diagonally_is_still_rejected",
        ),
        pytest.param(
            ["-.", "  a.-:", " .-."],
            "1\n",
            "feeds both input and output",
            id="a_wiring_on_both_sides_of_a_gate_is_rejected",
        ),
        pytest.param(
            ["    .-:", "-1-<", "    .-:"],
            "1\n",
            "empty output bundle",
            id="splitting_one_wire_is_rejected",
        ),
        pytest.param(
            ["{loop", "-loop-:", "}", "-loop-:"],
            "1\n",
            "recursively depends on itself",
            id="a_self_calling_function_is_rejected",
        ),
    ],
)
def test_rejected(circuit: list[str], stdin: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        run(circuit, ScriptedIO(stdin))
