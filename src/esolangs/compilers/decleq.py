"""Compiler that turns Decleq programs into RISC-V Linux assembly."""

from esolangs.compilers import _riscv_common as _common
from esolangs.compilers._riscv_common import (
    GETBYTE,
    PUTBYTE,
    cell_load_or_zero,
    cell_store_or_drop,
    dump_cells,
    start_preamble,
)
from esolangs.interpreters.memory import parse_int_memory as _parse

# Special addresses, matching esolangs.interpreters.register_based.decleq.
_OUT, _IN = -2, -1

# Fixed-size cell buffer: the interpreter's memory grows on out-of-range
# writes, but a compiled program gets a generous preallocated word array
# instead (the same tradeoff AddSubJump's, RAM0's, and S*bleq's compilers
# make).
_CELLS = 65536


def comp(code: str) -> str:
    """Compile a Decleq program to RISC-V assembly.

    Decleq's memory is self-modifying and its jump target ``c`` is a plain
    operand (not computed indirectly like S*bleq's), but ``a``/``b`` still
    address the same self-modifying cell array the program body lives in, so
    this emits a fetch-decode-execute loop over a ``.data`` array of 8-byte
    cells rather than unrolling per-token blocks.  Registers: ``s1`` =
    memory base, ``s2`` = pc (in cells), ``s3`` = memory length (in cells).
    Each instruction is ``a b c``: ``mem[b] = mem[a] - 1``, then jump to
    ``c`` when the new ``mem[b] <= 0``, else fall through three cells.
    ``a == -2`` outputs ``mem[b]``; ``a == -1`` reads a byte of input into
    ``mem[b]``; both fall through rather than branch.  EOF on ``a == -1``
    halts the program (matching the interpreter's ``EOFError``, which
    unwinds the run and keeps whatever output was already produced).

    Two edge cases the interpreter's Python-list memory model exposes are
    not reproduced here, matching the same tradeoff AddSubJump's compiler
    already makes: writes with ``b`` past the compile-time program length
    grow the interpreter's list (moving its halt boundary outward) but not
    this compiler's fixed ``_CELLS`` boundary check, and a *negative* ``b``
    hits Python's negative-index wraparound on the interpreter's list
    (``mem[-2]`` means "second from the end") rather than the "out of
    range" treatment every other special address gets -- an accident of the
    list-backed implementation, not documented language behavior, and not
    a shape any real countdown-idiom program produces.
    """
    cells = _parse(code)
    n = len(cells)
    if n < _CELLS:
        cells = cells + [0] * (_CELLS - n)

    res = (
        start_preamble(n) + ".loop:\n"
        "    bltz s2, .halt\n"
        "    bge  s2, s3, .halt\n"
        "    slli t0, s2, 3\n"
        "    add  t0, s1, t0\n"
        "    ld   a0, 0(t0)\n"  # a
        "    ld   a1, 8(t0)\n"  # b
        "    ld   a2, 16(t0)\n"  # c
        f"    li   t1, {_OUT}\n"
        "    bne  a0, t1, .not_out\n"
        "    mv   t2, a1\n"
        "    mv   a0, t2\n"
        "    call read_cell\n"  # a0 = mem[b]
        "    call putbyte\n"
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".not_out:\n"
        f"    li   t1, {_IN}\n"
        "    bne  a0, t1, .decrement\n"
        "    mv   t2, a1\n"
        "    call getbyte\n"  # a0 = next input byte (0 at EOF)
        "    mv   a1, a0\n"
        "    mv   a0, t2\n"
        "    call write_cell\n"  # mem[b] = byte
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".decrement:\n"
        "    mv   t2, a1\n"  # save b (write target)
        "    mv   t3, a2\n"  # save c (jump target)
        "    call read_cell\n"  # a0 = mem[a]; a0 already = a on entry
        "    addi t4, a0, -1\n"  # mem[a] - 1
        "    mv   a0, t2\n"
        "    mv   a1, t4\n"
        "    call write_cell\n"  # mem[b] = mem[a] - 1
        "    bgtz t4, .fallthrough\n"
        "    mv   s2, t3\n"
        "    j    .loop\n"
        ".fallthrough:\n"
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
        "\n"
        "# read_cell(addr: a0) -> a0; out-of-range reads as zero\n"
        "read_cell:\n"
        + cell_load_or_zero(_CELLS)
        + "\n"
        + "# write_cell(addr: a0, value: a1); out-of-range writes are dropped\n"
        + "write_cell:\n"
        + cell_store_or_drop(_CELLS)
        + "\n"
        + GETBYTE
        + "\n"
        + PUTBYTE
        + "\n"
    )
    return res + dump_cells(cells, _CELLS)


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
