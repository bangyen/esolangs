"""Shared RISC-V assembly fragments for the OISC-style compilers.

decleq, S*bleq, and AddSubJump all compile to a fetch-decode-execute loop
over a ``.data`` array of 8-byte cells (their jump targets are computed at
runtime, so unlike the token-unrolling compilers they can't emit static
per-token blocks).  These three routines -- byte I/O and the final
dword-per-row memory dump -- are copy-pasted identically between them;
keeping one copy here is what the ``duplicate-code`` check in
``scripts/verify.py`` enforces.
"""

GETBYTE = (
    "# getbyte() -> a0; reads one byte of stdin, halts the program at EOF\n"
    "# (matching the interpreter's EOFError, which unwinds the whole run)\n"
    "getbyte:\n"
    "    addi sp, sp, -16\n"
    "    sd   ra, 8(sp)\n"
    "    li   a7, 63\n"
    "    li   a0, 0\n"
    "    mv   a1, sp\n"
    "    li   a2, 1\n"
    "    ecall\n"
    "    blez a0, .halt\n"
    "    lbu  a0, 0(sp)\n"
    "    ld   ra, 8(sp)\n"
    "    addi sp, sp, 16\n"
    "    ret\n"
)

READ_BYTE_OR_EOF = (
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
)

PUTBYTE = (
    "# putbyte(value: a0) -- write the low byte to stdout\n"
    "putbyte:\n"
    "    addi sp, sp, -16\n"
    "    sd   ra, 8(sp)\n"
    "    andi t0, a0, 0xff\n"
    "    sb   t0, 0(sp)\n"
    "    li   a7, 64\n"
    "    li   a0, 1\n"
    "    mv   a1, sp\n"
    "    li   a2, 1\n"
    "    ecall\n"
    "    ld   ra, 8(sp)\n"
    "    addi sp, sp, 16\n"
    "    ret\n"
)


MUL32 = (
    "# a0 *= a1 (unsigned 32-bit), result in a0\n"
    "mul32:\n"
    "\tmv   t4, a0\n"
    "\tli   a0, 0\n"
    ".mul_loop:\n"
    "\tandi t5, a1, 1\n"
    "\tbeqz t5, .mul_skip\n"
    "\tadd  a0, a0, t4\n"
    ".mul_skip:\n"
    "\tslli t4, t4, 1\n"
    "\tsrli a1, a1, 1\n"
    "\tbnez a1, .mul_loop\n"
    "\tret"
)


def start_preamble(num_cells_used: int) -> str:
    """``.text``/``_start``: point ``s1`` at ``mem``, ``s2``/``s3`` at ip/length.

    ``num_cells_used`` is the compiled program's cell count (``n``), not
    the fixed buffer size -- ``s3`` bounds the fetch-decode-execute loop
    to the program itself, with the rest of the buffer as zeroed scratch.
    """
    return (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    la   s1, mem\n"
        "    li   s2, 0\n"
        f"    li   s3, {num_cells_used}\n"
    )


def cell_load_or_zero(num_cells: int) -> str:
    """Range-check ``a0`` against the cell buffer, load it or return 0.

    Expects ``s1`` = memory base.  Falls through from a caller that has
    already ruled out its own special addresses, so this only needs the
    generic bounds check every ``read_cell`` ends with.
    """
    return (
        "    bltz a0, .zero_ret\n"
        f"    li   t0, {num_cells}\n"
        "    bge  a0, t0, .zero_ret\n"
        "    slli t0, a0, 3\n"
        "    add  t0, s1, t0\n"
        "    ld   a0, 0(t0)\n"
        "    ret\n"
        ".zero_ret:\n"
        "    li   a0, 0\n"
        "    ret\n"
    )


def cell_store_or_drop(num_cells: int) -> str:
    """Range-check ``a0`` against the cell buffer and store ``a1``, or drop.

    Expects ``s1`` = memory base.  Like :func:`cell_load_or_zero`, this is
    the generic bounds check a ``write_cell`` falls through to after its
    own special addresses are ruled out.
    """
    return (
        "    bltz a0, .no_write\n"
        f"    li   t0, {num_cells}\n"
        "    bge  a0, t0, .no_write\n"
        "    slli t0, a0, 3\n"
        "    add  t0, s1, t0\n"
        "    sd   a1, 0(t0)\n"
        ".no_write:\n"
        "    ret\n"
    )


def dump_cells(cells: list[int], num_cells: int) -> str:
    """Render ``.data``/``.align``/dword rows for a fixed-size cell buffer."""
    res = "    .data\n    .align 3\nmem:\n"
    for i in range(0, num_cells, 8):
        row = cells[i : i + 8]
        res += "    .dword " + ", ".join(str(v) for v in row) + "\n"
    return res
