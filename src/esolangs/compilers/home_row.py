"""Compiler that turns Home Row programs into RISC-V Linux assembly."""

import sys
from re import sub


def count(code: str, ind: int) -> tuple[int, int]:
    """Return the run length of the command at ``ind`` and the next index."""
    code += " "
    num = 0

    if (start := code[ind]) in "as":
        while (ins := code[ind]) in "as":
            if ins == "a":
                num += 1
            else:
                num -= 1
            ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def comp(code: str) -> str:
    """Compile a Home Row program to RISC-V assembly on a 5x5 zeroed grid."""
    res = ""

    func = {
        "d": ["down", False, False],
        "f": ["right", False, False],
        "k": ["print", False, False],
    }

    reg = [
        ("[^asdfjkl;]", ""),
        ("([^j])k{2,}", r"\1k"),
        (";{2,}", ";"),
        ("^((ddddd)+|(fffff)+|k*j[^l]|k*l[^l]*l|k+)", ""),
        ("([^j])((ddddd)+|(fffff)+)", r"\1"),
        ("([^j]k)(j[^l]|l[^l]*l)", r"\1"),
    ]

    for x, y in reg:
        code = sub(x, y, code)

    skip = ind = 0
    end = False
    loop = 1

    while ind < len(code):
        num, new = count(code, ind)
        c = code[ind]

        if c in "as":
            if ind and code[ind - 1] == "j":
                num = 1 if c == "a" else -1
                new = ind + 1

            if num:
                res += f"\tlw   t0, 0(s1)\n\taddi t0, t0, {num}\n\tsw   t0, 0(s1)\n"
        elif c in "dfk":
            if ind and code[ind - 1] == "j":
                num, new = 1, ind + 1

            # always set t3: the movement/print subroutines are shared
            # between counted and single calls, so a single call must not
            # rely on a stale t3 from a previous counted run
            res += f"\tli   t3, {num}\n"
            res += f"\tcall {func[c][0]}\n"
            func[c][1] = True
            func[c][2] = True
        elif c == "j":
            skip += 1
            ind = new
            end = True

            n = skip if skip - 1 else ""
            res += f"\tlw   t0, 0(s1)\n\tbeqz t0, .skip{n}\n"

            continue
        elif c == "l":
            loop += 1
            n = m if (m := (loop // 2 - 1)) else ""
            res += "\tlw   t0, 0(s1)\n"

            if loop % 2:
                res += f"\tbnez t0, .top{n}\n.bot{n}:\n"
            else:
                res += f"\tbeqz t0, .bot{n}\n.top{n}:\n"
        else:
            # The first rewrite strips everything outside ``asdfjkl;`` and
            # the arms above take ``a s d f j k l``, so this is ``;``.
            res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n"

        if end:
            n = skip if skip - 1 else ""
            res += f".skip{n}:\n"
            end = False
        ind = new

    def cell(r: str) -> str:
        return (
            "\t# cell address for the coordinate in "
            + r
            + ": s1 = sp + 20*"
            + r
            + " + 4*s5\n"
            "\tslli t1, t0, 4\n"
            "\tslli t2, t0, 2\n"
            "\tadd  t1, t1, t2\n"
            "\tadd  t1, t1, sp\n"
            "\tslli t2, s5, 2\n"
            "\tadd  s1, t1, t2\n"
        )

    if func["d"][1]:
        s = "\tadd  s4, s4, t3\n"
        # wrap mod 5 (the 5x5 grid): subtract 5 once the index reaches 5
        s += "\tli   t4, 5\n\tblt  s4, t4, .down_ok\n\taddi s4, s4, -5\n.down_ok:\n"

        s += "\tmv   t0, s4\n" + cell("t0")

        res += "\ndown:\n" + s + "\tret\n"
    if func["f"][1]:
        s = "\tadd  s5, s5, t3\n"
        s += "\tli   t4, 5\n\tblt  s5, t4, .right_ok\n\taddi s5, s5, -5\n.right_ok:\n"

        s += "\tmv   t0, s5\n" + cell("t0")

        res += "\nright:\n" + s + "\tret\n"
    if func["k"][1]:
        b = func["k"][2]
        res += (
            "\nprint:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tsw   zero, 0(s1)\n"
            + ("\taddi t3, t3, -1\n\tbgt  t3, zero, print\n\taddi t3, t3, 1\n")
            * bool(b)
            + "\tret\n"
        )

    s = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi sp, sp, -100\n"
        "    mv   s1, sp\n"
        # the spec's 5x5 grid initializes to zero
        "    li   s3, 25\n"
        ".zero_grid:\n"
        "    sw   zero, 0(s1)\n"
        "    addi s1, s1, 4\n"
        "    addi s3, s3, -1\n"
        "    bnez s3, .zero_grid\n"
        "    mv   s1, sp\n"
        "    li   s4, 0\n"
        "    li   s5, 0\n"
    )

    return (f"{s}\n" + res).replace("\n\n\n", "\n\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
