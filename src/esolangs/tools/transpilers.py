"""Transpile programs between languages.

Each ``TRANSPILERS`` entry maps a ``(source, target)`` language-name pair to
a function that rewrites a program in the source language into an
equivalent program in the target.  A target is only added when its in-repo
interpreter matches the source language's semantics, so every transpiler is
verified end-to-end: the source runs on its interpreter, the target on its
own, and the outputs must agree.
"""

import re
from collections.abc import Callable
from typing import Any, Literal, cast

from esolangs.interpreters.register_based.bio import parse as bio_parse

__all__ = [
    "TRANSPILERS",
    "basicfuck_to_bf",
    "bf_to_circlefuck",
    "bf_to_painfuck",
    "bf_to_six_five",
    "bf_to_three_d_brainfuck",
    "bfstack_to_bf",
    "bio_to_bf",
    "decleq_to_sbleq",
    "dimensional_to_laserfuck",
]


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


def bf_to_three_d_brainfuck(program: str) -> str:
    """Rewrite a brainfuck program into 3D Brainfuck.

    3D Brainfuck is a brainfuck superset: the code pointer travels a 3D grid
    of the source characters (default heading +X), and the array moves
    ``n``/``s`` walk the data tape along that same axis.  So the translation
    is a one-to-one command swap — ``>`` → ``n``, ``<`` → ``s`` — with
    ``+``/``-``/``,``/``.``/``[``/``]`` unchanged.

    The supported class is programs whose pointer never moves below cell 0:
    brainfuck clamps ``<`` at the left edge, but 3D Brainfuck's ``s`` walks
    into the negative cells, so a program that dips below cell 0 diverges.
    A program that moves below cell 0 is rejected rather than mistranslated
    (``ValueError``), matching the Circlefuck transpiler's handling of its
    out-of-class programs.  Comment characters are carried through unchanged
    and stay comments in the target.
    """
    ptr = 0
    for char in program:
        if char == ">":
            ptr += 1
        elif char == "<":
            ptr -= 1
            if ptr < 0:
                raise ValueError(
                    "3D Brainfuck cannot represent a program that moves below cell 0 "
                    "(brainfuck clamps '<' but 3D Brainfuck's 's' walks negative)"
                )
    return program.translate(str.maketrans("><", "ns"))


# Painfuck's two substitution cycles, in the order the interpreter (and the
# Rust cross-check) scan them: a source character in a cycle is rewritten to
# the character ``k`` steps further along it, where ``k`` counts the
# characters translated so far.
_PAINFUCK_CYCLES = ("pevkjzwr", "yuctsobqihald")

# brainfuck command -> the Painfuck commands it expands to, before the cycle
# pre-shift.  ``>`` expands to ``r`` then ``l`` (two right, one left = +1),
# ``+`` to ``p`` then ``s`` (add two, subtract one = +1); ``<``/``-``/``[``/
# ``]``/``,``/``.`` map one-to-one.  The expansion cannot use
# ``str.translate`` (it is 1:1), so it is a per-command rewrite.
_BF_TO_PAINFUCK = {
    ">": "rl",
    "<": "l",
    "+": "ps",
    "-": "s",
    "[": "a",
    "]": "b",
    ",": "j",
    ".": "u",
}


def bf_to_painfuck(program: str) -> str:
    """Rewrite a brainfuck program into Painfuck.

    Painfuck's source is first translated through a fixed two-cycle Caesar
    substitution (each source character in a cycle is rewritten ``k`` steps
    along it, ``k`` counting the characters translated), then executed.
    Brainfuck maps onto Painfuck's commands directly — ``>``/``<`` become
    ``rl``/``l``, ``+``/``-`` become ``ps``/``s``, ``[``/``]``/``,``/``.``
    become ``a``/``b``/``j``/``u`` — and the interpreter's forward shift is
    undone by pre-shifting each emitted command ``k`` steps *back* along its
    cycle, so a generated program round-trips.  Every brainfuck program is in
    class; comment characters are dropped (Painfuck ignores characters in no
    cycle).
    """
    out: list[str] = []
    k = 0
    for char in program:
        for ch in _BF_TO_PAINFUCK.get(char, char):
            for cycle in _PAINFUCK_CYCLES:
                p = cycle.find(ch)
                if p != -1:
                    out.append(cycle[(p - k) % len(cycle)])
                    k += 1
                    break
    return "".join(out)


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
    loop close ``};`` must expand to the register of the ``0i?{`` it
    closes, so the command stack is tracked.  BIO's registers are unbounded while
    brainfuck's cells wrap mod 256, so the transpiler targets programs whose
    registers never reach a nonzero multiple of 256: output already agrees
    (``1i`` prints ``reg % 256``), and loop conditions agree exactly on that
    class.
    """
    cmds = bio_parse(program)
    res: list[str] = []
    loops: list[int] = []
    for cmd in cmds:
        # A loop-open carries the ``{`` that opens its body, so the register
        # is the triple's own last letter rather than the token's.
        reg = "xyz".find(cmd[2]) if cmd != "};" else -1
        op = cmd[:2]
        if op in _BIO_INC:
            res.append(">" * reg + _BIO_INC[op] + "<" * reg)
        elif op == "1i":
            res.append(">" * reg + "." + "<" * reg)
        elif op == "0i":
            res.append(">" * reg + "[" + "<" * reg)
            loops.append(reg)
        else:  # "};"
            # ``bio_parse`` matched the braces, so a ``};`` always has a loop.
            reg = loops.pop()
            res.append(">" * reg + "]" + "<" * reg)
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
                if pos >= len(tokens) or tokens[pos] != "}":
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
                    (
                        "assign",
                        t,
                        op,
                        ("const", int(rhs)) if rhs.isdigit() else ("var", rhs),
                    ),
                )
        return stmts, pos

    statements, _ = parse(0)

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


class _DecleqAsm:
    """Tiny S*bleq assembler used by :func:`decleq_to_sbleq`.

    Labels map to instruction indices; ``data`` and ``scratch`` cells are
    resolved to absolute addresses at build time, and ``jump`` cells hold the
    absolute address of a label so that S*bleq's *indirect* ``c`` operand
    (``ip = mem[c]``) can express a direct Decleq jump target.
    """

    def __init__(self, cells: list[int]) -> None:
        self.code: list[list[Any]] = []
        self.syms: dict[str, int] = {}
        self.data: list[int] = list(cells)
        self.cells: list[int] = []
        self._cells: dict[str, int] = {}
        self.jump_cells: dict[str, int] = {}

    def emit(self, a: Any, b: Any, c: Any, label: str | None = None) -> None:
        if label is not None:
            self.syms[label] = len(self.code)
        self.code.append([a, b, c])

    def data_addr(self, i: int) -> tuple[str, int]:
        return ("data", i)

    def scratch(self, name: str, value: int = 0) -> tuple[str, int]:
        if name not in self._cells:
            self._cells[name] = len(self.cells)
            self.cells.append(value)
        return ("scratch", self._cells[name])

    def jcell(self, label: str) -> tuple[str, int]:
        if label not in self.jump_cells:
            self.jump_cells[label] = len(self.cells)
            self.cells.append(0)
        return ("jump", self.jump_cells[label])

    def _resolve(self, v: Any, base_data: int, base_scratch: int) -> int:
        if isinstance(v, tuple):
            kind, idx = v
            base = base_data if kind == "data" else base_scratch
            return base + int(idx)
        return int(v)

    def build(self) -> list[int]:
        n = len(self.code)
        base_data = 3 * n
        base_scratch = base_data + len(self.data)
        for label, cell in self.jump_cells.items():
            self.cells[cell] = 3 * self.syms[label]
        mem: list[int] = []
        for a, b, c in self.code:
            mem += [
                self._resolve(a, base_data, base_scratch),
                self._resolve(b, base_data, base_scratch),
                self._resolve(c, base_data, base_scratch),
            ]
        return mem + self.data + self.cells


def _emit_copy(asm: _DecleqAsm, a: Any, b: Any, target: str, label: str) -> None:
    """Emit ``b = a - 1`` for ``a != b``, preserving ``a``, then branch on ``b``."""
    s1 = asm.scratch("s1")
    s2 = asm.scratch("s2")
    u = asm.scratch("u")
    zero = asm.scratch("zero", 0)
    one = asm.scratch("one", 1)
    neg = asm.scratch("neg", -1)
    t = asm.scratch("t")
    asm.emit(a, zero, asm.jcell(f"{label}.NEG"), label=label)
    asm.emit(s1, s1, asm.jcell(f"{label}.z2"), label=f"{label}.Z1")
    asm.emit(s2, s2, asm.jcell(f"{label}.z3"), label=f"{label}.z2")
    asm.emit(b, b, asm.jcell(f"{label}.L1"), label=f"{label}.z3")
    asm.emit(a, one, asm.jcell(f"{label}.C2"), label=f"{label}.L1")
    asm.emit(s1, neg, asm.jcell(f"{label}.j1"))
    asm.emit(s2, neg, asm.jcell(f"{label}.j2"), label=f"{label}.j1")
    asm.emit(u, u, asm.jcell(f"{label}.L1"), label=f"{label}.j2")
    asm.emit(s1, neg, asm.jcell(f"{label}.j1b"), label=f"{label}.C2")
    asm.emit(s2, neg, asm.jcell(f"{label}.L3"), label=f"{label}.j1b")
    asm.emit(s2, one, asm.jcell(f"{label}.C3"), label=f"{label}.L3")
    asm.emit(a, neg, asm.jcell(f"{label}.j3"))
    asm.emit(u, u, asm.jcell(f"{label}.L3"), label=f"{label}.j3")
    asm.emit(a, neg, asm.jcell(f"{label}.C4"), label=f"{label}.C3")
    asm.emit(s1, one, asm.jcell(f"{label}.C5"), label=f"{label}.C4")
    asm.emit(b, neg, asm.jcell(f"{label}.j5"))
    asm.emit(u, u, asm.jcell(f"{label}.C4"), label=f"{label}.j5")
    asm.emit(t, t, asm.jcell(f"{label}.A2"), label=f"{label}.NEG")
    asm.emit(t, neg, asm.jcell(f"{label}.A3"), label=f"{label}.A2")  # t = 1
    asm.emit(t, a, asm.jcell(f"{label}.A4"), label=f"{label}.A3")  # t = 1 - a
    asm.emit(b, b, asm.jcell(f"{label}.A5"), label=f"{label}.A4")
    asm.emit(t, one, asm.jcell(f"{label}.A7"), label=f"{label}.A5")  # t -= 1
    asm.emit(b, one, asm.jcell(f"{label}.A5"))  # b -= 1; loop
    asm.emit(b, one, asm.jcell(f"{label}.C5"), label=f"{label}.A7")  # final b -= 1
    asm.emit(b, zero, asm.jcell(target), label=f"{label}.C5")  # if b <= 0 goto target


def _emit_input(asm: _DecleqAsm, b: Any, target: str, label: str) -> None:
    """Emit ``b = <byte>`` (an input cell, so ``b >= 0``), then branch on ``b``."""
    u = asm.scratch("u")
    neg = asm.scratch("neg", -1)
    one = asm.scratch("one", 1)
    t = asm.scratch("t")
    asm.emit(b, b, asm.jcell(f"{label}.R2"), label=label)
    asm.emit(b, -2, asm.jcell(f"{label}.R3"), label=f"{label}.R2")  # b = -value
    asm.emit(t, t, asm.jcell(f"{label}.R4"), label=f"{label}.R3")
    asm.emit(t, neg, asm.jcell(f"{label}.R5"), label=f"{label}.R4")  # t = 1
    asm.emit(t, b, asm.jcell(f"{label}.S2L"), label=f"{label}.R5")  # t = 1 + value
    asm.emit(b, b, asm.jcell(f"{label}.S2L"))  # b = 0 (value >= 0)
    asm.emit(t, one, asm.jcell(f"{label}.C5"), label=f"{label}.S2L")  # t -= 1
    asm.emit(b, neg, asm.jcell(f"{label}.J"))  # b += 1
    asm.emit(u, u, asm.jcell(f"{label}.S2L"), label=f"{label}.J")
    asm.emit(
        b,
        asm.scratch("zero", 0),
        asm.jcell(target),
        label=f"{label}.C5",
    )  # if b <= 0 goto target


def decleq_to_sbleq(program: str) -> str:
    """Rewrite a Decleq program as an equivalent S*bleq program.

    Decleq's ``a b c`` does ``mem[b] = mem[a] - 1`` and jumps to ``c`` when
    the new ``mem[b]`` is at most zero; S*bleq's ``a b c`` does
    ``mem[a] -= mem[b]`` and jumps *indirectly* to ``mem[c]``.  Each Decleq
    instruction becomes a straight-line S*bleq block that materialises the
    arithmetic with scratch cells and then branches to the Decleq target.
    The ``-1`` (input) and ``-2`` (output) Decleq addresses map onto
    S*bleq's ``-1``/``-3`` specials and the input-address ``-2``.

    The translation is faithful for Decleq programs that keep the
    instruction pointer inside the original program and never treat a cell
    as both data and (later) an operand: writes that would be re-read as an
    operand of a reachable instruction are rejected with :class:`ValueError`
    (self-modifying Decleq code is out of scope), and a program that would
    run off the end into memory it extended past itself halts instead.
    Reading past end-of-input also differs (Decleq raises :class:`EOFError`,
    S*bleq reads zero).
    """
    from esolangs.interpreters.memory import parse_int_memory as _parse

    cells = _parse(program)
    n = len(cells) // 3
    if 3 * n != len(cells):
        raise ValueError("Decleq program length must be a multiple of three")

    succ: list[list[int]] = [[] for _ in range(n)]
    for k in range(n):
        a, c = cells[3 * k], cells[3 * k + 2]
        if a in (-1, -2):
            if k + 1 < n:
                succ[k].append(k + 1)
        elif c >= 0 and c % 3 == 0 and 0 <= c // 3 < n:
            succ[k].append(c // 3)
            if k + 1 < n:
                succ[k].append(k + 1)

    reachable: set[int] = set()
    stack = [0]
    while stack:
        k = stack.pop()
        if k in reachable or k >= n:
            continue
        reachable.add(k)
        stack.extend(succ[k])

    writers = [
        (k, cells[3 * k + 1])
        for k in range(n)
        if k in reachable and cells[3 * k] not in (-1, -2) and cells[3 * k + 1] >= 0
    ]
    for m, w in writers:
        seen: set[int] = set()
        stack = list(succ[m])
        while stack:
            k = stack.pop()
            if k in seen or k >= n:
                continue
            seen.add(k)
            lo, hi = (
                (3 * k, 3 * k + 1) if cells[3 * k] in (-1, -2) else (3 * k, 3 * k + 2)
            )
            if lo <= w <= hi:
                raise ValueError(
                    f"instruction {m} writes cell {w}, which is re-read as an "
                    f"operand of instruction {k} (self-modifying Decleq code "
                    "is out of scope)"
                )
            stack.extend(succ[k])

    max_addr = max(
        [len(cells) - 1]
        + [v for k in range(n) for v in (cells[3 * k], cells[3 * k + 1]) if v >= 0]
    )
    cells = cells + [0] * (max_addr + 1 - len(cells))
    asm = _DecleqAsm(cells)
    neg1 = asm.scratch("halt", -1)
    u = asm.scratch("u")
    for k in range(n):
        a, b, c = cells[3 * k], cells[3 * k + 1], cells[3 * k + 2]
        if c >= 0 and c % 3 != 0:
            raise ValueError("Decleq jump targets must be multiples of three")
        target = f"k{c // 3}" if 0 <= c < 3 * n else "halt"
        label = f"k{k}"
        if a == -2:  # output mem[b]
            asm.emit(-3, asm.data_addr(b), asm.jcell(target), label=label)
        elif a == -1:  # input into mem[b]
            _emit_input(asm, asm.data_addr(b), target, label)
        elif b < 0:
            raise ValueError("a negative non-special b is out of the supported class")
        elif a == b:  # countdown idiom: mem[a] -= 1; if <= 0 goto c
            asm.emit(
                asm.data_addr(a),
                asm.scratch("one", 1),
                asm.jcell(target),
                label=label,
            )
        else:  # b = a - 1; if <= 0 goto c
            src = asm.data_addr(a) if a >= 0 else asm.scratch("zero", 0)
            _emit_copy(asm, src, asm.data_addr(b), target, label)
    asm.emit(u, u, neg1, label="halt")
    return " ".join(map(str, asm.build()))


class _LaserGrid:
    """A LaserFuck grid being built: rows x columns of cells."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], str] = {}
        self.rows = 0
        self.cols = 0

    def set(self, row: int, col: int, c: str) -> None:
        old = self.cells.get((row, col))
        if old is not None and old != c:
            raise AssertionError(("collision", (row, col), old, c))
        self.cells[(row, col)] = c
        self.rows = max(self.rows, row + 1)
        self.cols = max(self.cols, col + 1)

    def dump(self) -> str:
        g = [[" "] * self.cols for _ in range(self.rows)]
        for (row, col), c in self.cells.items():
            g[row][col] = c
        return "\n".join("".join(ln).rstrip() for ln in g)


# The command alphabet ``_laser_parse`` emits: brainfuck's eight commands
# and nothing else.  Naming it lets the checker see that the emit and
# analyze walks handle every one, so neither needs a fallback arm for a
# character the parser has already rejected.
_LaserOp = Literal["+", "-", ">", "<", ".", ",", "[", "]"]


def _laser_funnel(g: _LaserGrid) -> None:
    """Send every initial heading right on row 0 (the start-marker funnel)."""
    g.set(0, 0, "\u00ff")
    g.set(0, 1, "}")
    g.set(0, 2, "}")
    g.set(1, 0, "|")
    g.set(1, 1, "o")
    g.set(1, 2, "^")
    g.set(2, 1, "_")


def _laser_emit(
    g: _LaserGrid, ops: list[_LaserOp], row: int, col: int
) -> tuple[int, int]:
    """Lay out ``ops`` on ``row`` heading right; return (next_col, bottom_row)."""
    i = 0
    bottom = row + 1
    while i < len(ops):
        c = ops[i]
        if c in "+-><.,":
            g.set(row, col, c)
            col += 1
            i += 1
        elif c == "[":
            depth = 1
            j = i + 1
            while j < len(ops) and depth:
                if ops[j] == "[":
                    depth += 1
                elif ops[j] == "]":
                    depth -= 1
                j += 1
            if depth != 0:
                raise AssertionError("balanced brackets were validated before emission")
            body = ops[i + 1 : j - 1]
            col, lbottom = _laser_loop(g, row, col, body)
            bottom = max(bottom, lbottom)
            i = j
    return col, bottom


def _laser_loop(
    g: _LaserGrid, strip_row: int, c: int, body: list[_LaserOp]
) -> tuple[int, int]:
    r"""Emit a while-loop ring below the strip's ``v`` at (strip_row, c).

    The beam turns down at the ``v``, the test ``# v ) \\`` on the row below
    reflects a nonzero cell back into the body and lets a zero cell fall
    through to the exit, and a loop-back returns the body's beam to the test
    via a clear up-column.  Returns (next_col, bottom_row) for the region.
    """
    r = strip_row
    g.set(r, c, "v")
    g.set(r + 1, c, "}")
    g.set(r + 1, c + 1, "#")
    g.set(r + 1, c + 2, "v")
    g.set(r + 1, c + 3, ")")
    g.set(r + 1, c + 4, "\\")
    g.set(r + 3, c + 2, "}")
    _, bbottom = _laser_emit(g, body, r + 3, c + 5)
    rcol = g.cols  # routing columns begin at the content's right edge
    rrow = bbottom
    g.set(r + 3, rcol, "v")
    g.set(rrow, rcol, "{")
    g.set(rrow, c, "^")
    g.set(r + 1, c, "}")
    exit_row = rrow + 1
    g.set(exit_row, c + 4, "}")
    u_exit = rcol + 2
    g.set(exit_row, u_exit, "^")
    g.set(r, u_exit, "}")
    return u_exit + 1, exit_row + 1


def _laser_analyze(ops: list[_LaserOp]) -> tuple[int, int, int | None]:
    """Analyze the ops statically: final pointer, max cell, output cell.

    Loops must have net-zero pointer displacement (so the pointer stays
    statically known), the pointer must never move below cell 0 (LaserFuck's
    tape has no negative cells), and a ``.`` is allowed only as the last
    top-level command (LaserFuck prints the tape once at the end).
    """
    ptr = 0
    maxcell = 0
    i = 0
    out_cell: int | None = None
    while i < len(ops):
        c = ops[i]
        if c == ">":
            ptr += 1
            maxcell = max(maxcell, ptr)
            i += 1
        elif c == "<":
            ptr -= 1
            if ptr < 0:
                raise ValueError(
                    "moving below cell 0 is out of the supported class (LaserFuck's "
                    "tape has no negative cells)"
                )
            i += 1
        elif c == ".":
            if i != len(ops) - 1:
                raise ValueError(
                    "a '.' must be the last command (LaserFuck prints the tape "
                    "once at the end, so only a final single output is in class)"
                )
            out_cell = ptr
            i += 1
        elif c == "[":
            depth = 1
            j = i + 1
            while j < len(ops) and depth:
                if ops[j] == "[":
                    depth += 1
                elif ops[j] == "]":
                    depth -= 1
                j += 1
            if depth != 0:
                raise AssertionError("balanced brackets were validated before analysis")
            body = ops[i + 1 : j - 1]
            if "." in body:
                raise ValueError("a '.' inside a loop is out of the supported class")
            bptr, bmax, _bout = _laser_analyze(body)
            if bptr != 0:
                raise ValueError(
                    "loops that drift the tape pointer are out of the supported class"
                )
            maxcell = max(maxcell, ptr + bmax)
            i = j
    return ptr, maxcell, out_cell


def _laser_parse(program: str) -> list[_LaserOp]:
    """Parse a Dimensional program into the supported command list.

    The supported class is Dimensional's brainfuck-like core on a linear
    tape: ``>0``/``<0`` moves, ``+``/``-``, ``.``/``,``, ``[``/``]``, and
    the ``=HH``/``:CH`` literals (emitted as a clear plus increments);
    ``*``..``*`` comments are skipped.  Everything else is rejected.
    """
    ops: list[_LaserOp] = []
    comment = False
    i = 0
    while i < len(program):
        ch = program[i]
        if comment:
            if ch == "*":
                comment = False
            i += 1
            continue
        if ch == "*":
            comment = True
            i += 1
        elif ch in "+-><.,[]":
            if ch in "><":
                neg = False
                j = i + 1
                if j < len(program) and program[j] == "~":
                    neg = True
                    j += 1
                if j < len(program) and program[j].isdigit():
                    k = j
                    while k < len(program) and program[k].isdigit():
                        k += 1
                    dim = int(program[j:k])
                    if neg:
                        dim = -dim
                    if dim != 0:
                        raise ValueError(
                            f"only dimension 0 moves are supported, got {dim}"
                        )
                    i = k
                else:
                    raise ValueError(
                        "bare '>'/'<' (dimension = current value) is out of the "
                        "supported class; write an explicit >0 / <0"
                    )
            else:
                i += 1
            # The elif above tested membership in the alphabet, so this is
            # where a parsed character becomes a typed command.
            ops.append(cast("_LaserOp", ch))
        elif ch == "=":
            if i + 2 >= len(program):
                raise ValueError("'=' must be followed by two hex digits")
            try:
                value = int(program[i + 1 : i + 3], 16)
            except ValueError:
                raise ValueError("'=' must be followed by two hex digits") from None
            ops.extend(["[", "-", "]"])
            ops.extend(["+"] * value)
            i += 3
        elif ch == ":":
            if i + 1 >= len(program):
                raise ValueError("':' must be followed by a character")
            value = ord(program[i + 1])
            ops.extend(["[", "-", "]"])
            ops.extend(["+"] * value)
            i += 2
        else:
            raise ValueError(f"command {ch!r} is out of the supported class")
    depth = 0
    for ch in ops:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced brackets")
    if depth:
        raise ValueError("unbalanced brackets")
    return ops


def dimensional_to_laserfuck(program: str) -> str:
    r"""Rewrite a Dimensional program into LaserFuck.

    Dimensional's brainfuck-like core (``>0``/``<0``, ``+``/``-``, ``.``/``,``,
    ``[``/``]``, and the ``=HH``/``:CH`` literals) maps onto a LaserFuck grid.
    A start-marker funnel pins the laser's random initial heading, ``[``
    becomes a ``v`` that detours the beam into a loop ring below the strip,
    and the ring's test ``# v ) \\`` reflects a nonzero cell back into the
    body and lets a zero cell fall through to the exit, so the loop runs
    exactly while its cell is nonzero like Dimensional's.

    LaserFuck prints the whole tape once when the laser dies, so the emitted
    program negates every working cell at the end; a final single ``.`` is
    kept (and touched) so the tape dump is exactly that one byte.  Everything
    outside this core is rejected rather than mistranslated: the pointer
    hierarchy (``$``, ``{``/``}``, ``?``/``!``), the numeric readers (``d``/
    ``x``), bare or non-zero-dimension moves, moving below cell 0, loops that
    drift the pointer, and any ``.`` other than a final single output.
    Cells do not wrap at 8 bits in the translation (LaserFuck cells are
    unbounded), so programs that rely on Dimensional's byte wrapping are out
    of class.
    """
    ops = _laser_parse(program)
    ptr, maxcell, out_cell = _laser_analyze(ops)
    epi: list[_LaserOp] = []
    epi.extend(["<"] * ptr)
    for cell in range(0, maxcell + 1):
        if cell == out_cell:
            epi.extend(["+", "-", ">"])
            continue
        epi.extend(["[", "-", "]", "-"])
        epi.append(">")
    g = _LaserGrid()
    _laser_funnel(g)
    _laser_emit(g, ops + epi, 0, 3)
    return g.dump()


TRANSPILERS: dict[tuple[str, str], Callable[..., str]] = {
    ("Basicfuck", "brainfuck"): basicfuck_to_bf,
    ("brainfuck", "Circlefuck"): bf_to_circlefuck,
    ("brainfuck", "6-5"): bf_to_six_five,
    ("brainfuck", "3D Brainfuck"): bf_to_three_d_brainfuck,
    ("brainfuck", "Painfuck"): bf_to_painfuck,
    ("BFStack", "brainfuck"): bfstack_to_bf,
    ("BIO", "brainfuck"): bio_to_bf,
    ("Decleq", "S*bleq"): decleq_to_sbleq,
    ("Dimensional", "LaserFuck"): dimensional_to_laserfuck,
}
