"""Compiler that turns Collatz Multiverse programs into RISC-V Linux assembly."""

import re
from typing import cast

from esolangs.compilers import _riscv_common as _common

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_LINE = re.compile(
    rf"^\s*({_NAME})(?:\[({_NAME})\])?\s*=\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*x\s*\+\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*,\s*(DO|NOT)\s+PRINT\.\s*$"
)

# Each named array gets this many direct-indexed slots, wrapped with a
# modulo (matching RAM0's fixed-256-cell tradeoff for unbounded indices).
_ARRAY_SIZE = 256


_Line = tuple[str, str | None, str, str | None, str, str | None, str]


def parse(code: str) -> list[_Line]:
    """Parse non-blank lines into ``(var1, idx1, var2, idx2, var3, idx3, DO|NOT)``."""
    lines = [ln for ln in code.splitlines() if ln.strip()]
    parsed: list[_Line] = []
    for ln in lines:
        m = _LINE.fullmatch(ln)
        if not m:
            raise ValueError(f"malformed line: {ln!r}")
        var1, idx1, var2, idx2, var3, idx3, do_print = m.groups()
        # Groups 1, 3, 5, 7 are not optional in the pattern, so they are
        # always matched when fullmatch succeeds.
        parsed.append(
            (
                cast(str, var1),
                idx1,
                cast(str, var2),
                idx2,
                cast(str, var3),
                idx3,
                cast(str, do_print),
            )
        )
    return parsed


def comp(code: str) -> str:
    """Compile a Collatz Multiverse program to RISC-V assembly.

    Every line's target and operands are statically known, so each line
    compiles to a labelled block (``.L{i}``, 1-indexed to match
    ``lineNumber``) that falls through to ``.L{i+1}``.  The only runtime
    indirection is an assignment to ``lineNumber``: since the jump target is
    a computed value, ``line_jump`` (a linear compare-and-branch scan over
    ``1..n``, the same table-scan shape as Jaune's ``.switch``) dispatches
    it, landing on ``.halt`` when the target falls outside ``1..n`` --
    program entry is just a ``line_jump`` from line 0.

    Scalar variables get one ``.dword`` slot apiece in a compile-time symbol
    table (``negativeOne`` pre-seeded -1, everything else 0, matching the
    interpreter); ``lineNumber`` is a register (``s2``) rather than a slot,
    since every read needs the *current* line.  Named arrays get
    ``_ARRAY_SIZE`` slots each, direct-indexed with a wrapping modulo for
    the unbounded index space (the same fixed-window tradeoff RAM0's
    compiler makes).  ``input`` parses a whole stdin line as a signed
    decimal integer, one byte at a time, stopping at a newline or EOF
    (unlike Suffolk's single-byte read).
    """
    parsed = parse(code)
    n = len(parsed)

    for var1, *_rest in parsed:
        if var1 == "input":
            raise ValueError("input cannot be redefined")

    scalars: dict[str, int] = {"negativeOne": 0}
    arrays: dict[str, int] = {}

    for var1, idx1, var2, idx2, var3, idx3, _ in parsed:
        for name, idx in ((var1, idx1), (var2, idx2), (var3, idx3)):
            if idx is not None:
                if name not in arrays:
                    arrays[name] = len(arrays)
                if idx not in scalars:
                    scalars[idx] = len(scalars)
            elif name not in ("input", "lineNumber") and name not in scalars:
                scalars[name] = len(scalars)

    n_scalars = len(scalars)

    def read_into(reg: str, name: str, idx: str | None) -> str:
        """Emit code loading ``name[idx]`` (or the bare ``name``) into ``reg``."""
        if name == "input":
            return f"\tcall read_input\n\tmv   {reg}, a0\n"
        if name == "lineNumber":
            return f"\tmv   {reg}, s2\n"
        if idx is not None:
            arr = arrays[name]
            idx_slot = scalars[idx]
            return (
                f"\tld   a0, {8 * idx_slot}(s4)\n"
                "\tcall array_index\n"
                "\tslli t6, a0, 3\n"
                f"\tla   t5, arr{arr}\n"
                "\tadd  t5, t5, t6\n"
                f"\tld   {reg}, 0(t5)\n"
            )
        slot = scalars[name]
        return f"\tld   {reg}, {8 * slot}(s4)\n"

    def write_from(reg: str, name: str, idx: str | None) -> str:
        """Emit code storing ``reg`` into ``name[idx]`` (or the bare ``name``)."""
        if idx is not None:
            arr = arrays[name]
            idx_slot = scalars[idx]
            return (
                f"\tld   a0, {8 * idx_slot}(s4)\n"
                "\tcall array_index\n"
                "\tslli t6, a0, 3\n"
                f"\tla   t5, arr{arr}\n"
                "\tadd  t5, t5, t6\n"
                f"\tsd   {reg}, 0(t5)\n"
            )
        slot = scalars[name]
        return f"\tsd   {reg}, {8 * slot}(s4)\n"

    body = ""
    for i, (var1, idx1, var2, idx2, var3, idx3, do_print) in enumerate(parsed):
        line = i + 1
        body += f".L{line}:\n"
        body += f"\tli   s2, {line}\n"
        body += read_into("t0", var2, idx2)  # a
        body += read_into("t1", var3, idx3)  # b
        body += read_into("t2", var1, idx1)  # t (current value)
        body += (
            f"\tbeqz t2, .odd{line}\n"
            "\tandi t3, t2, 1\n"
            f"\tbnez t3, .odd{line}\n"
            "\tsrai t2, t2, 1\n"
            f"\tj    .done{line}\n"
            f".odd{line}:\n"
            "\tmv   a0, t0\n"
            "\tmv   a1, t1\n"
            "\tcall collatz_odd\n"  # a0 = t0 * (old t2, passed via a2) + t1
            "\tmv   t2, a0\n"
            f".done{line}:\n"
        )

        if var1 == "lineNumber":
            body += "\tmv   a0, t2\n\tj    dispatch\n"
        else:
            body += write_from("t2", var1, idx1)
            if do_print == "DO":
                body += "\tmv   a0, t2\n\tcall write_byte\n"
            target = f".L{line + 1}" if line < n else ".halt"
            body += f"\tj    {target}\n"

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        # The linker relaxes later "la" references to .data (arrN) into
        # gp-relative addi, so gp needs the usual startup value -- there is
        # no libc to set it here.
        "    la   gp, __global_pointer$\n"
        "    la   s4, scalars\n"
        f"    li   t0, {8 * n_scalars}\n"
        "    add  t1, s4, t0\n"
        "1:\n"
        "    bge  s4, t1, 2f\n"
        "    sd   zero, 0(s4)\n"
        "    addi s4, s4, 8\n"
        "    j    1b\n"
        "2:\n"
        "    la   s4, scalars\n"
        "    li   t0, -1\n"
        "    sd   t0, 0(s4)\n"  # negativeOne = -1
        "    li   a0, 1\n"
        "    j    dispatch\n"
    )

    res += body
    res += ".halt:\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n"

    res += (
        "\n"
        "# dispatch: jump to .L{a0}, or .halt if a0 is outside 1..n\n"
        "dispatch:\n"
        "\tmv   s2, a0\n"
    )
    for line in range(1, n + 1):
        res += f"\tli   t0, {line}\n\tbeq  s2, t0, .L{line}\n"
    res += "\tj    .halt\n"

    res += (
        "\n"
        "# array_index(idx: a0) -> a0, wrapped into 0.._ARRAY_SIZE-1\n"
        "# (_ARRAY_SIZE is a power of two, so a bitmask is the wrapped modulo\n"
        "# even for negative idx, without needing the M extension's rem)\n"
        "array_index:\n"
        f"\tandi a0, a0, {_ARRAY_SIZE - 1}\n"
        "\tret\n"
        "\n"
        "# collatz_odd(a: a0, b: a1) -> a0 = t2 * a0 + a1 (t2 = current value)\n"
        "collatz_odd:\n"
        "\tmv   t4, t2\n"  # magnitude accumulator, doubled each pass
        "\tmv   t5, a0\n"  # remaining multiplier
        "\tli   t6, 0\n"  # sign of the product (0 = same sign, 1 = flip)
        "\tbgez t4, 1f\n"
        "\tsub  t4, x0, t4\n"
        "\txori t6, t6, 1\n"
        "1:\n"
        "\tbgez t5, 2f\n"
        "\tsub  t5, x0, t5\n"
        "\txori t6, t6, 1\n"
        "2:\n"
        "\tli   a0, 0\n"
        "3:\n"
        "\tbeqz t5, 4f\n"
        "\tandi t3, t5, 1\n"
        "\tbeqz t3, 5f\n"
        "\tadd  a0, a0, t4\n"
        "5:\n"
        "\tslli t4, t4, 1\n"
        "\tsrli t5, t5, 1\n"
        "\tj    3b\n"
        "4:\n"
        "\tbeqz t6, 6f\n"
        "\tsub  a0, x0, a0\n"
        "6:\n"
        "\tadd  a0, a0, a1\n"
        "\tret\n"
        "\n"
        "# write_byte(value: a0)\n"
        "write_byte:\n"
        "\taddi sp, sp, -16\n"
        "\tsd   ra, 8(sp)\n"
        "\tandi t0, a0, 0xff\n"
        "\tsb   t0, 0(sp)\n"
        "\tli   a7, 64\n"
        "\tli   a0, 1\n"
        "\tmv   a1, sp\n"
        "\tli   a2, 1\n"
        "\tecall\n"
        "\tld   ra, 8(sp)\n"
        "\taddi sp, sp, 16\n"
        "\tret\n"
        "\n"
    )

    # `read_input` is emitted only when the program has an input line to
    # call it -- the same `used`-flag gate the tape compilers apply to
    # their subroutines.  `x + <input>` is the only command that reaches
    # it, and nothing dispatches to it indirectly.
    if "\tcall read_input\n" in res:
        res += (
            "# read_input() -> a0: parse one stdin line as a signed decimal integer.\n"
            "# EOF before any byte of the line is read halts, matching the\n"
            "# interpreter's EOFError convention; EOF after some digits (the last\n"
            "# line with no trailing newline) still returns the parsed value.\n"
            "read_input:\n"
            "\taddi sp, sp, -32\n"
            "\tsd   ra, 8(sp)\n"
            "\tsd   s0, 16(sp)\n"  # accumulator
            "\tsd   s1, 24(sp)\n"  # sign flag
            "\tli   s0, 0\n"
            "\tli   s1, 0\n"
            "\tli   t2, 0\n"  # any byte of this line consumed yet
            ".ri_loop:\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, sp\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tbgtz a0, .ri_have_byte\n"
            "\tbnez t2, .ri_done\n"
            "\tj    .halt\n"
            ".ri_have_byte:\n"
            "\tli   t2, 1\n"
            "\tlbu  t0, 0(sp)\n"
            "\tli   t1, 10\n"
            "\tbeq  t0, t1, .ri_done\n"  # '\\n'
            "\tli   t1, 45\n"  # '-'
            "\tbne  t0, t1, .ri_digit\n"
            "\tli   s1, 1\n"
            "\tj    .ri_loop\n"
            ".ri_digit:\n"
            "\taddi t0, t0, -48\n"
            "\tli   t1, 10\n"
            "\tmv   a0, s0\n"
            "\tmv   a1, t1\n"
            "\tcall mul_small\n"
            "\tadd  s0, a0, t0\n"
            "\tj    .ri_loop\n"
            ".ri_done:\n"
            "\tmv   a0, s0\n"
            "\tbeqz s1, .ri_ret\n"
            "\tsub  a0, x0, a0\n"
            ".ri_ret:\n"
            "\tld   s0, 16(sp)\n"
            "\tld   s1, 24(sp)\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 32\n"
            "\tret\n"
            "\n"
        )

    res += (
        "# mul_small(a0, a1) -> a0 = a0 * a1 (unsigned, small multiplier)\n"
        "mul_small:\n"
        "\tmv   t4, a0\n"
        "\tmv   t5, a1\n"
        "\tli   a0, 0\n"
        "1:\n"
        "\tbeqz t5, 2f\n"
        "\tandi t6, t5, 1\n"
        "\tbeqz t6, 3f\n"
        "\tadd  a0, a0, t4\n"
        "3:\n"
        "\tslli t4, t4, 1\n"
        "\tsrli t5, t5, 1\n"
        "\tj    1b\n"
        "2:\n"
        "\tret\n"
    )

    res += "\n    .data\n    .align 3\nscalars:\n"
    res += f"    .space {8 * max(n_scalars, 1)}\n"
    for arr_slot in arrays.values():
        res += f"    .align 3\narr{arr_slot}:\n    .space {8 * _ARRAY_SIZE}\n"

    return res


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
