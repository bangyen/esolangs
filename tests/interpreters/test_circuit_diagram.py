r"""Unit tests for the Circuit Diagram interpreter.

The wiki page carries three worked circuits -- a 4-bit prime tester, a
flip-flop, and a constant-output loop -- and they are the ground truth here,
because the spec leaves the execution cadence, the halting rule, the input
ordering, and the exact gate port geometry unstated.  See the module
docstring of ``esolangs.interpreters.grid_based.circuit_diagram`` for how
each gap is resolved and which circuit pins it down.

The prime tester is the strongest of the three: replaying it over all
sixteen 4-bit inputs and comparing against the primes in 0-15 is a check no
wrong signal model passes by accident.  It is also drawn with five
characters missing, so both the repaired circuit and the page's own
as-drawn silence are pinned below.
"""

import pytest

from esolangs.interpreters.grid_based.circuit_diagram import (
    _OUTPUT,
    _Grid,
    _Machine,
    _Parser,
    run,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle

# The wiki's 4-bit prime tester, exactly as the page draws it.  Two of its
# OR gates have an input no gate ever drives, so it prints nothing; see
# ``PRIME_TESTER`` for the repaired circuit and the module docstring for
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

# The same circuit with the two omissions repaired: four ``-`` closing the
# gap on the third line, and the ``/`` whose two ``=`` crossings the page
# already draws.  This computes primality of a 4-bit input, MSB first.
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

# The wiki's flip-flop: two NOTs wired into each other through a crossover.
# The page states its output as ``1N1N1N...``.
FLIP_FLOP = [
    "--.~.",
    "   =",
    "  .~.--",
]

# The wiki's "it is possible to produce a constant output" circuit.
CONSTANT = [
    "     .",
    "--.-. a.----.--.~.",
    "   \\ .     /    =",
    "    \\     /    .~.-----",
    "     .~.~.",
]

PRIMES = frozenset({2, 3, 5, 7, 11, 13})


def output_for(code: list[str], stdin: str) -> str:
    """Run ``code`` on ``stdin`` and return everything it printed."""
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def bits_of(value: int) -> str:
    """Return ``value`` as four input lines, most significant bit first."""
    return "\n".join(format(value, "04b")) + "\n"


class TestPrimeTester:
    """The page's only worked example, replayed over its whole input space."""

    @pytest.mark.parametrize("value", range(16))
    def test_detects_exactly_the_primes(self, value: int) -> None:
        expected = "1" if value in PRIMES else "0"
        assert output_for(PRIME_TESTER, bits_of(value)) == expected

    def test_the_whole_truth_table_is_primality(self) -> None:
        """Guard the replay as a set, not just value by value."""
        detected = {n for n in range(16) if output_for(PRIME_TESTER, bits_of(n)) == "1"}
        assert detected == PRIMES

    def test_it_halts_rather_than_looping(self) -> None:
        machine = _Machine(PRIME_TESTER, ScriptedIO(bits_of(7)))
        assert run_until_halt_or_cycle(machine) is True

    def test_missing_input_bits_read_as_zero(self) -> None:
        """An exhausted stdin fills the remaining wires with zero bits."""
        assert output_for(PRIME_TESTER, "") == "0"

    def test_as_drawn_the_page_prints_nothing(self) -> None:
        """The unrepaired diagram is silent, for every input.

        Two of its OR gates have an input no gate drives, so under the
        spec's own "gates wait" rule they never fire and the output is
        never reached.  This pins the page's own text as characterization,
        so a later change to the connection rules cannot quietly turn the
        broken diagram into a working one without this failing.
        """
        for value in range(16):
            assert output_for(PRIME_TESTER_AS_DRAWN, bits_of(value)) == ""


class TestFlipFlop:
    """Feedback: the page states this alternates rather than settling."""

    def test_it_alternates_one_and_null(self) -> None:
        """The page gives this circuit's output as ``1N1N1N...``."""
        machine = _Machine(FLIP_FLOP, ScriptedIO("1\n"))
        seen = []
        for _ in range(6):
            value = machine.wirings[0].value
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
            value = machine.wirings[0].value
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
        held = [w.value for w in machine.wirings if w.value == (1,)]
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

    def test_output_prints_every_wire(self) -> None:
        assert output_for(["-3-:"], "1\n0\n1\n") == "101"

    def test_a_summed_label_totals_its_parts(self) -> None:
        machine = _Machine(["-1+2-:"], ScriptedIO("1\n1\n0\n"))
        assert machine.wirings[0].width == 3

    def test_and_over_many_wires_needs_them_all(self) -> None:
        """Multi-input AND is 1 iff every wire is 1."""
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
        """``<`` sends floor(n/2) wires up and the rest down."""
        circuit = [
            "    .-:",
            "-3-<",
            "    .-:",
        ]
        machine = _Machine(circuit, ScriptedIO("1\n0\n1\n"))
        split = next(g for g in machine.gates if g.kind == "<")
        assert [w.width for w in split.outputs] == [1, 2]

    def test_a_splitter_sends_the_first_wires_up(self) -> None:
        """The upper output takes the low-numbered wires, in order."""
        circuit = [
            "    .-:",
            "-3-<",
            "    .-:",
        ]
        assert output_for(circuit, "1\n0\n1\n") == "101"


class TestWiring:
    """The connection rules that turn ASCII into a graph."""

    def test_a_crossover_joins_opposite_sides(self) -> None:
        assert output_for(["-=-~.-:"], "1\n") == "0"

    def test_a_crossover_chain_is_walked_through(self) -> None:
        """The prime tester's ``.===.`` spans three crossovers at once."""
        assert output_for(["-===-~.-:"], "1\n") == "0"

    def test_crossing_wires_do_not_mix(self) -> None:
        """A ``=`` carries each direction through independently.

        The vertical wire crossing the input's path is a separate wiring,
        so it neither steals the input bit nor adds a driver to it: the
        ``~`` still sees exactly the bit that was read.
        """
        circuit = [
            "  |",
            "-=-~.-:",
            "  |",
        ]
        assert output_for(circuit, "1\n") == "0"
        assert output_for(circuit, "0\n") == "1"

    def test_a_connection_must_be_mutual(self) -> None:
        """``-`` and ``|`` never join: neither reaches toward the other.

        The stray ``|`` sits directly right of the upper ``-``, and if that
        counted as a connection the two rows would be one wiring and the
        second input bit would XOR into the first.  Printing the first bit
        unchanged shows they stayed apart.
        """
        circuit = [
            "-|",
            "-.~.-:",
        ]
        assert output_for(circuit, "1\n0\n") == "1"

    def test_multiple_drivers_are_xored(self) -> None:
        """One wiring driven twice takes the XOR of its drivers."""
        circuit = [
            "-.~.",
            "    .-:",
            "-.~.",
        ]
        assert output_for(circuit, "1\n1\n") == "0"
        assert output_for(circuit, "1\n0\n") == "1"


class TestParseErrors:
    """Malformed and out-of-scope programs are rejected, not guessed at."""

    def test_unknown_character_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown character"):
            run(["-.#.-:"], ScriptedIO(""))

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
        with pytest.raises(ValueError, match="letter-labelled"):
            run(["-width-:"], ScriptedIO(""))

    def test_a_gate_missing_an_input_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="input"):
            run(["-.a.-:"], ScriptedIO("1\n"))

    def test_an_empty_program_has_nothing_to_run(self) -> None:
        assert output_for([], "") == ""

    def test_an_output_is_exempt_from_the_out_port_count(self) -> None:
        """An output sinks its wire and drives nothing, so arity skips its ports.

        ``_check_arity`` inspects every parsed gate, outputs included, and
        returns early for them.  The early return is load-bearing rather than
        defensive: an output always parses with zero out-ports, so without it
        the ``wanted_out = 1`` check below would reject every program that
        prints.  This asserts the port counts the parser actually assigns.
        """
        parser = _Parser(_Grid(["-.~.-:"]))
        outputs = [g for g in parser.gates if g.kind == _OUTPUT]
        assert outputs, "the program has an output gate"
        assert [(len(g.inputs), len(g.outputs)) for g in outputs] == [(1, 0)]
        assert output_for(["-.~.-:"], "1\n") == "0"


class TestWireLabelErrors:
    """A wire label has to name a width, and the widths have to agree."""

    def test_a_non_numeric_label_is_rejected(self) -> None:
        """``3+x`` is not a sum of widths, so the label means nothing."""
        with pytest.raises(ValueError, match="malformed wire label"):
            run(["-3+x-:"], ScriptedIO(""))

    def test_a_zero_width_label_is_rejected(self) -> None:
        """A wire carrying no bits cannot be read or driven."""
        with pytest.raises(ValueError, match="must be positive"):
            run(["-0-:"], ScriptedIO(""))

    def test_a_label_touching_no_wire_is_rejected(self) -> None:
        """A width written beside nothing annotates nothing."""
        with pytest.raises(ValueError, match="annotates no wire"):
            run([" 3 "], ScriptedIO(""))

    def test_two_labels_disagreeing_on_a_wire_are_rejected(self) -> None:
        """One wire cannot be two widths at once."""
        with pytest.raises(ValueError, match="inconsistent wire labels"):
            run(["-2-3-:"], ScriptedIO(""))

    def test_a_splitter_needs_both_its_outputs(self) -> None:
        """``<`` drives two wires; with one the circuit is malformed."""
        with pytest.raises(ValueError, match="output"):
            run(["-2-<-:"], ScriptedIO(""))


def test_a_crossover_running_off_the_grid_connects_nothing() -> None:
    """A ``=`` chain walked to the edge has no cell on the far side.

    The walk hops crossovers rather than stepping one cell, so it has to
    check the bounds each hop as well as after the last one; a wire that
    ends in a crossover at the border simply connects to nothing.
    """
    io = ScriptedIO("1\n")
    run(["-1-="], io)
    assert io.getvalue() == ""


def test_a_gate_contradicting_an_explicit_label_is_rejected() -> None:
    """``~`` preserves width, so the labels either side must agree.

    Widths flow forward from wherever a label fixes them; where that flow
    meets a *different* explicit label the circuit is contradictory, and
    guessing which label wins would silently read the wrong number of bits.
    """
    with pytest.raises(ValueError, match="implies 2 wire"):
        run(["-2-~-3-:"], ScriptedIO(""))


class TestCircuitDiagramMutationSurvivors:
    """Two conditions a mutation survived, both about *when* the machine stops.

    Mutation testing (mutmut against a ``bundle_one`` build of this module)
    reported these as changeable without any test noticing.  The suite
    checks what each circuit computes and that it halts at all, so a mutant
    that produced the right answer a generation early was invisible: the
    output is the same string either way.  Each was confirmed by loading
    the mutant and the original side by side and diffing their behaviour.
    """

    def test_the_prime_tester_settles_in_ten_generations(self) -> None:
        """Quiescence needs *both* halves: nothing fired and no wire is live.

        The rule reads ``not fired and all(... is None ...)``.  A mutant
        reading it with ``or`` halted as soon as either half held, one
        generation early, and every input still printed the right answer --
        so only the count says the halt moved.
        """
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

    def test_halted_starts_as_the_boolean_false(self) -> None:
        """``halted`` is a bool, not merely something falsy.

        The VM's cycle detector puts this in every snapshot it hashes, and
        a mutant that initialised it to ``None`` compared equal to nothing
        while still reading as false.  Pinning the type keeps the flag a
        flag.
        """
        machine = _Machine(["-.~.-:"], ScriptedIO("0\n"))
        assert machine.halted is False
