"""Covers :mod:`esolangs.tools.minifuck_sim` against the interpreter."""

from unittest.mock import patch

from tests.tools.minifuck_support import _MinifuckCase


class TestMinifuckSim(_MinifuckCase):
    """The simulator against the interpreter it stands in for."""

    def test_the_simulator_mirrors_the_interpreter_at_its_edges(self) -> None:
        """The search's model of a row has to match what Minifuck does.

        The search prunes on simulated state, so a divergence here would
        make it reason about tapes the interpreter never produces.  The
        edges are the ones a mid-tape step never shows: a dead row ignores
        everything after it, a spent skip eats one instruction, ``<`` is
        pinned at cell 0, the tape grows on demand, and a print reads the
        first eight cells as one byte -- emitting that character, or
        killing the row if the byte is zero.
        """
        from esolangs.tools.minifuck import _Sim

        dead = _Sim(16)
        dead.dead = True
        dead.exec("[")
        assert dead.ptr == 0, "a dead row executes nothing"

        skipping = _Sim(16)
        skipping.skip = True
        skipping.exec("[")
        assert skipping.ptr == 0, "the skipped instruction does nothing"
        assert not skipping.skip, "and the skip is spent"

        pinned = _Sim(16)
        pinned.exec("<")
        assert pinned.ptr == 0, "there is nothing to the left of cell 0"

        growing = _Sim(3)
        for _ in range(5):
            growing.exec("[")
        assert growing.length > 3, "the tape grows to meet the pointer"

        # The print flips the cell it steps onto first, so a print inside
        # the byte writes its own 1: cell 1 makes 0b01000000 == 64.
        printing = _Sim(16)
        printing.exec(".")
        assert printing.out == ["@"]
        assert not printing.dead

        # Past cell 8 the flip lands outside the byte, which stays zero.
        zero = _Sim(16)
        zero.ptr = 9
        zero.exec(".")
        assert zero.dead, "printing a zero byte ends the row"
        assert zero.out == []

    def test_the_simulator_agrees_with_a_real_run_on_random_streams(self) -> None:
        """``_Sim`` and a whole-program run agree, instruction for instruction.

        The edges above are hand-picked; this is the same claim made over
        random programs, which is what would catch a divergence nobody
        thought to write a case for.  ``_Sim`` advances by its own closed-
        form laws -- that is the point of the module, the build path no
        longer drives the interpreter -- so the two *can* disagree now, and
        this comparison against a real ``run`` is one of the two tests that
        would say so (the other pins each law to ``_step`` from arbitrary
        states, below).

        Only live rows are compared cell by cell: once a row is ``dead`` the
        emitter stops tracking it by contract, while a real run keeps going,
        so past that point only the output and the death itself are shared.
        """
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import run
        from esolangs.tools.minifuck import _Sim

        rng = random.Random(20260902)
        printed = deaths = skips = 0

        for _ in range(300):
            stream = "".join(rng.choice("<[.x") for _ in range(rng.randrange(1, 40)))

            sim = _Sim(64)
            for ins in stream:
                sim.exec(ins)

            io_ = ScriptedIO("")
            try:
                run(stream, io_)
            except EOFError:
                # The whole-program run fetches input where the emitter
                # instead marks the row dead; that is the one divergence
                # the emitter's contract creates on purpose.
                assert sim.dead, (stream, "the emitter missed a read")
                deaths += 1
                continue

            assert not sim.dead, (stream, "the emitter killed a live row")
            assert "".join(sim.out) == io_.getvalue(), stream
            printed += len(sim.out)
            skips += sim.skip

        # The comparison is worthless if the interesting transitions never
        # fire, so assert the sample reached all three.
        assert printed, "no stream printed"
        assert deaths, "no stream hit the zero-pool read"
        assert skips, "no stream ended on a pending skip"

    def test_the_closed_form_runs_agree_with_stepping_them(self) -> None:
        """A whole run's law matches applying it one instruction at a time.

        ``run_left``, ``run_walk`` and ``run_brackets`` each claim a closed
        form over a run of ``k`` tokens; ``exec`` applies the same laws one
        token at a time.  The two spellings must compose to the same state
        -- the staircase inverse and the prefix-XOR doubling are exactly the
        parts a per-token application does not share -- and the
        disagreement this invites is not hypothetical: a first ``run_walk``
        that ignored the cascade a ``[`` fires when its flip lands on zero
        matched on the easy states and diverged on 877 of 3000 random ones.

        So the comparison is made from *arbitrary* states, not fresh ones --
        a fresh row has a zero tape and no pending skip, which is exactly
        where a wrong model still looks right.
        """
        import random

        from esolangs.tools.minifuck import _Sim

        rng = random.Random(20260906)
        skips = walks_cascaded = clamped = 0

        for _ in range(400):
            start = _Sim(96)
            for _ in range(rng.randrange(0, 25)):
                start.exec(rng.choice("<[.x"))
            count = rng.randrange(0, 12)

            for token, closed in (
                ("<", "run_left"),
                ("[x", "run_walk"),
                ("[", "run_brackets"),
            ):
                stepped = start.copy()
                for ins in token * count:
                    stepped.exec(ins)

                direct = start.copy()
                getattr(direct, closed)(count)

                assert direct.key() == stepped.key(), (
                    token,
                    count,
                    start.key(),
                    "the closed form left a different state",
                )

            if start.skip:
                skips += 1
            if start.ptr and count:
                clamped += 1
            probe = start.copy()
            probe.run_walk(count)
            if probe.tape != start.tape:
                walks_cascaded += 1

        # A sweep that never reaches the interesting states proves nothing:
        # the pending skip is what makes the run's first instruction special,
        # and a walk that never wrote a cell never exercised the cascade.
        assert skips, "no state carried a pending skip"
        assert clamped, "no clamp started away from cell 0"
        assert walks_cascaded, "no walk touched the tape"

    def test_the_parsed_emission_matches_stepping_every_row(self) -> None:
        """``_Joint.emit`` parses a code once and advances rows by whole runs.

        The parse and the per-run laws have to compose to exactly what
        applying the laws one character at a time does -- the run boundaries
        and the skip handed from one run to the next are where a parse bug
        would live.  Synthetic codes do not reach the states this has to get
        right: random emissions leave the rows' pointers converged, and it
        is precisely the *divergent* pointers the real construction creates
        that make an emission's effect differ row by row.  So the generator
        itself drives the comparison, with every emission checked both ways
        as it happens.
        """
        from esolangs.tools import minifuck_sim
        from esolangs.tools.minifuck import minifuck

        real_emit = minifuck_sim._Joint.emit  # noqa: SLF001
        checked = [0]

        def checking_emit(self: object, code: str) -> None:
            rows = self.ms  # type: ignore[attr-defined]
            reference = [m.copy() for m in rows]
            real_emit(self, code)
            for row in reference:
                for ch in code:
                    row.exec(ch)
            assert [m.key() for m in rows] == [m.key() for m in reference], (
                f"the parsed emission of {code!r} diverged from stepping it"
            )
            # What makes the comparison bite is rows whose pointers differ:
            # an emission's effect is row-dependent exactly there, and they
            # are the states the construction actually produces.
            if len({m.ptr for m in reference}) > 1:
                checked[0] += 1

        # ``minifuck`` and the pool searches under it are cached, so a table
        # an earlier test already built emits far less the second time.
        # Counting only the divergent-pointer emissions keeps the floor
        # meaningful without depending on which caches happen to be warm.
        minifuck.cache_clear()
        with patch.object(minifuck_sim._Joint, "emit", checking_emit):  # noqa: SLF001
            for table in ("01", "0110", "10010110"):
                minifuck(table)
        minifuck.cache_clear()

        assert checked[0], "no emission met rows whose pointers had diverged"
