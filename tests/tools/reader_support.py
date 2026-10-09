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


#: The tree readers these shared checks were written for.
_READERS = {name: _reader(name) for name in ("false", "thue", "unlambda")}


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
