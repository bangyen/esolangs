"""Transpile programs between languages.

Each ``TRANSPILERS`` entry maps a ``(source, target)`` language-name pair to
a function that rewrites a program in the source language into an
equivalent program in the target.  A target is only added when its in-repo
interpreter matches the source language's semantics, so every transpiler is
verified end-to-end: the source runs on its interpreter, the target on its
own, and the outputs must agree.
"""

import re
import string
from collections.abc import Callable
from typing import Any, Literal, get_args

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
    "streetcode_to_laserfuck",
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

    3D Brainfuck holds a *three-dimensional* grid of byte cells and moves
    the array pointer along six axes (``n``/``s`` on x, ``u``/``d`` on y,
    ``e``/``w`` on z), so brainfuck's tape is its ``y = z = 0`` row and
    ``>``/``<`` become ``n``/``s``.  The two languages agree on everything
    else that is observable: cells wrap 0-255 in both, both create cells on
    demand, both print ``chr(cell)``, and both raise :class:`EOFError` when
    input runs out.

    The one disagreement is the left edge.  Brainfuck *clamps* ``<`` at
    cell 0 while 3D Brainfuck's ``s`` walks into the negative cells, and
    the clamping is load-bearing rather than incidental: ``+.<.`` prints
    the same byte twice in brainfuck precisely because ``<`` was a no-op
    there.  No static shift of the origin repairs that -- a shift cannot
    turn a move into a non-move -- so ``<`` compiles to a *runtime* guard
    instead, which is what makes the rewrite total.

    The guard puts a sentinel where data cannot reach it.  A prefix
    ``su+dn`` writes ``1`` at ``(-1, 1, 0)`` -- one step below the tape,
    one step off it on the y axis -- and returns the pointer to the origin.
    Then ``<`` becomes ``su[dnu]d``:

    - at column ``k > 0``, ``s`` lands on ``k - 1`` and ``u`` reads
      ``(k - 1, 1, 0)``, which is zero, so the loop body is skipped and
      ``d`` drops back to the tape: one cell left, as brainfuck moves;
    - at column ``0``, ``s`` lands on ``-1`` and ``u`` reads the sentinel,
      so the body runs once -- ``dnu`` walks back to ``(0, 1, 0)``, which
      is zero, closing the loop -- and ``d`` lands on the origin: no net
      move, which is brainfuck's clamp.

    The guard never writes a data cell, writes the sentinel once and never
    again, never moves below column ``-1``, and its brackets are textually
    balanced, so they nest with the program's own loops.

    Only the eight brainfuck commands are emitted; every other character is
    dropped.  That is not cosmetic.  Brainfuck comment characters include
    ``n``, ``s``, ``e``, ``w``, ``u`` and ``d``, which are *array moves* in
    3D Brainfuck, so passing them through silently mistranslates -- an
    ordinary word like ``hello`` in a comment moves the pointer twice --
    and a stray ``u`` or ``d`` would leave the ``y = 0`` plane entirely,
    where a later ``+`` could forge the sentinel.  Dropping them matches
    the Painfuck transpiler.
    """
    guard = "su[dnu]d"
    body = "".join(
        {">": "n", "<": guard}.get(char, char) for char in program if char in "><+-.,[]"
    )
    return "su+dn" + body


# Painfuck's two substitution cycles, in the order the interpreter (and the
# reference) scan them: a source character in a cycle is rewritten to
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
    then A..Z -- the [wiki spec](https://esolangs.org/wiki/6-5)'s "numbers
    beyond 9 denoted using letters", so the highest addressable marker is
    ``Z`` == 35.  A program is therefore limited to 17 loops (34 markers);
    an 18th loop would need marker 36, which no spec-defined operand names.
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
                if markers + 2 > _SIX_FIVE_MAX_LABEL:
                    raise ValueError(
                        "the BF-to-6-5 transpiler supports "
                        f"{_SIX_FIVE_MAX_LABEL // 2} loops at most",
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


# The highest 7n/8n operand the 6-5 spec names: the digits 0..9 and then the
# letters A..Z ("numbers beyond 9 denoted using letters", A=10), so ``Z`` ==
# 35.  Past this the interpreter's ``ord(c.upper()) - 55`` decode keeps going
# over undefined characters (``[`` for 36) -- see the conformance note in
# ``docs/limitations.md``; the transpiler must not emit into that region.
_SIX_FIVE_MAX_LABEL = 10 + len(string.ascii_uppercase) - 1


def _six_five_label(value: int) -> str:
    """Return the single character 6-5 reads as ``value`` for a 7n/8n operand."""
    if not 0 <= value <= _SIX_FIVE_MAX_LABEL:
        raise ValueError(f"6-5 has no operand character for {value}")
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


_SEQ = object()  # sentinel ``c``: fall through to the next instruction


class _SbleqAsm:
    """Tiny S*bleq assembler used by :func:`decleq_to_sbleq`.

    Emits into three regions -- ``[code | scratch | image]`` -- and resolves
    symbolic operands at :meth:`build` time.  An operand is an ``int`` (a
    literal address, including the ``-1``/``-2``/``-3`` specials), a
    ``("scratch", i)`` pair, or a ``("field", label, off)`` reference to
    operand ``off`` of the instruction at ``label`` -- the last is how the
    emulator patches its own operands to reach an address it computed at
    runtime, which is S*bleq's only form of indirect load and store.

    S*bleq branches when the difference is at most zero and otherwise falls
    through, so a ``c`` of ``_SEQ`` still has to name the next instruction:
    :meth:`build` allocates a cell holding that address.
    """

    def __init__(self) -> None:
        self.code: list[list[Any]] = []
        self.syms: dict[str, int] = {}
        self.names: dict[str, int] = {}
        self.scratch: list[int] = []
        self.jumps: dict[str, int] = {}
        self.image: list[int] = []
        self._serial = 0

    # -- allocation ---------------------------------------------------

    def cell(self, name: str, value: int = 0) -> tuple[str, int]:
        """Return the named scratch cell, creating it with ``value``."""
        if name not in self.names:
            self.names[name] = len(self.scratch)
            self.scratch.append(value)
        return ("scratch", self.names[name])

    def const(self, value: int) -> tuple[str, int]:
        """Return a scratch cell holding the constant ``value``."""
        return self.cell(f"_k{value}", value)

    def jcell(self, label: str) -> tuple[str, int]:
        """Return a scratch cell holding the address of ``label``.

        S*bleq's ``c`` operand is indirect (``ip = mem[c]``), so a jump
        needs a cell holding the target rather than the target itself.
        """
        key = "@" + label
        if key not in self.names:
            self.names[key] = len(self.scratch)
            self.scratch.append(0)
            self.jumps[label] = self.names[key]
        return ("scratch", self.names[key])

    def field(self, label: str, off: int) -> tuple[str, str, int]:
        """Return the address of operand ``off`` of instruction ``label``."""
        return ("field", label, off)

    def fresh(self, stem: str) -> str:
        """Return a label unique to this assembler."""
        self._serial += 1
        return f"{stem}.{self._serial}"

    # -- emission -----------------------------------------------------

    def emit(self, a: Any, b: Any, c: Any = _SEQ, label: str | None = None) -> None:
        """Emit ``a b c``; ``c`` defaults to falling through."""
        if label is not None:
            self.mark(label)
        self.code.append([a, b, c])

    def mark(self, label: str) -> None:
        """Attach ``label`` to the next instruction emitted."""
        if label in self.syms:
            raise ValueError(f"duplicate label {label}")
        self.syms[label] = len(self.code)

    # -- macros -------------------------------------------------------

    def goto(self, label: str) -> None:
        """Jump to ``label`` unconditionally (zeroing a cell always branches)."""
        z = self.cell("_zero")
        self.emit(z, z, self.jcell(label))

    def clear(self, dst: Any) -> None:
        """``dst = 0``."""
        self.emit(dst, dst)

    def sub(self, dst: Any, src: Any) -> None:
        """``dst -= src``, falling through whatever the sign."""
        self.emit(dst, src)

    def add(self, dst: Any, src: Any) -> None:
        """``dst += src``, via a negated temporary."""
        neg = self.cell("_neg")
        self.emit(neg, neg)
        self.emit(neg, src)
        self.emit(dst, neg)

    def move(self, dst: Any, src: Any) -> None:
        """``dst = src``, preserving ``src``."""
        self.clear(dst)
        self.add(dst, src)

    def branch_neg(self, value: Any, label: str) -> None:
        """Branch to ``label`` when ``value`` is negative, preserving it.

        ``value < 0`` is ``value + 1 <= 0``, which is the branch S*bleq
        actually offers.
        """
        t = self.cell("_bt")
        self.move(t, value)
        self.emit(t, self.const(-1), self.jcell(label))

    def branch_le(self, value: Any, other: Any, label: str) -> None:
        """Branch to ``label`` when ``value <= other``, preserving both."""
        t = self.cell("_bt")
        self.move(t, value)
        self.emit(t, other, self.jcell(label))

    def load_indirect(self, dst: Any, addr: Any) -> None:
        """``dst = mem[addr]`` for a runtime address held in ``addr``."""
        site = self.fresh("ld")
        f = self.field(site, 1)
        self.clear(f)
        self.add(f, addr)
        self.clear(dst)
        neg = self.cell("_neg")
        self.emit(neg, neg)
        self.emit(neg, 0, label=site)  # neg -= mem[addr]; b is patched above
        self.emit(dst, neg)  # dst = -neg

    def store_indirect(self, addr: Any, value: Any) -> None:
        """``mem[addr] = value`` for a runtime address held in ``addr``."""
        zap, put = self.fresh("stz"), self.fresh("stp")
        for site, off in ((zap, 0), (zap, 1), (put, 0)):
            f = self.field(site, off)
            self.clear(f)
            self.add(f, addr)
        neg = self.cell("_neg2")
        self.clear(neg)
        self.sub(neg, value)  # neg = -value
        self.emit(0, 0, label=zap)  # mem[addr] -= mem[addr]
        self.emit(0, neg, label=put)  # mem[addr] -= -value

    # -- build --------------------------------------------------------

    def build(self) -> list[int]:
        """Resolve every symbolic operand and lay the three regions out."""
        base_scratch = 3 * len(self.code)

        seq: dict[int, int] = {}
        for i, (_a, _b, c) in enumerate(self.code):
            if c is _SEQ and 3 * (i + 1) not in seq:
                self.scratch.append(3 * (i + 1))
                seq[3 * (i + 1)] = len(self.scratch) - 1

        base_image = base_scratch + len(self.scratch)
        # ``base`` holds the image's own address, which only becomes known
        # here; the emulator adds a Decleq index to it to reach a cell.
        self.scratch[self.names["base"]] = base_image
        for label, idx in self.jumps.items():
            self.scratch[idx] = -1 if label == _HALT else 3 * self.syms[label]

        def resolve(v: Any) -> int:
            if isinstance(v, tuple):
                if v[0] == "scratch":
                    return base_scratch + int(v[1])
                return 3 * self.syms[str(v[1])] + int(v[2])
            return int(v)

        mem: list[int] = []
        for i, (a, b, c) in enumerate(self.code):
            target = base_scratch + seq[3 * (i + 1)] if c is _SEQ else resolve(c)
            mem += [resolve(a), resolve(b), target]
        return mem + self.scratch + self.image


_HALT = "__halt__"  # a jump cell holding -1; S*bleq halts on a negative target


def decleq_to_sbleq(program: str) -> str:
    """Rewrite a Decleq program as an equivalent S*bleq program.

    Decleq's ``a b c`` does ``mem[b] = mem[a] - 1`` and jumps to ``c`` when
    the new ``mem[b]`` is at most zero; S*bleq's ``a b c`` does
    ``mem[a] -= mem[b]`` and jumps *indirectly* to ``mem[c]``.

    A Decleq program is self-modifying memory -- it can compute a jump into
    the middle of what it just wrote -- so no static per-instruction
    rewrite can be total: a computed target may land anywhere, including
    the interior of a translated block.  The output is therefore a Decleq
    *emulator*: a fixed fetch-decode-execute loop over the Decleq image,
    which is embedded as data.  S*bleq supplies the dynamic dispatch this
    needs, its ``c`` operand being indirect, and the loop reaches a
    computed address by patching the operand fields of its own load and
    store instructions.

    Memory is laid out as ``[loop | scratch | image]`` with the image
    *last*, so that Decleq's grow-on-write and read-past-the-end-as-zero
    conventions coincide with S*bleq's own.  Decleq's ``pc`` and its live
    memory length live in scratch cells; the length is what moves the halt
    boundary outward when a write lands past the end.

    The rewrite is total over programs: every whitespace-separated list of
    integers translates, whatever the values, and whatever the length --
    including the self-modifying, non-multiple-of-three and negative-operand
    programs that have no static translation.  It agrees with the Decleq
    interpreter on every run that interpreter completes normally.  What it
    cannot reproduce are that interpreter's *error* exits, and two of those
    are structural rather than incidental: S*bleq's sole input primitive
    (address ``-2``) yields ``0`` both at end-of-input and for an empty
    input line, where Decleq raises :class:`EOFError` and yields ``10``
    respectively.  Two inputs reaching one value is a collision in the
    target language's only input primitive, so *no* S*bleq program can tell
    them apart, and no translation can either.  The rest are not behaviour
    to reproduce: Decleq's ``HaltError`` is a harness step budget, and an
    out-of-range negative ``b`` crashes the interpreter with
    :class:`IndexError`.
    """
    from esolangs.interpreters.memory import parse_int_memory as _parse

    cells = _parse(program)
    asm = _SbleqAsm()
    asm.image = list(cells)

    base = asm.cell("base", 0)  # absolute address of the image, set on build
    pc = asm.cell("pc", 0)
    dlen = asm.cell("dlen", len(cells))
    a, b, c = asm.cell("a"), asm.cell("b"), asm.cell("c")
    val = asm.cell("val")
    beff = asm.cell("beff")
    addr = asm.cell("addr")
    idx = asm.cell("idx")
    one, two, three = asm.const(1), asm.const(2), asm.const(3)

    def load_cell(dst: Any, index: Any) -> None:
        """``dst = mem[index]`` under Decleq's guard: out of range reads zero."""
        done = asm.fresh("gl")
        asm.clear(dst)
        asm.branch_neg(index, done)
        asm.branch_le(dlen, index, done)  # dlen <= index: past the end
        asm.move(addr, base)
        asm.add(addr, index)
        asm.load_indirect(dst, addr)
        asm.mark(done)

    def equals(value: Any, want: int, label: str) -> None:
        """Branch to ``label`` when ``value == want`` (two ``<=`` tests)."""
        low, done = asm.fresh("eq"), asm.fresh("eq")
        t = asm.cell("_et")
        asm.move(t, value)
        asm.sub(t, asm.const(want))
        asm.emit(t, asm.const(0), asm.jcell(low))  # value <= want
        asm.goto(done)
        asm.mark(low)
        asm.clear(t)
        asm.add(t, asm.const(want))
        asm.sub(t, value)
        asm.emit(t, asm.const(0), asm.jcell(label))  # want <= value
        asm.mark(done)

    def effective_b() -> None:
        """``beff`` = Decleq's write index for ``b``, growing memory to fit.

        A negative ``b`` indexes from the end (the reference interpreter
        writes through Python's negative indexing), and a write at or past
        the end extends memory, which is what moves the halt boundary.
        """
        stem = asm.fresh("be")
        asm.move(beff, b)
        asm.branch_neg(b, stem + ".neg")
        asm.goto(stem + ".sized")
        asm.mark(stem + ".neg")
        asm.add(beff, dlen)
        asm.mark(stem + ".sized")
        asm.branch_le(dlen, beff, stem + ".grow")
        asm.goto(stem + ".done")
        asm.mark(stem + ".grow")  # dlen <= beff: extend to beff + 1
        asm.move(dlen, beff)
        asm.add(dlen, one)
        asm.mark(stem + ".done")

    # -- fetch --------------------------------------------------------
    asm.mark("fetch")
    asm.branch_neg(pc, _HALT)
    asm.branch_le(dlen, pc, _HALT)
    load_cell(a, pc)
    asm.move(idx, pc)
    asm.add(idx, one)
    load_cell(b, idx)
    asm.move(idx, pc)
    asm.add(idx, two)
    load_cell(c, idx)

    # -- decode -------------------------------------------------------
    equals(a, -2, "out")
    equals(a, -1, "in")
    asm.goto("arith")

    # -- output: print mem[b], then fall through three cells ----------
    asm.mark("out")
    load_cell(val, b)
    asm.emit(-3, val)
    asm.add(pc, three)
    asm.goto("fetch")

    # -- input: mem[b] = next byte, then fall through three cells -----
    asm.mark("in")
    effective_b()
    asm.clear(val)
    asm.sub(val, -2)  # val = -byte; -2 is read exactly once
    asm.clear(addr)
    asm.sub(addr, val)
    asm.move(val, addr)  # val = byte
    asm.move(addr, base)
    asm.add(addr, beff)
    asm.store_indirect(addr, val)
    asm.add(pc, three)
    asm.goto("fetch")

    # -- arithmetic: mem[b] = mem[a] - 1; branch to c when <= 0 -------
    asm.mark("arith")
    effective_b()
    load_cell(val, a)
    asm.sub(val, one)
    asm.move(addr, base)
    asm.add(addr, beff)
    asm.store_indirect(addr, val)
    asm.branch_le(val, asm.const(0), "taken")
    asm.add(pc, three)
    asm.goto("fetch")
    asm.mark("taken")
    asm.move(pc, c)
    asm.goto("fetch")

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
# character the parser has already rejected.  Every arm must still advance
# the walk: a command that falls through without stepping ``i`` spins
# forever, so the walks name the commands they merely skip over.
_LaserOp = Literal["+", "-", ">", "<", ".", ",", "[", "]"]

# Typed so the parser's membership test narrows the character to a
# command, instead of asserting it afterwards.
_LASER_OPS: frozenset[_LaserOp] = frozenset(get_args(_LaserOp))


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
        if c == "]":
            # A loop close is consumed by the ``[`` arm below; one reaching
            # the walk directly has no cell of its own, so just step past it.
            i += 1
        elif c in "+-><.,":
            g.set(row, col, c)
            col += 1
            i += 1
        else:
            # ``_laser_parse`` emits only ``+-<>.,[]`` and the arms above
            # take the other seven, so this is a loop open.
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
    r"""Analyze the ops statically: final pointer, max cell, output cell.

    Loops must have net-zero pointer displacement (so the pointer stays
    statically known) and the pointer must never move below cell 0
    (LaserFuck's tape has no negative cells).  Prints are unrestricted:
    any number of them, anywhere, including inside a loop, since each
    appends onto an output region at runtime and the dump replays the
    region at halt (:func:`_laser_stage_prints`).  ``out_cell`` reports
    the last print's cell, for callers that still ask about a
    single-output program.
    """
    ptr = 0
    maxcell = 0
    i = 0
    out_cell: int | None = None
    while i < len(ops):
        c = ops[i]
        if c in "+-,]":
            # Cell mutation and the loop close move no pointer and reach no
            # new cell, so they only need to advance the walk.
            i += 1
        elif c == ">":
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
            # Any number of top-level prints are in class: they are staged
            # into an output region and dumped in order at halt (see
            # ``_laser_stage_prints``).  ``out_cell`` records the last one
            # only for callers that still ask about a single-output program.
            out_cell = ptr
            i += 1
        else:
            # As in ``_laser_emit``: the parse admits only ``+-<>.,[]``, so
            # what is left after the arms above is a loop open.
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
        elif ch in _LASER_OPS:
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
            ops.append(ch)
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


def _laser_move(delta: int) -> list[_LaserOp]:
    """Return the moves that shift the pointer by ``delta``."""
    return [">"] * delta if delta > 0 else ["<"] * -delta


def _laser_stage_prints(
    ops: list[_LaserOp], maxcell: int
) -> tuple[list[_LaserOp], int, int, int, int]:
    r"""Rewrite each ``.`` into an append onto the output region.

    LaserFuck has no output command: it prints the tape once, when the last
    laser dies.  A single final ``.`` therefore translates by leaving that
    one cell for the dump -- but a program that prints several times, or
    prints before doing more work, has nothing to translate into under that
    reading.

    It does under a staged one.  Equivalence is judged on the output a
    terminating run captures, so *when* a byte leaves the program is
    unobservable; only its order survives.  So each ``.`` copies its cell
    onto the end of an output region and the dump replays the region, in
    tape order, at the end.

    The append is found at *runtime* rather than numbered at compile time,
    which is what lets a ``.`` sit inside a loop, where the number of
    prints is not known until the loop runs.  A slot holds ``value + 1``,
    so an occupied slot is nonzero and an empty one is zero, and ``[>]``
    walks to the first free slot.  That bias needs a cell that cannot
    collide at the top of its range, which LaserFuck's *unbounded* cells
    give -- the same encoding is impossible on a byte that wraps, where
    ``255 + 1`` would read as empty.  The epilogue subtracts the bias back
    out.

    The layout is::

        0        landmark, set to 1 once and never cleared
        1..M+1   the program's cells (logical cell ``i`` at ``i + 1``)
        M+2      t, the transfer counter
        M+3      t2, the duplicate-and-restore scratch
        M+4      gap, permanently zero: the left walk's landmark
        M+5..    the output slots

    Cell 0 is a landmark because LaserFuck *prepends* a cell when ``<``
    runs at cell 0 rather than clamping, which would shift every address
    and corrupt the layout; a nonzero cell 0 stops ``[<]`` before it can
    happen.  The gap is never written, and movement alone does not mark a
    cell as used, so it stays invisible to the dump.

    Each print is three phases, all pointer-neutral, so they nest inside
    the program's own loops: duplicate the source into ``t`` (restoring it
    through ``t2``), walk to the first free slot and claim it with ``+``
    (which is the bias, and also the write that makes the slot visible to
    the dump -- a staged ``\x00`` would otherwise be skipped as untouched),
    then transfer ``t`` units into that slot one lap at a time, stepping
    back one cell from the first *free* slot each lap so the units land
    together rather than scattering.

    A copy drains its source one unit per lap, so it needs that source to
    be non-negative -- and a Dimensional cell goes negative only by relying
    on the byte wrap LaserFuck's unbounded cells do not have, which is
    already out of class.  What staging changes is how that shows: the
    epilogue's ``[-]`` already failed to terminate on a negative *working*
    cell (``-->0+.`` hangs before this change too), and now a negative
    *printed* cell does the same, where it used to print nothing and lose
    the byte.  Both are wrong for an out-of-class program; a hang is at
    least loud.  Rejecting them instead would need to prove a cell stays
    non-negative through arbitrary loops, which is the unsound static
    value analysis this module has twice removed.

    Returns the rewritten ops and the ``base``, ``t``, ``t2`` and ``gap``
    addresses.
    """
    base = 1  # logical cell 0, one past the landmark
    t = base + maxcell + 1
    t2 = t + 1
    gap = t2 + 1

    out: list[_LaserOp] = ["+"]  # the landmark, written once
    out.extend(_laser_move(base))
    ptr = base

    for op in ops:
        if op != ".":
            out.append(op)
            ptr += (op == ">") - (op == "<")
            continue

        # duplicate the source into t, restoring it through t2
        out.append("[")
        out.append("-")
        out.extend(_laser_move(t - ptr))
        out.append("+")
        out.extend(_laser_move(t2 - t))
        out.append("+")
        out.extend(_laser_move(ptr - t2))
        out.append("]")
        out.extend(_laser_move(t2 - ptr))
        out.append("[")
        out.append("-")
        out.extend(_laser_move(ptr - t2))
        out.append("+")
        out.extend(_laser_move(t2 - ptr))
        out.append("]")
        out.extend(_laser_move(t - t2))

        # claim the first free slot: this is the bias, and the write that
        # makes the slot visible to the dump
        out.extend(_laser_move(gap - t))
        out.append(">")
        out.extend(["[", ">", "]"])
        out.append("+")
        out.extend(["[", "<", "]"])
        out.extend(_laser_move(t - gap))

        # transfer t into the claimed slot, one unit per lap
        out.append("[")
        out.append("-")
        out.extend(_laser_move(gap - t))
        out.append(">")
        out.extend(["[", ">", "]"])
        out.append("<")
        out.append("+")
        out.extend(["[", "<", "]"])
        out.extend(_laser_move(t - gap))
        out.append("]")

        out.extend(_laser_move(ptr - t))

    return out, base, t, t2, gap


def _laser_assemble(ops: list[_LaserOp]) -> str:
    r"""Analyze ``ops``, stage its output, and lay out the grid.

    The half of a LaserFuck translation that does not depend on the source
    language: every transpiler targeting LaserFuck ends here, so the
    supported class (:func:`_laser_analyze`) and the printed tape are the
    same whichever language the ops came from.

    LaserFuck prints the whole tape when the last laser dies, which is its
    only output, so the program's bytes are appended to an output region by
    :func:`_laser_stage_prints` and the epilogue arranges for the dump to
    show exactly that region: the landmark, the working cells and both
    scratch cells are driven negative (``[-]-`` clears a cell and then
    takes it below zero, and the dump excludes negative cells), the gap is
    stepped over unwritten, and ``[->]`` walks the slots subtracting the
    bias each holds.  A slot biased to ``1`` lands on zero and stays
    visible, since claiming it was a write, so a printed ``\x00`` survives.
    """
    ptr, maxcell, _out_cell = _laser_analyze(ops)
    staged, base, _t, _t2, gap = _laser_stage_prints(ops, maxcell)

    # The staged program is pointer-neutral at every print, and an in-class
    # loop has net-zero displacement, so it ends where the original does --
    # shifted by the landmark.  Counting the emitted text would be wrong:
    # claiming a slot spends a ``>`` whose return is inside a walk.
    epi: list[_LaserOp] = _laser_move(-(base + ptr))
    for _cell in range(gap):  # landmark, working cells, t and t2
        epi.extend(["[", "-", "]", "-", ">"])
    epi.append(">")  # step over the gap, unwritten and so invisible
    epi.extend(["[", "-", ">"])  # debias each slot, halting on the first free
    epi.append("]")
    g = _LaserGrid()
    _laser_funnel(g)
    _laser_emit(g, staged + epi, 0, 3)
    return g.dump()


def dimensional_to_laserfuck(program: str) -> str:
    r"""Rewrite a Dimensional program into LaserFuck.

    Dimensional's brainfuck-like core (``>0``/``<0``, ``+``/``-``, ``.``/``,``,
    ``[``/``]``, and the ``=HH``/``:CH`` literals) maps onto a LaserFuck grid.
    A start-marker funnel pins the laser's random initial heading, ``[``
    becomes a ``v`` that detours the beam into a loop ring below the strip,
    and the ring's test ``# v ) \\`` reflects a nonzero cell back into the
    body and lets a zero cell fall through to the exit, so the loop runs
    exactly while its cell is nonzero like Dimensional's.

    LaserFuck prints the whole tape once when the laser dies, which is its
    only output, so each ``.`` appends its cell to an output region that
    the dump replays in order (:func:`_laser_stage_prints`); the epilogue
    drives the working cells negative to hide them.  A program may
    therefore print as many times as it likes, wherever it likes --
    including inside a loop, where the number of prints is not known until
    the loop runs.

    Everything outside this core is rejected rather than mistranslated: the
    pointer hierarchy (``$``, ``{``/``}``, ``?``/``!``), the numeric
    readers (``d``/``x``), bare or non-zero-dimension moves, moving below
    cell 0, and loops that drift the pointer.  Cells do not wrap at 8
    bits in the translation (LaserFuck cells are unbounded), so programs
    that rely on Dimensional's byte wrapping are out of class -- and a
    negative cell makes the emitted program hang rather than answer, both
    at a print and, as before this change, in the epilogue.
    """
    ops = _laser_parse(program)
    return _laser_assemble(ops)


# Streetcode's instruction set is brainfuck's, one glyph for one command,
# which is what makes the pair a rewrite rather than an interpreter.  ``U``
# and ``;`` are absent on purpose: both are *movement*, already accounted
# for by the drive graph the walk follows, and neither leaves a command
# behind.  Anything else on the grid is road.
_STREET_OPS: dict[str, _LaserOp] = {
    "^": "+",
    "~": "-",
    "=": ">",
    "_": "<",
    "I": ",",
    "O": ".",
}


def _street_linearize(machine: Any) -> list[_LaserOp]:
    """Walk the drive graph from the car's start, emitting its commands.

    The whole of the Streetcode frontend.  Each drive state's successors
    are keyed by the two zero-ness bits movement may read -- the arrival
    cell and the current one -- so a state whose four successors agree is
    road the car drives the same way whatever the tape holds, and the
    square's command can simply be emitted.  A state whose successors
    differ is one the *tape* steers, and this walk rejects it: see
    :func:`streetcode_to_laserfuck` for why a drawn loop has no brainfuck
    image.

    What remains is a straight walk, so it needs no recursion and no
    bracket emission.  The ``seen`` guard is still load-bearing: the
    interpreter validates that the car can always drive *out* of a square,
    not that it ever stops, so a junction-free ring is a program that
    never halts and has nothing to translate into.
    """
    ops: list[_LaserOp] = []
    state = machine._state  # noqa: SLF001
    seen: set[Any] = set()
    while state != "halt" and state is not None:
        if state in seen:
            raise ValueError(
                "the car drives a ring with nothing to stop it: the program "
                "does not halt, so it has no translation"
            )
        seen.add(state)
        edges = machine._graph[state]  # noqa: SLF001
        if len({*edges.values()}) > 1:
            raise ValueError(
                "the car steers on the tape at "
                f"{(state.row, state.col)}: drawn control flow is out of the "
                "supported class (a Streetcode ring has no brainfuck loop "
                "image -- see streetcode_to_laserfuck)"
            )
        if op := _STREET_OPS.get(machine.grid[state.row, state.col]):
            ops.append(op)
        state = edges[0, 0]
    return ops


def streetcode_to_laserfuck(program: str) -> str:
    r"""Rewrite a Streetcode program into LaserFuck.

    The two languages hold the same thing -- a tape of unbounded signed
    cells under a pointer -- and Streetcode's instructions are brainfuck's
    under different glyphs (``^~`` increment and decrement, ``=_`` move the
    cell pointer, ``I``/``O`` read and write a character).  What differs is
    control flow: Streetcode has no loop command, only *roads*, and the car
    branches by taking the leftmost exit of a junction when the cell under
    it is zero and the second-leftmost otherwise.

    So the translation is a linearization.  The interpreter's own drive
    graph -- :meth:`_Machine._drive_states`, which enumerates every state
    the car can reach and keys each one's successors by the tape bits
    movement is allowed to read -- is walked from the start, emitting the
    command under each square.  Movement itself emits nothing, because the
    walk has already accounted for it.

    The supported class is programs the tape never steers: straight-line
    drives, input included, with a single trailing ``O``.  Everything else
    is rejected rather than mistranslated.

    Why drawn control flow is out of class
    --------------------------------------

    brainfuck's loop tests its cell at the top and again at the bottom of
    the same body, so a translation needs a drive state the car returns to
    once per lap.  A drawn Streetcode ring does not offer one.  Two
    measured examples, both in the test suite:

    * A ring entered from a junction re-joins the road *past* that
      junction's square, and comes back under a different heading and
      different steering latches -- so the state that decides the loop is
      never revisited, and there is no ``[`` to close.
    * The counting loop in ``tests/interpreters/test_streetcode.py`` does
      re-cross its test square, but its lap crosses further gaps, and
      every gap crossing reads the CPth cell.  Those extra reads are
      junctions too; proving they cannot steer needs to know the
      accumulator never reaches zero mid-lap, which is value analysis
      across iterations rather than a rewrite.

    Both are shapes a *compiler* could lower with scratch cells and a
    converged answer.  Neither is a program rewrite, which is what a
    transpiler in this package is, so the walk rejects a tape-steered
    square and says so.  The boolean generator's programs are further out
    still: they are decision trees, whose leaves each print.

    Also rejected, by :func:`_laser_analyze` on the way out: moving below
    cell 0, and any output that is not a single final one (LaserFuck
    prints its tape once, when the last laser dies).

    Cells do not wrap in either language, and both read input as the first
    character of a line (zero on a blank one), so the tape and the I/O need
    no translation of their own.
    """
    from esolangs.interpreters.grid_based.streetcode import _Machine
    from esolangs.interpreters.io import ScriptedIO

    machine = _Machine(program.splitlines(), ScriptedIO(""))
    return _laser_assemble(_street_linearize(machine))


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
    ("Streetcode", "LaserFuck"): streetcode_to_laserfuck,
}
