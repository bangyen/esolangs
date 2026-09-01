"""Compiler that turns Forbin programs into RISC-V Linux assembly.

Forbin's values are bits and functions, and its functions nest, are
first-class, and recurse -- so unlike the transliterating compilers this
lowers to a real call graph over a runtime frame chain.

**Scoping is dynamic, not lexical**, and that is the fact the whole design
turns on.  ``_call`` builds each frame as ``_Frame(callee, caller)``, so the
chain a name resolves through is the *call* chain, not the enclosing text.
Both halves of ``_lookup`` walk it: a frame's ``locals`` and its function's
``nested`` table are checked at each level before moving outward, so a
caller's nested definition is visible inside a callee (probed and
confirmed against the interpreter).  Two consequences shape the output:

* No closure capture is needed.  A function value carries no environment,
  only its identity, so it lowers to a small integer naming a
  compile-time-known body.
* A name cannot be resolved at compile time.  Every read emits a runtime
  walk; only the outermost fallbacks (globals, the ``in``/``out`` builtins)
  are static, because those are the levels ``_lookup`` reaches last.

Every frame is a record in a bump-allocated arena::

    [ parent | nested_table | n_slots | id0 | val0 | id1 | val1 | ... ]

Names are interned to integers at compile time.  A frame's slots are
scanned **backward** so the newest binding wins -- the association-list
technique the Forþ compiler uses for its ``;`` lookup, here matching the
interpreter's ``frame.locals`` dict-overwrite semantics.  ``nested_table``
points at a static, NUL-terminated ``(name_id, fn_value)`` array emitted
per function, searched at the same level as that frame's locals.

Values are tagged 64-bit words: a bit is ``0`` or ``1``, and a function is
``(index << 1) | 1`` where ``index`` selects a compiled body.  Tagging is
what lets ``!`` and ``out`` reject a function the way the interpreter's
``HaltError`` does, and lets a call check that its callee is callable.
The two builtins are the reserved values ``-2`` (``in``) and ``-4``
(``out``), which no bit or function value collides with.

Frames are never freed: a bump pointer (``s1``) only grows, because the
interpreter's frames are garbage-collected objects whose lifetime a
returned function value can extend.  Arena exhaustion aborts.

Aborts match the interpreter's ``HaltError`` sites -- an undeclared
identifier, ``!`` or ``out`` on a non-bit, a wrong ``out`` arity, calling a
non-function, a non-bit ``for`` bound -- and exit 0 through ``.halt``,
matching the other compilers' convention.  ``in`` at EOF halts the run, as
the interpreter's ``EOFError`` unwinds it.

The parser is imported from the interpreter rather than rewritten, so the
compiler accepts exactly the programs the interpreter accepts; that shared
parse is what makes acceptance totality hold by construction rather than by
coincidence.

Registers: ``s1`` = arena bump pointer, ``s2`` = current frame, ``s3`` =
arena limit, ``s4``/``s5`` = a range loop's live counter and limit, ``s6``
= this invocation's stack mark.  The last three are saved and restored by
every function prologue/epilogue rather than only around each loop: a
``return`` from inside a loop jumps straight to the epilogue and so
discards that loop's own stack save, which would otherwise hand a
mid-loop *caller* a clobbered counter.
"""

import sys

from esolangs.interpreters.other.forbin import (
    _Assign,
    _CallNode,
    _For,
    _Function,
    _Iter,
    _Parser,
    _Range,
    _Statement,
    _ValueNode,
)

# Frame layout in bytes: parent, nested-table pointer, slot count, then
# 16-byte (id, value) pairs.
_HDR = 24
_PAIR = 16
# Slots per frame and total frames; a frame that overflows either aborts.
_SLOTS = 32
_FRAMES = 512
_IN, _OUT = -2, -4


class _Compiler:
    """Lowers a parsed Forbin program to RISC-V assembly.

    ``bodies`` collects one emitted subroutine per reachable function, and a
    function value is an index into it.  ``names`` interns identifiers so a
    frame slot stores an integer id rather than a string, and ``tables``
    collects the static nested-definition arrays.
    """

    def __init__(self, globals_: dict[str, _Function]) -> None:
        self.globals = globals_
        self.bodies: list[str | None] = []
        self.index: dict[int, int] = {}
        self.by_index: dict[int, _Function] = {}
        self.names: dict[str, int] = {}
        self.tables: list[str] = []
        self.label = 0
        # The enclosing function's epilogue label, installed by emit_fn.
        self.ret_label: str | None = None

    def name_id(self, name: str) -> int:
        """Intern ``name``, returning the integer a frame slot stores."""
        return self.names.setdefault(name, len(self.names))

    def new_label(self) -> str:
        """Return a fresh assembler-local label."""
        self.label += 1
        return f".L{self.label}"

    def fn_index(self, fn: _Function) -> int:
        """Return the body index for ``fn``, emitting it on first sight.

        Reserving the slot before emitting is what lets a recursive or
        mutually-recursive function reach its own index without looping.
        """
        key = id(fn)
        if key in self.index:
            return self.index[key]
        ind = len(self.bodies)
        self.index[key] = ind
        self.by_index[ind] = fn
        self.bodies.append(None)
        self.bodies[ind] = self.emit_fn(fn, ind)
        return ind

    def fn_value(self, fn: _Function) -> int:
        """Return the tagged word representing ``fn`` as a value."""
        return (self.fn_index(fn) << 1) | 1

    # -- values -----------------------------------------------------------

    def emit_value(self, node: _ValueNode, fn: _Function) -> str:
        """Emit code leaving ``node``'s tagged value in ``a0``."""
        if node[0] == "lit":
            return f"    li   a0, {node[1]}\n"
        if node[0] == "not":
            # ``!`` needs a bit: anything else is the interpreter's
            # "! needs a bit" halt.  Unsigned compare catches both the
            # function tag and the negative builtin words.
            return (
                self.emit_value(node[1], fn)
                + "    li   t0, 1\n"
                + "    bgtu a0, t0, .abort\n"
                + "    xori a0, a0, 1\n"
            )
        if node[0] == "var":
            return self.emit_lookup(node[1])
        if node[0] == "fnlit":
            return f"    li   a0, {self.fn_value(node[1])}\n"
        return self.emit_call(node, fn)

    def emit_lookup(self, name: str) -> str:
        """Emit a runtime frame-chain walk resolving ``name`` into ``a0``.

        Mirrors ``_lookup``: at each frame, its locals newest-first, then
        its nested table; then outward.  Only when the chain runs out do the
        static globals and builtins apply.

        Takes no enclosing function, and that absence is the design: Forbin
        resolves names along the *call* chain, so which function encloses
        the read tells you nothing about what it will find.
        """
        nid = self.name_id(name)
        top, scan, tbl, tnext, nxt, done = (self.new_label() for _ in range(6))
        static = self.new_label()
        return (
            f"    mv   t1, s2\n"
            f"    li   t4, {nid}\n"
            f"{top}:\n"
            f"    beqz t1, {static}\n"
            f"    ld   t2, 16(t1)\n"
            f"    addi t3, t1, {_HDR}\n"
            f"    slli t2, t2, 4\n"
            f"    add  t2, t3, t2\n"
            f"{scan}:\n"
            f"    beq  t2, t3, {tbl}\n"
            f"    addi t2, t2, -{_PAIR}\n"
            f"    ld   t5, 0(t2)\n"
            f"    bne  t5, t4, {scan}\n"
            f"    ld   a0, 8(t2)\n"
            f"    j    {done}\n"
            # the frame's own nested definitions, at the same level
            f"{tbl}:\n"
            f"    ld   t2, 8(t1)\n"
            f"    beqz t2, {nxt}\n"
            f"{tnext}:\n"
            f"    ld   t5, 0(t2)\n"
            f"    bltz t5, {nxt}\n"
            f"    addi t2, t2, {_PAIR}\n"
            f"    bne  t5, t4, {tnext}\n"
            f"    ld   a0, -8(t2)\n"
            f"    j    {done}\n"
            f"{nxt}:\n"
            f"    ld   t1, 0(t1)\n"
            f"    j    {top}\n"
            f"{static}:\n" + self.emit_static(name) + f"{done}:\n"
        )

    def emit_static(self, name: str) -> str:
        """Emit the outermost lookup arm: globals, then the two builtins.

        A name reaching here unresolved is the interpreter's ``undeclared
        identifier`` halt.
        """
        if name in self.globals:
            return f"    li   a0, {self.fn_value(self.globals[name])}\n"
        if name == "in":
            return f"    li   a0, {_IN}\n"
        if name == "out":
            return f"    li   a0, {_OUT}\n"
        return "    j    .abort\n"

    # -- calls ------------------------------------------------------------

    def emit_call(self, node: _CallNode, fn: _Function) -> str:
        """Emit a call, leaving its result in ``a0``.

        The callee and arguments are evaluated left to right (matching
        ``_eval``'s own order) onto the machine stack, then dispatched: the
        two builtins are handled inline, and a user function goes through
        ``.invoke``, which builds the frame.  A callee that is neither is
        the interpreter's "called value is not a function" halt.
        """
        _, callee_node, args = node
        code = self.emit_value(callee_node, fn)
        code += "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        for arg in args:
            code += self.emit_value(arg, fn)
            code += "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        # a1 = argument base (lowest address holds the last argument),
        # a2 = argument count, a0 = callee.
        code += f"    ld   a0, {16 * len(args)}(sp)\n"
        code += "    mv   a1, sp\n"
        code += f"    li   a2, {len(args)}\n"
        code += "    call .dispatch\n"
        code += f"    addi sp, sp, {16 * (len(args) + 1)}\n"
        return code

    # -- statements -------------------------------------------------------

    def emit_stmts(self, stmts: list[_Statement], fn: _Function) -> str:
        """Emit a statement list in the current frame's scope."""
        return "".join(self.emit_stmt(s, fn) for s in stmts)

    def emit_stmt(self, stmt: _Statement, fn: _Function) -> str:
        """Emit one statement.

        ``return`` leaves its value in ``a0`` and jumps to the function's
        epilogue, which is what makes a ``return`` inside nested loops exit
        the whole function as ``_exec_stmt`` does.
        """
        if stmt[0] == "return":
            return self.emit_value(stmt[1], fn) + f"    j    {self.ret_label}\n"
        if stmt[0] == "assign":
            return self.emit_assign(stmt, fn)
        if stmt[0] == "call":
            # a statement-position call discards its result
            return self.emit_call(stmt, fn)
        return self.emit_for(stmt, fn)

    def emit_assign(self, stmt: _Assign, fn: _Function) -> str:
        """Emit an assignment, binding each target in the current frame.

        A single right-hand value is **re-evaluated once per target**, not
        computed once and broadcast: ``_exec_stmt`` calls ``_eval`` inside
        its target loop, so ``a,...,h = (in 0)`` performs eight reads --
        which is exactly how the boolean generator loads an input byte.  A
        ``_`` target is skipped entirely, so it consumes no read.
        Otherwise targets and values pair up positionally and a surplus on
        either side is dropped, matching ``zip(..., strict=False)``.
        """
        _, targets, rhs = stmt
        code = ""
        if len(rhs) == 1:
            for name in targets:
                if name != "_":
                    code += self.emit_value(rhs[0], fn)
                    code += self.emit_bind(name)
            return code
        for name, value in zip(targets, rhs, strict=False):
            if name != "_":
                code += self.emit_value(value, fn)
                code += self.emit_bind(name)
        return code

    def emit_bind(self, name: str) -> str:
        """Emit an append of ``(name, a0)`` to the current frame's slots.

        Appending rather than searching is what gives the backward scan its
        overwrite semantics, and it keeps a binding O(1).
        """
        return (
            f"    li   t0, {self.name_id(name)}\n"
            f"    ld   t1, 16(s2)\n"
            f"    li   t2, {_SLOTS}\n"
            f"    bge  t1, t2, .abort\n"
            f"    slli t2, t1, 4\n"
            f"    addi t2, t2, {_HDR}\n"
            f"    add  t2, s2, t2\n"
            f"    sd   t0, 0(t2)\n"
            f"    sd   a0, 8(t2)\n"
            f"    addi t1, t1, 1\n"
            f"    sd   t1, 16(s2)\n"
        )

    # -- loops ------------------------------------------------------------

    def emit_for(self, stmt: _For, fn: _Function) -> str:
        """Emit a ``for`` statement.

        Both forms bind their variables in the *enclosing* frame -- the
        interpreter writes loop variables into ``frame.locals``, so a body's
        writes and the loop variable share one scope and outlive the loop.
        """
        _, spec, body = stmt
        if spec[0] == "range":
            return self.emit_range(spec, body, fn)
        return self.emit_iter(spec, body, fn)

    def emit_range(self, spec: _Range, body: list[_Statement], fn: _Function) -> str:
        """Emit a range loop over ``start..end`` inclusive.

        Bounds are evaluated once, in order, before the loop; each must be a
        bit (the interpreter's ``_bound`` rejects a function), and an empty
        range (``lo > hi``) runs zero times, which is what makes
        ``for _:!b..b`` an if-statement on ``b``.
        """
        _, name, start_node, end_node = spec
        top, done = self.new_label(), self.new_label()
        code = self.emit_value(start_node, fn)
        code += "    li   t0, 1\n    bgtu a0, t0, .abort\n"
        code += "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        code += self.emit_value(end_node, fn)
        code += "    li   t0, 1\n    bgtu a0, t0, .abort\n"
        # s4/s5 are the live counter and limit; save the caller's so
        # nested range loops in one frame do not clobber each other.
        code += "    addi sp, sp, -32\n    sd   s4, 0(sp)\n    sd   s5, 8(sp)\n"
        code += "    mv   s5, a0\n    ld   s4, 32(sp)\n"
        code += f"{top}:\n"
        code += f"    bgt  s4, s5, {done}\n"
        code += "    mv   a0, s4\n"
        if name != "_":
            code += self.emit_bind(name)
        code += self.emit_stmts(body, fn)
        code += "    addi s4, s4, 1\n"
        code += f"    j    {top}\n"
        code += f"{done}:\n"
        code += "    ld   s4, 0(sp)\n    ld   s5, 8(sp)\n    addi sp, sp, 48\n"
        return code

    def emit_iter(self, spec: _Iter, body: list[_Statement], fn: _Function) -> str:
        """Emit an iteration loop over an explicit pattern list.

        A wildcard stands for both bit values, and its count is fixed at
        compile time, so each pattern expands to the same rows
        ``_for_rows`` builds -- in the same order, since
        ``itertools.product`` counts the last wildcard fastest.  Non-wildcard
        entries are expressions re-evaluated per row, matching the
        interpreter, which evaluates them while building the row list.
        """
        _, names, patterns = spec
        code = ""
        for pat in patterns:
            items = list(pat[1]) if pat[0] == "group" else [pat]
            wilds = [j for j, p in enumerate(items) if p[0] == "*"]
            for combo in self.combos(len(wilds)):
                w = 0
                row: list[_ValueNode] = []
                for p in items:
                    if p[0] == "*":
                        # a wildcard's filling is a literal bit, so the row
                        # is a plain value list the body can evaluate
                        lit: _ValueNode = ("lit", combo[w])
                        row.append(lit)
                        w += 1
                    else:
                        row.append(p[1])
                code += self.emit_row(names, row, body, fn)
        return code

    @staticmethod
    def combos(count: int) -> list[tuple[int, ...]]:
        """Return the wildcard fillings, last wildcard counting fastest."""
        rows: list[tuple[int, ...]] = [()]
        for _ in range(count):
            rows = [(*r, b) for r in rows for b in (0, 1)]
        return rows

    def emit_row(
        self,
        names: list[str],
        row: list[_ValueNode],
        body: list[_Statement],
        fn: _Function,
    ) -> str:
        """Emit one iteration row: bind the names, then run the body once.

        Values are evaluated into temporaries before any is bound, since the
        interpreter builds the whole row before binding it -- so a row that
        reads a name it also binds sees the old value.
        """
        code = ""
        pairs = list(zip(names, row, strict=False))
        for _, value in pairs:
            code += self.emit_value(value, fn)
            code += "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        for k, (name, _) in enumerate(pairs):
            if name != "_":
                code += f"    ld   a0, {16 * (len(pairs) - 1 - k)}(sp)\n"
                code += self.emit_bind(name)
        code += f"    addi sp, sp, {16 * len(pairs)}\n"
        code += self.emit_stmts(body, fn)
        return code

    # -- functions --------------------------------------------------------

    def emit_fn(self, fn: _Function, ind: int) -> str:
        """Emit one function body as a subroutine.

        On entry ``s2`` already points at the frame ``.invoke`` built, so the
        body only needs its statements and an epilogue.  Falling off the end
        returns 0, matching ``_call``'s ``result if result is not None else 0``.
        """
        table = self.emit_table(fn)
        # The epilogue label is per-function: `return` inside nested loops
        # jumps here to leave the whole function, as _exec_stmt does.
        # Saved and restored because emitting this body can emit another
        # function's, which would otherwise leave its label installed.
        outer = self.ret_label
        self.ret_label = f".ret{ind}"
        body = self.emit_stmts(fn.body, fn)
        self.ret_label = outer
        return (
            f"# function {fn.name or '<anonymous>'} (index {ind})\n"
            f".fn{ind}:\n"
            # s6 holds this invocation's stack mark.  A `return` inside
            # any number of open loops jumps straight to the epilogue, so
            # the epilogue restores sp from the mark rather than trusting
            # the loops to have unwound their saved registers.
            #
            # s4/s5 are a range loop's live counter and limit.  They are
            # saved here, not only per-loop, because a `return` from inside
            # a callee's loop discards that loop's own stack save -- and if
            # the *caller* is mid-loop, its counter would come back
            # clobbered.  The epilogue runs on every exit path, so saving
            # them per-invocation hands the caller its values back however
            # the callee leaves.
            f"    addi sp, sp, -48\n"
            f"    sd   ra, 0(sp)\n"
            f"    sd   s6, 8(sp)\n"
            f"    sd   s4, 16(sp)\n"
            f"    sd   s5, 24(sp)\n"
            f"    mv   s6, sp\n"
            f"{body}"
            f"    li   a0, 0\n"
            f".ret{ind}:\n"
            f"    mv   sp, s6\n"
            f"    ld   ra, 0(sp)\n"
            f"    ld   s6, 8(sp)\n"
            f"    ld   s4, 16(sp)\n"
            f"    ld   s5, 24(sp)\n"
            f"    addi sp, sp, 48\n"
            f"    ret\n"
            f"{table}"
        )

    def emit_table(self, fn: _Function) -> str:
        """Emit ``fn``'s static nested-definition table, if it has one.

        The table is ``(name_id, fn_value)`` pairs terminated by ``-1``,
        which is what the lookup's ``bltz`` end test reads.
        """
        if not fn.nested:
            return ""
        rows = "".join(
            f"    .dword {self.name_id(name)}, {self.fn_value(nested)}\n"
            for name, nested in fn.nested.items()
        )
        return (
            f"    .section .rodata\n"
            f".tbl{self.index[id(fn)]}:\n"
            f"{rows}"
            f"    .dword -1, -1\n"
            f"    .text\n"
        )

    def emit_table_store(self, ind: int) -> str:
        """Emit a body's frame setup: its nested table, then its parameters.

        Both are per-function, so they belong on the dispatch's per-index
        arm rather than in the shared frame allocation.  Parameters are
        bound in declaration order, defaulting to 0 when the call passed
        fewer -- ``_call`` presets every parameter to 0 before the zip.
        """
        fn = self.by_index[ind]
        code = ""
        if fn.nested:
            code += f"    la   t2, .tbl{ind}\n    sd   t2, 8(s2)\n"
        for k, param in enumerate(fn.args):
            got, done = self.new_label(), self.new_label()
            code += (
                f"    li   t0, {k}\n"
                f"    blt  t0, a2, {got}\n"
                f"    li   a0, 0\n"
                f"    j    {done}\n"
                f"{got}:\n"
                # arguments were pushed left to right, so argument k sits
                # at a1 + 16*(argc-1-k)
                f"    addi t0, a2, -1\n"
                f"    li   t1, {k}\n"
                f"    sub  t0, t0, t1\n"
                f"    slli t0, t0, 4\n"
                f"    add  t0, a1, t0\n"
                f"    ld   a0, 0(t0)\n"
                f"{done}:\n"
            ) + self.emit_bind(param)
        return code

    def compile(self) -> str:
        """Emit the whole program: entry, runtime, and every function body."""
        main = self.globals["main"]
        main_ind = self.fn_index(main)
        # Emitting bodies interns names and may emit more bodies, so the
        # dispatch tables are built only once that has settled.
        bodies = "".join(b for b in self.bodies if b)
        return (
            # Relaxation would turn `la` into a gp-relative `addi`, and
            # nothing initializes gp under -nostdlib, so the arena pointer
            # would be garbage.  Every symbol here is addressed absolutely.
            "    .option norelax\n"
            "    .text\n"
            "    .global _start\n"
            "_start:\n"
            f"    la   s1, forbin_arena\n"
            f"    li   t0, {_FRAMES * (_HDR + _SLOTS * _PAIR)}\n"
            "    add  s3, s1, t0\n"
            "    li   s2, 0\n"
            # main is called with a single dummy argument 0 (per the wiki)
            "    addi sp, sp, -16\n"
            "    sd   zero, 0(sp)\n"
            f"    li   a0, {(main_ind << 1) | 1}\n"
            "    mv   a1, sp\n"
            "    li   a2, 1\n"
            "    call .dispatch\n"
            "    j    .halt\n" + self.emit_runtime() + bodies + self.emit_data()
        )

    def emit_runtime(self) -> str:
        """Emit dispatch, frame construction, the builtins, and the aborts."""
        arms = "".join(
            f"    li   t1, {ind}\n    beq  t0, t1, .body{ind}\n"
            for ind in range(len(self.bodies))
        )
        jumps = "".join(
            f".body{ind}:\n"
            + self.emit_table_store(ind)
            # `call`, not `j`: the body must return here so the dispatch can
            # restore the caller's frame before handing the value back.
            + f"    call .fn{ind}\n"
            + "    j    .dispatch_ret\n"
            for ind in range(len(self.bodies))
        )
        return (
            "# dispatch(callee: a0, args: a1, argc: a2) -> a0\n"
            ".dispatch:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s2, 8(sp)\n"
            f"    li   t0, {_IN}\n"
            "    beq  a0, t0, .do_in\n"
            f"    li   t0, {_OUT}\n"
            "    beq  a0, t0, .do_out\n"
            # a function value is odd; anything else is not callable
            "    andi t0, a0, 1\n"
            "    beqz t0, .abort\n"
            "    srli t0, a0, 1\n"
            + self.emit_frame()
            + arms
            + "    j    .abort\n"
            + jumps
            + ".dispatch_ret:\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s2, 8(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n" + self.emit_builtins() + self.emit_abort()
        )

    def emit_frame(self) -> str:
        """Emit the frame allocation shared by every user-function call.

        The parent is the *calling* frame, which is what makes scoping
        dynamic.  The arena is checked before the bump, so exhaustion
        aborts rather than writing past the end; the per-function parts
        (nested table, parameter binding) are emitted by
        :meth:`emit_table_store` on each dispatch arm.
        """
        return (
            "    mv   t3, s1\n"
            f"    li   t4, {_HDR + _SLOTS * _PAIR}\n"
            "    add  t4, t3, t4\n"
            "    bgtu t4, s3, .abort\n"
            "    mv   s1, t4\n"
            "    sd   s2, 0(t3)\n"
            "    sd   zero, 8(t3)\n"
            "    sd   zero, 16(t3)\n"
            "    mv   s2, t3\n"
        )

    def emit_builtins(self) -> str:
        """Emit ``in`` and ``out``.

        ``in`` returns one bit, most significant first, refilling from a
        byte of stdin and halting the run at EOF (the interpreter's
        ``EOFError``).  ``out`` needs exactly eight bit arguments and writes
        their byte; any other arity, or a non-bit, is a halt.
        """
        return (
            # ``in`` is line-faithful, matching IO.input_char: a refill
            # takes the first byte of a line and discards the rest of that
            # line, an empty line reads as the '\n' that ended it, and EOF
            # with nothing read halts the run (the interpreter's EOFError).
            # Reading raw consecutive bytes instead would make identical
            # stdin produce different output from the interpreter, which is
            # the whole point of the differential.
            ".do_in:\n"
            "    la   t0, forbin_bitcount\n"
            "    ld   t1, 0(t0)\n"
            "    bnez t1, .have_bits\n"
            "    call .readline\n"
            "    la   t3, forbin_bitbuf\n"
            "    sd   a0, 0(t3)\n"
            "    li   t1, 8\n"
            ".have_bits:\n"
            "    addi t1, t1, -1\n"
            "    la   t0, forbin_bitcount\n"
            "    sd   t1, 0(t0)\n"
            "    la   t3, forbin_bitbuf\n"
            "    ld   t2, 0(t3)\n"
            "    srl  a0, t2, t1\n"
            "    andi a0, a0, 1\n"
            "    j    .dispatch_ret\n"
            # readline() -> a0: the line's first character, per input_char
            ".readline:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s4, 8(sp)\n"
            "    li   a7, 63\n"
            "    li   a0, 0\n"
            "    addi a1, sp, 16\n"
            "    li   a2, 1\n"
            "    ecall\n"
            # nothing read at all: past the end of the input, so halt
            "    blez a0, .halt\n"
            "    lbu  s4, 16(sp)\n"
            "    li   t0, 10\n"
            # an empty line: the character read is the newline itself
            "    beq  s4, t0, .readline_done\n"
            ".readline_skip:\n"
            "    li   a7, 63\n"
            "    li   a0, 0\n"
            "    addi a1, sp, 16\n"
            "    li   a2, 1\n"
            "    ecall\n"
            "    blez a0, .readline_done\n"
            "    lbu  t1, 16(sp)\n"
            "    li   t0, 10\n"
            "    bne  t1, t0, .readline_skip\n"
            ".readline_done:\n"
            "    mv   a0, s4\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s4, 8(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n"
            ".do_out:\n"
            "    li   t0, 8\n"
            "    bne  a2, t0, .abort\n"
            # arguments sit highest-first at a1 + 16*(argc-1) downward
            "    li   t1, 0\n"
            "    li   t2, 0\n"
            ".out_loop:\n"
            "    li   t3, 8\n"
            "    beq  t2, t3, .out_done\n"
            "    li   t4, 7\n"
            "    sub  t4, t4, t2\n"
            "    slli t4, t4, 4\n"
            "    add  t4, a1, t4\n"
            "    ld   t5, 0(t4)\n"
            "    li   t6, 1\n"
            "    bgtu t5, t6, .abort\n"
            "    slli t1, t1, 1\n"
            "    add  t1, t1, t5\n"
            "    addi t2, t2, 1\n"
            "    j    .out_loop\n"
            ".out_done:\n"
            "    addi sp, sp, -16\n"
            "    sb   t1, 0(sp)\n"
            "    li   a7, 64\n"
            "    li   a0, 1\n"
            "    mv   a1, sp\n"
            "    li   a2, 1\n"
            "    ecall\n"
            "    addi sp, sp, 16\n"
            "    li   a0, 0\n"
            "    j    .dispatch_ret\n"
        )

    @staticmethod
    def emit_abort() -> str:
        """Emit the halt path shared by every ``HaltError`` site."""
        return (
            "# every HaltError site lands here; the interpreter unwinds the\n"
            "# whole run, and the other compilers exit 0 on a halt\n"
            ".abort:\n"
            ".halt:\n"
            "    li   a0, 0\n"
            "    li   a7, 93\n"
            "    ecall\n"
        )

    @staticmethod
    def emit_data() -> str:
        """Emit the input-bit buffer and the frame arena."""
        return (
            "    .bss\n"
            "    .align 3\n"
            "forbin_bitbuf:\n"
            "    .space 8\n"
            "forbin_bitcount:\n"
            "    .space 8\n"
            "forbin_arena:\n"
            f"    .space {_FRAMES * (_HDR + _SLOTS * _PAIR)}\n"
        )


def comp(code: str) -> str:
    """Compile a Forbin program to RISC-V assembly with syscall I/O."""
    globals_ = _Parser(code).parse()
    if "main" not in globals_:
        raise ValueError("Forbin program has no main function")
    return _Compiler(globals_).compile()


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1]) as _source:
        print(comp(_source.read()), end="")
