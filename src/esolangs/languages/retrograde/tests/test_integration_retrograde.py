"""Retrograde VM, wrapped serialization and exact step witnesses."""

import esolangs
from esolangs.debugger import make_vm
from esolangs.languages.retrograde.tests.test_boolean_retrograde import (
    check_boolean_tables,
)
from esolangs.languages.retrograde.tests.test_retrograde import (
    check_instruction_semantics,
)


def test_language_contract() -> None:
    """Opcode directions, Boolean rows, serialization and step witnesses."""
    check_instruction_semantics()
    check_boolean_tables()
    language = esolangs.Language("Retrograde")
    for n in range(1, 9):
        table = "0" * ((1 << n) - 1) + "1"
        template = language.generate(table, width=1)
        template = language.load_program(language.dump_program(template))
        source = language.instantiate(template, (1,) * n)
        vm = make_vm(language.name, source)
        steps = 0
        for _ in range(12 * n + 1):
            if vm.halted:
                break
            vm.step()
            steps += 1
        assert vm.halted
        assert steps == 12 * n - 2
        assert vm.ptr == n
        assert vm.output == "1"
