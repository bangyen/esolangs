"""Compiler that turns AddSubJump programs into RISC-V Linux assembly."""

import sys

from esolangs.interpreters.memory import parse_int_memory as _parse

# Special addresses, matching esolangs.interpreters.register_based.addsubjump.
_IO, _CF, _ZF, _NF, _OF, _ONE, _ZERO, _NEG, _FUM = -1, -2, -3, -4, -5, -6, -7, -8, -9

# Fixed-size cell buffer: the interpreter's memory grows on out-of-range
# writes, but a compiled program gets a generous preallocated word array
# instead (the same tradeoff RAM0's compiler makes for its 256-cell RAM).
_CELLS = 65536


def comp(code: str) -> str:
    """Compile an AddSubJump program to RISC-V assembly.

    AddSubJump's memory is self-modifying and its jump target (``*c``) is
    computed at runtime, so unlike the other compilers this cannot unroll
    into static per-token blocks: it emits a real fetch-decode-execute loop
    over a ``.data`` array of 8-byte cells.  Registers: ``s1`` = memory base,
    ``s2`` = ip (in cells), ``s3`` = memory length (in cells), ``s4`` = flag
    update mode, ``s5``/``s6`` = zero/negative flags.  ``read_cell`` and
    ``write_cell`` centralize the special-address handling (``-1`` I/O,
    ``-2``..``-5`` flags, ``-6``/``-7``/``-8`` constants, ``-9`` flag mode)
    that both operand fetch and the write-back share.
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
        "    li   s4, 0\n"
        "    li   s5, 0\n"
        "    li   s6, 0\n"
        ".loop:\n"
        "    bltz s2, .halt\n"
        "    bge  s2, s3, .halt\n"
        "    slli t0, s2, 3\n"
        "    add  t0, s1, t0\n"
        "    ld   a0, 0(t0)\n"  # a
        "    ld   a1, 8(t0)\n"  # b
        "    ld   a2, 16(t0)\n"  # c
        "    ld   a3, 24(t0)\n"  # d
        "    mv   t1, a0\n"  # save a (write target) across calls
        "    mv   t2, a2\n"  # save c (jump target)
        "    mv   a0, a3\n"
        "    call read_cell\n"  # vd = read(d)
        "    mv   t3, a0\n"
        "    mv   a0, a1\n"
        "    call read_cell\n"  # vb = read(b)
        "    mv   t4, a0\n"  # vb
        "    li   t0, -1\n"
        "    bne  t1, t0, .not_io\n"
        "    mv   a0, t4\n"  # a == -1: write vb straight to I/O
        "    j    .have_new\n"
        ".not_io:\n"
        "    mv   a0, t1\n"
        "    call read_cell\n"  # read(a)
        "    blez t3, .add\n"
        "    sub  a0, a0, t4\n"
        "    j    .have_new\n"
        ".add:\n"
        "    add  a0, a0, t4\n"
        ".have_new:\n"
        "    mv   t5, a0\n"  # new
        "    mv   a1, t5\n"
        "    mv   a0, t1\n"
        "    call write_cell\n"
        "    beqz s4, .no_flags\n"
        "    seqz s5, t5\n"
        "    sltz s6, t5\n"
        ".no_flags:\n"
        "    mv   a0, t2\n"
        "    call read_cell\n"  # ip = read(c)
        "    mv   s2, a0\n"
        "    j    .loop\n"
        ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
        "\n"
        "# read_cell(addr: a0) -> a0\n"
        "read_cell:\n"
        f"    li   t0, {_IO}\n"
        "    bne  a0, t0, 1f\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 8(sp)\n"
        "    li   a7, 63\n"
        "    li   a0, 0\n"
        "    mv   a1, sp\n"
        "    li   a2, 1\n"
        "    ecall\n"
        "    blez a0, .eof\n"
        "    lbu  a0, 0(sp)\n"
        "    ld   ra, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "1:\n"
        f"    li   t0, {_CF}\n"
        "    bne  a0, t0, 2f\n"
        "    li   a0, 0\n"
        "    ret\n"
        "2:\n"
        f"    li   t0, {_ZF}\n"
        "    bne  a0, t0, 3f\n"
        "    mv   a0, s5\n"
        "    ret\n"
        "3:\n"
        f"    li   t0, {_NF}\n"
        "    bne  a0, t0, 4f\n"
        "    mv   a0, s6\n"
        "    ret\n"
        "4:\n"
        f"    li   t0, {_OF}\n"
        "    bne  a0, t0, 5f\n"
        "    li   a0, 0\n"
        "    ret\n"
        "5:\n"
        f"    li   t0, {_ONE}\n"
        "    bne  a0, t0, 6f\n"
        "    li   a0, 1\n"
        "    ret\n"
        "6:\n"
        f"    li   t0, {_ZERO}\n"
        "    bne  a0, t0, 7f\n"
        "    li   a0, 0\n"
        "    ret\n"
        "7:\n"
        f"    li   t0, {_NEG}\n"
        "    bne  a0, t0, 8f\n"
        "    li   a0, -1\n"
        "    ret\n"
        "8:\n"
        f"    li   t0, {_FUM}\n"
        "    bne  a0, t0, 9f\n"
        "    mv   a0, s4\n"
        "    ret\n"
        "9:\n"
        "    bltz a0, .zero_ret\n"
        f"    li   t0, {_CELLS}\n"
        "    bge  a0, t0, .zero_ret\n"
        "    slli t0, a0, 3\n"
        "    add  t0, s1, t0\n"
        "    ld   a0, 0(t0)\n"
        "    ret\n"
        ".zero_ret:\n"
        "    li   a0, 0\n"
        "    ret\n"
        ".eof:\n"
        "    li   a0, 1\n"
        "    li   a7, 93\n"
        "    ecall\n"
        "\n"
        "# write_cell(addr: a0, value: a1)\n"
        "write_cell:\n"
        f"    li   t0, {_IO}\n"
        "    bne  a0, t0, 1f\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 8(sp)\n"
        "    andi t0, a1, 0xff\n"
        "    sb   t0, 0(sp)\n"
        "    li   a7, 64\n"
        "    li   a0, 1\n"
        "    mv   a1, sp\n"
        "    li   a2, 1\n"
        "    ecall\n"
        "    ld   ra, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "1:\n"
        f"    li   t0, {_FUM}\n"
        "    bne  a0, t0, 2f\n"
        "    mv   s4, a1\n"
        "    ret\n"
        "2:\n"
        f"    li   t0, {_CF}\n"  # -8..-2 (NEG..CF): other specials are read-only
        "    bgt  a0, t0, 3f\n"
        f"    li   t1, {_NEG}\n"
        "    blt  a0, t1, 3f\n"
        "    j    .no_write\n"
        "3:\n"
        "    bltz a0, .no_write\n"
        f"    li   t0, {_CELLS}\n"
        "    bge  a0, t0, .no_write\n"
        "    slli t0, a0, 3\n"
        "    add  t0, s1, t0\n"
        "    sd   a1, 0(t0)\n"
        ".no_write:\n"
        "    ret\n"
        "\n"
        "    .data\n"
        "    .align 3\n"
        "mem:\n"
    )
    for i in range(0, _CELLS, 8):
        row = cells[i : i + 8]
        res += "    .dword " + ", ".join(str(v) for v in row) + "\n"
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
