"""Transpile programs between languages.

Each ``TRANSPILERS`` entry maps a ``(source, target)`` language-name pair to
a function that rewrites a program in the source language into an
equivalent program in the target.

Admission criteria
------------------

A transpiler is admitted only if it is **total** over its source language.
Partial transpilers were removed rather than documented, because a
supported *subset* is a promise the caller cannot check: the ones this repo
carried drifted, in every case, toward either refusing programs their
source language accepts or -- worse -- translating them wrongly without
saying so.  What replaced them is a contract with five parts, each of which
a candidate must satisfy before it is added.

1. **Total over the source.**  The transpiler accepts every program the
   source language's own interpreter accepts.  It may raise only where that
   interpreter raises on the identical input -- unbalanced brackets are
   malformed in both, so refusing them is not a class restriction.
   Rejecting any well-formed source program is disqualifying.

2. **Equivalent on completed runs.**  For every run the source interpreter
   completes normally, the translation produces identical output through
   the target's interpreter.  Verified by a pinned battery *and* a seeded
   fuzz, and the fuzz may not carry a rejection skip-arm: an
   ``except ValueError: continue`` hides exactly the programs a partial
   transpiler drops.  Assert instead how many random programs actually ran.

3. **Residues proved, not asserted.**  A divergence may survive only if it
   is a property of the *target language* rather than of the translation --
   proved to that standard, recorded in ``docs/limitations.md``, and pinned
   by a test that asserts the divergence rather than avoiding it.
   :func:`decleq_to_sbleq` is the worked example: S*bleq's only input
   primitive maps end-of-input and an empty line onto the same value, so no
   S*bleq program whatsoever can separate them, and the test says so.

4. **No narrated restrictions.**  A class restriction stated in a docstring
   but not enforced in code is disqualifying on its own.  That defect is
   what removed ``bio_to_bf``: it named a class its callers had no way to
   observe, and a program outside it was quietly mistranslated.

5. **Witnesses executed.**  Every claim above is settled by running the two
   interpreters and comparing, never by reading the code.  Each raise site
   an admitted transpiler keeps must be reached by a test.

The five that meet this are ``brainfuck -> 3D Brainfuck``,
``brainfuck -> Painfuck``, ``brainfuck -> Streetcode``,
``BFStack -> brainfuck`` and ``Decleq -> S*bleq``.  The six removed, and why
each failed, are recorded under "Transpilers: the admission bar, and what it
removed" in ``docs/limitations.md``.

``brainfuck -> Streetcode`` lowers brainfuck's tape to Streetcode's road
network: a loop is a room the car laps until the tested cell is zero.  It is
in ``transpilers/_bf_streetcode.py`` rather than here because its geometry pass is
large; the wraparound Streetcode lacks is handled by a brainfuck-level
canonicalizer before the drawing, so the drawing stays total.
"""

from collections.abc import Callable
from typing import Any

from esolangs.transpilers._bf_streetcode import bf_to_streetcode
from esolangs.transpilers._sbleq_asm import _HALT, _SbleqAsm

__all__ = [
    "TRANSPILERS",
    "bf_to_painfuck",
    "bf_to_streetcode",
    "bf_to_three_d_brainfuck",
    "bfstack_to_bf",
    "decleq_to_sbleq",
]


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
    clamping is required: ``+.<.`` prints
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
    Brainfuck maps onto Painfuck's commands directly: ``>``/``<`` become
    ``rl``/``l``, ``+``/``-`` become ``ps``/``s``, ``[``/``]``/``,``/``.``
    become ``a``/``b``/``j``/``u``.  The interpreter's forward shift is
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


TRANSPILERS: dict[tuple[str, str], Callable[..., str]] = {
    ("brainfuck", "3D Brainfuck"): bf_to_three_d_brainfuck,
    ("brainfuck", "Painfuck"): bf_to_painfuck,
    ("brainfuck", "Streetcode"): bf_to_streetcode,
    ("BFStack", "brainfuck"): bfstack_to_bf,
    ("Decleq", "S*bleq"): decleq_to_sbleq,
}
