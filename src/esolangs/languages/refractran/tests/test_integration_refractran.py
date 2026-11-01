"""REFRACTRAN templates survive serialization, reflow and VM execution."""

import esolangs
from esolangs.debugger import make_vm


def test_serialized_narrow_template_and_vm() -> None:
    language = esolangs.Language("REFRACTRAN")
    template = language.generate("0110", width=1)
    restored = language.load_program(language.dump_program(template))
    for bits, answer in [((0, 0), "0"), ((0, 1), "1"), ((1, 0), "1"), ((1, 1), "0")]:
        program = language.instantiate(restored, bits)
        vm = make_vm(language.name, program)
        for _ in range(1000):
            if vm.halted:
                break
            vm.step()
        assert vm.halted
        assert language.read_answer(vm.output) == answer
