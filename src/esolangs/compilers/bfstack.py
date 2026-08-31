"""Compiler that turns BFStack programs into RISC-V Linux assembly."""

import itertools
import re
import sys
from dataclasses import dataclass


@dataclass
class _Routine:
    """One of the four helper subroutines a BFStack program may call.

    ``used`` records that the program calls it at all (so its body is
    emitted), and ``looped`` that some call site passed a repeat count (so
    the body needs the counter loop around it).
    """

    label: str
    used: bool = False
    looped: bool = False


def parse(code: str) -> list[tuple[str, int]]:
    """Normalize a BFStack program into ``(command, count)`` tokens.

    Filters to the command alphabet, cancels adjacent opposite increments,
    drops loops that are removed by a skip, and collapses zeroing and runs of
    identical commands.
    """

    def con(*s: str) -> tuple[str, int]:
        if s[0] in "+-":
            x = s.count("+")
            y = s.count("-")
            return "+", x - y
        return s[0], len(s)

    def key(v: str) -> str:
        if v in "+-":
            return "+"
        return v

    filtered = re.sub(r"[^><+-.,\][]", "", code)

    while re.search(r"(>[+-]*<|\+-|-\+)", filtered):
        filtered = re.sub(">[+-]*<", "", filtered)
        filtered = filtered.replace("+-", "").replace("-+", "")

    while m := re.search(r"[>\]]\[", filtered):
        ind = m.start() + 1
        mat = 1

        while mat:
            ind += 1
            if ind == len(filtered):
                return []
            if (c := filtered[ind]) == "[":
                mat += 1
            elif c == "]":
                mat -= 1

        filtered = filtered[: m.start() + 1] + filtered[ind + 1 :]

    filtered = re.sub(r"[+-]*\[[+-]]", "0", filtered)
    filtered = re.sub("[+-]+<", "<", filtered)
    grouped = itertools.groupby(filtered, key=key)
    return [con(*g) for _, g in grouped]


def comp(code: str) -> str:
    """Compile a BFStack program to RISC-V assembly with syscall I/O."""
    tokens = parse(code)
    jump = 0
    arr = []
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi s1, sp, -6\n"
        "    li   s2, 1\n"
        "    addi s3, sp, -1\n\n"
    )

    ins = {
        ">": _Routine("right"),
        "<": _Routine("left"),
        ".": _Routine("output"),
        ",": _Routine("input"),
    }

    for char, num in tokens:
        if char == "+":
            # ``parse`` strips every ``+-`` and ``-+`` pair before grouping,
            # so a group is all pluses or all minuses and its net is never
            # zero.  The test stays as the guard the emitted ``addi`` needs.
            if num:  # pragma: no branch - a zero-net group cannot survive parse
                res += f"\tlbu  t0, 0(s1)\n\taddi t0, t0, {num}\n\tsb   t0, 0(s1)\n"
        elif char == "0":
            res += "\tsb   zero, 0(s1)\n"
        elif char in "><.,":
            if num > 1:
                res += f"\tli   s2, {num}\n"
                ins[char].looped = True
            res += f"\tcall {ins[char].label}\n"

            ins[char].used = True
        else:
            # ``parse`` keeps only ``><+-.,[]``, rewrites ``[+-]`` to ``0``,
            # and groups ``-`` under ``+``, so the only tokens left here are
            # the brackets.
            for _ in range(num):
                if char == "[":
                    jump += 1
                    arr.append(jump)
                    res += f".T{jump}:\n\tlbu  t0, 0(s1)\n\tbeqz t0, .B{jump}\n"
                elif arr:
                    m = arr.pop()
                    res += f"\tj .T{m}\n.B{m}:\n"

    res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n"

    def end(s: str, *, mul: bool) -> str:
        return (
            mul * ("\taddi s2, s2, -1\n\tbgt  s2, zero, " + s + "\n\taddi s2, s2, 1\n")
            + "\tret\n"
        )

    if ins[">"].used:
        res += "\nright:\n\taddi s1, s1, -1\n\tsb   zero, 0(s1)\n" + end(
            "right", mul=ins[">"].looped
        )
    if ins["<"].used:
        res += "\nleft:\n\tbeq  s1, s3, .done_left\n\taddi s1, s1, 1\n"
        if ins["<"].looped:
            res += "\taddi s2, s2, -1\n\tbgt  s2, zero, left\n\taddi s2, s2, 1\n"
        res += ".done_left:\n\tret\n"
    if ins["."].used:
        res += (
            "\noutput:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n" + end("output", mul=ins["."].looped)
        )
    if ins[","].used:
        res += (
            "\ninput:\n"
            "\taddi s1, s1, -1\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n" + end("input", mul=ins[","].looped)
        )

    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
