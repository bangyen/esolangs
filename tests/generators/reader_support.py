"""Shared reader-generator samples and execution probes."""

import importlib
from collections.abc import Callable, Iterator
from typing import Any

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import generator_for
from tests.support.witness_tables import row_bits


def _reader(language_id: str) -> tuple[Callable[[str], Any], Callable[..., None]]:
    """Return any registered language's generator and interpreter ``run``."""
    lang = next(lang for lang in LANGUAGES.values() if lang.id == language_id)
    assert lang.backend is not None
    assert lang.runtime.interpreter is not None
    module = importlib.import_module(f"esolangs.languages.{lang.id}.interpreter")
    return generator_for(lang.name), module.run


#: The tree readers whose ``LANGUAGE`` asks for these shared checks.
_READERS = {
    lang.id: _reader(lang.id)
    for lang in LANGUAGES.values()
    if load_certification(lang).reader_checked
}


def assert_emissions_grow_by_a_line(
    generate: Callable[[str], Any], *, parity: bool = False
) -> None:
    """Successive size differences quadruple, exactly, as ``n`` steps by two.

    Measured on ``01...``, which ignores all but the last input, or on
    parity, which reads every one, for a generator that drops ignored ones.
    """
    sizes = [
        len(
            generate(
                "".join(str(row.bit_count() & 1) for row in range(2**n))
                if parity
                else "01" * (2 ** (n - 1))
            )
        )
        for n in (4, 6, 8)
    ]
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) == 4.0


_TABLES = [
    "10",  # NOT
    "0001",  # AND
    "00000000",  # constant, which folds all the way down
    "01101001",  # parity, which folds nothing
    "00110101",  # mux, which reading the inputs out of order breaks
    "1000000000000000",  # AND4
]


def _read_answers(name: str, table: str) -> Iterator[tuple[str, int]]:
    """Run every row of one generated program with fresh input and machine state."""
    generate, run = _reader(name)
    program = generate(table)
    n = len(table).bit_length() - 1
    for row in range(1 << n):
        io = ScriptedIO(esolangs.encode_inputs(name, row_bits(row, n)))
        run(program, io)
        yield io.getvalue(), io.reads
