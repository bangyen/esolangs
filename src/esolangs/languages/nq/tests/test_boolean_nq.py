"""NQ Boolean rows and serialized, wrapped programs."""

from itertools import product
from random import Random

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.languages.nq.generator import nq
from esolangs.languages.nq.tests.ablations import ablate
from esolangs.languages.nq.tests.test_nq import check_instructions


@pytest.mark.medium
def test_language_contract() -> None:
    """Execute all small tables and sampled larger rows through the real VM."""
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
            settings = esolangs.DialectSettings(guard_binding=binding)
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
                assert steps <= 3 * n + 3
                assert language.read_answer(vm.output) == answer
                assert vm.snapshot()[-1] == n
    for binding in ("opcode", "recursive"):
        settings = esolangs.DialectSettings(guard_binding=binding)
        for n in range(1, 9):
            table = "0" * ((1 << n) - 1) + "1"
            source = language.generate(table, width=1, settings=settings)
            source = language.load_program(language.dump_program(source))
            assert source.settings == settings
            vm = make_vm("NQ", source, stdin="1" * n)
            steps = 0
            while not vm.halted:
                vm.step()
                steps += 1
            assert steps == 3 * n + 3
            assert vm.output == "#"
