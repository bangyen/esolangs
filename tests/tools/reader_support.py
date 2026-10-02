"""Shared reader-generator samples and execution probes."""

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.thue import run as run_thue
from esolangs.interpreters.other.unlambda import run as run_unlambda
from esolangs.interpreters.stack_based.false import run as run_false

_READERS = {
    "false": (boolean.false, run_false),
    "thue": (boolean.thue, run_thue),
    "unlambda": (boolean.unlambda, run_unlambda),
}


_TABLES = [
    "01",  # identity
    "10",  # NOT
    "0001",  # AND
    "1110",  # NAND
    "0110",  # XOR
    "00000000",  # constant, which folds all the way down
    "01101001",  # parity, which folds nothing
    "10100101",
    "1000000000000000",  # AND4
]


def _bits(row: int, n: int) -> list[int]:
    return [(row >> (n - 1 - i)) & 1 for i in range(n)]


def _read_answer(name: str, table: str, row: int) -> tuple[str, int]:
    """Return what the generated program printed, and how many inputs it read."""
    generate, run = _READERS[name]
    n = len(table).bit_length() - 1
    io = ScriptedIO(esolangs.encode_inputs(name, _bits(row, n)))
    run(generate(table), io)
    return io.getvalue(), io.reads
