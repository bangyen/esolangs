"""Execute larger tables through the public API and VM."""

import random

import pytest

import esolangs
from esolangs import debugger as debugger_api


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Cyclic tag", "Boolfuck", "Subleq", "///"])
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("case", range(11))
def test_larger_tables(language: str, n: int, case: int) -> None:
    rng = random.Random(1729 + n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        *("".join(str(rng.randrange(2)) for _ in range(1 << n)) for _ in range(8)),
    ]
    for table in tables[case : case + 1]:
        template = esolangs.generate(language, table)
        for row in range(1 << n):
            bits = [int(c) for c in f"{row:0{n}b}"]
            source = (
                esolangs.instantiate(language, template, bits)
                if language in ("Cyclic tag", "///")
                else template
            )
            stdin = (
                ""
                if language in ("Cyclic tag", "///")
                else esolangs.encode_inputs(language, bits)
            )
            assert esolangs.run(language, source, stdin) == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Cyclic tag", "Boolfuck", "Subleq", "///"])
def test_vm_output_matches_runner(language: str) -> None:
    template = esolangs.generate(language, "0110")
    bits = [0, 1]
    source = (
        esolangs.instantiate(language, template, bits)
        if language in ("Cyclic tag", "///")
        else template
    )
    stdin = (
        ""
        if language in ("Cyclic tag", "///")
        else esolangs.encode_inputs(language, bits)
    )
    vm = debugger_api.make_vm(language, source, stdin)
    for _ in range(10000):
        if vm.halted:
            break
        vm.step()
    assert vm.halted
    if vm.dumps_on_the_post_halt_step:
        vm.step()
    assert vm.output == esolangs.run(language, source, stdin) == "1"


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Cyclic tag", "Boolfuck", "Subleq", "///"])
def test_executed_rendered_scaling(language: str) -> None:
    sizes = []
    for n in (8, 10, 12):
        rng = random.Random(1729)
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        template = esolangs.generate(language, table)
        sizes.append(len(template))
        row = (1 << n) // 3
        bits = [int(c) for c in f"{row:0{n}b}"]
        if language in ("Cyclic tag", "///"):
            source = esolangs.instantiate(language, template, bits)
            stdin = ""
        else:
            source = template
            stdin = esolangs.encode_inputs(language, bits)
        assert esolangs.run(language, source, stdin) == table[row]
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4
