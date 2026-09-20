"""The drive-state graph: what it enumerates, and that stepping agrees."""

from pathlib import Path
from unittest.mock import patch

import pytest

from esolangs.interpreters.grid_based.streetcode import (
    _NO_LATCHES,
    _Car,
    _drive,
    _Grid,
    _Latches,
    _Machine,
    _Merge,
    _plus_dist,
    _State,
)
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.vm import _StepMachine, run_until_halt_or_cycle
from tests.interpreters.streetcode_support import _RING_PROGRAM


class TestStreetcodeStepMachine:
    def test_step_tracks_position_and_heading(self) -> None:
        machine = _Machine(["CIO;"], ScriptedIO("Z"))
        # A single row: wall South (out of bounds) and open East at 'C'
        # resolves the initial heading straight to East, no dead end.
        assert (machine.row, machine.col, machine.heading) == (0, 0, "E")
        machine.step()  # 'C' is a nop; drives onto 'I'
        assert (machine.row, machine.col) == (0, 1)

    def test_snapshot_includes_input_cursor(self) -> None:
        machine = _Machine(["CIO;"], ScriptedIO("A"))
        before = machine.snapshot()
        machine.step()  # 'C'
        machine.step()  # 'I' consumes the input line
        after = machine.snapshot()
        assert before != after
        assert machine.io.position() == 1

    def test_the_machine_satisfies_the_vm_step_protocol(self) -> None:
        """``run_until_halt_or_cycle`` steps this, so it must conform.

        ``_StepMachine`` is ``runtime_checkable``, so the structural
        check is the contract itself rather than a restatement of it.
        """
        assert isinstance(_Machine(["C;"], IO()), _StepMachine)

    def test_snapshot_separates_every_state_the_machine_carries(self) -> None:
        """No two distinct states may share a snapshot, and it must hash.

        The hang detector's verdict is only sound if a repeat is a real
        repeat: two states that differ anywhere must differ here, or a
        program that is still making progress looks like a proven cycle.
        The state is one :class:`_State` record beside the tape, CP, I/O
        and halted flag, so this walks every field of it -- including
        each latch separately, which a snapshot that dropped the record
        or flattened it carelessly would be the way to get wrong.
        """
        code = ["+----+", "|C  ;|", "|    |", "+----+"]
        merge = _Merge(1, 1, "left", "S", crossing=False)
        # The fixture starts heading South, so "N" and "W" are both real
        # changes; using "S" here would silently retest the base state.
        latch_sets = [
            _NO_LATCHES._replace(merge=merge),
            _NO_LATCHES._replace(merging_heading="N"),
            _NO_LATCHES._replace(skip_hug=3),
        ]
        states = [
            _State(1, 1, "S", _NO_LATCHES),  # the machine's own start
            _State(2, 1, "S", _NO_LATCHES),
            _State(1, 2, "S", _NO_LATCHES),
            _State(1, 1, "N", _NO_LATCHES),
            _State(1, 1, "W", _NO_LATCHES),
            *[_State(1, 1, "S", latches) for latches in latch_sets],
        ]

        snapshots = []
        for state in states:
            machine = _Machine(code, IO())
            machine._state = state  # noqa: SLF001
            snapshots.append(machine.snapshot())
        # ...and the three fields that are not part of the drive state.
        for mutate in (
            lambda m: setattr(m, "cp", 5),
            lambda m: m.cells.__setitem__(0, 9),
            lambda m: setattr(m, "_done", True),
        ):
            machine = _Machine(code, IO())
            mutate(machine)
            snapshots.append(machine.snapshot())

        assert len(set(snapshots)) == len(snapshots)
        assert all(hash(s) is not None for s in snapshots)

    def test_halting_program_is_detected_as_halted(self) -> None:
        assert run_until_halt_or_cycle(_Machine(["C;"], IO())) is True

    def test_step_on_an_already_halted_machine_is_a_no_op(self) -> None:
        machine = _Machine(["C;"], IO())
        machine.step()  # 'C', moves onto ';'
        machine.step()  # ';' halts
        assert machine.halted
        before = machine.snapshot()
        machine.step()  # calling step() again must not raise or move further
        assert machine.snapshot() == before


class TestStreetcodeDriveStates:
    """The drive-state graph (``_drive_states``) and its two uses.

    The graph is the movement half of ``snapshot`` enumerated over the
    whole grid, built by driving the real helpers.  It backs the
    construction-time totality check and ``step`` itself, and in tests it
    pins the mouth-depth bound to the behaviour it produces rather than
    to the cells it scans.
    """

    def _corridor(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_every_state_has_a_successor(self) -> None:
        """A validated street is total: no reachable state wedges the car."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        # ``None`` means only "ran out of road" now -- a deliberate stop at
        # ``;`` reports itself as ``"halt"`` -- so a wedge needs no check
        # against the square underneath.
        wedged = [
            state
            for state, edges in graph.items()
            if any(succ is None for succ in edges.values())
        ]
        assert wedged == []

    def test_exploring_leaves_the_machine_untouched(self) -> None:
        """``_drive_states`` drives the live machine, so it must restore it."""
        machine = _Machine(self._corridor(), IO())
        before = machine.snapshot()
        machine._drive_states((1, 1))  # noqa: SLF001
        assert machine.snapshot() == before

    def test_each_state_is_keyed_by_both_branch_bits(self) -> None:
        """Both tape reads a step can make are probed, so all four pairs."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        assert graph
        for edges in graph.values():
            assert set(edges) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    def test_a_wedging_phase_is_rejected_at_construction(self) -> None:
        """The check fires when the movement rules do run out of road.

        Ordinary wall-following cannot wedge on a validated street (see
        ``_validate_total``), so the state this rejects is reached by
        breaking a phase rather than by drawing one: the check is a
        regression net over the phases, and this is what tripping it
        looks like.

        The phase is patched through the imported module object rather
        than by its dotted string path: ``scripts/mutate_one.py`` bundles
        the interpreter into a single module to mutate it, and a string
        target naming the package still resolves to the *unbundled*
        interpreter there, so the patch lands on a function the bundled
        machine never calls and the wedge never happens.  Patching the
        module object works either way, because the bundler rewrites the
        import that produced it.
        """
        from esolangs.interpreters.grid_based import _streetcode_geometry as module

        with (
            patch.object(
                module,
                "_heading_from_hug",
                lambda _grid, _car, latches: (None, latches),
            ),
            pytest.raises(ValueError, match="cannot drive out of"),
        ):
            _Machine(self._corridor(), IO())

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/streetcode.txt"],
    )
    def test_mouth_depth_bound_does_not_change_the_driving(self, path: str) -> None:
        """``_MOUTH_MAX_DEPTH`` is pinned by behaviour, not by its scans.

        The bound is two-sided -- raising it makes the scan run past the
        box it is reading and pair up two ``+`` that bound nothing, which
        is what happens in the 1-arity boolean programs -- so the check
        that matters is not "the same mouths are found" but "the car
        drives the same way".  Comparing the whole drive-state graph at
        the shipped bound against a generous one says exactly that.
        """
        from esolangs.interpreters.grid_based import _streetcode_geometry as module

        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        machine = _Machine(code, IO())
        start = (machine.row, machine.col)
        shipped = machine._drive_states(start)  # noqa: SLF001

        original = module._MOUTH_MAX_DEPTH  # noqa: SLF001
        module._MOUTH_MAX_DEPTH = machine.grid.height + machine.grid.width  # noqa: SLF001
        try:
            generous = machine._drive_states(start)  # noqa: SLF001
        finally:
            module._MOUTH_MAX_DEPTH = original  # noqa: SLF001
        assert shipped == generous


class TestStreetcodeDriveInvariants:
    """What holds of a drive state under every reading of the spec.

    The geometry rules are reverse-engineered and several remain
    judgement calls; these are not.  A car inside a wall, or one that
    teleports rather than driving a cell at a time, is wrong however the
    spec is read, so ``_check_state_invariants`` asserts them over the
    whole drive-state graph at construction.  Each test drives the
    checker with a state the enumeration cannot currently produce --
    that is the point, since a reachable breach would be a live bug.
    """

    def _machine(self) -> _Machine:
        """The grid from ``701de45``, whose lower room the car drove into."""
        return _Machine(
            [
                "+---------+",
                "|         |",
                "|C^      ;|",
                "+--+  ++--+",
                "   |      |",
                "   |;     |",
                "   +------+",
            ],
            IO(),
        )

    def test_a_car_inside_a_wall_is_caught(self) -> None:
        """The regression from ``701de45``, as a construction-time failure.

        A junction fired while its gap still opened a cell ahead, and the
        turn drove the car inside the wall the mouth opens through --
        ``(3, 2)`` on this very grid, which is the ``-`` of the lower
        room's top wall.  That was found by hand-drawing a program and
        watching the car misbehave; the invariant names the square.
        """
        machine = self._machine()
        assert not machine.grid.open_at(3, 2)
        with pytest.raises(AssertionError, match="not open floor"):
            machine._check_state_invariants(  # noqa: SLF001
                _State(3, 2, "S", _NO_LATCHES), {}
            )

    def test_a_teleporting_step_is_caught(self) -> None:
        """A successor two cells away is the car skipping a square."""
        machine = self._machine()
        state = _State(2, 1, "E", _NO_LATCHES)
        edges = {(0, 0): _State(2, 3, "E", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="not one orthogonal step"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_step_into_a_wall_is_caught(self) -> None:
        """A successor on a wall cell, one step away or not."""
        machine = self._machine()
        state = _State(2, 2, "S", _NO_LATCHES)
        edges = {(0, 0): _State(3, 2, "S", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="which is not open"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_merge_target_off_the_travel_axis_is_caught(self) -> None:
        """The approach holds its lane, so the target is straight ahead."""
        machine = self._machine()
        # Heading East from (2, 1), so the axis is row 2; row 1 is beside it.
        merge = _Merge(1, 4, "right", "E", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="off the axis"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_merge_target_behind_the_car_is_caught(self) -> None:
        """The car drives forwards onto the target; it cannot reverse to it."""
        machine = self._machine()
        merge = _Merge(2, 1, "right", "E", crossing=False)
        state = _State(2, 3, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="behind it"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_stale_latch_is_not_checked(self) -> None:
        """A latch the next step abandons describes no geometry.

        Once the heading no longer matches the one the latch was taken
        under, ``_heading_from_merge_target`` drops it; its target is
        stale by construction, and holding it to the axis rule would
        reject states the enumeration really does reach (1,116 of them
        across the example and generated programs).
        """
        machine = self._machine()
        # Off-axis and behind -- but latched under a heading the state no
        # longer holds, so neither rule applies.
        merge = _Merge(5, 4, "right", "S", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_every_shipped_program_satisfies_them(self) -> None:
        """The invariants hold over every program the repo ships.

        Construction runs the check, so this passing means the whole
        drive-state graph of each example is clean -- not just the paths
        a particular input drives.
        """
        root = Path(__file__).resolve().parents[2]
        paths = sorted((root / "examples").glob("**/streetcode.txt"))
        # A relative glob silently matches nothing from another working
        # directory, which would leave this passing over no programs at all.
        assert paths
        for path in paths:
            _Machine(path.read_text().split("\n"), IO())


class TestStreetcodeGraphBackedStepping:
    """Graph-backed stepping must agree with the movement rules exactly.

    ``step`` looks the next state up in the graph enumerated at
    construction, falling back to calling the phases when there is no
    graph or the state is outside it.  Those two paths are two ways of
    computing the same thing, so the test that matters is that they
    never disagree: drive both in lockstep and compare the whole
    ``snapshot`` after every step.
    """

    def _lockstep(self, code: list[str], stdin: str = "", limit: int = 20000) -> int:
        """Run one machine on the graph and one on the phases, in step."""
        fast = _Machine(code, ScriptedIO(stdin))
        slow = _Machine(code, ScriptedIO(stdin))
        # Emptying the graph forces every step down the fallback path.
        slow._graph = None  # noqa: SLF001
        assert fast._graph is not None, "the fixture needs a validated street"  # noqa: SLF001

        steps = 0
        for steps in range(1, limit + 1):
            fast_error = slow_error = None
            try:
                fast.step()
            except Exception as exc:
                fast_error = type(exc).__name__
            try:
                slow.step()
            except Exception as exc:
                slow_error = type(exc).__name__
            assert fast_error == slow_error, (
                f"step {steps}: {fast_error} vs {slow_error}"
            )
            assert fast.snapshot() == slow.snapshot(), f"diverged at step {steps}"
            if fast.halted or fast_error:
                break
        return steps

    def test_a_plain_corridor_agrees(self) -> None:
        assert self._lockstep(["+----+", "|C^O;|", "|    |", "+----+"]) > 1

    def test_a_junction_agrees(self) -> None:
        """The early-sighted mouth fixture, which defers a turn to the gap."""
        code = [
            "+---------+",
            "|         |",
            "|C^      ;|",
            "+--+  ++--+",
            "   |      |",
            "   |;     |",
            "   +------+",
        ]
        assert self._lockstep(code) > 1

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/streetcode.txt"],
    )
    def test_the_shipped_examples_agree(self, path: str) -> None:
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        assert self._lockstep(code, stdin="1\n") > 1

    def test_a_ring_program_agrees(self) -> None:
        """The ring program latches a merge, so it drives the latch path."""
        assert self._lockstep(_RING_PROGRAM) > 1

    def test_an_off_graph_state_falls_back(self) -> None:
        """A state the search never reached still drives, via the phases.

        Setting the heading by hand is how the interpreter's own tests
        reach such a state; the graph has no entry for it, and ``step``
        must not fail looking for one.
        """
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(
            machine.row,
            machine.col,
            "N",
            _NO_LATCHES._replace(merging_heading="N"),
        )
        machine._state = state  # noqa: SLF001
        assert state not in machine._graph  # noqa: SLF001
        machine.step()
        assert not machine.halted

    def test_a_halt_edge_stops_the_car(self) -> None:
        """A ``"halt"`` edge stops the car rather than driving it nowhere.

        Every edge without a successor in a real program sits on ``;``,
        and ``;`` halts before the lookup is reached, so this arm is the
        graph's own guard rather than a path a validated street takes.
        Blanking the ``;`` after construction leaves the recorded
        ``"halt"`` in place and lets the lookup answer for it.
        """
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(1, 4, "N", _NO_LATCHES)
        assert all(v == "halt" for v in machine._graph[state].values())  # noqa: SLF001

        machine.place(1, 4, "N")
        machine.grid[1] = list("|C   |")  # the ';' would halt one arm earlier
        machine.step()
        assert machine.halted

    def test_a_wedged_edge_raises_rather_than_halting(self) -> None:
        """A ``None`` edge is a validator bug, and must not pass for a stop.

        ``_validate_total`` rejects a street with a wedged state, so a
        ``None`` surviving into the lookup means the graph and the check
        disagree.  Halting on it would hand back a truncated run as though
        the program had finished; the two are told apart precisely so this
        can raise instead.  Only forging the edge reaches it.
        """
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(1, 1, "E", _NO_LATCHES)
        machine._graph[state] = dict.fromkeys(  # noqa: SLF001
            ((0, 0), (0, 1), (1, 0), (1, 1))
        )

        machine.place(1, 1, "E")
        with pytest.raises(AssertionError, match="outlived"):
            machine.step()
        assert not machine.halted

    def test_a_u_turn_without_an_opposite_lane_has_no_successor(self) -> None:
        """``U`` needs a lane to turn into; without one the state is a dead end.

        A one-row grid has nothing north or south of the ``U``, so heading
        East the reversed lane is off the grid.  ``step`` reports that as a
        width violation at run time; the search just declines to drive on.
        """
        grid = _Grid(["CU;"])
        assert _drive(grid, _State(0, 1, "E", _NO_LATCHES), 0, 0) is None
        assert _drive(grid, _State(0, 1, "W", _NO_LATCHES), 0, 0) is None
        # ...while a lane that is on the grid does produce a successor.
        assert _drive(grid, _State(0, 1, "N", _NO_LATCHES), 0, 0) is not None


class TestStreetcodeMutationSurvivors:
    """Four conditions a mutation survived, each pinned by behaviour.

    Mutation testing (mutmut against a ``bundle_one`` build of this module)
    reported these as changeable without any test noticing.  Two are the
    bounds of the isolated-cell exemption in :meth:`_Machine._validate_width`,
    one is the halt the shipped example reaches, and one is the ``+`` search
    the junction rules steer by.  Each was confirmed by loading the mutant
    and the original side by side and diffing their behaviour.
    """

    def test_a_single_walled_cell_is_not_a_street(self) -> None:
        """One reachable cell is exempt: there is no street to measure.

        The exemption reads ``len(visited) <= 1``.  A mutant that tightened
        it to ``< 1`` stopped exempting the one-cell case, and the wall
        check behind it then rejected a grid the interpreter accepts.
        """
        machine = _Machine(["+-+", "|C|", "+-+"], IO())
        assert (machine.row, machine.col) == (1, 1)

    def test_a_one_wide_corridor_is_still_rejected(self) -> None:
        """The exemption covers one cell, not two: a corridor is a street.

        A mutant that loosened the bound to ``len(visited) <= 2`` exempted
        this grid instead of measuring it, and a one-wide street -- which
        has no opposite lane for ``U`` to end in -- was accepted.
        """
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+-+", "|C|", "|U|", "+-+"], IO())

    def test_the_hello_world_example_halts(self) -> None:
        """The example halts, and in a bounded number of steps.

        Asserting only on the output leaves the halt untested: a mutant of
        ``step`` printed ``Hello, World!`` in full and then drove on for
        ever, parked on one cell.  The step count pins the termination the
        output alone does not.
        """
        root = Path(__file__).resolve().parents[2]
        code = (root / "tests/fixtures/streetcode_hello.txt").read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        scripted = ScriptedIO("")
        machine = _Machine(code, scripted)
        steps = 0
        # 426 is the real count; the cap is headroom, and a tight one keeps
        # a mutant that stops the example halting cheap to reject.
        while not machine.halted and steps < 1000:
            machine.step()
            steps += 1
        assert machine.halted
        assert steps == 426
        assert scripted.getvalue() == "Hello, World!"

    def test_plus_dist_measures_the_nearest_plus_on_a_side(self) -> None:
        """The scan reports the distance, and ``None`` when there is no ``+``.

        ``_crossing_mouth`` reads this to find the two ``+`` bounding a
        mouth, so a mutant that always returned ``None`` unpacked nothing
        and crashed both shipped examples.  Pinning one hit and the misses
        keeps the search itself under test.
        """
        root = Path(__file__).resolve().parents[2]
        code = (root / "tests/fixtures/streetcode_hello.txt").read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        machine = _Machine(code, IO())
        assert (machine.row, machine.col) == (5, 3)
        car = _Car(machine.row, machine.col, machine.heading)
        assert _plus_dist(machine.grid, car, "S") == 1
        assert _plus_dist(machine.grid, car, "N") is None
        assert _plus_dist(machine.grid, car, "E") is None
        assert _plus_dist(machine.grid, car, "W") is None
