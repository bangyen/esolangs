"""Compiler that turns Jaune programs into RISC-V Linux assembly.

Compiled Jaune programs read one character per input operation, so a
program can only input a single character at a time.
"""

from re import Match, findall, sub
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
        # ``prep`` can assign a marker number above nine, so walk back over
        # the whole run it emitted.  The interpreter parses the same
        # ``<digits><marker>`` shape forward as one numbered command.
        j = ind
        while j > 0 and code[j - 1].isdigit():
            j -= 1
        operand = code[j:ind]
        num = -1 if at(ind - 1) == "v" else int(operand) if operand else -1
        ind += 1
    else:
        while at(ind) == start:
            num += 1
            ind += 1
        # A ``v`` immediately before an operator that takes a number is that
        # operator's operand, not part of this run: ``_parse`` reads ``vv+``
        # as ``v`` then ``v+``, and ``vv?`` as ``v`` then ``v?``.  Counting
        # it here looped the read an extra time and left the second digit
        # unused.
        if start == "v" and num > 1 and at(ind) in "+-?!@":
            num -= 1
            ind -= 1

    return num, ind


def prep(
    code: str,
) -> tuple[str, list[int], list[int], dict[str, list[tuple[int, int]]]]:
    """Filter to the command alphabet and assign labels to jumps/routines.

    The fourth element is what a *computed* jump or call needs: the numbers
    the source spelled, paired with the ones they were renumbered to, under
    ``":"`` for labels and ``"$"`` for subroutines.  A static ``1@`` is
    rewritten to the new number at compile time and never needs it, but
    ``v@`` compares an input digit against what the program spelled, so the
    switch has to know both.  It is a list of pairs rather than a dict
    because a *run* of adjacent markers (``1:2:``) collapses to a single
    label, leaving several originals sharing one renumbered target.
    """

    def rep(sym: str) -> str:
        return sub(r"\d[?!]", "", sym)

    code = sub(r"[^^v><\d+\-#&:?!.$@;%]", "", code)
    code = sub(r"([#.;%])\1+", r"\1", code)
    code = sub("v[:$]", "", code)

    jump: list[int] = []
    rout: list[int] = []
    spelled: dict[str, list[tuple[int, int]]] = {":": [], "$": []}

    mappings: dict[str, dict[int, int]] = {":": {}, "$": {}}
    for c in ":$":
        esc = "\\$" if c == "$" else c
        num = jump if c == ":" else rout

        def renumber(
            match: Match[str],
            marker: str = c,
            target: list[int] = num,
            token_pattern: str = rf"(\d+){esc}",
        ) -> str:
            # The pattern guarantees a regex match; keeping the callback
            # local lets each occurrence be rewritten exactly once instead
            # of finding its spelling again inside a newly emitted ``10:``.
            text = match.group(0)
            originals = [int(n) for n in findall(token_pattern, text)]
            new = target[-1] + 1 if target else 0
            target.append(new)
            spelled[marker].extend((old, new) for old in originals)
            for old in originals:
                mappings[marker].setdefault(old, new)
            return f"{new}{marker}"

        code = sub(rf"(?:\d+{esc})+", renumber, code)

    def rewrite_jump(match: Match[str]) -> str:
        text = match.group(0)
        old = int(text[:-1])
        return f"{mappings[':'].get(old, old)}{text[-1]}"

    def rewrite_call(match: Match[str]) -> str:
        text = match.group(0)
        old = int(text[:-1])
        return f"{mappings['$'].get(old, old)}@"

    code = sub(r"\d+[?!]", rewrite_jump, code)
    code = sub(r"\d+@", rewrite_call, code)

    for s in findall(r"(?:[v\d][?!]){2,}", code):
        if "?" in s and "!" in s:
            n = s.find("!") if s[1] == "?" else s.find("?")

            repl = s[:2] + rep(s[2 : n - 1]) + s[n - 1 : n + 1] + rep(s[n + 1 :])
        else:
            repl = s[:2] + rep(s[2:])

        code = code.replace(s, repl)

    return code, jump, rout, spelled


def comp(code: str) -> str:
    """Compile a Jaune program to RISC-V assembly with decimal output."""

    def add(m: int) -> str:
        return str(m + 1) if m else ""

    code, jump, rout, spelled = prep(code)
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
        # The floor is cell 0 itself.  It used to sit at ``sp - 48``, three
        # cells to the *right* of the ``sp - 60`` start (the tape grows
        # downward), so ``<`` at cell 0 stepped into scratch below the tape
        # instead of clamping: ``5+<^.`` printed 0 where the interpreter now
        # prints 5.  Anchoring the floor at the start cell makes ``<`` a
        # no-op there, matching ``_advance``.
        "    addi s0, sp, -60\n"
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
            if c == "v" and code[new : new + 1] not in ("+", "-", "?", "!", "@"):
                # A bare ``v`` stores what it read: ``_advance`` does
                # ``_set(cells, ptr, value)``, so ``v^`` prints the digit.
                # The store is here rather than inside ``input:`` because
                # every operator taking a read operand reaches the same
                # routine and must leave the cell alone: ``v+``/``v-`` add
                # ``s7`` to what is there, and ``v?``/``v!``/``v@`` select
                # on it without touching the tape.  Storing for those three
                # put the digit in cell 0, which is what made ``v@`` print
                # its own input instead of calling the subroutine it names.
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
                # The ``v`` before the marker is its own command and has
                # already emitted the read, leaving the digit in ``s7`` for
                # the switch to select on -- the same division of labour
                # ``v+`` uses.  Because that read runs before the branch is
                # tested, the digit is consumed whether or not the jump is
                # taken, which is the interpreter's rule too.
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
                # As with ``v?`` above, the preceding ``v`` has already read
                # the digit ``switch`` selects on.
                res += "\tcall switch\n"
                inp[1] = True
        elif c == ";":
            res += "\tld   ra, 8(sp)\n\taddi sp, sp, 16\n\tret\n"
        elif c == "%":
            res += "\tsw   zero, 0(s1)\n"

        ind = new

    # The switches select on ``s7``, the digit the preceding ``v`` read, and
    # so compare against the numbers the *source* spelled rather than the
    # ones ``prep`` renumbered to: a program naming label 3 is asking for
    # the input 3, whatever index the label ended up with.  Comparing the
    # renumbered index instead is what made every computed jump miss.
    #
    # An input naming no label or no subroutine falls through: the call
    # switch returns and the jump switch continues at the branch, where the
    # interpreter raises ``HaltError`` instead.  The compiled program has no
    # error path to raise on, so this stays a documented divergence rather
    # than an emitted trap.
    if jump and inp[0]:
        res += "\n.switch:\n"
        for spell, k in spelled[":"]:
            res += f"\tli   t0, {spell}\n\tbeq  s7, t0, .lab{add(k)}\n"
        res += "\tj .switch_end\n"
        for k in jump:
            res += f".lab{add(k)}:\n\tj .label{add(k)}\n"
        res += ".switch_end:\n"
    if rout and inp[1]:
        # ``switch`` is itself reached by ``call``, and each arm below is a
        # further ``call`` that overwrites ``ra`` -- the same clobber the
        # ``$`` prologue fixes for a subroutine body.  Without a frame here
        # the arm's ``ret`` returns into ``switch`` rather than to the
        # caller and the program spins, which is what ``v@`` did.
        res += "\nswitch:\n\taddi sp, sp, -16\n\tsd   ra, 8(sp)\n"
        for spell, k in spelled["$"]:
            res += f"\tli   t0, {spell}\n\tbeq  s7, t0, .sub{add(k)}\n"
        res += "\tld   ra, 8(sp)\n\taddi sp, sp, 16\n\tret\n"
        for k in rout:
            res += (
                f".sub{add(k)}:\n\tcall sub{add(k)}\n"
                "\tld   ra, 8(sp)\n\taddi sp, sp, 16\n\tret\n"
            )

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
