"""Covers :mod:`esolangs.tools.minifuck.sim` against the interpreter."""


def test_settled_embed_matches_the_interpreter() -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine
    from esolangs.tools.minifuck.pool import _embed
    from tests.tools.fills import _fill_minifuck

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
