"""Compiler that turns RAM0 programs into RISC-V Linux assembly."""

import re

from esolangs.compilers import _riscv_common as _common


def parse(code: str) -> list[str]:
    """Tokenize a RAM0 program into ``Z A N C L S`` commands and digit gotos."""
    return re.findall(r"[ZANCLS]|[1-9]\d*", code)


def comp(code: str) -> str:
    """Compile a RAM0 program to RISC-V assembly with syscall output.

    Registers: ``s1`` = z, ``s2`` = n, ``s3`` = RAM base, ``s4`` = insertion
    order base, ``s5`` = order length, ``s6`` = set flags base, ``s7``/``s8``
    scratch.  Each token becomes a labelled block that jumps to the next
    (``C`` skips one when ``z == 0``, a digit jumps to line ``d - 1``), then
    the final state is dumped in the interpreter's ``z:/n:/ram:`` format.
    """
    tokens = parse(code)
    n = len(tokens)

    def target(k: int) -> str:
        return f".L{k}" if 0 <= k < n else ".done"

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    li   t0, -2304\n"
        "    add  sp, sp, t0\n"
        "    li   s1, 0\n"  # z
        "    li   s2, 0\n"  # n
        "    mv   s3, sp\n"  # ram[256]
        "    addi s4, sp, 1024\n"  # insertion order[256]
        "    li   t0, 2048\n"
        "    add  s6, sp, t0\n"  # set flags[256]
        "    li   s5, 0\n"  # order length
        "    j    .L0\n"
    )

    for i, tok in enumerate(tokens):
        res += f".L{i}:\n"
        if tok == "Z":
            res += "\tli   s1, 0\n"
        elif tok == "A":
            res += "\taddi s1, s1, 1\n"
        elif tok == "N":
            res += "\tmv   s2, s1\n"
        elif tok == "L":
            res += "\tslli t0, s1, 2\n\tadd  t0, s3, t0\n\tlw   s1, 0(t0)\n"
        elif tok == "S":
            res += (
                "\tslli t0, s2, 2\n"
                "\tadd  t0, s3, t0\n"
                "\tsw   s1, 0(t0)\n"  # ram[n] = z
                "\tadd  t1, s6, s2\n"
                "\tlbu  t2, 0(t1)\n"
                "\tbnez t2, 1f\n"  # n already in the order
                "\tli   t2, 1\n"
                "\tsb   t2, 0(t1)\n"  # set[n] = 1
                "\tslli t2, s5, 2\n"
                "\tadd  t2, s4, t2\n"
                "\tsw   s2, 0(t2)\n"  # order[orderlen] = n
                "\taddi s5, s5, 1\n"
                "1:\n"
            )
        elif tok == "C":
            res += f"\tbeqz s1, {target(i + 2)}\n"
        else:
            # ``parse`` matches ``[ZANCLS]`` or ``[1-9]\d*`` and nothing
            # else, so every token that reaches here is a goto.
            res += f"\tj {target(int(tok) - 1)}\n"
            continue
        res += f"\tj {target(i + 1)}\n"

    res += (
        ".done:\n"
        "    la   a1, str_z\n"
        "    call print_str\n"
        "    mv   a0, s1\n"
        "    call print_dec\n"
        "    la   a1, str_nl\n"
        "    call print_str\n"
        "    la   a1, str_n\n"
        "    call print_str\n"
        "    mv   a0, s2\n"
        "    call print_dec\n"
        "    la   a1, str_nl\n"
        "    call print_str\n"
        "    beqz s5, .ram_empty\n"
        "    la   a1, str_ram\n"
        "    call print_str\n"
        "    li   s8, 0\n"
        ".ram_loop:\n"
        "    bge  s8, s5, .ram_done\n"
        "    slli t1, s8, 2\n"
        "    add  t1, s4, t1\n"
        "    lw   s7, 0(t1)\n"  # key = order[i]
        "    la   a1, str_sp\n"
        "    call print_str\n"
        "    mv   a0, s7\n"
        "    call print_dec\n"
        "    la   a1, str_col\n"
        "    call print_str\n"
        "    slli t1, s7, 2\n"
        "    add  t1, s3, t1\n"
        "    lw   a0, 0(t1)\n"  # ram[key]
        "    call print_dec\n"
        "    addi t1, s8, 1\n"
        "    blt  t1, s5, .ram_comma\n"
        "    la   a1, str_nl\n"
        "    j    .ram_next\n"
        ".ram_comma:\n"
        "    la   a1, str_comma\n"
        ".ram_next:\n"
        "    call print_str\n"
        "    addi s8, s8, 1\n"
        "    j    .ram_loop\n"
        ".ram_done:\n"
        "    la   a1, str_end\n"
        "    call print_str\n"
        "    j    .exit\n"
        ".ram_empty:\n"
        "    la   a1, str_ram_empty\n"
        "    call print_str\n"
        ".exit:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
    )

    res += (
        "\n"
        "# print the null-terminated string at a1\n"
        "print_str:\n"
        "    mv   t3, a1\n"
        "    mv   t2, a1\n"
        "1:\n"
        "    lbu  t4, 0(t2)\n"
        "    beqz t4, 2f\n"
        "    addi t2, t2, 1\n"
        "    j    1b\n"
        "2:\n"
        "    sub  a2, t2, t3\n"
        "    li   a7, 64\n"
        "    li   a0, 1\n"
        "    ecall\n"
        "    ret\n"
        "\n"
        "# print a0 in decimal (software division by 10: rv64i has no M)\n"
        "print_dec:\n"
        "    addi sp, sp, -64\n"
        "    sd   ra, 56(sp)\n"
        "    li   t0, 0\n"
        "    bnez a0, 1f\n"
        "    li   t5, 48\n"
        "    sb   t5, 0(sp)\n"
        "    mv   a1, sp\n"
        "    li   a2, 1\n"
        "    li   a7, 64\n"
        "    li   a0, 1\n"
        "    ecall\n"
        "    ld   ra, 56(sp)\n"
        "    addi sp, sp, 64\n"
        "    ret\n"
        "1:\n"
        "    li   t1, 10\n"
        "2:\n"
        "    call div_u\n"
        "    addi t5, t5, 48\n"
        "    add  t6, sp, t0\n"
        "    sb   t5, 0(t6)\n"
        "    addi t0, t0, 1\n"
        "    bnez a0, 2b\n"
        "3:\n"
        "    addi t0, t0, -1\n"
        "    add  a1, sp, t0\n"
        "    li   a2, 1\n"
        "    li   a7, 64\n"
        "    li   a0, 1\n"
        "    ecall\n"
        "    bnez t0, 3b\n"
        "    ld   ra, 56(sp)\n"
        "    addi sp, sp, 64\n"
        "    ret\n"
        "\n"
        "# a0 / t1 -> a0 quotient, t5 remainder (unsigned 64-bit)\n"
        "div_u:\n"
        "    mv   t6, a0\n"
        "    li   a0, 0\n"
        "    li   t5, 0\n"
        "    li   t2, 64\n"
        "1:\n"
        "    slli t5, t5, 1\n"
        "    srli t3, t6, 63\n"
        "    or   t5, t5, t3\n"
        "    slli t6, t6, 1\n"
        "    bltu t5, t1, 2f\n"
        "    sub  t5, t5, t1\n"
        "    ori  a0, a0, 1\n"
        "2:\n"
        "    addi t2, t2, -1\n"
        "    beqz t2, 3f\n"
        "    slli a0, a0, 1\n"
        "    j    1b\n"
        "3:\n"
        "    ret\n"
        "\n"
        "    .section .rodata\n"
        'str_z:  .asciz "z: "\n'
        'str_n:  .asciz "n: "\n'
        'str_nl: .asciz "\\n"\n'
        'str_ram: .asciz "ram: {\\n"\n'
        'str_ram_empty: .asciz "ram: {}"\n'
        'str_sp: .asciz "    "\n'
        'str_col: .asciz ": "\n'
        'str_comma: .asciz ",\\n"\n'
        'str_end: .asciz "}"\n'
    )
    return res


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
