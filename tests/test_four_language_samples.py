"""Execute larger tables through the public API and VM."""

import random

import pytest

import esolangs


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
