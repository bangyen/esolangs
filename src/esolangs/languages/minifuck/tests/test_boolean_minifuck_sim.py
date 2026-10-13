"""Covers :mod:`esolangs.languages.minifuck.generator.sim` against the interpreter."""


def test_settled_embed_matches_the_interpreter() -> None:
    from esolangs.languages.minifuck.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from tests.generators.fills import fill

    _fill_minifuck = fill("Minifuck")
    from esolangs.languages.minifuck.tests.minifuck_support import _embed

    for n in (1, 2, 3):
        for settle in (1, 2):
            joint = _embed(n, settle=settle)
            for bits, model in zip(joint.rows, joint.ms, strict=True):
                code = _fill_minifuck(joint.template(), bits)
                machine = _Machine(code, ScriptedIO(""))
                while not machine.halted:
                    machine.step()
                assert machine.ptr == model.ptr
                assert machine.snapshot()[0] == model.tape


def test_law_guard_skip_and_single_cross_arms() -> None:
    """The guard, skip and single-cross arms the lockstep builds never reach."""
    from esolangs.languages.minifuck.generator.sim import _Joint, _Sim

    # A dead row: every law returns without moving.
    for arm in ("run_left", "run_comment", "run_walk", "run_brackets"):
        machine = _Sim(8)
        machine.dead = True
        getattr(machine, arm)(3)
        assert (machine.ptr, machine.tape, machine.out) == (0, 0, [])
    dead = _Sim(8)
    dead.dead = True
    dead.run_dot()
    assert dead.ptr == 0

    # A non-positive count: same guard, no law applied.
    for arm in ("run_left", "run_comment", "run_walk", "run_brackets"):
        machine = _Sim(8)
        getattr(machine, arm)(0)
        assert machine.ptr == 0

    # A pending skip is eaten by the next law; a lone walk pair and a lone
    # bracket end on the skip alone.
    for arm, count in (
        ("run_left", 1),
        ("run_comment", 1),
        ("run_walk", 1),
        ("run_brackets", 1),
    ):
        machine = _Sim(8)
        machine.skip = True
        getattr(machine, arm)(count)
        assert not machine.skip
    # A walk of two pairs leaves one to run after the skip.
    walk = _Sim(8)
    walk.skip = True
    walk.run_walk(2)
    assert not walk.skip
    assert walk.ptr == 1
    # A skip before two brackets leaves one to cross.
    crossed = _Sim(8)
    crossed.skip = True
    crossed.run_brackets(2)
    assert not crossed.skip
    assert crossed.ptr == 1

    # The spelled-out single crossing: a clear cell sets it, a set cell
    # carries above and leaves the skip pending.
    for before, expect_skip in ((0, False), (0b11, True)):
        machine = _Sim(2)
        machine.tape = before
        machine.run_brackets(1)
        assert machine.skip is expect_skip
        assert (machine.ptr, machine.length) == (1, 3)

    # The print law: a pending skip is a no-op, and a zero read freezes the row.
    skipped = _Sim(8)
    skipped.skip = True
    skipped.run_dot()
    assert not skipped.skip
    assert not skipped.dead
    frozen = _Sim(8)
    frozen.tape = 0b10
    frozen.run_dot()
    assert frozen.dead
    assert frozen.ptr == 0

    # An empty emission is not parsed.
    joint = _Joint(1)
    joint.emit("")
    assert joint.parts == [""]
    assert joint.ms[0].ptr == 0
