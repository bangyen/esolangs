"""Table semantics through the public source-binding path."""

from itertools import product

from esolangs import generate, run
from esolangs.operations.instantiation import instantiate


def test_folded_and_wrapped_templates() -> None:
    for table in ("00000000", "00001111", "00010111", "01101001"):
        native = generate("Trml", table)
        wrapped = generate("Trml", table, width=11)
        for ordinal, bits in enumerate(product((0, 1), repeat=3)):
            for template in (native, wrapped):
                program = instantiate("Trml", template, bits)
                result = run("Trml", program, stdin="unused").unwrap()
                assert result.output == table[ordinal]
                assert result.input_reads == 0
