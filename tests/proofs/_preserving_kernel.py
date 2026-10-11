"""Build preserving-prefix vectors in bounded 128-bit arithmetic, when available."""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.proofs._brainfuck_balanced import Matrix


def construct(
    rows: list[list[int]],
    edges: list[list[int]],
    types: list[int],
    kinds: int,
    scale: int,
    bound: tuple[int, int],
) -> list[Matrix] | None:
    """Return a candidate vector; absent C11/128-bit support leaves Python in charge."""
    compiler = shutil.which("cc")
    if compiler is None or sys.platform == "win32":
        return None
    starts = sorted({0, *(row[6] for row in rows if row[6] >= 0)})
    positions = [starts.index(row) if row in starts else -1 for row in range(len(rows))]
    integer = ctypes.c_int
    word = ctypes.c_uint64

    def packed(values: list[int]) -> ctypes.Array[ctypes.c_int]:
        return (integer * len(values))(*values)

    with tempfile.TemporaryDirectory(prefix="preserving-kernel-") as directory:
        library = Path(directory) / "kernel.so"
        compilation = subprocess.run(
            [
                compiler,
                "-std=c11",
                "-O2",
                "-shared",
                "-fPIC",
                str(Path(__file__).with_suffix(".c")),
                "-o",
                str(library),
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if compilation.returncode:
            return None
        kernel = ctypes.CDLL(str(library)).construct
        kernel.argtypes = (
            [ctypes.POINTER(integer)] * 5
            + [integer] * 4
            + [word] * 3
            + [ctypes.POINTER(word)]
        )
        kernel.restype = integer
        output = (word * (len(edges) * len(starts) * len(rows)))()
        status = kernel(
            packed([entry for row in rows for entry in row]),
            packed([entry for row in edges for entry in row]),
            packed(types),
            packed(starts),
            packed(positions),
            len(rows),
            len(edges),
            kinds,
            len(starts),
            *bound,
            scale,
            output,
        )
        if status <= 0:
            raise RuntimeError(f"preserving native construction aborted ({status})")
        matrices: list[Matrix] = [[{} for _ in rows] for _ in edges]
        for state, matrix in enumerate(matrices):
            for position, start in enumerate(starts):
                offset = (state * len(starts) + position) * len(rows)
                matrix[start] = {
                    end: output[offset + end]
                    for end in range(len(rows))
                    if output[offset + end]
                }
        return matrices
