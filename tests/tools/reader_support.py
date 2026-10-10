"""Shared reader-generator samples and execution probes."""

import importlib
from collections.abc import Callable
from typing import Any

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES
from tests.witness_tables import row_bits


def _reader(language_id: str) -> tuple[Callable[[str], Any], Callable[..., None]]:
    """Return any registered language's generator and interpreter ``run``."""
    lang = next(lang for lang in LANGUAGES.values() if lang.id == language_id)
    assert lang.boolean is not None
    assert lang.interpreter is not None
    module = importlib.import_module(f"esolangs.interpreters.{lang.interpreter}")
    return lang.boolean, module.run


#: The tree readers whose ``LANGUAGE`` asks for these shared checks.
_READERS = {
    lang.id: _reader(lang.id) for lang in LANGUAGES.values() if lang.reader_checked
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


def _read_answer(name: str, table: str, row: int) -> tuple[str, int]:
    """Return what the generated program printed, and how many inputs it read."""
    generate, run = _reader(name)
    n = len(table).bit_length() - 1
    io = ScriptedIO(esolangs.encode_inputs(name, row_bits(row, n)))
    run(generate(table), io)
    return io.getvalue(), io.reads
