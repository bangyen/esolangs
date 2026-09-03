"""Compiler that turns S*bleq programs into RISC-V Linux assembly."""

from esolangs.compilers import _riscv_common as _common
from esolangs.compilers._riscv_common import (
    PUTBYTE,
    READ_BYTE_OR_EOF,
    cell_load_or_zero,
    dump_cells,
)
from esolangs.interpreters.memory import parse_int_memory as _parse

# Special addresses, matching esolangs.interpreters.tape_based.sbleq.
_IP, _IN, _OUT = -1, -2, -3

# Fixed-size cell buffer: the interpreter's memory grows on out-of-range
# writes, but a compiled program gets a generous preallocated word array
# instead (the same tradeoff AddSubJump's and RAM0's compilers make).
_CELLS = 65536


def comp(code: str) -> str:
    """Compile an S*bleq program to RISC-V assembly.

    S*bleq's memory is self-modifying and its jump target (``read(c)``) is
    computed at runtime, so like AddSubJump this cannot unroll into static
    per-token blocks: it emits a real fetch-decode-execute loop over a
    ``.data`` array of 8-byte cells.  Registers: ``s1`` = memory base,
    ``s2`` = ip (in cells), ``s3`` = memory length (in cells).
    ``read_cell``/``write_cell`` centralize the special-address handling
    (``-1`` ip, ``-2`` input, ``-3`` is output-only and never read/written
    through these helpers -- the main loop checks ``a``/``b`` for ``-3``
    directly, matching the interpreter's ``step``).  This compiler targets
    the base store variant (S*bleq stores the difference in ``a`` only).

    Writes past the compile-time program length grow the interpreter's
    list (moving its halt boundary outward) but not this compiler's fixed
    ``_CELLS`` boundary check -- the same tradeoff AddSubJump's and
    Decleq's compilers make.
    """
    cells = _parse(code)
    n = len(cells)
    if n < _CELLS:
        cells = cells + [0] * (_CELLS - n)

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    la   s1, mem\n"
        "    li   s2, 0\n"
        f"    li   s3, {n}\n"
        ".loop:\n"
        "    bltz s2, .halt\n"
        "    addi t0, s3, -2\n"
        "    bge  s2, t0, .halt\n"
        "    slli t0, s2, 3\n"
        "    add  t0, s1, t0\n"
        "    ld   a0, 0(t0)\n"  # a
        "    ld   a1, 8(t0)\n"  # b
        "    ld   a2, 16(t0)\n"  # c
        f"    li   t1, {_OUT}\n"
        "    bne  a0, t1, .not_out_a\n"
        "    mv   a0, a1\n"
        "    call read_cell\n"  # output(read(b))
        "    call putbyte\n"
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".not_out_a:\n"
        "    bne  a1, t1, .not_out_b\n"
        "    call read_cell\n"  # a0 already holds a; output(read(a))
        "    call putbyte\n"
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".not_out_b:\n"
        "    mv   t2, a0\n"  # save a (write target)
        "    mv   t3, a2\n"  # save c (jump target)
        "    mv   t6, a1\n"  # save b (read_cell clobbers a1 as scratch)
        "    call read_cell\n"  # a0 = read(a); a0 already = a on entry
        "    mv   t4, a0\n"
        "    mv   a0, t6\n"
        "    call read_cell\n"  # a0 = read(b)
        "    sub  t5, t4, a0\n"  # diff = read(a) - read(b)
        "    mv   a0, t2\n"
        "    mv   a1, t5\n"
        "    call write_cell\n"  # write(a, diff)
        "    bgtz t5, .fallthrough\n"
        "    mv   a0, t3\n"
        "    call read_cell\n"  # target = read(c)
        "    bltz a0, .halt\n"
        "    mv   s2, a0\n"
        "    j    .loop\n"
        ".fallthrough:\n"
        "    addi s2, s2, 3\n"
        "    j    .loop\n"
        ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
        "\n"
        "# read_cell(addr: a0) -> a0\n"
        "read_cell:\n"
        f"    li   t0, {_IP}\n"
        "    bne  a0, t0, 1f\n"
        "    mv   a0, s2\n"
        "    ret\n"
        "1:\n"
        f"    li   t0, {_IN}\n"
        "    bne  a0, t0, 2f\n"
        + READ_BYTE_OR_EOF
        + "2:\n"
        + cell_load_or_zero(_CELLS)
        + ".eof:\n"
        "    li   a0, 0\n"
        "    ld   ra, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "\n"
        "# write_cell(addr: a0, value: a1)\n"
        "write_cell:\n"
        f"    li   t0, {_IP}\n"
        "    bne  a0, t0, 1f\n"
        "    mv   s2, a1\n"
        "    ret\n"
        "1:\n"
        "    bltz a0, .no_write\n"
        f"    li   t0, {_CELLS}\n"
        "    bge  a0, t0, .no_write\n"
        "    slli t0, a0, 3\n"
        "    add  t0, s1, t0\n"
        "    sd   a1, 0(t0)\n"
        ".no_write:\n"
        "    ret\n"
        "\n" + PUTBYTE + "\n"
    )
    return res + dump_cells(cells, _CELLS)


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
