"""Compiler that turns Jaune programs into RISC-V Linux assembly.

Compiled Jaune programs read one character per input operation, so a
program can only input a single character at a time.
"""

from re import findall, sub
from typing import Literal

from esolangs.compilers import _riscv_common as _common
from esolangs.compilers._riscv_common import MUL32, Routine

# The four commands that compile to a called subroutine rather than to
# inline instructions.
_Subr = Literal["^", "v", "<", "&"]

# The three that dispatch through the shared table below; "&" is
# handled by its own arm.  Typed so the membership test narrows the
# command to the key type rather than asserting it afterwards.
_CALLED: frozenset[_Subr] = frozenset(("^", "v", "<"))


def count(code: str, ind: int) -> tuple[int | str, int]:
    """Return the operand value at ``ind`` and the next index.

    Handles digit-run operands, command run-lengths, and the marker commands
    ``: $ @ ? !`` whose operand is the preceding character.

    A digit run is read *forward* and belongs to the operator that follows
    it, which is how the interpreter's ``_parse`` reads it and what makes
    each ``<digits><op>`` an independent command.  Reading a single digit
    backwards instead -- and summing a chain of them -- is what made
    ``10+`` an add of one and collapsed ``5+0+`` into a single add of five.
    """

    # ``at`` stands in for the trailing space this used to append: the scan
    # reads one position of lookahead past the end, and appending a sentinel
    # copied the whole program on every call, which is quadratic over a long
    # program (as it measurably was in the Suffolk and Home Row compilers).
    #
    # The negative index is part of that contract, not an accident.  A sign
    # at index 0 reads ``code[-1]`` for its operand, which on the *padded*
    # string was the appended space -- so it must stay a space here rather
    # than wrapping around to the program's own last character, which is
    # what Python's negative indexing would otherwise give.
    def at(k: int) -> str:
        return code[k] if 0 <= k < len(code) else " "

    start = code[ind]
    num = 0

    if start.isdigit():
        # A digit run is the operand of whatever operator follows it, which
        # is how ``_parse`` reads it: scan the *whole* run forward, then
        # attach it.  Reading a single digit backwards from the operator --
        # what this did before -- made ``10+`` an add of 1 rather than 10,
        # and let a chain like ``5+0+`` be summed into one command instead
        # of the two the interpreter runs.
        j = ind
        while j < len(code) and code[j].isdigit():
            j += 1
        value = int(code[ind:j])
        if at(j) in "+-":
            # The sign belongs to the count, so the caller's ``c`` is the
            # digit and the emitted step has to carry it.
            return (value if at(j) == "+" else -value), j + 1
        # A numbered marker (``: $ @ ? !``) keeps reading its operand from
        # the preceding character, which ``prep`` has already renumbered
        # into a single digit.  A bare number with no operator is a no-op
        # in the interpreter, and falls through to one here.
        return 0, j

    if start in "+-":
        if (n := at(ind - 1)) == "v":
            return n, ind + 1
        # A run like ``++++`` is one counted command of that length, as
        # ``_parse`` reads it.  A digit before the sign was consumed by the
        # digit arm above, which returns past the sign, so reaching here
        # means the sign genuinely starts a run.
        run = 0
        while ind < len(code) and code[ind] == start:
            run += 1
            ind += 1
        return (run if start == "+" else -run), ind
    if start in ":$@?!":
        # These still read a single preceding character, which is safe only
        # because ``prep`` renumbers labels and routines from 0 upward: a
        # program with ten or more of either would spell one ``10:`` and be
        # read here as ``0:``.  Not reachable through ``prep`` today, and
        # left alone rather than widened along with the counts above.
        num = -1 if (c := at(ind - 1)) == "v" else int(c) if c.isdigit() else -1
        ind += 1
    else:
        while at(ind) == start:
            num += 1
            ind += 1
        # A ``v`` immediately before ``+``/``-`` is that operator's operand,
        # not part of this run: ``_parse`` reads ``vv+`` as ``v`` then
        # ``v+``.  Counting it here looped the read an extra time and left
        # the second digit unused.
        if start == "v" and num > 1 and at(ind) in "+-":
            num -= 1
            ind -= 1

    return num, ind


def prep(code: str) -> tuple[str, list[int], list[int]]:
    """Filter to the command alphabet and assign labels to jumps/routines."""

    def rep(sym: str) -> str:
        return sub(r"\d[?!]", "", sym)

    code = sub(r"[^^v><\d+\-#&:?!.$@;%]", "", code)
    code = sub(r"([#.;%])\1+", r"\1", code)
    code = sub("v[:$]", "", code)

    jump: list[int] = []
    rout: list[int] = []

    for c in ":$":
        esc = "\\$" if c == "$" else c
        r = rf"(?:[\d]{esc})+"
        for s in findall(r, code):
            lst = [k for k in s if k.isnumeric()]
            num = jump if c == ":" else rout
            opr = "?!" if c == ":" else "@"

            plus = num[-1] + 1 if num else 0
            num.append(plus)
            m = str(plus)

            for n in lst:
                for k in opr:
                    code = code.replace(n + k, m + k)

            code = code.replace(s, m + c)

    for s in findall(r"(?:[v\d][?!]){2,}", code):
        if "?" in s and "!" in s:
            n = s.find("!") if s[1] == "?" else s.find("?")

            repl = s[:2] + rep(s[2 : n - 1]) + s[n - 1 : n + 1] + rep(s[n + 1 :])
        else:
            repl = s[:2] + rep(s[2:])

        code = code.replace(s, repl)

    return code, jump, rout


def comp(code: str) -> str:
    """Compile a Jaune program to RISC-V assembly with decimal output."""

    def add(m: int) -> str:
        return str(m + 1) if m else ""

    code, jump, rout = prep(code)
    inp = [False, False]
    ind = 0

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi s1, sp, -60\n"
        # The tape floor, fixed once here.  ``left:`` used to recompute it
        # as ``sp - 48`` at the moment of the move, which silently made the
        # floor depend on whatever the stack pointer happened to be -- so a
        # subroutine that saves ``ra`` (16 bytes) moved the floor four cells
        # and ``<`` inside one landed a cell off.  Anchoring it in a saved
        # register keeps the floor a property of the tape rather than of
        # the call depth.
        "    addi s0, sp, -48\n"
        "    li   s2, 0\n"
        "    li   s3, 1\n"
        "    li   s7, 0\n\n"
    )
    subr: dict[_Subr, Routine] = {
        "^": Routine("output"),
        "v": Routine("input"),
        "<": Routine("left"),
        "&": Routine("mult"),
    }

    while ind < len(code):
        c = code[ind]
        num, new = count(code, ind)

        # A digit run is not a command of its own: it is the operand of the
        # operator that follows, and ``count`` has already returned past
        # that operator.  Dispatch on the operator rather than on the digit
        # -- ``10+`` is an add of ten, whose ``c`` would otherwise be "1".
        # A digit run with no operator after it is the interpreter's
        # bare-number no-op, which ``count`` reports as a zero step.
        if c.isdigit():
            # ``count`` returns past the sign when there is one, so the
            # character just before ``new`` says whether this run was an
            # operand or a bare number.  It cannot be read off ``num``: a
            # zero count is a real ``0+``, which adds one.
            sign = code[new - 1] if new and new <= len(code) else ""
            if sign not in "+-":
                ind = new  # a bare number: the interpreter ignores it
                continue
            c = sign

        # ``+``/``-`` is the only command whose operand can be a bare ``v``,
        # which ``count`` reports as a str; taking that arm first leaves
        # ``num`` narrowed to int for every command below.
        if c in "+-":
            if isinstance(num, int):
                # An explicit zero count means one, the same fallback the
                # interpreter spells ``cells[ptr] + (cmd.arg or 1)``.  It has
                # to be re-derived from ``c`` rather than left to ``num``,
                # because ``count`` folds the sign into the value and
                # ``int("-0")`` is ``0`` -- so a bare zero cannot say which
                # direction it meant.  Only ``+``/``-`` take this fallback:
                # a zero count on ``> < ^ &`` is a no-op in the interpreter
                # too, checked against it rather than assumed.
                step = num or (1 if c == "+" else -1)
                res += f"\tlw   t0, 0(s1)\n\taddi t0, t0, {step}\n\tsw   t0, 0(s1)\n"
            elif c == "+":
                res += "\tlw   t0, 0(s1)\n\tadd  t0, t0, s7\n\tsw   t0, 0(s1)\n"
            else:
                res += "\tlw   t0, 0(s1)\n\tsub  t0, t0, s7\n\tsw   t0, 0(s1)\n"
            ind = new
            continue

        if isinstance(num, str):  # pragma: no cover - see the comment above
            raise ValueError(f"unexpected operand {num!r} for {c!r}")

        if c in _CALLED:
            routine = subr[c]
            if num > 1:
                res += f"\tli   s3, {num}\n"
                routine.looped = True
            res += f"\tcall {routine.label}\n"
            routine.used = True
            if c == "v" and code[new : new + 1] not in ("+", "-"):
                # A bare ``v`` stores what it read: ``_advance`` does
                # ``_set(cells, ptr, value)``, so ``v^`` prints the digit.
                # The store is here rather than inside ``input:`` because
                # ``v+``/``v-`` reach the same routine for their operand and
                # must leave the cell alone, adding ``s7`` to what is there.
                res += "\tsw   s7, 0(s1)\n"
        elif c == "&":
            if num > 1:
                res += f"\tli   s3, {num}\n\tcall {subr['&'].label}\n"
                subr["&"].used = subr["&"].looped = True
            else:
                res += "\tlw   t0, 0(s1)\n\tadd  t0, t0, s2\n\tsw   t0, 0(s1)\n"
        elif c == ">":
            res += f"\tli   t0, {4 * num}\n\tsub  s1, s1, t0\n"
        elif c == "#":
            res += "\tlw   s2, 0(s1)\n"
        elif c == ":":
            res += f".label{add(num)}:\n"
        elif c in "?!":
            res += "\tlw   t0, 0(s1)\n"
            jcc = "bnez" if c == "?" else "beqz"
            if num >= 0:
                res += f"\t{jcc} t0, .label{add(num)}\n"
            else:
                res += f"\t{jcc} t0, .switch\n"
                inp[0] = True
        elif c == ".":
            res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n"
        elif c == "$":
            # Save the return address on entry.  Every command that
            # compiles to a ``call`` -- ``^ v < &`` and a nested ``@`` --
            # overwrites ``ra``, so a subroutine containing one used to
            # ``ret`` back into its own body and spin there forever.
            # ``1$#<&;`` was the program that showed it; ``^``, ``v``, a
            # looped ``&`` and a nested ``@`` all hang the same way, which
            # is why this sits at the subroutine boundary rather than in
            # any one routine.  Same idiom as ``output:`` and ``mult:``.
            res += f"sub{add(num)}:\n\taddi sp, sp, -16\n\tsd   ra, 8(sp)\n"
        elif c == "@":
            if num >= 0:
                res += f"\tcall sub{add(num)}\n"
            else:
                res += "\tcall switch\n"
                inp[1] = True
        elif c == ";":
            res += "\tld   ra, 8(sp)\n\taddi sp, sp, 16\n\tret\n"
        elif c == "%":
            res += "\tsw   zero, 0(s1)\n"

        ind = new

    if jump and inp[0]:
        res += "\n.switch:\n"
        for k in jump[:-1]:
            res += f"\tli   t0, {k}\n\tbeq  s7, t0, .lab{add(k)}\n"
        for k in jump[::-1]:
            n = add(k)
            if k != jump[-1]:
                res += f".lab{n}:\n"
            res += f"\tj .label{n}\n"
    if rout and inp[1]:
        res += "\nswitch:\n"
        for k in rout[:-1]:
            res += f"\tli   t0, {k}\n\tbeq  s7, t0, .sub{add(k)}\n"
        res += "\tret\n"
        for k in rout[::-1]:
            n = add(k)
            if k != rout[-1]:
                res += f".sub{n}:\n"
            res += f"\tcall sub{n}\n\tret\n"

    def end(opr: _Subr) -> str:
        if subr[opr].looped:
            mul = (
                "\taddi s3, s3, -1\n"
                f"\tbgt  s3, zero, {subr[opr].label}\n"
                "\taddi s3, s3, 1\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if subr["^"].used:
        res += (
            "\noutput:\n"
            "\taddi sp, sp, -16\n"
            "\tsd   ra, 8(sp)\n"
            "\tlw   s4, 0(s1)\n"
            "\tbltz s4, .out_neg\n"
            "\tmv   t0, s4\n"
            "\tj    .out_pos\n"
            ".out_neg:\n"
            "\tli   t0, '-'\n"
            "\tsb   t0, 0(s1)\n"
            "\tcall print\n"
            "\tsub  t0, x0, s4\n"
            ".out_pos:\n"
            "\taddi sp, sp, -32\n"
            "\taddi s5, sp, 32\n"
            "\tli   s6, 0\n"
            ".out_digits:\n"
            "\tmv   a0, t0\n"
            "\tli   a1, 10\n"
            "\tcall divmod\n"
            "\tmv   t0, a0\n"
            "\taddi s5, s5, -1\n"
            "\taddi t2, a1, 48\n"
            "\tsb   t2, 0(s5)\n"
            "\taddi s6, s6, 1\n"
            "\tbnez t0, .out_digits\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s5\n"
            "\tmv   a2, s6\n"
            "\tecall\n"
            "\taddi sp, sp, 32\n"
            "\tsw   s4, 0(s1)\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 16\n" + end("^") + "\nprint:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tret\n"
            "\n"
            "# a0 / a1: quotient in a0, remainder in a1 (repeated subtraction)\n"
            "divmod:\n"
            "\tli   t0, 0\n"
            ".div_loop:\n"
            "\tbltu a0, a1, .div_done\n"
            "\tsub  a0, a0, a1\n"
            "\taddi t0, t0, 1\n"
            "\tj    .div_loop\n"
            ".div_done:\n"
            "\tmv   a1, a0\n"
            "\tmv   a0, t0\n"
            "\tret\n"
        )
    if subr["v"].used:
        res += (
            # One *line* per read, matching the interpreter's
            # ``io.input_str()``: take the first byte, then drain through
            # the newline so the next ``v`` starts on the next line.  An
            # *empty* line gives 0 (``ord(ch[0]) if ch else 0``), while
            # input that has run out halts, as the interpreter's
            # ``EOFError`` unwinds the run.  The byte lands in a scratch
            # slot below the stack pointer; reading into ``s1 - 4`` left
            # the raw character in the *next* tape cell, so ``v>^`` printed
            # 49 rather than 0.
            "\ninput:\n"
            "\taddi sp, sp, -16\n"
            "\tli   s7, 0\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, sp\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tblez a0, .in_eof\n"
            "\tlbu  s7, 0(sp)\n"
            "\tli   t0, 10\n"
            "\tbeq  s7, t0, .in_empty\n"
            "\taddi s7, s7, -48\n"
            ".in_skip:\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, sp\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tblez a0, .in_done\n"
            "\tlbu  t1, 0(sp)\n"
            "\tli   t0, 10\n"
            "\tbne  t1, t0, .in_skip\n"
            "\tj    .in_done\n"
            ".in_empty:\n"
            "\tli   s7, 0\n"
            ".in_done:\n"
            "\taddi sp, sp, 16\n" + end("v") + ".in_eof:\n"
            "\tli   a0, 0\n"
            "\tli   a7, 93\n"
            "\tecall\n"
        )
    if subr["<"].used:
        res += (
            "\nleft:\n"
            "\tslli t0, s3, 2\n"
            "\tadd  s1, s1, t0\n"
            "\tbge  s0, s1, .left_done\n"
            "\tmv   s1, s0\n"
            ".left_done:\n"
            "\tret\n"
        )
    if subr["&"].used:
        res += (
            "\nmult:\n"
            "\taddi sp, sp, -16\n"
            "\tsd   ra, 8(sp)\n"
            "\tmv   a0, s2\n"
            "\tmv   a1, s3\n"
            "\tcall mul32\n"
            "\tlw   t0, 0(s1)\n"
            "\tadd  t0, t0, a0\n"
            "\tsw   t0, 0(s1)\n"
            # `mult` takes its multiplier in s3, the shared loop counter,
            # and unlike the looped routines it never counts back down.
            # Leaving it set made the *next* counted command repeat that
            # many times -- `&&^` printed twice.
            "\tli   s3, 1\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 16\n"
            "\tret\n"
            "\n" + MUL32 + "\n"
        )

    return res.replace("\n\n\n", "\n\n")


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
