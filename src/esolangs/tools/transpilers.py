"""Transpile programs between languages.

Each ``TRANSPILERS`` entry maps a ``(source, target)`` language-name pair to
a function that rewrites a program in the source language into an
equivalent program in the target.  A target is only added when its in-repo
interpreter matches the source language's semantics, so every transpiler is
verified end-to-end: the source runs on its interpreter, the target on its
own, and the outputs must agree.
"""

import importlib
import re
from collections.abc import Callable
from typing import Any, cast

__all__ = [
    "TRANSPILERS",
    "ascii_art_to_bf",
    "basicfuck_to_bf",
    "bf_to_ascii_art",
    "bf_to_circlefuck",
    "bf_to_six_five",
    "bfstack_to_bf",
    "bio_to_bf",
    "huf_to_bf",
    "nocomment_to_bf",
]

# The eight brainfuck commands -> their ASCII-art blocks.  This is the
# single source of truth for the art alphabet; ``ascii-art.parse`` decodes
# exactly these blocks (by line count and final character).
_BF_ASCII_ART_BLOCKS = {
    "-": "-",
    ".": "#\n#",
    ",": "|\n|\n|",
    "<": "\\\n\\\n\\\n\\",
    ">": "/\n/\n/\n/",
    "+": "|\n|\n|\n|\n|",
    "[": "_\n_\n_\n_\n_\n_",
    "]": "|\n|\n|\n|\n|\n|",
}


def bf_to_ascii_art(program: str) -> str:
    """Rewrite a brainfuck program as ASCII art.

    Each command becomes its art block; anything that is not a brainfuck
    command is dropped.  The empty program stays empty.
    """
    return "\n\n".join(
        _BF_ASCII_ART_BLOCKS[c] for c in program if c in _BF_ASCII_ART_BLOCKS
    )


def ascii_art_to_bf(program: str) -> str:
    """Rewrite an ASCII-art program back to brainfuck.

    This is the ASCII-art interpreter's own decoder: ``ascii-art.parse``
    maps the art blocks to brainfuck commands, so the translation runs
    identically by construction.  Unknown blocks are ignored and the empty
    program stays empty.
    """
    parse = cast(
        Callable[[str], str],
        importlib.import_module("esolangs.interpreters.tape_based.ascii_art").parse,
    )
    return parse(program)


def _auto_size(ops: list[str]) -> int:
    """Compute the smallest data region that contains the program's pointer.

    Walks the filtered commands tracking the pointer's minimum and maximum
    reach.  A loop whose body returns to its entry pointer (net-zero
    displacement) can never drift the pointer, so its reach is bounded by
    the body's own excursions regardless of how many times it runs.  The
    empty program needs one cell.
    """
    stack: list[int] = []
    match: dict[int, int] = {}
    for i, c in enumerate(ops):
        if c == "[":
            stack.append(i)
        elif c == "]" and stack:
            j = stack.pop()
            match[i] = j
            match[j] = i

    def scan(i: int, end: int, p: int) -> tuple[int, int, int, bool]:
        lo = hi = p
        while i < end:
            c = ops[i]
            if c == ">":
                p += 1
                hi = max(hi, p)
            elif c == "<":
                p -= 1
                lo = min(lo, p)
            elif c == "[":
                j = match.get(i)
                if j is None or j >= end:
                    raise ValueError("unbalanced brackets cannot be transpiled")
                blo, bhi, bend, ok = scan(i + 1, j, p)
                if not ok:
                    return (lo, hi, p, False)
                hi = max(hi, bhi)
                lo = min(lo, blo)
                if bend != p:
                    return (lo, hi, p, False)
                i = j + 1
                continue
            i += 1
        return (lo, hi, p, True)

    lo, hi, _, ok = scan(0, len(ops), 0)
    if lo < 0:
        raise ValueError(
            "the program moves its data pointer below cell 0, where brainfuck "
            "clamps but Circlefuck's tape wraps around",
        )
    if not ok:
        raise ValueError(
            "the program has a loop that drifts the data pointer without bound; "
            "pass size explicitly if the program stays within [0, size)",
        )
    return hi + 1


def bf_to_circlefuck(program: str, size: int | None = None) -> str:
    """Rewrite a brainfuck program into Circlefuck.

    Circlefuck's tape is the program itself, so a clean data region must be
    set up first.  Each of the ``size`` data cells holds ``>`` -- the only
    command whose value (62) is not a bracket -- so the setup walk can move
    past them and zero each with an exact run of ``-``s without ever writing
    a ``[``/``]`` character (Circlefuck's bracket matching reads the current
    cell values, so a zeroed ``[`` would no longer be a bracket).  The
    brainfuck commands then follow unchanged: Circlefuck's ``[``/``]``
    already test the cell at the data pointer.  ``@`` halts.

    The data pointer must stay within ``[0, size)``: moving below cell 0
    wraps around to the end of the program (where brainfuck clamps), and
    moving past cell ``size - 1`` enters the setup code.  When ``size`` is
    omitted it is computed from the program: the smallest bound that holds
    for every loop whose body has net-zero pointer displacement.  Programs
    with loops that drift the pointer, or that move below cell 0, are
    rejected rather than silently mistranslated; pass ``size`` explicitly to
    cover a program you know stays in bounds.
    """
    ops = [c for c in program if c in "+-<>.,[]"]
    if size is None:
        size = _auto_size(ops)
    if size < 1:
        raise ValueError(f"size must be positive, got {size}")
    setup = ">" * size + ("<" + "-" * 62) * size
    return setup + "".join(ops) + "@"


_NOCOMMENT_TO_BF = {"c": "[-]", "i": "+", "d": "-", "o": "."}


def nocomment_to_bf(program: str) -> str:
    """Rewrite a NoComment program into brainfuck.

    Handles the ``c``/``i``/``d``/``o`` subset of NoComment, which maps
    directly onto brainfuck: ``c`` clears the current cell (``[-]``), ``i``
    increments it (``+``), ``d`` decrements it (``-``), and ``o`` prints it
    as a byte (``.``).  Anything else is dropped (the full language's tape,
    stack, and ``s``/``b`` jumps have no brainfuck translation here).
    Dropping characters also makes this a lenient receiver: a program the
    interpreter would reject for a non-command still transpiles by ignoring
    it.
    """
    return "".join(_NOCOMMENT_TO_BF[c] for c in program if c in _NOCOMMENT_TO_BF)


_BFSTACK_TO_BF = {
    ">": ">",
    "<": "[-]<",
    "+": "+",
    "-": "-",
    ".": ".",
    ",": ">,",
    "[": "[",
    "]": "]",
}


def bfstack_to_bf(program: str) -> str:
    """Rewrite a BFStack program into brainfuck.

    BFStack is a stack, modelled on brainfuck's tape with the top of the
    stack at the current cell.  ``>`` pushes a fresh zero cell and stays a
    ``>``; ``<`` pops, but must first clear the cell (``[-]<``) so a later
    push lands on a fresh zero again; ``,`` reads a byte and pushes, so it
    becomes ``>,``.  The remaining commands map directly.  Anything else is
    a comment and is dropped.
    """
    return "".join(_BFSTACK_TO_BF[c] for c in program if c in _BFSTACK_TO_BF)


_BIO_INC = {"0o": "+", "1o": "-"}


def bio_to_bf(program: str) -> str:
    """Rewrite a BIO program into brainfuck.

    BIO's three registers x/y/z live in the first three brainfuck cells.
    Every command is prefixed by a move to its register and suffixed by a
    move back to cell 0, because brainfuck has no absolute addressing; the
    loop close ``}`` must expand to the register of the ``0i`` it closes, so
    the command stack is tracked.  BIO's registers are unbounded while
    brainfuck's cells wrap mod 256, so the transpiler targets programs whose
    registers never reach a nonzero multiple of 256: output already agrees
    (``1i`` prints ``reg % 256``), and loop conditions agree exactly on that
    class.
    """
    cmds = [c.lower() for c in re.findall(r"([01][oOiI][xXyYzZ]|})", program)]
    res: list[str] = []
    loops: list[int] = []
    for cmd in cmds:
        reg = "xyz".find(cmd[-1])
        op = cmd[:2]
        if op in _BIO_INC:
            res.append(">" * reg + _BIO_INC[op] + "<" * reg)
        elif op == "1i":
            res.append(">" * reg + "." + "<" * reg)
        elif op == "0i":
            res.append(">" * reg + "[" + "<" * reg)
            loops.append(reg)
        else:  # "}"
            reg = loops.pop()
            res.append(">" * reg + "]" + "<" * reg)
    return "".join(res)


_HUF_MUL = (
    ">>>[-]<<<"  # zero the refresh cell
    ">>[-]<<"  # zero the temp cell
    ">-<"  # mul -= 1
    "[->>+<<]"  # num -> temp
    ">"
    "[->[-<<+>>>+<]>[-<+>]<<]"  # add temp to num, mul-1 times, refreshing it
    "<"
)


def huf_to_bf(program: str) -> str:
    """Rewrite a Huf program into brainfuck.

    Huf's variables live in cells 0 (num) and 1 (mul).  ``#`` resets both,
    ``>`` prints ``chr(num)`` and clears it, ``|`` sets mul to 1, and ``+``
    increments num or mul depending on whether mul is set -- since Huf is
    straight line, the transpiler tracks which.  ``!`` multiplies num by
    ``mul - 1``: the multiplier is copied to a temp cell that each loop
    iteration adds to num and refreshes from a running accumulator, so the
    loop can run ``mul - 1`` times without destroying the multiplicand.
    Anything outside a ``#...#@`` segment is a comment.
    """
    syms = "".join(re.findall(r"#[^#@]+@", program))
    res: list[str] = []
    mul = False
    for sym in syms:
        if sym == "#":
            res.append("[-]>[-]<")
            mul = False
        elif sym == ">":
            res.append(".[-]")
        elif sym == "+":
            res.append(">+<" if mul else "+")
        elif sym == "|":
            res.append(">[-]+<")
            mul = True
        else:  # "!"
            res.append(_HUF_MUL)
            mul = False
    return "".join(res)


def bf_to_six_five(program: str) -> str:
    """Rewrite a brainfuck program into 6-5.

    Brainfuck's commands map to fixed 6-5 runs: ``+``/``-`` are ``62``/``59``
    (each nets +1/-1), ``>``/``<`` are ``13``/``3``, and ``,``/``.`` are
    ``B``/``A``.  A ``[`` emits ``8n4`` and its ``]`` emits ``4708(n-1)``:
    entering jumps to the n-th ``4`` marker (the ``]``'s), where ``70`` skips
    the ``8(n-1)`` jump back if the cell is zero, else takes it -- so the
    body runs while the cell is nonzero, exactly like brainfuck.  Each loop
    consumes two ``4`` markers, and the marker labels are the digits 0..9
    then A..Z, so a program is limited to 18 loops (36 markers total).
    """
    markers = 0
    res: list[str] = []

    def build(s: str) -> str:
        nonlocal markers
        out: list[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == ">":
                out.append("13")
            elif c == "<":
                out.append("3")
            elif c == "+":
                out.append("62")
            elif c == "-":
                out.append("59")
            elif c == ",":
                out.append("B")
            elif c == ".":
                out.append("A")
            elif c == "[":
                if markers + 2 > 36:
                    raise ValueError(
                        "the BF-to-6-5 transpiler supports 18 loops at most",
                    )
                depth = 1
                j = i + 1
                while j < len(s) and depth:
                    if s[j] == "[":
                        depth += 1
                    elif s[j] == "]":
                        depth -= 1
                    j += 1
                if depth:
                    raise ValueError("unbalanced brackets cannot be transpiled")
                start = markers + 1  # the ['s 4 marker
                markers += 1
                body = build(s[i + 1 : j - 1])
                end = markers + 1  # the ]'s 4 marker
                markers += 1
                out.append(f"8{_six_five_label(end)}4")
                out.append(body)
                out.append(f"4708{_six_five_label(start)}")
                i = j
                continue
            i += 1  # anything else is a comment or a plain command
        return "".join(out)

    res.append(build(program))
    return "".join(res)


def _six_five_label(value: int) -> str:
    """Return the single character 6-5 reads as ``value`` for a 7n/8n operand."""
    return str(value) if value < 10 else chr(value + 55)


def basicfuck_to_bf(program: str) -> str:
    """Compile a Basicfuck program into brainfuck.

    Basicfuck is a high-level brainfuck: named cells and arrays, ``+=``/
    ``-=``, ``if``/``while`` (optionally negated), and ``write``/``read``.
    This mirrors the interpreter's own compilation -- each variable or array
    element becomes a tape cell at the same offset -- and emits the
    equivalent brainfuck, using a scratch cell pair per nesting level for the
    value copies and loop gates.  The brainfuck pointer always returns to
    cell 0 between statements, so nested ``if``/``while`` compile cleanly.

    The emitted program is 8-bit wrapping brainfuck, so it matches the
    Basicfuck interpreter only for programs whose cells stay within ``0~255``
    while they run (the interpreter's ``wrap`` resets and ``nearest`` clamps
    are only observable out of that range, and brainfuck has no tape-size
    bound).  A ``r=0~255`` tape is therefore required; anything else is
    rejected rather than silently mistranslated.
    """
    from esolangs.interpreters.tape_based.basicfuck import (
        _DIRECTIVE,
        _index,
        _lexer,
        _parse_allocate,
    )

    lines = program.split("\n")
    if len(lines) < 2:
        raise ValueError("Basicfuck program needs a directive and an #allocate line")
    directive = lines[0]
    allocate = lines[1]
    body = "\n".join(lines[2:])

    m = _DIRECTIVE.fullmatch(directive)
    if not m:
        raise ValueError("Missing/Invalid directives.")
    if m.group(2) != "0" or m.group(3) != "255":
        raise ValueError("Basicfuck->brainfuck requires r=0~255 cells")

    var, _ = _parse_allocate(allocate)
    body = re.sub(r"//[^\n]*", "", body)
    tokens = _lexer(body)

    def parse(pos: int) -> tuple[list[tuple[Any, ...]], int]:
        """Recursively parse statements from ``tokens`` until a ``}``."""
        stmts: list[tuple[Any, ...]] = []
        while pos < len(tokens):
            t = tokens[pos]
            if t in ("if", "while"):
                pos += 1
                neg = False
                if tokens[pos] == "!":
                    neg = True
                    pos += 1
                if tokens[pos] != "(":
                    raise ValueError("Invalid syntax.")
                pos += 1
                cond = tokens[pos]
                pos += 1
                if tokens[pos] != ")":
                    raise ValueError("Invalid syntax.")
                pos += 1
                if tokens[pos] != "{":
                    raise ValueError("Invalid syntax.")
                pos += 1
                body_stmts, pos = parse(pos)
                if tokens[pos] != "}":
                    raise ValueError("Invalid syntax.")
                pos += 1
                stmts.append((t, neg, cond, body_stmts))
            elif t in ("write", "read"):
                arrow = "<-" if t == "write" else "->"
                pos += 1
                if tokens[pos] != arrow:
                    raise ValueError("Invalid syntax.")
                pos += 1
                name = tokens[pos]
                pos += 1
                if tokens[pos] != ";":
                    raise ValueError("Invalid syntax.")
                pos += 1
                stmts.append((t, name))
            elif t == "}":
                return stmts, pos
            else:
                pos += 1
                op = tokens[pos]
                if op not in ("+=", "-="):
                    raise ValueError("Invalid syntax.")
                pos += 1
                rhs = tokens[pos]
                pos += 1
                if tokens[pos] != ";":
                    raise ValueError("Invalid syntax.")
                pos += 1
                stmts.append(
                    ("assign", t, op, ("const", int(rhs))
                     if rhs.isdigit() else ("var", rhs)),
                )
        return stmts, pos

    statements, _ = parse(0)

    def depth(node: tuple[Any, ...]) -> int:
        """Return the max ``if``/``while`` nesting depth of a statement."""
        if node[0] in ("if", "while"):
            return 1 + max((depth(b) for b in node[3]), default=0)
        return 0

    base = sum(size for _, size in var)  # cells used by the variables

    out: list[str] = []

    def move(target: int, cur: int) -> int:
        """Emit the pointer movement to ``target``, returning the new offset."""
        if target > cur:
            out.append(">" * (target - cur))
        elif target < cur:
            out.append("<" * (cur - target))
        return target

    def copy_preserving(src: int, dest: int, temp: int, cur: int) -> int:
        """Copy cell ``src`` to ``dest`` (preserving ``src``) via ``temp``.

        ``src -> dest`` and ``src -> temp``, then ``temp -> src``; the
        pointer ends on ``dest``.
        """
        cur = move(dest, cur)
        out.append("[-]")  # zero the copy target and temp so a zero src
        cur = move(temp, cur)
        out.append("[-]")  # leaves them zero (and skips the restore loop)
        cur = move(src, cur)
        out.append("[")
        cur = move(dest, cur)
        out.append("+")
        cur = move(temp, cur)
        out.append("+")
        cur = move(src, cur)
        out.append("-")
        out.append("]")
        cur = move(temp, cur)
        out.append("[")
        cur = move(src, cur)
        out.append("+")
        cur = move(temp, cur)
        out.append("-")
        out.append("]")
        return move(dest, cur)

    def flag_from_q(*, neg: bool, p: int, q: int, cur: int) -> int:
        """Set ``p`` to the truthiness of ``q`` (negated if ``neg``).

        ``p`` starts at 0 and ``q`` holds the value; ``p`` ends as 0/1 and
        ``q`` ends at 0.
        """
        cur = move(p, cur)
        out.append("[-]")  # clear the copy's leftover value
        if neg:
            out.append("+")  # p = 1, corrected to 0 below when q != 0
            cur = move(q, cur)
            out.append("[")
            cur = move(p, cur)
            out.append("[-]")
            cur = move(q, cur)
            out.append("-")
            out.append("]")
            return move(p, cur)
        cur = move(q, cur)
        out.append("[")
        cur = move(p, cur)
        out.append("+")
        cur = move(q, cur)
        out.append("-")
        out.append("]")
        return move(p, cur)

    def compile_stmts(stmts: list[tuple[Any, ...]], depth: int, cur: int) -> int:
        p = base + 2 * depth
        q = base + 2 * depth + 1
        for stmt in stmts:
            kind = stmt[0]
            if kind in ("if", "while"):
                neg, cond, body = stmt[1], stmt[2], stmt[3]
                x = _index(cond, var)
                cur = move(x, cur)
                cur = copy_preserving(x, q, p, cur)
                cur = flag_from_q(neg=neg, p=p, q=q, cur=cur)
                out.append("[")
                cur = move(0, cur)
                cur = compile_stmts(body, depth + 1, cur)
                cur = 0
                if kind == "while":
                    cur = move(x, cur)
                    cur = copy_preserving(x, q, p, cur)
                    cur = flag_from_q(neg=neg, p=p, q=q, cur=cur)
                else:
                    cur = move(p, cur)
                    out.append("[-]")
                out.append("]")
                cur = move(0, cur)
            elif kind in ("write", "read"):
                cur = move(_index(stmt[1], var), cur)
                out.append("." if kind == "write" else ",")
                cur = move(0, cur)
            else:  # assign
                x = _index(stmt[1], var)
                op = stmt[2]
                rhs = stmt[3]
                if rhs[0] == "const":
                    k = rhs[1]
                    if abs(k) >= 256:
                        raise ValueError(
                            "Basicfuck->brainfuck requires constants within 0~255",
                        )
                    cur = move(x, cur)
                    out.append(("+" if op == "+=" else "-") * abs(k))
                    cur = move(0, cur)
                else:
                    y = _index(rhs[1], var)
                    cur = move(y, cur)
                    cur = copy_preserving(y, q, p, cur)
                    out.append("[")
                    cur = move(x, cur)
                    out.append("+" if op == "+=" else "-")
                    cur = move(q, cur)
                    out.append("-")
                    out.append("]")
                    cur = move(0, cur)
        return cur

    compile_stmts(statements, 0, 0)
    return "".join(out)


TRANSPILERS: dict[tuple[str, str], Callable[..., str]] = {
    ("brainfuck", "ASCII art"): bf_to_ascii_art,
    ("ASCII art", "brainfuck"): ascii_art_to_bf,
    ("Basicfuck", "brainfuck"): basicfuck_to_bf,
    ("brainfuck", "Circlefuck"): bf_to_circlefuck,
    ("brainfuck", "6-5"): bf_to_six_five,
    ("NoComment", "brainfuck"): nocomment_to_bf,
    ("BFStack", "brainfuck"): bfstack_to_bf,
    ("BIO", "brainfuck"): bio_to_bf,
    ("huf", "brainfuck"): huf_to_bf,
}
