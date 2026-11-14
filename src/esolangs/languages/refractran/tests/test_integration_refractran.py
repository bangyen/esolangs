"""REFRACTRAN templates survive serialization, reflow and VM execution."""

from random import Random

import esolangs
from esolangs.debugger import make_vm


def check_serialized_narrow_template_and_vm() -> None:
    language = esolangs.Language("REFRACTRAN")
    template = language.generate("0110", width=1)
    restored = language.from_json(language.to_json(template))
    for bits, answer in [((0, 0), "0"), ((0, 1), "1"), ((1, 0), "1"), ((1, 1), "0")]:
        program = language.instantiate(restored, bits)
        vm = make_vm(language.name, program)
        for _ in range(1000):
            if vm.halted:
                break
            vm.step()
        assert vm.halted
        assert language.read_answer(vm.output) == answer

    table = "".join(Random(4242 + 10).choices("01", k=1024))
    template = language.generate(table, balance=True)
    restored = language.from_json(language.to_json(template))
    for row in (0, 1, 511, 1023):
        program = language.instantiate(restored, [int(b) for b in f"{row:010b}"])
        output = language.run(
            program,
            limits=esolangs.ExecutionLimits(max_steps=2 * len(program.source) + 1),
        ).output
        assert language.read_answer(output) == table[row]
