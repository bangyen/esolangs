"""Unit tests for the Interprogck8 boolean generator.

Every claim here is made by running the emitted program: the corridor is
routed by ``DownAccLines``, whose off-by-one is the whole construction,
so reading the source proves nothing about where a chain dismounts.
"""

import hashlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _dice, _Machine
from esolangs.tools import interprogck8
from esolangs.tools.helpers import _greedy_input_order, permute_truth_table
from esolangs.tools.interprogck8 import _assemble, _validate
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.boolean_runners import run_interprogck8


def _dense_table(n: int) -> str:
    """The contract suite's dense pseudo-random table, the worst to fold."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _tables(n: int) -> list[str]:
    return [bin(v)[2:].zfill(2**n) for v in range(2 ** (2**n))]


class TestExhaustive:
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
    def test_every_table_of_every_arity(self, n: int) -> None:
        """All 4, 16 and 256 tables, every row, executed.

        This is the phase-1 gate answered by construction rather than by
        argument: a full decision tree routes through ``DownAccLines``
        alone, and the current-function slot is never touched.
        """
        for table in _tables(n):
            program = interprogck8(table)
            assert "<" not in program, "routing must not use the function slot"
            for row in range(2**n):
                bits = list(bin(row)[2:].zfill(n))
                assert run_interprogck8(program, bits) == table[row], (
                    f"{table} row {row}"
                )


class TestReads:
    @pytest.mark.parametrize("table", ["00000000", "11111111", "01101001"])
    def test_a_folded_table_still_consumes_its_inputs(self, table: str) -> None:
        """Every path reads all three digits before printing.

        The reads are the interface: leaving a bit unread desynchronises
        whatever runs on the same stream next.
        """
        program = interprogck8(table)
        io = ScriptedIO("0\n1\n1\n")
        machine = _Machine(program.splitlines(), io)
        run_until_halt_or_cycle(machine)
        assert io.position() == 3, "a constant table must still read all three"
        assert io.getvalue() == table[0b011]


class TestCorridor:
    """Past n=3 flights cross whole subtrees on the shared corridor."""

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_a_tree_past_one_hop_still_computes_its_table(self, n: int) -> None:
        """Every row of a table too long to route in single hops.

        The n=5 parity corridor is ~2000 lines against a reach of 255,
        so every 1-arm rides shared rungs across its sibling subtree --
        and a flight that dismounts on the wrong line is a *wrong
        answer* rather than a refusal, which is why the assertion is on
        the output and not on the program building.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = interprogck8(table)
        assert "<" not in program, "routing must not use the function slot"
        for row in range(2**n):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8(program, bits) == table[row], f"n={n} row {row}"

    @pytest.mark.parametrize("n", [8, pytest.param(10, marks=pytest.mark.slow)])
    def test_a_high_arity_table_is_computed_row_by_row(self, n: int) -> None:
        """The lifted ceiling, held by execution on hash-picked rows.

        Running all 1024 rows again on every suite run buys nothing over
        a fixed sample once the full sweep has passed, so the rows are
        drawn deterministically from the table's own digest -- plus the
        two ends, where an off-by-one in the printers would land.
        """
        table = _dense_table(n)
        program = interprogck8(table)
        digest = hashlib.sha256(f"rows:{n}".encode()).digest()
        rows = {0, 2**n - 1}
        rows.update(int.from_bytes(digest[i : i + 2]) % 2**n for i in range(0, 32, 2))
        for row in sorted(rows):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8(program, bits) == table[row], f"n={n} row {row}"

    def test_relay_flights_past_255_keep_size_flat(self) -> None:
        """Relay chains route past-255 flights with flat per-entry size.

        Dense n=6 has 51 of 97 flights spanning past ``DownAccLines``'s
        255-line reach (longest 5478 lines), so the relay is exercised,
        not assumed -- and the emitted program still computes all 64
        rows.  Per-entry size stays flat (674 at n=6, 742 at n=10) while
        total flight length is already super-linear (309x nT at n=6
        against 56x at n=2): sharing decouples size from flight length,
        so a routed-tree edge-length count alone cannot close the
        roadmap's size cell and any bound must price the sharing.
        """
        table = _dense_table(6)
        program = interprogck8(table)
        lines, flights = _assemble(table, 6)
        _validate(lines, flights)
        over = [f for f in flights if f[2] - f[0] > 255]
        assert len(over) > len(flights) // 2, "the relay must actually fire"
        assert max(f[2] - f[0] for f in flights) > 5000
        assert 600 <= len(program) / 64 <= 900, "flat through the relay regime"
        total = sum(stop - launch for launch, _, stop in flights)
        assert total > 200 * 6 * 64, "flight length already super-linear"
        for row in range(2**6):
            bits = list(bin(row)[2:].zfill(6))
            assert run_interprogck8(program, bits) == table[row], f"row {row}"

    @pytest.mark.slow
    def test_dense_size_stays_flat_to_twelve_while_flights_grow(self) -> None:
        """Dense per-entry size is flat to n=12 while flight length is not.

        Dense n=12 emits 714.4 characters per entry (741.9 at n=10, 745.7
        at n=11: no trend) in 0.2 s, and 18 digest-sampled rows execute --
        but total flight length reaches 11592x nT against 3711x at n=10,
        so the routed-tree edge count and the size are decoupled one more
        rung out.  The registry contract (to n=12) confirms the cell; this
        pins the numbers it must confirm.
        """
        n = 12
        table = _dense_table(n)
        program = interprogck8(table)
        lines, flights = _assemble(table, n)
        _validate(lines, flights)
        assert 600 <= len(program) / 2**n <= 900, "flat one rung past n=10"
        total = sum(stop - launch for launch, _, stop in flights)
        assert total > 3711 * n * 2**n, "flights grew past the n=10 figure"
        digest = hashlib.sha256(f"rows:{n}".encode()).digest()
        rows = {0, 2**n - 1}
        rows.update(int.from_bytes(digest[i : i + 2]) % 2**n for i in range(0, 32, 2))
        seen = set()
        for row in sorted(rows):
            bits = list(bin(row)[2:].zfill(n))
            got = run_interprogck8(program, bits)
            assert got == table[row], f"n={n} row {row}"
            seen.add(got)
        assert seen == {"0", "1"}, "the sample must cover both polarities"

    @pytest.mark.slow
    def test_input_order_collapse_is_not_spendable(self) -> None:
        """A greedy input order collapses pass-through but cannot be spent.

        The cofactor-popcount scorer finds input 7 first on the n=10
        ``x7`` table and the permuted build shrinks 476.8 to 12.5
        characters per entry, all 1024 rows executing on permuted inputs --
        so the scorer fires and a flat result elsewhere is real.  But level
        ``k`` necessarily splits on stream input ``k`` (the reads are the
        interface), so feeding that program stream-order inputs mismatches
        512 of 1024 rows: reordering is not a construction for this
        generator.  Symmetric sparse tables (AND, OR, single minterm) score
        every input tied, keep the identity, and gain nothing.
        """
        n = 10
        table = "".join(str((row >> (n - 1 - 7)) & 1) for row in range(2**n))
        order = _greedy_input_order(table, n)
        assert order[0] == 7, "the scorer must find the live input first"
        program = interprogck8(permute_truth_table(table, order))
        assert len(program) / 2**n < 476.8 / 10, "the collapse must be large"
        for row in range(2**n):
            bits = list(bin(row)[2:].zfill(n))
            fed = [bits[order[k]] for k in range(n)]
            assert run_interprogck8(program, fed) == table[row], f"row {row}"
        bad = 0
        for row in range(2**n):
            bits = list(bin(row)[2:].zfill(n))
            if run_interprogck8(program, bits) != table[row]:
                bad += 1
        assert bad == 512, "stream-order inputs must break the permuted build"

    def test_open_depths_price_one_residue_each(self) -> None:
        """Each open depth owns one odd residue of fifteen.

        Dense n=6 holds six distinct stride-30 launch residues against
        the fifteen odd residues mod 30, leaving nine free -- the pool
        exhausts at depth fifteen, which is the shipped class boundary,
        not a fitted constant. Four executed rows keep it honest.
        """
        table = _dense_table(6)
        program = interprogck8(table)
        lines, flights = _assemble(table, 6)
        _validate(lines, flights)
        residues = {launch % 30 for launch, stride, _ in flights if stride == 30}
        assert len(residues) == 6, "one channel per open depth"
        assert 15 - len(residues) == 9, "nine of fifteen odd residues free"
        for row in (0, 1, 62, 63):
            bits = list(bin(row)[2:].zfill(6))
            assert run_interprogck8(program, bits) == table[row], f"row {row}"

    def test_every_flight_dismounts_on_its_own_stop(self) -> None:
        """The corridor property, pinned on the assembled artifact.

        :func:`_validate` walks each recorded flight over the emitted
        lines exactly as ``DownAccLines`` flies it; parity at n=5 has
        flights crossing whole subtrees and they all land.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(32))
        lines, flights = _assemble(table, 5)
        assert flights, "a routed tree records its flights"
        _validate(lines, flights)


class TestModelFacts:
    """Two facts a corridor construction past depth 14 has to get past.

    Both are the reason no O(T) hand-built alternative shipped in
    ``docs/roadmap.md``'s Interprogck8 bullet: the accumulator cannot carry
    a jump distance past 255, and a residue shared for transit collides
    with a nested landing marker on the same residue.
    """

    def test_a_spelled_distance_past_255_wraps(self) -> None:
        """``NnNn`` + 26 ``@id`` + 1 ``@nd`` spells 261, but acc is mod 256.

        The jump lands ``(261 % 256) = 5`` lines past ``DownAccLines``, not
        261: the marker at the wrapped offset prints, the one at the
        intended offset does not.
        """
        spell = ["NnNn", *(["@id"] * 26), "@nd"]
        lines = [*spell, "DownAccLines"]
        wrapped_target = len(lines) + 1 + 5  # (26*10 + 1) % 256 == 5
        intended_target = len(lines) + 261
        program_lines = lines + ["x"] * (intended_target + 2 - len(lines))
        program_lines[wrapped_target] = "nNnN"  # loads 65 ('A')
        program_lines[wrapped_target + 1] = "div"
        program_lines[intended_target] = "NnNn"  # loads 0
        program_lines[intended_target + 1] = "div"  # would print NUL
        machine = _Machine(program_lines, ScriptedIO(""))
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue()[:1] == "A", (
            "the acc-mod-256 wrap, not the spelled 261"
        )

    def test_a_shared_transit_residue_collides_with_a_nested_marker(self) -> None:
        """An outer flight stops at an inner node's own landing marker.

        Reserving one residue mod 30 for every level's transit (removing
        the per-depth-band residue growth) makes a longer flight land on
        whichever nested node's marker sits on that residue first, not its
        own target: this two-hop flight (should reach +60) stops at the
        marker planted at +30.
        """
        launch = 5  # odd, so an unoccupied default line acts as DownAccLines
        lines = ["x"] * 100
        lines[0], lines[1], lines[2] = "u", "@dd", "@dd"  # acc = 28 or 29
        lines[launch] = "DownAccLines"
        inner_marker = launch + 30  # a nested node's own (unrelated) stop
        lines[inner_marker], lines[inner_marker + 1] = "NnNn", "div"
        true_target = launch + 60  # the outer flight's real destination
        lines[true_target], lines[true_target + 1] = "nNnN", "div"
        machine = _Machine(lines, ScriptedIO("1\n"))  # '1' -> acc=29, the flying arm
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue()[:1] == "\x00", (
            "stopped on the inner marker, not the target"
        )

    def test_even_launches_do_not_add_a_second_shared_residue(self) -> None:
        """A mixed-parity channel still stops at a nested marker.

        Giving a stride-30 flight an even launch (the unused parity in the
        shipped corridor) does not distinguish it from an odd launch: both
        visit the same residue progression.  The marker at ``+30`` catches
        the flight intended for ``+60`` and prints NUL instead of ``A``.
        """
        lines = ["x"] * 80
        lines[0:3] = ["u", "@dd", "@dd"]  # input 1 leaves acc = 29
        launch = 8  # even, unlike the shipped corridor's odd launches
        lines[launch] = "DownAccLines"
        lines[launch + 30 : launch + 32] = ["NnNn", "div"]
        lines[launch + 60 : launch + 62] = ["nNnN", "div"]
        machine = _Machine(lines, ScriptedIO("1\n"))
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue()[:1] == "\x00"


def _leaf(bit: int) -> list[str]:
    """Print one digit: load 0, then decimal-spell it up and print."""
    digit = 48 + bit
    tens, ones = divmod(digit, 10)
    return ["NnNn", *(["@id"] * tens), *(["@nd"] * ones), "div"]


def _one_level_slot_tree(table: str) -> list[str]:
    """One read, branching on the function slot instead of ``DownAccLines``.

    ``<...>`` captures a body and jumps past it for free, with no
    accumulator distance at all -- the 0-subtree is captured, skipped,
    then conditionally ``EXE``'d by ``IFQ``; the 1-subtree is captured
    the same way afterward and conditionally run by ``IFT``.
    """
    d48 = _dice(48)
    return [
        "<",
        *_leaf(int(table[0])),
        ">",
        "u",
        f"{{values/=/={d48}/={d48}}}",
        "IFQ",
        "<",
        *_leaf(int(table[1])),
        ">",
        "IFT",
    ]


def _staged_two_bit_reader() -> list[str]:
    """Capture one reader per first-bit arm, then read a second bit.

    The two bodies leave distinct accumulator ranges: body 0 returns 48/49,
    while body 1 adds ten and returns 58/59.  This is a positive probe for
    persistent slot state, not a generator route: a third stage would need a
    fresh capture inside each arm, which the interpreter refuses to nest.
    """
    return [
        "u",
        *("@dd" for _ in range(4)),
        *("@nt" for _ in range(8)),
        "DownAccLines",
        "@id",
        "DownAccLines",
        "x",
        "<",
        "u",
        "@id",
        ">",
        "EXE",
        "div",
        "DownAccLines",
        "x",
        "x",
        "x",
        "<",
        "u",
        ">",
        "EXE",
        "div",
        *("x" for _ in range(53)),
    ]


class TestPrimitiveSurvey:
    """Round-3's primitive-by-primitive check for a branch past ``acc``.

    Every primitive that moves control or holds state, executed: acc and
    ``DownAccLines`` (8-bit, capped at 255, see ``TestModelFacts``);
    ``{values...}`` (writes only 81/84, never more of a jump target);
    bare ``$py``/``u`` (assigns acc with no ``% 256``, unbounded, but only
    from a stdin read -- not from anything the build controls); ``z``
    (restarts to line 0, not a data-dependent target); and the function
    slot, below.
    """

    def test_values_only_ever_writes_the_two_verdicts(self) -> None:
        """``{values...}`` cannot carry a target past 8 bits.

        Comparing acc (0) against two distinct 300+-pip literals is
        forced unequal, so the only reachable outputs are 81 (Q) or 84
        (T) -- never the literals' own magnitude.
        """
        program = ["NnNn", "{values/=/=" + "." * 300 + "/=" + "." * 301 + "}", "$ay"]
        machine = _Machine(program, ScriptedIO(""))
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue() == _dice(84)

    def test_bare_py_sets_acc_with_no_wrap_but_needs_a_read(self) -> None:
        """Bare ``$py``/``u`` skip the ``% 256`` every arithmetic op has.

        Feeding a 300-pip literal and jumping lands 300 lines on, not 44
        (``300 % 256``) -- unbounded, but only by consuming an extra
        stdin read outside the n-bit convention, so it cannot encode a
        build-fixed jump distance.
        """
        lines = ["$py", "DownAccLines"] + ["x"] * 400
        lines[2 + 44], lines[2 + 44 + 1] = "nNnN", "div"  # wrapped landing
        lines[2 + 300], lines[2 + 300 + 1] = "NnNn", "div"  # true landing
        machine = _Machine(lines, ScriptedIO("." * 300 + "\n"))
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue()[:1] == "\x00", "lands at +300, not the wrapped +44"

    def test_z_restart_drops_the_selected_slot_and_accumulator(self) -> None:
        """``z`` cannot carry either direct control state across its restart.

        It can be reached conditionally and its deletion changes the text,
        but the new run starts with neither the captured continuation nor
        the accumulator value that selected it.  Any use as a relay must
        recover state from the altered text.
        """
        program = ["<", "nNnN", "div", ">", "nNnN", "z", "EXE"]
        machine = _Machine(program, ScriptedIO(""))
        machine.step()  # capture the printer
        machine.step()  # load 65
        machine.step()  # delete that load and z, then restart
        assert machine.state.acc == 0
        assert machine.state.slot is None
        assert machine.state.lines == ("<", "nNnN", "div", ">", "EXE")

    @pytest.mark.parametrize(("bit", "survivor"), [("0", "nNnN"), ("1", "NnNn")])
    def test_z_can_retain_a_branch_in_its_remaining_text(
        self, bit: str, survivor: str
    ) -> None:
        """A selected ``z`` leaves one distinguishable marker behind.

        This is why dropping acc and the slot is not a normal form: a
        restart can retain the branch in the program itself.  A language
        lower bound must account for that deletion state.
        """
        d48 = _dice(48)
        program = [
            "u",
            f"{{values/=/={d48}/={d48}}}",
            "DownAccLines",
            *(["x"] * 80),
            "NnNn",
            "z",
            "x",
            "nNnN",
            "z",
        ]
        machine = _Machine(program, ScriptedIO(f"{bit}\n"))
        for _ in range(4):
            machine.step()
        assert machine.state.acc == 0
        assert machine.state.slot is None
        assert survivor in machine.state.lines
        assert ({"NnNn", "nNnN"} - {survivor}).isdisjoint(machine.state.lines)

    def test_z_deletion_channel_holds_exactly_one_bit(self) -> None:
        """A conditional ``z`` restart persists exactly two states.

        Both first-bit branches restart with acc 0 and an empty slot;
        the full post-restart texts differ only in which adjacent marker
        survives -- one bit, worth at most one extra residue level past
        the corridor pool, not an escape from it.
        """
        d48 = _dice(48)
        states = set()
        for bit in ("0", "1"):
            program = [
                "u",
                f"{{values/=/={d48}/={d48}}}",
                "DownAccLines",
                *("x" for _ in range(80)),
                "NnNn",
                "z",
                "x",
                "nNnN",
                "z",
            ]
            machine = _Machine(program, ScriptedIO(f"{bit}\n"))
            for _ in range(4):
                machine.step()
            assert machine.state.acc == 0
            assert machine.state.slot is None
            states.add(tuple(machine.state.lines))
        assert len(states) == 2, "the deletion channel is one bit"

    def test_z_branch_cannot_retire_a_read_for_a_nested_pass(self) -> None:
        """The smallest two-pass recorder leaves its first ``u`` live.

        The two conditional targets delete different marker pairs, then
        restart.  The read at line zero is untouched, so the second pass
        consumes the next bit at the same read instead of advancing to a
        nested conditional.  Its fixed jump then lands at the shifted EOF.
        """
        d48 = _dice(48)
        program = [
            "u",
            f"{{values/=/={d48}/={d48}}}",
            "DownAccLines",
            *("x" for _ in range(81)),
            "NnNn",
            "z",
            "x",
            "nNnN",
            "z",
        ]
        io = ScriptedIO("0\n1\n")
        machine = _Machine(program, io)
        for _ in range(5):  # u, compare, jump, marker, z/restart
            machine.step()
        assert io.position() == 1
        assert machine.state.lines[0] == "u"
        run_until_halt_or_cycle(machine)
        assert io.position() == 2
        assert machine.halted
        assert io.getvalue() == ""

    def test_z_restart_recaptures_a_reader_but_loses_prior_bit(self) -> None:
        """Alternating slot ownership across ``z`` cannot retain old state.

        The first pass captures and executes ``u`` for the first bit, then
        ``z`` restarts after deleting its own marker.  The second pass
        recaptures the same reader and prints the second bit; all four rows
        execute, but the first bit has vanished from the result.
        """
        program = ["<", "u", ">", "EXE", "z", "x", ">", "EXE", "div"]
        for first in "01":
            for second in "01":
                machine = _Machine(program, ScriptedIO(f"{first}\n{second}\n"))
                run_until_halt_or_cycle(machine)
                assert machine.io.getvalue() == second, f"row={first}{second}"

    def test_the_function_slot_branches_with_no_jump_distance(self) -> None:
        """One read, routed by ``EXE``/``IFT``/``IFQ`` alone: all 4 rows.

        No ``DownAccLines`` appears in this program at all -- the capture
        does the skipping, for free, regardless of the skipped body's
        size (``test_the_slot_skips_past_255_lines_uncapped``).
        """
        for table in ("01", "10", "00", "11"):
            program = _one_level_slot_tree(table)
            assert "DownAccLines" not in program
            for bit in "01":
                machine = _Machine(program, ScriptedIO(f"{bit}\n"))
                run_until_halt_or_cycle(machine)
                assert machine.io.getvalue() == table[int(bit)], (
                    f"table={table} bit={bit}"
                )

    def test_staged_slot_carries_one_bit_through_a_second_read(self) -> None:
        """Two staged captures preserve the first bit across the second read."""
        program = _staged_two_bit_reader()
        for first in "01":
            for second in "01":
                machine = _Machine(program, ScriptedIO(f"{first}\n{second}\n"))
                run_until_halt_or_cycle(machine)
                expected = chr(48 + int(second) + 10 * int(first))
                assert machine.io.getvalue() == expected, f"row={first}{second}"

    def test_the_slot_skips_past_255_lines_uncapped(self) -> None:
        """A captured body of 400 lines is skipped in one step, no relay.

        ``_capture``'s scan is a text search for ``>``, not accumulator
        arithmetic, so it has none of ``DownAccLines``'s 255-line cap.
        """
        program = ["<", *(["x"] * 400), ">", "nNnN", "div"]
        machine = _Machine(program, ScriptedIO(""))
        run_until_halt_or_cycle(machine)
        assert machine.io.getvalue() == "A"

    def test_the_slot_cannot_nest_a_second_level(self) -> None:
        """The one-level trick does not compose to a depth-2 tree.

        Capturing a subtree that itself contains ``<`` -- needed for a
        second read -- is refused at the capture scan, unconditionally:
        the function slot cannot recurse, so it cannot build an n>1 tree
        by itself.
        """
        left, right = _one_level_slot_tree("0110"[:2]), _one_level_slot_tree("0110"[2:])
        d48 = _dice(48)
        program = [
            "<",
            *left,
            ">",
            "u",
            f"{{values/=/={d48}/={d48}}}",
            "IFQ",
            "<",
            *right,
            ">",
            "IFT",
        ]
        machine = _Machine(program, ScriptedIO("0\n0\n"))
        with pytest.raises(HaltError, match="nested function opener"):
            run_until_halt_or_cycle(machine)
