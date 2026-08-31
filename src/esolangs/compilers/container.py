r"""Compiler that turns Container programs into RISC-V Linux assembly.

Container is a *synchronous* rule system, and that is the fact the whole
lowering turns on.  Every tick, each container computes a new value from
the values every container held at the *start* of the tick -- including its
own -- so a tick is a dataflow round, not a sequence of assignments.  The
compiled form is two 8-byte-per-container buffers, ``old`` and ``new``:
every rule reads ``old``, every container writes ``new``, and the tick ends
by copying ``new`` over ``old``.  Nothing else would be correct; updating in
place would let a container declared earlier feed a later one its *new*
value within the same tick.

Containers and their rules are entirely static -- the program has no
dispatch, no addressing, and no control flow -- so the tick body is emitted
as straight-line unrolled code and the outer loop is the only branch that
is not a comparison.  A rule ``n X>=Y`` becomes two loads (or immediates),
one ``bge``, and one ``addi``; ``max(res, 0)`` is one ``bgez`` per
container, wrapping the whole rule sum rather than each rule, matching the
interpreter's single ``max`` at the end of ``update``.

The parser is the interpreter's own ``_Machine.__init__`` rather than a
rewrite, so the compiler accepts exactly the programs the interpreter
parses: the colon-strip, the ``name = initial`` split, the blank-line skip,
and the rule-before-declaration ``ValueError`` all come from one shared
implementation.

**Undeclared names are rejected at compile time**, and this rejects exactly
the programs the interpreter crashes on rather than narrowing the class.
``update`` calls ``val`` on every operand of every rule on every tick, and
``val`` falls through to ``int(s)`` for a name no container declares -- so
such a program raises ``ValueError`` on its *first* tick, before any input
or output can happen.  A static check is therefore equivalent, not stricter.

The three special containers keep the interpreter's order within a tick --
PRINT, then input, then EXIT -- because that order is observable:

* **PRINT** fires on the *edge* ``old == 0`` and ``new != 0``, and only when
  ``OUT`` is declared.  It writes ``new[OUT] % 128``: the mask is **0x7f**,
  not the 0xff a byte write would use.
* **The empty-named container** fires on the same edge and writes the byte
  it reads into ``new[IN]`` -- *after* IN's own rules have run, so the read
  clobbers whatever IN computed on that tick and only on that tick.  When a
  program declares ``""`` but no ``IN``, the interpreter drops the write
  next tick (the container list has no IN to carry it), so the compiled form
  reads the byte and discards it, which is the same observable behaviour.
* **EXIT** fires on *any* change, not on an edge to nonzero: an EXIT falling
  from 5 to 4 halts with code 4.  The new value is the exit code, which the
  compiled program passes to the ``exit`` syscall.

Input is read as raw bytes with ``\n`` skipped, which reproduces the
interpreter's queue exactly.  The interpreter refills from
``IO.input_str``, whose lines arrive *without* their terminators, and
``self.queue += list(s)`` concatenates those line contents; the
``while not self.queue`` loop then skips empty lines.  The concatenation of
every line's contents is the raw byte stream minus its newlines, so a
byte reader that skips ``\n`` builds the same queue.  This is the one place
``_riscv_common.GETBYTE`` is used by a compiler whose input is actually
exercised: the roadmap's note that GETBYTE is no precedent for a *reader*
applies to line-faithful readers like Forbin's ``in``, and Container's is
not one -- it consumes a line one character per pulse, not one character per
line.  EOF halts the run, matching the interpreter's ``EOFError``.

Values are 64-bit signed words where the interpreter's are unbounded Python
integers, the fixed-width caveat the other compilers document.  Comparisons
are signed because both initial values and rule literals may be negative.

Registers: ``s1`` = the ``old`` buffer, ``s2`` = the ``new`` buffer, ``s3``
= a rule sum under construction, ``t6`` = a computed address for a cell
past the 12-bit load/store offset.  ``t0``--``t2`` are the per-rule
scratch, which is why the far-cell path can use ``t6`` freely.
"""

import sys

from esolangs.compilers._riscv_common import GETBYTE, PUTBYTE
from esolangs.interpreters.io import IO
from esolangs.interpreters.other.container import _Machine

# The interpreter's three special names, each with its own tick-order slot.
_PRINT = "PRINT"
_OUT = "OUT"
_IN = "IN"
_EXIT = "EXIT"
_READER = ""


# `ld`/`sd` take a 12-bit signed offset, so a cell past 255 cannot be
# addressed directly.  The boolean generator reaches that: a truth table
# needs `2**n + 2n + 7` containers, which passes 255 at `n == 8`.
_MAX_OFFSET = 2040


def _access(op: str, reg: str, base: str, cell: int) -> str:
    """Emit ``ld``/``sd`` of ``reg`` at ``cell``, indirect when it is far.

    Every offset is a compile-time constant, so the wide form is chosen per
    site rather than applied everywhere: past the 12-bit immediate, ``t6``
    (which no rule emit uses) carries the computed address.
    """
    offset = cell * 8
    if offset <= _MAX_OFFSET:
        return f"    {op}   {reg}, {offset}({base})\n"
    return f"    li   t6, {offset}\n    add  t6, {base}, t6\n    {op}   {reg}, 0(t6)\n"


def _operand(token: str, cells: dict[str, int], reg: str) -> str:
    """Emit ``reg = token``: a load from ``old``, or an immediate.

    Mirrors the interpreter's ``val``: a declared container's name reads its
    value, and anything else is an integer literal.  A name that is neither
    is what :func:`_conditions` rejects.
    """
    if token in cells:
        return _access("ld", reg, "s1", cells[token])
    return f"    li   {reg}, {int(token)}\n"


def _conditions(machine: _Machine) -> None:
    """Reject any rule operand that is neither a container nor a literal.

    The interpreter would raise ``ValueError`` from ``int()`` on the first
    tick, so this rejects the same programs, only earlier.
    """
    for con in machine.obj:
        for _, cond in con.rules:
            sep = "<=" if "<" in cond else ">="
            for token in cond.split(sep):
                if token not in machine.var:
                    try:
                        int(token)
                    except ValueError:
                        raise ValueError(
                            f"undeclared container in condition: {token!r}"
                        ) from None


def _emit_container(index: int, con: object, cells: dict[str, int]) -> str:
    """Emit one container's update: sum its satisfied deltas, then clamp.

    ``s3`` accumulates from the container's *old* value; each rule compares
    two operands and adds its delta when the comparison holds.  The clamp is
    one test at the end, not one per rule, matching ``max(res, 0)``.
    """
    res = _access("ld", "s3", "s1", cells[con.name])  # type: ignore[attr-defined]
    for i, (delta, cond) in enumerate(con.rules):  # type: ignore[attr-defined]
        label = f".skip_{index}_{i}"
        if "<" in cond:
            left, right = cond.split("<=")
            res += _operand(left, cells, "t0")
            res += _operand(right, cells, "t1")
            res += f"    blt  t1, t0, {label}\n"  # skip unless left <= right
        else:
            left, right = cond.split(">=")
            res += _operand(left, cells, "t0")
            res += _operand(right, cells, "t1")
            res += f"    blt  t0, t1, {label}\n"  # skip unless left >= right
        res += f"    li   t2, {delta}\n"
        res += "    add  s3, s3, t2\n"
        res += f"{label}:\n"
    res += f"    bgez s3, .keep_{index}\n"
    res += "    li   s3, 0\n"
    res += f".keep_{index}:\n"
    res += _access("sd", "s3", "s2", cells[con.name])  # type: ignore[attr-defined]
    return res


def _emit_print(cells: dict[str, int]) -> str:
    """Emit the PRINT edge: fire on ``old == 0`` and ``new != 0``.

    Only a program declaring both PRINT and OUT can print; the byte written
    is ``OUT % 128``, so the mask is 0x7f rather than a byte's 0xff.
    """
    if _PRINT not in cells or _OUT not in cells:
        return ""
    return (
        _access("ld", "t0", "s1", cells[_PRINT])
        + "    bnez t0, .no_print\n"
        + _access("ld", "t0", "s2", cells[_PRINT])
        + "    beqz t0, .no_print\n"
        + _access("ld", "a0", "s2", cells[_OUT])
        + "    andi a0, a0, 0x7f\n"  # the interpreter's `% (1 << 7)`, not 0xff
        "    call putbyte\n"
        ".no_print:\n"
    )


def _emit_read(cells: dict[str, int]) -> str:
    """Emit the input edge: read one queue character into ``new[IN]``.

    The write lands in the *new* buffer after IN's own rules have already
    written it, reproducing the interpreter's clobber.  With no IN declared
    the byte is still consumed and then dropped, which is what the
    interpreter's dict-comprehension does with the orphaned key.
    """
    if _READER not in cells:
        return ""
    res = (
        _access("ld", "t0", "s1", cells[_READER])
        + "    bnez t0, .no_read\n"
        + _access("ld", "t0", "s2", cells[_READER])
        + "    beqz t0, .no_read\n"
        + "    call readqueue\n"
    )
    if _IN in cells:
        res += _access("sd", "a0", "s2", cells[_IN])
    res += ".no_read:\n"
    return res


def _emit_exit(cells: dict[str, int]) -> str:
    """Emit the EXIT check: halt on *any* change, with the new value as code."""
    if _EXIT not in cells:
        return ""
    return (
        _access("ld", "t0", "s1", cells[_EXIT])
        + _access("ld", "t1", "s2", cells[_EXIT])
        + "    beq  t0, t1, .no_exit\n"
        "    mv   a0, t1\n"
        "    li   a7, 93\n"
        "    ecall\n"
        ".no_exit:\n"
    )


def _readqueue() -> str:
    r"""Emit the queue reader: the next stdin byte that is not a newline.

    ``IO.input_str`` strips line terminators and the interpreter's refill
    loop skips empty lines, so the queue holds every input byte except
    ``\n``.  EOF halts, as the interpreter's ``EOFError`` unwinds the run.
    """
    return (
        "# readqueue() -> a0; the next non-newline byte, matching the\n"
        "# interpreter's queue of line contents (input_str drops terminators)\n"
        "readqueue:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 8(sp)\n"
        ".readqueue_loop:\n"
        "    call getbyte\n"
        "    li   t0, 10\n"
        "    beq  a0, t0, .readqueue_loop\n"
        "    ld   ra, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
    )


def comp(code: str) -> str:
    """Compile a Container program to RISC-V assembly with syscall I/O."""
    machine = _Machine(code.split("\n"), IO())
    _conditions(machine)

    # Declaration order is the tick's write order, and a name declared twice
    # shares one cell: the interpreter builds `new` as a dict comprehension,
    # so the last container of a repeated name wins, which a later store to
    # the same cell reproduces exactly.
    cells: dict[str, int] = {}
    for con in machine.obj:
        cells.setdefault(con.name, len(cells))

    if not machine.obj:
        # No containers is an immediately halted program: `halted` is true
        # before the first tick, and `run` exits without a code.
        return (
            "    .text\n    .option norelax\n    .global _start\n_start:\n"
            "    li   a0, 0\n    li   a7, 93\n    ecall\n"
        )

    body = ""
    for i, con in enumerate(machine.obj):
        body += _emit_container(i, con, cells)
    body += _emit_print(cells)
    body += _emit_read(cells)
    body += _emit_exit(cells)

    # Commit: new becomes old for the next tick.  Every container stores to
    # `new` unconditionally, so swapping `s1`/`s2` would also be correct and
    # would cost two instructions instead of `2n`; the copy is kept because
    # the specials above read *both* buffers by name, and an alternating
    # role for the two registers would make each of those reads depend on
    # the tick's parity.
    for i in range(len(cells)):
        body += _access("ld", "t0", "s2", i) + _access("sd", "t0", "s1", i)

    initial = [0] * len(cells)
    for name, cell in cells.items():
        initial[cell] = machine.var[name]

    # `old` and `new` are halves of one array so a single symbol reaches
    # both; both start at the declared initial values, since the first tick
    # overwrites every cell of `new` before anything reads it.
    data = "    .data\n    .align 3\ncon_cells:\n"
    data += "".join(f"    .dword {v}\n" for v in initial * 2)

    # `.option norelax` for the reason Forbin needs it: the assembler
    # otherwise relaxes `la` to a gp-relative `addi`, and nothing
    # initializes `gp` under `-nostdlib`, so the buffer pointer would be
    # garbage and every store would land outside mapped memory.
    return (
        "    .text\n"
        "    .option norelax\n"
        "    .global _start\n"
        "_start:\n"
        "    la   s1, con_cells\n"
        # `li`+`add` rather than `addi`: the offset passes 12 bits at 256
        # containers, and `li` materializes any width.
        f"    li   t0, {len(cells) * 8}\n"
        "    add  s2, s1, t0\n"
        ".tick:\n" + body + "    j    .tick\n"
        "# EXIT is the only halt a Container program has; EOF on input\n"
        "# lands here, matching the interpreter's unwinding EOFError\n"
        ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n" + GETBYTE + PUTBYTE + _readqueue() + data
    )


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1]) as _source:
        print(comp(_source.read()), end="")
