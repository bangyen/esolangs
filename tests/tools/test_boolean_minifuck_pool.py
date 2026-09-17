"""Covers the pool half of :mod:`esolangs.tools.minifuck_pool`."""

import importlib
from unittest.mock import patch

import pytest

from tests.tools.minifuck_support import _MinifuckCase


class TestMinifuckPool(_MinifuckCase):
    """The pool codes, the rule that picks one, and the endgame printing through it."""

    def test_sculpt_pool_code_matches_scan(self) -> None:
        """The named sculpt code is what the replaced scan would have found.

        ``_mux_probe`` used to scan ``_POOL_CODES`` through ``_pool_reaches``
        -- a real interpreter probe, and the module's hot spot at five
        inputs.  It is now :data:`_SCULPT_POOL_CODE`, a constant, because the
        probe state is canonical: the ``x`` and the clamp put every row at
        pointer 0 with the same pool region, a sculpting round cannot write
        into that region under the rewind guard, and no pool code's own
        execution reaches past cell 6.

        This replays the scan on the states a sculpt actually reaches and
        asserts the constant answers exactly what it returned -- the same
        specification-oracle shape the other closed searches keep.  Both
        orientations are scanned at every recorded state from the retired
        emitted-loop oracle, always at ``cell7 == 0`` -- so
        "``cell7 == 1`` is answered by none" stays pinned as a measured
        fact rather than an assumption baked into the constant.
        """

        module = importlib.import_module("esolangs.tools.minifuck_mux")
        pool = importlib.import_module("esolangs.tools.minifuck_pool")

        seen: list[object] = []
        real = module._mux_probe  # noqa: SLF001

        def record(joint: object, acc: int, cell7: int, hint: object = None) -> object:
            if len(seen) < 60:
                probe = joint.fork()  # type: ignore[attr-defined]
                probe.emit("x")
                module._clamp(probe)  # noqa: SLF001
                seen.append(probe)
            return real(joint, acc, cell7, hint)

        base = module._mux_separate(4)  # noqa: SLF001
        acc = min(base.ptrs()) - 2
        with patch.object(module, "_mux_probe", record):
            assert (
                module._mux_sculpt(  # noqa: SLF001
                    base,
                    "0110100110010110",
                    4,
                    acc,
                    0,
                    direct=True,
                )
                is not None
            )
        assert seen, "no sculpting probes were observed"

        for probe in seen:
            for cell7 in (0, 1):
                scanned = next(
                    (
                        code
                        for code in pool._POOL_CODES  # noqa: SLF001
                        if pool._pool_reaches(  # noqa: SLF001
                            probe,
                            code,
                            cell7,
                            module._PROBE_WALK_OUT,  # noqa: SLF001
                        )
                    ),
                    None,
                )
                assert scanned == module._sculpt_pool_code(cell7), cell7  # noqa: SLF001

    def test_the_pool_codes_cover_every_route(self) -> None:
        """The fixed codes must serve every route that reaches the endgame.

        They replaced a breadth-first search, so the property that matters
        is coverage: wherever the search would have found a pool, the list
        must too.  This builds through the public entry point precisely
        because the routes differ -- the degenerate one reaches the endgame
        from states the mux never produces, and six of the ten codes answer
        only those.

        It deliberately does not assert that each code is necessary.
        Measured, none of them is: every one can be dropped alone and every
        table at both arities still builds.  That is not because the codes
        cover for each other -- six of them uniquely answer 40 of the 16766
        call sites -- but because a missing pool is *recoverable*:
        ``_endgame`` raises, ``_try_print`` counts it as one failed
        read/orientation, and another accumulator answers the table.  So
        coverage of the routes is the real property, and minimality is not
        one to pin.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        for table_int in range(16):
            table = format(table_int, "04b")
            assert module.minifuck.__wrapped__(table), table

    def test_the_pool_codes_are_generated_from_the_law(self) -> None:
        """The five codes are spelled by the law, not stored as strings.

        ``_POOL_CODES`` is built by walking ``_PLANS`` through :func:`_step`,
        which inverts the ``ceil(k / 2)`` law: a carry of ``c`` fixes the
        bracket run at ``2 * c - 1``, or ``2 * c`` where the pending skip is
        not wanted.  The five literals below are the anchor -- with the source
        deriving them, every number in the plans and in the step law is
        otherwise unpinned, and this one assertion is what makes a wrong
        carry, a wrong override, or a reordered plan fail.

        The plans are also checked for the property that makes them a
        construction rather than five parameter dumps: two of the five carry
        no override at all.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        # The anchor: the derivation must reproduce these exactly, in order.
        assert module._POOL_CODES == (  # noqa: SLF001
            "[[[<[<<<<",
            "[<[[[<[<[<",
            "[<[<[[[<[<[<",
            "[<<[<[<[[[<[<",
            "[<[<[<<[[[<[[<<<",
        )

        # The step law itself, away from the plans: a carry of c spells a run
        # of 2c-1 brackets, and dropping the skip spells the even run.
        step = module._step  # noqa: SLF001
        assert step() == "[<"  # the default: carry one, trail by one
        assert step(carry=2) == "[[[<"
        assert step(carry=1, odd=False) == "[[<"
        assert step(carry=1, backs=4) == "[<<<<"

        # Two of the five plans are (steps, core) and nothing else, which is
        # what "one construction indexed by where the mark goes" means.
        plans = module._PLANS  # noqa: SLF001
        assert len(plans) == len(module._POOL_CODES)  # noqa: SLF001
        bare = [(n, core) for n, core, over in plans if not over]
        assert bare == [(4, 1), (5, 2)], bare

        # Every plan has exactly one core, and it is inside the walk.
        for n, core, over in plans:
            assert 0 <= core < n, (n, core)
            assert all(0 <= i < n for i in over), (n, over)

    def test_the_pool_codes_are_one_construction(self) -> None:
        """Each pool code is a mark, shifted three cells by a shared core.

        The five read as unrelated strings -- edit distance 2 to 7, and an
        exact regex factors *longer* than it lists -- but that measures
        spelling.  Behaviourally every code is ``prefix + '[[[<[' + suffix``
        with the core appearing exactly once, and for three of the five the
        prefix plants a single 1 that the core then shifts three cells right.

        One law runs through it: a run of ``k`` brackets carries a mark right
        by ``ceil(k / 2)``, leaving a pending skip when ``k`` is odd.  The
        core opens with three brackets and so moves a mark +2; the suffixes
        that open with none only reposition the pointer, which is why two
        codes share the suffix ``'<[<'`` verbatim at different marks.

        The exception is the point: the walk is clean only when the pointer
        sits just left of the mark.  The code with an empty prefix has no
        mark to carry, and ``'[<[<[<<'`` arrives at cell 3 with the pointer
        at 1 rather than 2, so the core spreads marks instead of moving one.
        """

        from esolangs.tools.minifuck import _POOL_CODES, _Sim

        core = "[[[<["

        def run(code: str) -> object:
            machine = _Sim(64)
            for char in code:
                machine.exec(char)
            return machine

        # The law the whole family rests on: a run of k brackets carries a
        # mark right by ceil(k / 2).  Checked away from the codes first, so a
        # failure here says "the language changed" rather than "a code did".
        for start in (2, 3, 4, 5):
            for brackets in range(1, 9):
                machine = run("[<" * start + "[" * brackets)
                marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
                assert marks == [start + (brackets + 1) // 2], (start, brackets, marks)
                assert machine.skip is bool(brackets % 2), (start, brackets)  # type: ignore[attr-defined]

        shifted = 0
        for code in _POOL_CODES:
            # The decomposition itself holds for every code.
            assert code.count(core) == 1, code
            prefix = code[: code.find(core)]

            # The prefix plants at most one mark and writes nothing else.
            before = run(prefix)
            marks = [i for i in range(32) if before.cell(i)]  # type: ignore[attr-defined]
            assert len(marks) <= 1, (code, marks)

            # Where the prefix leaves the pointer on its mark, the core moves
            # that mark three cells right and takes the pointer with it.
            after = run(prefix + core)
            moved = [i for i in range(32) if after.cell(i)]  # type: ignore[attr-defined]
            if marks and before.ptr == marks[0] - 1:  # type: ignore[attr-defined]
                assert moved == [marks[0] + 3], (code, marks, moved)
                assert after.ptr == marks[0] + 2, (code, after.ptr)  # type: ignore[attr-defined]
                shifted += 1
        assert shifted == 3, shifted

        # And ``'[<' * n`` is what plants a mark at cell n -- the parameter.
        for n in range(1, 6):
            machine = run("[<" * n)
            marks = [i for i in range(32) if machine.cell(i)]  # type: ignore[attr-defined]
            assert marks == [n], (n, marks)

    @pytest.mark.slow
    def test_the_pool_rule_matches_the_scan_it_replaced(self) -> None:
        """``_find_pool`` answers what trying every code would have answered.

        The scan below *is* the specification: it is what ``_find_pool`` used
        to do -- walk the codes in order through the simulator and take the
        first that reaches the pool.  The shipped rule instead asks each row
        which code it names and checks the rows agree, so this pins the two
        together over the whole domain the rule claims, not over the states a
        build happens to visit.

        Both halves matter and each caught a real bug while landing.  The
        exhaustive half covers every single-row key; the random half builds
        *joints*, which is where the two cross-row conditions live -- rows must
        name the same code and be left on the same cell by it.  Independent
        random rows almost never collide in the low byte, so the joints are
        drawn by perturbing one window: with rows drawn independently the
        end-pointer split showed up in none of 40000 joints, and in 5 of the
        first 80000 built this way.
        """
        import random

        module = importlib.import_module("esolangs.tools.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001
        width = module._POOL_WIDTH  # noqa: SLF001
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        def scan(joint: object, cell7: int, walk_out: int) -> str | None:
            """The replaced search, kept as the oracle."""
            for code in codes:
                if module._pool_reaches(joint, code, cell7, walk_out):  # noqa: SLF001
                    return code
            return None

        def joint_of(sims: list[object]) -> object:
            joint = module._Joint.__new__(module._Joint)  # noqa: SLF001
            joint.ms = sims
            return joint

        def row(tape: int, ptr: int = 0, *, skip: bool = False) -> object:
            sim = module._Sim(512)  # noqa: SLF001
            sim.tape = tape
            sim.ptr = ptr
            sim.skip = skip
            return sim

        # Every single-row key in the derived domain, against the oracle.
        for low in range(1 << width):
            for ptr in range(ptr_max + 1):
                for skip in (False, True):
                    for cell7 in (0, 1):
                        joint = joint_of([row(low, ptr, skip=skip)])
                        walk_out = module._PROBE_WALK_OUT  # noqa: SLF001
                        assert module._find_pool(joint, cell7, walk_out) == scan(  # noqa: SLF001
                            joint, cell7, walk_out
                        ), (low, ptr, skip, cell7)

        # Joints, where the cross-row conditions live.
        rnd = random.Random(20260906)
        for _ in range(3000):
            seed_low = rnd.getrandbits(width)
            ptr = rnd.randint(0, ptr_max)
            sims = []
            for _ in range(rnd.choice([2, 4, 8])):
                low = seed_low
                if rnd.random() < 0.5:
                    low ^= 1 << rnd.randrange(width)
                sims.append(row(low | (rnd.getrandbits(16) << width), ptr))
            joint = joint_of(sims)
            for cell7 in (0, 1):
                walk_out = rnd.choice([9, 12, 20, 33])
                assert module._find_pool(joint, cell7, walk_out) == scan(  # noqa: SLF001
                    joint, cell7, walk_out
                ), [(s.tape & ((1 << width) - 1), s.ptr) for s in sims]

    def test_the_pool_slices_cover_the_whole_domain(self) -> None:
        """Deriving a slice at a time answers what one big table would.

        The slices exist so a caller pays for the ``(pointer, skip)`` it
        actually asks about -- a build touches one of the six, and deriving
        all of them on first use billed a 0.2ms build 57ms of work it had no
        use for.  What must not change is the *answers*: this rebuilds the
        whole-domain derivation the slices replaced and pins the union to it,
        so a slice that quietly disagreed with it would fail here.
        """

        module = importlib.import_module("esolangs.tools.minifuck")
        codes = module._POOL_CODES  # noqa: SLF001
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        whole = {
            (low, ptr, skip, cell7): answer
            for low in range(1 << module._POOL_WIDTH)  # noqa: SLF001
            for ptr in range(ptr_max + 1)
            for skip in (False, True)
            for cell7 in (0, 1)
            if (
                answer := module._pool_code_for_row(  # noqa: SLF001
                    codes, low, ptr, cell7, skip=skip
                )
            )
            is not None
        }

        union = {
            (low, ptr, skip, cell7): answer
            for ptr in range(ptr_max + 1)
            for skip in (False, True)
            for (low, cell7), answer in module._pool_slice(  # noqa: SLF001
                codes, ptr, skip=skip
            ).items()
        }

        assert union == whole
        assert whole, "the derivation should not be empty"

    def test_the_pool_rule_declines_outside_its_domain(self) -> None:
        """The bound is a refusal, not a gap in a table.

        Past ``_POOL_PTR_MAX`` the window byte is no longer the whole key --
        the codes reach above cell 7 -- so there is no answer to look up and
        the rule says None rather than guessing.  Codes do still fit out
        there, which is the point: this is where the rule stops claiming, not
        where the language stops working.
        """

        module = importlib.import_module("esolangs.tools.minifuck")
        ptr_max = module._POOL_PTR_MAX  # noqa: SLF001

        outside = module._Sim(512)  # noqa: SLF001
        outside.tape = 156
        outside.ptr = 3
        joint = module._Joint.__new__(module._Joint)  # noqa: SLF001
        joint.ms = [outside]

        assert ptr_max == 2, "the bound this test pins has moved"
        assert module._find_pool(joint, 1, 12) is None  # noqa: SLF001
        # ... while the simulator still finds a code from there.
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, 1, 12)  # noqa: SLF001
        ]
        assert served, "expected the scan to still answer outside the domain"

    def test_pool_reaches_refuses_a_code_that_kills_a_row(self) -> None:
        """``_pool_reaches`` rejects code that kills or desynchronises a row.

        The pool list is chosen so the codes it does offer keep every row
        alive, so this refusal never fires during a build -- but it is what
        makes a *candidate* code safe to try.  Checked against joints
        captured from a real build rather than a hand-built state, for the
        reason the pool test gives: a bare embed is not a state any call
        sees.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        joint = module._mux_separate(2)  # noqa: SLF001
        joint.emit("x")
        module._clamp(joint)  # noqa: SLF001
        cell7 = 0
        walk_out = min(module._mux_separate(2).ptrs()) - 3  # noqa: SLF001
        # ``[[`` leaves a row dead or mid-skip, so the code is refused before
        # the walk out is priced -- a dead row cannot be walked at all.
        assert not module._pool_reaches(joint, "[[", cell7, walk_out)  # noqa: SLF001
        # ``x`` writes under the pointer and is refused as well.
        assert not module._pool_reaches(joint, "x", cell7, walk_out)  # noqa: SLF001
        # A code that ends past the walk-out target is refused rather than
        # walked backwards: the walk out only ever moves right, so a pointer
        # already beyond it can never arrive.
        assert not module._pool_reaches(joint, "[x", cell7, 0)  # noqa: SLF001
        # Bare navigation is refused too: reaching the state is not enough,
        # the code has to leave the answer where the read will find it.
        assert not module._pool_reaches(joint, "", cell7, walk_out)  # noqa: SLF001
        # Exactly one of the pool's own codes serves this joint -- the guards
        # are a filter over the list, not a formality that passes everything.
        served = [
            code
            for code in module._POOL_CODES  # noqa: SLF001
            if module._pool_reaches(joint, code, cell7, walk_out)  # noqa: SLF001
        ]
        assert len(served) == 1, served

    def test_the_pool_search_needs_the_rows_to_agree_on_the_pointer(self) -> None:
        """A pool is only a pool if every row reads it from one place.

        The embed leaves the rows on different cells -- that spread is what
        carries the inputs -- so the pool search declines outright until a
        clamp has brought them back together.
        """
        from esolangs.tools.minifuck import _clamp, _embed, _find_pool

        spread = _embed(2)
        assert len(set(spread.ptrs())) > 1, "the embed should leave rows apart"
        assert _find_pool(spread, 0, 12) is None

        clamped = _embed(2)
        _clamp(clamped)
        assert len(set(clamped.ptrs())) == 1

    def test_the_endgame_refuses_an_impossible_setup(self) -> None:
        """Two ways the endgame cannot run, reported rather than emitted.

        The pool occupies cells 0..7, so an accumulator inside it would be
        overwritten by the digit it is supposed to carry.  And the pool has
        to be *built*: if no pattern reaches it from here, there is nothing
        to print, and emitting the read anyway would print a junk byte.
        """

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.minifuck_pool")
        from esolangs.tools.minifuck import _clamp, _embed, _endgame

        joint = _embed(2)
        _clamp(joint)

        with pytest.raises(ValueError, match="must sit past the pool"):
            _endgame(joint.fork(), 3, "[<", 0)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_find_pool", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="no pool pattern"):
                _endgame(joint.fork(), 12, "[<", 0)

    def test_the_computed_endgame_choice_matches_trying_all_four(self) -> None:
        """``_try_print`` still matches its retired trial as an oracle.

        The trial loop -- fork the joint, run every ``(read, orientation)``
        endgame, keep whichever printed -- is the specification, so it is
        replayed here, spelled as it stood, on explicit embed states.  The
        production construction no longer calls either spelling.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        def retired(joint: object, truth_table: str, acc: int) -> object:
            """The replaced trial loop, verbatim."""
            for read in module._READS:  # noqa: SLF001
                for cell7 in (0, 1):
                    probe = joint.fork()  # type: ignore[attr-defined]
                    try:
                        module._endgame(probe, acc, read, cell7)  # noqa: SLF001
                    except ValueError:
                        continue
                    if probe.printed() == list(truth_table):
                        return probe
            return None

        real = module._try_print  # noqa: SLF001
        sites: list[tuple[object, str, int]] = []
        base = module._BASE  # noqa: SLF001
        for n, table, acc in (
            (0, "1", base),
            (1, "01", base),
            (2, "0011", base),
            (2, "0110", base),
        ):
            joint = module._embed(n)  # noqa: SLF001
            module._clamp(joint)  # noqa: SLF001
            sites.append((joint, table, acc))
        misses = hits = 0
        for joint, table, acc in sites:
            expected = retired(joint, table, acc)
            got = real(joint, table, acc)
            if expected is None:
                assert got is None, (table, acc)
                misses += 1
            else:
                assert got is not None, (table, acc)
                assert got.template() == expected.template(), (table, acc)
                hits += 1
        # The comparison has to see both verdicts to mean anything.
        assert hits, "no site printed"
        assert misses, "no site declined"

    def test_the_walk_needs_a_converged_pointer_going_right(self) -> None:
        """``[x`` walks are only safe rightward from one shared position.

        Every row runs the same program, so a walk emitted while the rows
        disagree about where the pointer is would move them different
        distances.  And ``[x`` only advances -- the pointer is Minifuck's
        one leftward channel, and it is not this one -- so a leftward
        target is refused rather than silently ignored.
        """
        from esolangs.tools.minifuck import _clamp, _embed, _walk_to

        spread = _embed(2)
        with pytest.raises(ValueError, match="converged pointer"):
            _walk_to(spread, 0)

        clamped = _embed(2)
        _clamp(clamped)
        with pytest.raises(ValueError, match="cannot walk left"):
            _walk_to(clamped, -5)
