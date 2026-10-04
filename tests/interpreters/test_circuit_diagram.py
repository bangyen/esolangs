"""Circuit Diagram parser diagnostics and malformed programs."""

import pytest

from esolangs.interpreters.grid_based.circuit_diagram import (
    _Connections,
    _Grid,
    _Machine,
    run,
)
from esolangs.interpreters.io import ScriptedIO

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
    "source", [["-.", "  \\", "   :"], ["   :", "  /", "-."], ["-.:"], ["-=:"], [":"]]
)
def test_output_requires_a_horizontal_dash_directly_left(source: list[str]) -> None:
    with pytest.raises(ValueError, match="requires '-' directly to its left"):
        output_for(source, "1\n")


def test_output_rejects_an_additional_diagonal_input() -> None:
    with pytest.raises(ValueError, match=r"takes 1 input\(s\), found 2"):
        output_for(["-.", "  \\", "---:"], "1\n")


class TestFunctions:
    """Named custom gates are declared outside and called inside the grid."""

    def test_fixed_function_input_width_is_checked(self) -> None:
        circuit = ["{invert", "-2-~-2-:", "}", "-3-invert-:"]
        with pytest.raises(ValueError, match="expects 2 input wires"):
            run(circuit, ScriptedIO("1\n0\n1\n"))

    def test_function_input_cannot_be_a_symbolic_sum(self) -> None:
        circuit = ["{invert", "-n+m-~-n+m-:", "}", "-2-invert-:"]
        with pytest.raises(ValueError, match="number or one name"):
            run(circuit, ScriptedIO("1\n0\n"))

    def test_duplicate_function_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate function"):
            run(["{foo", "-.~.-:", "}", "{foo", "-.~.-:", "}"], ScriptedIO(""))

    def test_unterminated_function_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unterminated function"):
            run(["{foo", "-.~.-:"], ScriptedIO(""))

    def test_reserved_function_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="reserved"):
            run(["{a", "-.~.-:", "}"], ScriptedIO(""))

    def test_builtin_definition_may_be_spelled_out(self) -> None:
        code = ["{%", "-n-.", "    ?.-:", "-m-.", "}", "(-2-:"]
        assert output_for(code, "") == "00"

    def test_unlabelled_function_input_requires_one_wire(self) -> None:
        code = ["{invert", "-.~.-:", "}", "-2-invert-:"]
        with pytest.raises(ValueError, match="one-wire input"):
            run(code, ScriptedIO("1\n0\n"))

    def test_one_symbol_cannot_bind_to_two_input_widths(self) -> None:
        code = [
            "{same",
            "-n-.",
            "    a.-:",
            "-n-.",
            "}",
            "-2-.",
            "    same.-:",
            "-3-.",
        ]
        with pytest.raises(ValueError, match="binds 'n'"):
            run(code, ScriptedIO("1\n0\n1\n0\n1\n"))

    def test_function_that_does_not_settle_is_rejected(self) -> None:
        code = ["{loop", *FLIP_FLOP, "}", "-loop-:"]
        with pytest.raises(ValueError, match="does not settle"):
            run(code, ScriptedIO("1\n"))

    def test_function_without_a_return_is_rejected(self) -> None:
        code = ["{silent", "-.~.-", "}", "-silent-:"]
        with pytest.raises(ValueError, match="did not return bits"):
            run(code, ScriptedIO("1\n"))


class TestWiring:
    """The connection rules that turn ASCII into a graph."""

    def test_a_crossover_chain_off_any_edge_connects_to_nothing(self) -> None:
        """``through`` rejects the cell it lands on, off *any* of the four.

        The chain walks while it sees ``=``, so a chain at the border
        walks straight off the grid.  The guard covers both axes and both
        ends of each, and the existing crossover tests all land back on
        the grid -- so the ``and`` joining the two axes, and each ``<``
        in it, were free to change.  The east case lands with its row in
        range and its column one past the last, which is what separates
        the two halves.
        """
        conn = _Connections(_Grid(["-=", "  "]))
        assert conn.through(0, 0, (0, 1)) is None, "off the right edge"
        assert conn.through(0, 0, (0, -1)) is None, "off the left edge"
        assert conn.through(0, 0, (-1, 0)) is None, "off the top"
        assert conn.through(1, 0, (1, 0)) is None, "off the bottom"
        # A step that stays on the grid still returns the cell it reaches.
        assert conn.through(0, 0, (1, 0)) == (1, 0)


class TestParseErrors:
    """Malformed and out-of-scope programs are rejected, not guessed at."""

    def test_unknown_character_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown character"):
            run(["-.#.-:"], ScriptedIO(""))

    @pytest.mark.parametrize("prefix", ["   ", "-  ", ".  "])
    def test_a_bad_character_after_a_valid_one_is_still_rejected(
        self, prefix: str
    ) -> None:
        """Validation scans the whole grid, not up to the first legal cell.

        Every other malformed-grid test here puts the offending character
        first, so a scan that stopped early would still pass them.  Leading
        with a space, a wire and a gate covers the arms that skip a cell.
        """
        with pytest.raises(ValueError, match="out of scope"):
            run([f"{prefix}?"], ScriptedIO(""))

    def test_a_bad_character_after_a_gate_is_still_rejected(self) -> None:
        """Character validation cannot stop after seeing a gate."""
        with pytest.raises(ValueError, match="out of scope"):
            run(["~?"], ScriptedIO(""))

    def test_a_gate_missing_an_input_is_rejected(self) -> None:
        """The position is asserted too: it is the only reader of a gate's
        ``row`` and ``col``, which nothing else on a valid program looks at.
        """
        with pytest.raises(ValueError, match="input") as caught:
            run(["-.a.-:"], ScriptedIO("1\n"))
        assert str(caught.value) == "'a' at (2, 0) takes 2 input(s), found 1"


class TestGrid:
    """The padded character grid the parser reads through.

    Its three decisions -- what is stripped from a line, how wide an empty
    program is, and what lies outside the grid -- are all reachable, and
    none had a test: every program in the suite is non-empty, written
    without trailing spaces, and read inside its own bounds.
    """

    def test_only_the_newline_is_stripped(self) -> None:
        """Trailing spaces are part of the row, since columns are positions.

        Stripping whitespace generally would shorten a row, and column
        positions are what the parser navigates by -- so a diagram whose
        wire ends in spaces would lose them.
        """
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        grid = _Grid(["ab   \n"])
        assert grid.rows == ["ab   "]
        assert grid.width == 5

    def test_an_empty_program_has_zero_width(self) -> None:
        """With no rows there is no width, and the maximum has no default."""
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        assert _Grid([]).width == 0
        assert _Grid([]).rows == []

    def test_outside_the_grid_reads_as_one_blank(self) -> None:
        """A position off the grid is a single space, not a longer string.

        The parser compares this against single characters, so a wider
        filler would silently stop matching anything.
        """
        from esolangs.interpreters.grid_based.circuit_diagram import _Grid

        grid = _Grid(["ab"])
        assert grid.at(0, 0) == "a"
        assert grid.at(9, 9) == " "


class TestWireLabelErrors:
    """A wire label has to name a width, and the widths have to agree."""

    def test_a_zero_width_label_is_rejected(self) -> None:
        """A wire carrying no bits cannot be read or driven."""
        with pytest.raises(ValueError, match="must be positive") as caught:
            run(["-0-:"], ScriptedIO(""))
        assert str(caught.value) == "wire label '0' at (1, 0) must be positive"

    def test_a_label_touching_no_wire_is_rejected(self) -> None:
        """A width written beside nothing annotates nothing."""
        with pytest.raises(ValueError, match="annotates no wire"):
            run([" 3 "], ScriptedIO(""))

    def test_a_label_missing_its_right_wire_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="annotates no wire"):
            run(["-3 "], ScriptedIO(""))

    def test_two_labels_disagreeing_on_a_wire_are_rejected(self) -> None:
        """One wire cannot be two widths at once."""
        with pytest.raises(ValueError, match="inconsistent wire labels"):
            run(["-2-3-:"], ScriptedIO(""))

    def test_repeated_symbol_cannot_have_two_fixed_widths(self) -> None:
        with pytest.raises(ValueError, match="inconsistent widths"):
            run(["-2-n-:", "-3-n-:"], ScriptedIO(""))

    def test_symbolic_sum_must_agree_with_a_fixed_width(self) -> None:
        with pytest.raises(ValueError, match="symbolic wire label implies"):
            run(["-3-n+n-:"], ScriptedIO(""))

    def test_a_splitter_needs_both_its_outputs(self) -> None:
        """``<`` drives two wires; with one the circuit is malformed."""
        with pytest.raises(ValueError, match="output") as caught:
            run(["-2-<-:"], ScriptedIO(""))
        assert str(caught.value) == "'<' at (3, 0) drives 2 output(s), found 0"

    def test_remove_must_leave_an_output_wire(self) -> None:
        circuit = ["-2-.", "    %-:", "-2-."]
        with pytest.raises(ValueError, match="removes every output wire"):
            run(circuit, ScriptedIO(""))


def test_a_crossover_running_off_the_grid_connects_nothing() -> None:
    """A ``=`` chain walked to the edge has no cell on the far side.

    The walk hops crossovers rather than stepping one cell, but it needs no
    bounds check per hop: ``_Grid.at`` reads an off-grid cell as a space,
    which is never a crossover, so walking past the border ends the loop and
    the single check after it rejects where the walk landed.  A wire ending
    in a crossover at the border simply connects to nothing.
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

    def test_halted_starts_as_the_boolean_false(self) -> None:
        """``halted`` is a bool, not merely something falsy.

        The VM's cycle detector puts this in every snapshot it hashes, and
        a mutant that initialised it to ``None`` compared equal to nothing
        while still reading as false.  Pinning the type keeps the flag a
        flag.
        """
        machine = _Machine(["-.~.-:"], ScriptedIO("0\n"))
        assert machine.halted is False


def test_a_not_fed_only_diagonally_is_still_rejected() -> None:
    r"""The level-input rescue needs a level input to find.

    A ``~`` with more than one incoming port is read as a gate some other
    wiring is routed diagonally past, so the parser retries with the level
    cell alone and keeps that when it is the only one.  Here both feeders are
    diagonal -- ``\`` points down-right and ``/`` up-right, so each aims into
    the gate -- and the cell level with it is blank, so the retry finds
    nothing and the two diagonals stand.  A NOT takes one input, so the
    circuit is malformed rather than quietly reading one of them.
    """
    with pytest.raises(ValueError, match=r"takes 1 input\(s\), found 2"):
        run(["-\\  ", "  ~-:", "-/  "], ScriptedIO("1\n0\n"))
