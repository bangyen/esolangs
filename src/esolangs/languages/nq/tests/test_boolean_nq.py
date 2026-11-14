"""NQ Boolean rows and serialized, wrapped programs."""

from itertools import product
from random import Random

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.languages.nq.generator import nq
from esolangs.languages.nq.tests.ablations import ablate
from esolangs.languages.nq.tests.test_nq import check_instructions
from scripts.benchmark import WrittenState
from tests.support.cli_support import call_main
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row


def _check_cli_answers(capsys: pytest.CaptureFixture[str]) -> None:
    """NQ's final space is an answer, including after an earlier true answer."""
    for output, answer in ((" ", "0"), ("#", "1"), ("# \n", "0")):
        assert call_main(["read-answer", "NQ"], capsys, stdin=output) == answer + "\n"
    with pytest.raises(SystemExit) as exc:
        call_main(["read-answer", "NQ"], capsys)
    assert exc.value.code == 2
    assert "nothing on stdin" in capsys.readouterr().err


@pytest.mark.medium
def test_language_contract(monkeypatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Execute all small tables and sampled larger rows through the real VM."""
    _check_cli_answers(capsys)
    _check_constants()
    check_instructions()
    language = esolangs.Language("NQ")
    rng = Random(1847)
    tables = [
        "".join(bits) for n in range(1, 4) for bits in product("01", repeat=1 << n)
    ]
    tables += [
        "".join(rng.choice("01") for _ in range(1 << n))
        for n in range(4, 7)
        for _ in range(5)
    ]
    for table in tables:
        n = (len(table) - 1).bit_length()
        source = nq(table)
        assert source == ablate(table, "default")
        assert len(source) <= 10 * len(table) - 6
        for binding in ("opcode", "recursive"):
            assert nq(table, guard_binding=binding) == source
            settings = esolangs.Language("NQ").settings(guard_binding=binding)
            for row, answer in enumerate(table):
                bits = tuple((row >> (n - 1 - i)) & 1 for i in range(n))
                vm = make_vm(
                    "NQ", source, stdin=language.encode_inputs(bits), settings=settings
                )
                steps = 0
                for _ in range(3 * n + 4):
                    if vm.halted:
                        break
                    vm.step()
                    steps += 1
                assert vm.halted
                assert steps <= 3 * n + 4
                assert language.read_answer(vm.output) == answer
                assert vm.snapshot()[-1] == n
    for binding in ("opcode", "recursive"):
        settings = esolangs.Language("NQ").settings(guard_binding=binding)
        for n in range(1, 9):
            table = "0" * ((1 << n) - 1) + "1"
            source = language.generate(table, width=1, settings=settings)
            source = language.from_json(language.to_json(source))
            assert source.settings == settings
            vm = make_vm("NQ", source, stdin="1" * n)
            steps = 0
            while not vm.halted:
                vm.step()
                steps += 1
            assert steps == 3 * n + (4 if n == 1 else 3)
            assert vm.output == "#"

    from esolangs.languages.nq import generator

    canonical = generator.subtree_ids

    def wrong_children(table):
        ids = [list(row) for row in canonical(table)]
        ids[1][1] = ids[1][0]
        return ids

    with monkeypatch.context() as patch:
        patch.setattr(generator, "subtree_ids", wrong_children)
        for binding in ("opcode", "recursive"):
            program = language.generate(
                "0011", settings=esolangs.Language("NQ").settings(guard_binding=binding)
            )
            with pytest.raises(AssertionError):
                assert_every_row("NQ", "0011", program=program)


def _check_constants() -> None:
    from esolangs.languages.nq.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for binding in ("opcode", "recursive"):
                for options in ({}, {"width": 1}, {"balance": True}):
                    source = esolangs.generate("NQ", bit * (1 << n), **options).source
                    for bits in ([0] * n, [1] * n):
                        io = ReadFirstIO("".join(map(str, bits)) + "7", expected=n)
                        machine = _Machine(source, io, guard_binding=binding)
                        written = WrittenState(machine.workspace_snapshot())
                        for _ in range(n + 3):
                            assert not machine.halted
                            machine.step()
                            written.sample(machine.workspace_snapshot())
                        assert machine.halted
                        assert list(machine.queue) == [2 * int(bit), *bits]
                        assert io.getvalue() == ("#" if bit == "1" else " ")
                        assert io.reads == n
                        assert io.past_end == 0
                        assert io.input_char() == ord("7")
                        assert written.bits <= 2 * n + len(source).bit_length() + 32
