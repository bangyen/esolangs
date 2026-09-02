r"""Compiler that turns MyScript programs into RISC-V Linux assembly.

MyScript is the richest call graph the compilers cover: first-class
functions, ``return``, ``while``/``check`` blocks, and values that are not
just machine words.  Three facts about the language shape the whole
design, and each was probed against the interpreter rather than taken
from the wiki.

**Scoping is lexical, over live frames.**  ``_Function`` stores the
*declaration* scope and ``_call_function`` runs the body in
``Scope(function.outer)``, so a name resolves along the chain of
enclosing text, not the chain of calls.  The discriminating probe is a
top-level ``f`` whose body reads ``x``, called from a ``g`` that declares
a local ``x``: the interpreter halts with ``undefined variable``.  (A
callee *declared inside* its caller does see the caller's locals, but
that is lexical too, which is why it cannot tell the two rules apart.)
So unlike Forbin -- whose frames chain to the caller -- a function value
here carries the frame it was created in, and the lookup walks that.

**Closures escape, so frames are never freed.**  A function returning an
inner function that reads the outer one's parameter still prints it after
the outer call returned, and two calls produce two independent frames.
Frames therefore live in a bump-allocated arena that only grows, the way
Forbin's do; exhaustion aborts.

**Every variable read auto-calls a nullary function.**  ``_parse_expr``
consumes ``len(value.params)`` argument expressions from whatever value
the variable holds *at that moment*, so a bare ``h`` holding a
zero-parameter closure invokes it instead of yielding it.  A plain load
would diverge, so every read of a name not bound to a ``func`` literal
emits a runtime tag test that calls a nullary closure.  Two consequences
follow: a zero-parameter function value can never reach ``equals`` (the
read calls it first), and a one-or-more-parameter one consumes arguments
instead of being compared -- so function values are never comparable, and
no closure-identity equality is needed.

Values are tagged 64-bit words.  The low three bits carry the tag and the
upper 61 the payload, so an integer is ``value << 3``::

    000  integer (payload is the signed value)
    001  boolean (payload 0 or 1)
    010  none     (the value ``say`` and a bare ``return`` produce)
    011  string   (payload is an arena/rodata address >> 3)
    100  array    (payload is an arena address >> 3)
    101  function (payload is a closure record address >> 3)

Tagging is what lets ``add`` reject a string the way the interpreter's
``_num`` raises ``HaltError``, and lets ``say`` print ``yes`` for a
boolean while printing ``1`` for the integer that compares equal to it.
Booleans are a distinct tag rather than the integers 0 and 1 because the
interpreter prints them differently while comparing them equal
(``equals yes 1`` is true, but ``say yes`` writes ``yes``); arithmetic and
comparison coerce the tag away, printing does not.

A string is a length-prefixed byte record and an array a length-prefixed
word record, both ``.align 3``.  Literals live in ``.rodata``; ``concat``
and ``ask`` allocate in the same arena the frames use.

**The scoped value domain.**  The roadmap asked for this to be settled
before starting, and three parts of MyScript's domain are deliberately
left out, each aborting at runtime or rejected at compile time:

* **Floats.**  The target is ``rv64i``, which has no hardware float, and
  the interpreter prints floats with Python's shortest-repr algorithm --
  a bill out of proportion to the rest.  A float *literal* is rejected at
  compile time, and ``divide`` lowers to exact integer division that
  aborts on a nonzero remainder.  Within that domain the two agree
  exactly, since ``_as_str`` renders an integral float as an integer
  (``divide 4 2`` prints ``2`` in both).
* **Arrays reaching ``say`` or ``concat``.**  The interpreter renders
  those through Python's ``str(list)``, which prints element *reprs* --
  ``say [ "a" ]`` writes ``['a']`` with quotes and ``say [ yes ]`` writes
  ``[True]``, leaking Python's own spelling of a value that MyScript
  otherwise calls ``yes``.  Building, measuring, and indexing arrays is
  supported; printing one aborts.
* **Two distinct arrays reaching ``equals``.**  Python's ``==`` compares
  them elementwise and recurses into nested ones, so
  ``equals [ 1 ] [ 1 ]`` is true; comparing the two arena addresses would
  answer ``no`` instead.  Rather than answer wrongly this aborts, so the
  one array comparison that stays exact is a value against *itself*,
  which is equal by address.
* **Integer width.**  MyScript's integers are Python's, so unbounded;
  these are 64-bit and wrap.

Two divergences in *timing* rather than domain are worth naming.  The
interpreter raises its ``ValueError``s when a statement executes, so a
malformed statement in a branch that never runs never raises; this
compiler walks the whole tree and rejects it eagerly, matching the way
CV(N)(C) rejects a malformed program up front.  And an ``ask`` past the
end of input halts the run, the interpreter's ``EOFError`` unwinding it.

``ask`` reads bytes to a newline and returns the line without it,
matching ``IO.input_str``: a final unterminated line is still a line (the
interpreter's ``splitlines`` yields it), and only a read that gets no
bytes at all is the end of input.

The tokenizer, block builder, and string-literal decoder are imported
from the interpreter rather than rewritten, so the two agree on how a
program *parses* -- the same acceptance parity Forbin and CV(N)(C) get
from sharing a parser.  That parity is about parsing only: the domain
exclusions above are enforced afterward, when the tree is walked, so a
program the interpreter parses can still be rejected here.

Registers: ``s1`` = arena bump pointer, ``s2`` = current frame, ``s3`` =
arena limit, ``s6`` = this invocation's stack mark.  ``s6`` is saved and
restored by every prologue/epilogue so a ``return`` from inside any
number of open ``while`` loops unwinds to the right stack depth.
"""

import sys

from esolangs.interpreters.register_based.myscript import (
    _ARITY,
    Node,
    _block_tree,
    _parse_string,
)

# Value tags, in the low three bits of every word.
_T_INT, _T_BOOL, _T_NONE, _T_STR, _T_ARR, _T_FUN = range(6)
_TAG_BITS = 3

# Frame layout in bytes: parent pointer, slot count, then 16-byte
# (name_id, value) pairs.
_HDR = 16
_PAIR = 16
# Slots per frame, and the arena's total size; overflowing either aborts.
_SLOTS = 32
_FRAMES = 4096
_FRAME_SIZE = _HDR + _SLOTS * _PAIR
# Bytes of arena reserved for strings and arrays built at runtime.
_HEAP = 1 << 16

# A closure record: body index, parameter count, defining frame.
_CLOSURE = 24


def _tagged(payload: int, tag: int) -> int:
    """Return the word representing ``payload`` at ``tag``."""
    return (payload << _TAG_BITS) | tag


class _Function:
    """A ``func`` literal: parameters, body, and the index of its code."""

    def __init__(self, params: list[str], body: list[Node], index: int) -> None:
        """Bind ``params`` to ``body``, compiled as subroutine ``index``."""
        self.params = params
        self.body = body
        self.index = index


class _Compiler:
    """Lowers a parsed MyScript program to RISC-V assembly.

    ``bodies`` collects one emitted subroutine per ``func`` literal, and a
    closure record names one by index.  ``names`` interns identifiers so a
    frame slot stores an integer rather than a string, and ``strings``
    collects the literals ``.rodata`` holds.

    ``arities`` is what makes a call compile at all.  MyScript's parse is
    *runtime*-dependent -- ``_parse_expr`` consumes as many argument
    expressions as the value in the variable has parameters -- so a static
    lowering needs each name to have one settled arity.  Every ``func``
    literal bound to a name records its parameter count here, and a second
    binding of the same name at a different arity is rejected: that is the
    agreement domain, stated the way CV(N)(C) states its ASCII one.
    """

    def __init__(self) -> None:
        self.bodies: list[str | None] = []
        self.functions: list[_Function] = []
        self.names: dict[str, int] = {}
        self.strings: dict[str, str] = {}
        self.arities: dict[str, int] = {}
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

    def string_label(self, text: str) -> str:
        """Intern a string literal, returning the label of its record."""
        if text not in self.strings:
            self.strings[text] = f".str{len(self.strings)}"
        return self.strings[text]

    # -- arity ------------------------------------------------------------

    def scan_arities(self, nodes: list[Node]) -> None:
        """Record every ``func`` literal's arity before emitting any code.

        A whole-program pre-pass, so a call textually above the
        declaration still compiles: the interpreter resolves the callee at
        run time, by which point the declaration has executed.
        """
        for tokens, children in nodes:
            if (
                tokens[0] == "var"
                and len(tokens) > 3
                and tokens[2] == "is"
                and tokens[3] == "func"
            ):
                name, params = tokens[1], tokens[4:]
                if self.arities.setdefault(name, len(params)) != len(params):
                    raise ValueError(
                        f"{name!r} is bound to functions of different arities, "
                        "which this compiler cannot resolve statically"
                    )
            self.scan_arities(children)

    # -- values -----------------------------------------------------------

    def emit_expr(self, tokens: list[str], pos: int) -> tuple[str, int]:
        """Emit one prefix expression, leaving its value in ``a0``.

        Mirrors ``_parse_expr``: the token decides the form, a builtin
        consumes its fixed arity, and a name bound to a ``func`` literal
        consumes that many arguments.  Returns the code and the position
        just past the expression.
        """
        if pos >= len(tokens):
            raise ValueError("expression ended before its operands")
        tok = tokens[pos]
        if tok == "ask":
            return "    call .do_ask\n", pos + 1
        if tok in ("yes", "no"):
            return f"    li   a0, {_tagged(int(tok == 'yes'), _T_BOOL)}\n", pos + 1
        if tok[0] == '"':
            label = self.string_label(_parse_string(tok))
            return (
                f"    la   a0, {label}\n"
                f"    srli a0, a0, {_TAG_BITS}\n"
                f"    slli a0, a0, {_TAG_BITS}\n"
                f"    ori  a0, a0, {_T_STR}\n"
            ), pos + 1
        if tok[0].isdigit():
            if "." in tok:
                raise ValueError(
                    "float literals are outside this compiler's value domain"
                )
            return f"    li   a0, {_tagged(int(tok), _T_INT)}\n", pos + 1
        if tok == "[":
            return self.emit_array(tokens, pos + 1)
        if tok in _ARITY:
            return self.emit_builtin(tok, tokens, pos + 1)
        if tok in self.arities:
            return self.emit_call(tok, tokens, pos + 1)
        # A name with no ``func`` literal binding: load it, then call it if
        # it turns out to hold a nullary closure, which is what
        # ``_parse_expr`` does when the value has no parameters.
        return self.emit_lookup(tok) + "    call .autocall\n", pos + 1

    def emit_array(self, tokens: list[str], pos: int) -> tuple[str, int]:
        """Emit ``[v1, v2, ...]`` starting just after the ``[``.

        Elements are evaluated left to right onto the machine stack, then
        copied into a fresh arena record, so an element that itself builds
        an array cannot be clobbered mid-construction.
        """
        code = ""
        count = 0
        while pos < len(tokens) and tokens[pos] != "]":
            piece, pos = self.emit_expr(tokens, pos)
            code += piece + "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
            count += 1
            if pos < len(tokens) and tokens[pos] == ",":
                pos += 1
        code += f"    li   a0, {count}\n    call .alloc_arr\n"
        for k in range(count):
            # element k was pushed first, so it sits deepest
            code += (
                f"    ld   t0, {16 * (count - 1 - k)}(sp)\n"
                f"    sd   t0, {8 * (k + 1)}(a0)\n"
            )
        code += f"    addi sp, sp, {16 * count}\n"
        code += (
            f"    srli a0, a0, {_TAG_BITS}\n"
            f"    slli a0, a0, {_TAG_BITS}\n"
            f"    ori  a0, a0, {_T_ARR}\n"
        )
        return code, pos + 1

    def emit_builtin(self, name: str, tokens: list[str], pos: int) -> tuple[str, int]:
        """Emit a builtin call, its arguments evaluated left to right."""
        code = ""
        arity = _ARITY[name]
        for _ in range(arity):
            piece, pos = self.emit_expr(tokens, pos)
            code += piece + "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        # pop into a0 (first argument) and a1 (second), matching push order
        if arity == 1:
            code += "    ld   a0, 0(sp)\n    addi sp, sp, 16\n"
        elif arity == 2:
            code += "    ld   a1, 0(sp)\n    ld   a0, 16(sp)\n    addi sp, sp, 32\n"
        code += f"    call .b_{name}\n"
        return code, pos

    def emit_call(self, name: str, tokens: list[str], pos: int) -> tuple[str, int]:
        """Emit a call to a name bound to a ``func`` literal.

        The callee is looked up at run time (the variable may have been
        rebound), but *how many* arguments to consume is the static arity
        the pre-pass recorded.
        """
        code = ""
        arity = self.arities[name]
        for _ in range(arity):
            piece, pos = self.emit_expr(tokens, pos)
            code += piece + "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        code += self.emit_lookup(name)
        # a1 = argument base (deepest slot holds the first argument),
        # a2 = argument count, a0 = callee.
        code += "    mv   a1, sp\n"
        code += f"    li   a2, {arity}\n"
        code += "    call .invoke\n"
        code += f"    addi sp, sp, {16 * arity}\n"
        return code, pos

    def emit_lookup(self, name: str) -> str:
        """Emit a walk of the lexical frame chain resolving ``name``.

        Mirrors ``Scope.get``: each frame's slots newest-first, then
        outward along the chain the *declaration* built.  A name that
        never resolves is the interpreter's ``undefined variable`` halt.
        """
        nid = self.name_id(name)
        top, scan, nxt, done = (self.new_label() for _ in range(4))
        return (
            f"    mv   t1, s2\n"
            f"    li   t4, {nid}\n"
            f"{top}:\n"
            f"    beqz t1, .abort\n"
            f"    ld   t2, 8(t1)\n"
            f"    addi t3, t1, {_HDR}\n"
            f"    slli t2, t2, 4\n"
            f"    add  t2, t3, t2\n"
            f"{scan}:\n"
            f"    beq  t2, t3, {nxt}\n"
            f"    addi t2, t2, -{_PAIR}\n"
            f"    ld   t5, 0(t2)\n"
            f"    bne  t5, t4, {scan}\n"
            f"    ld   a0, 8(t2)\n"
            f"    j    {done}\n"
            f"{nxt}:\n"
            f"    ld   t1, 0(t1)\n"
            f"    j    {top}\n"
            f"{done}:\n"
        )

    def emit_bind(self, name: str) -> str:
        """Emit an append of ``(name, a0)`` to the current frame's slots.

        Appending rather than searching gives the backward scan its
        overwrite semantics, matching ``Scope.declare`` into a dict, and
        keeps a declaration O(1).
        """
        return (
            f"    li   t0, {self.name_id(name)}\n"
            f"    ld   t1, 8(s2)\n"
            f"    li   t2, {_SLOTS}\n"
            f"    bge  t1, t2, .abort\n"
            f"    slli t2, t1, 4\n"
            f"    addi t2, t2, {_HDR}\n"
            f"    add  t2, s2, t2\n"
            f"    sd   t0, 0(t2)\n"
            f"    sd   a0, 8(t2)\n"
            f"    addi t1, t1, 1\n"
            f"    sd   t1, 8(s2)\n"
        )

    def emit_assign(self, name: str) -> str:
        """Emit a rebinding of an existing ``name``, walking outward.

        ``Scope.assign`` writes where the name already lives rather than
        shadowing it, so a function assigning to an enclosing variable is
        seen by the enclosing scope; a name that resolves nowhere halts.
        """
        nid = self.name_id(name)
        top, scan, nxt, done = (self.new_label() for _ in range(4))
        return (
            f"    mv   t1, s2\n"
            f"    li   t4, {nid}\n"
            f"{top}:\n"
            f"    beqz t1, .abort\n"
            f"    ld   t2, 8(t1)\n"
            f"    addi t3, t1, {_HDR}\n"
            f"    slli t2, t2, 4\n"
            f"    add  t2, t3, t2\n"
            f"{scan}:\n"
            f"    beq  t2, t3, {nxt}\n"
            f"    addi t2, t2, -{_PAIR}\n"
            f"    ld   t5, 0(t2)\n"
            f"    bne  t5, t4, {scan}\n"
            f"    sd   a0, 8(t2)\n"
            f"    j    {done}\n"
            f"{nxt}:\n"
            f"    ld   t1, 0(t1)\n"
            f"    j    {top}\n"
            f"{done}:\n"
        )

    # -- statements -------------------------------------------------------

    def emit_stmts(self, nodes: list[Node]) -> str:
        """Emit every statement in an indentation block."""
        return "".join(self.emit_stmt(t, c) for t, c in nodes)

    def emit_stmt(self, tokens: list[str], children: list[Node]) -> str:
        """Emit one statement (a line's tokens and its indented block)."""
        head = tokens[0]
        if head == "var":
            return self.emit_var(tokens, children)
        if head == "return":
            if len(tokens) == 1:
                return (
                    f"    li   a0, {_tagged(0, _T_NONE)}\n    j    {self.ret_label}\n"
                )
            code, _ = self.emit_expr(tokens[1:], 0)
            return code + f"    j    {self.ret_label}\n"
        if head == "while":
            return self.emit_while(tokens, children)
        if head == "check":
            return self.emit_check(tokens, children)
        if head in ("if", "else"):
            # an if/else outside a check is the interpreter's HaltError
            return "    j    .abort\n"
        if head == "is":
            raise ValueError("malformed statement")
        if len(tokens) >= 3 and tokens[1] == "is":
            code, _ = self.emit_expr(tokens[2:], 0)
            return code + self.emit_assign(head)
        code, _ = self.emit_expr(tokens, 0)
        return code

    def emit_var(self, tokens: list[str], children: list[Node]) -> str:
        """Emit a ``var`` declaration, which may bind a ``func`` literal.

        A ``func`` binding builds its closure record *here*, capturing the
        frame in effect, so a declaration inside a loop or a called
        function mints a fresh closure per execution -- which is what lets
        two calls of one factory return functions over separate frames.
        """
        if len(tokens) < 3 or tokens[2] != "is":
            raise ValueError("malformed var declaration")
        name, rest = tokens[1], tokens[3:]
        if rest and rest[0] == "func":
            fn = _Function(rest[1:], children, len(self.bodies))
            self.bodies.append(None)
            self.functions.append(fn)
            self.bodies[fn.index] = self.emit_fn(fn)
            return (
                f"    li   a0, {fn.index}\n"
                f"    li   a1, {len(fn.params)}\n"
                f"    call .alloc_closure\n"
            ) + self.emit_bind(name)
        code, _ = self.emit_expr(rest, 0)
        return code + self.emit_bind(name)

    def emit_while(self, tokens: list[str], children: list[Node]) -> str:
        """Emit a ``while`` loop, re-evaluating its condition each pass.

        The body runs in the enclosing frame, matching the interpreter's
        ``_run_block(children, io, scope)``: a ``var`` inside the body
        binds into the same scope and outlives the pass.
        """
        top, done = self.new_label(), self.new_label()
        cond, _ = self.emit_expr(tokens[1:-1], 0)
        return (
            f"{top}:\n"
            + cond
            + "    call .truthy\n"
            + f"    beqz a0, {done}\n"
            + self.emit_stmts(children)
            + f"    j    {top}\n"
            + f"{done}:\n"
        )

    def emit_check(self, tokens: list[str], children: list[Node]) -> str:
        """Emit a ``check`` switch: the first equal ``if`` case, or ``else``.

        The subject is evaluated once and each case value compared to it
        with the same equality ``equals`` uses; a ``check`` matching
        nothing and carrying no ``else`` simply falls through.
        """
        done = self.new_label()
        subject, _ = self.emit_expr(tokens[1:-1], 0)
        code = subject + "    addi sp, sp, -16\n    sd   a0, 0(sp)\n"
        for case_tokens, case_body in children:
            if case_tokens[0] == "else":
                code += self.emit_stmts(case_body) + f"    j    {done}\n"
                break
            if case_tokens[0] != "if":
                raise ValueError("malformed check case")
            nxt = self.new_label()
            value, _ = self.emit_expr(case_tokens[1:-1], 0)
            code += value
            code += "    mv   a1, a0\n    ld   a0, 0(sp)\n"
            code += "    call .b_equals\n"
            code += f"    li   t0, {_tagged(1, _T_BOOL)}\n"
            code += f"    bne  a0, t0, {nxt}\n"
            code += self.emit_stmts(case_body)
            code += f"    j    {done}\n"
            code += f"{nxt}:\n"
        code += f"{done}:\n    addi sp, sp, 16\n"
        return code

    # -- functions --------------------------------------------------------

    def emit_fn(self, fn: _Function) -> str:
        """Emit one ``func`` literal's body as a subroutine.

        On entry ``s2`` already points at the frame ``.invoke`` built with
        the parameters bound, so the body needs only its statements and an
        epilogue.  Falling off the end returns ``none``, matching
        ``_call_function``'s ``return None``.
        """
        outer = self.ret_label
        self.ret_label = f".ret{fn.index}"
        body = self.emit_stmts(fn.body)
        self.ret_label = outer
        return (
            f"# function index {fn.index}, {len(fn.params)} parameter(s)\n"
            f".fn{fn.index}:\n"
            # s6 marks this invocation's stack depth: a `return` from
            # inside any number of open `while` loops or a `check` jumps
            # straight to the epilogue, which restores sp from the mark
            # rather than trusting those blocks to have unwound their own
            # pushes.
            f"    addi sp, sp, -16\n"
            f"    sd   ra, 0(sp)\n"
            f"    sd   s6, 8(sp)\n"
            f"    mv   s6, sp\n"
            f"{body}"
            f"    li   a0, {_tagged(0, _T_NONE)}\n"
            f".ret{fn.index}:\n"
            f"    mv   sp, s6\n"
            f"    ld   ra, 0(sp)\n"
            f"    ld   s6, 8(sp)\n"
            f"    addi sp, sp, 16\n"
            f"    ret\n"
        )

    def emit_dispatch(self) -> str:
        """Emit ``.invoke``: build the callee's frame, bind, and jump.

        The new frame's parent is the closure's *defining* frame, which is
        what makes scoping lexical; the arena check runs before the bump,
        so exhaustion aborts rather than writing past the end.  A callee
        given the wrong number of arguments is the interpreter's
        ``zip(..., strict=True)`` failure and halts.
        """
        arms = "".join(
            f"    li   t1, {fn.index}\n    beq  t0, t1, .body{fn.index}\n"
            for fn in self.functions
        )
        jumps = "".join(
            f".body{fn.index}:\n"
            + "".join(
                # arguments were pushed left to right, so parameter k sits
                # deepest at a1 + 16*(argc-1-k)
                f"    ld   a0, {16 * (len(fn.params) - 1 - k)}(a1)\n"
                + self.emit_bind(param)
                for k, param in enumerate(fn.params)
            )
            # `call`, not `j`: the body must come back so .invoke can
            # restore the caller's frame before handing the value over
            + f"    call .fn{fn.index}\n"
            + "    j    .invoke_ret\n"
            for fn in self.functions
        )
        return (
            "# invoke(callee: a0, args: a1, argc: a2) -> a0\n"
            ".invoke:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s2, 8(sp)\n"
            "    sd   a1, 16(sp)\n"
            f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t1, {_T_FUN}\n"
            "    bne  t0, t1, .abort\n"
            f"    srli t0, a0, {_TAG_BITS}\n"
            f"    slli t0, t0, {_TAG_BITS}\n"
            # the closure record: body index, parameter count, frame
            "    ld   t2, 8(t0)\n"
            "    bne  t2, a2, .abort\n"
            "    ld   t3, 16(t0)\n"
            "    ld   t0, 0(t0)\n"
            + self.emit_frame()
            + "    ld   a1, 16(sp)\n"
            + arms
            + "    j    .abort\n"
            + jumps
            + ".invoke_ret:\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s2, 8(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n"
        )

    @staticmethod
    def emit_frame() -> str:
        """Emit the frame allocation every call shares.

        ``t3`` holds the closure's defining frame, which becomes the new
        frame's parent -- the one line that makes the chain lexical rather
        than the call chain Forbin walks.
        """
        return (
            "    mv   t4, s1\n"
            f"    li   t5, {_FRAME_SIZE}\n"
            "    add  t5, t4, t5\n"
            "    bgtu t5, s3, .abort\n"
            "    mv   s1, t5\n"
            "    sd   t3, 0(t4)\n"
            "    sd   zero, 8(t4)\n"
            "    mv   s2, t4\n"
        )

    def compile(self, nodes: list[Node]) -> str:
        """Emit the whole program: entry, top-level code, runtime, bodies."""
        self.scan_arities(nodes)
        # The top level runs in a frame of its own, so a closure declared
        # there captures it the same way one inside a function does.
        self.ret_label = ".top_end"
        top = self.emit_stmts(nodes)
        bodies = "".join(b for b in self.bodies if b)
        return (
            # Relaxation would turn `la` into a gp-relative `addi`, and
            # nothing initializes gp under -nostdlib, so every arena and
            # literal address would be garbage.
            "    .option norelax\n"
            "    .text\n"
            "    .global _start\n"
            "_start:\n"
            "    la   s1, ms_arena\n"
            f"    li   t0, {_FRAMES * _FRAME_SIZE + _HEAP}\n"
            "    add  s3, s1, t0\n"
            "    li   s2, 0\n"
            # the top-level frame: no parent, so a lookup that walks off
            # its end is an undefined variable
            "    li   t3, 0\n" + self.emit_frame() + "    mv   s6, sp\n" + top +
            # a top-level `return` clears the stack in the interpreter,
            # which ends the program
            ".top_end:\n"
            "    j    .halt\n"
            + self.emit_dispatch()
            + self.emit_runtime(top + bodies)
            + bodies
            + self.emit_data()
        )

    # -- runtime ----------------------------------------------------------

    def emit_runtime(self, body: str) -> str:
        """Emit the builtins, the allocators, and the shared abort.

        ``ask`` is emitted only when ``body`` calls it -- ``ask`` is the
        only command that does, and nothing dispatches to it indirectly --
        so a program that never reads carries no reader, matching the
        ``used``-flag gate the tape compilers apply to their subroutines.
        """
        return (
            self.emit_alloc()
            + self.emit_autocall()
            + self.emit_arith()
            + self.emit_compare()
            + self.emit_strings()
            + self.emit_arrays()
            + self.emit_say()
            + (self.emit_ask() if "    call .do_ask\n" in body else "")
            + self.emit_abort()
        )

    @staticmethod
    def emit_alloc() -> str:
        """Emit the bump allocators for closures, strings, and arrays.

        Every record is 8-byte aligned so its address survives the three
        tag bits a value word carries.
        """
        return (
            # alloc(bytes: a0) -> a0, aligned to 8
            ".alloc:\n"
            "    addi a0, a0, 7\n"
            "    andi a0, a0, -8\n"
            "    mv   t0, s1\n"
            "    add  t1, t0, a0\n"
            "    bgtu t1, s3, .abort\n"
            "    mv   s1, t1\n"
            "    mv   a0, t0\n"
            "    ret\n"
            # alloc_closure(index: a0, arity: a1) -> tagged closure in a0
            ".alloc_closure:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            "    sd   a0, 8(sp)\n"
            "    sd   a1, 16(sp)\n"
            f"    li   a0, {_CLOSURE}\n"
            "    call .alloc\n"
            "    ld   t0, 8(sp)\n"
            "    sd   t0, 0(a0)\n"
            "    ld   t0, 16(sp)\n"
            "    sd   t0, 8(a0)\n"
            "    sd   s2, 16(a0)\n"
            f"    ori  a0, a0, {_T_FUN}\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n"
            # alloc_str(len: a0) -> untagged record in a0 (length, bytes)
            ".alloc_str:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    sd   a0, 8(sp)\n"
            "    addi a0, a0, 8\n"
            "    call .alloc\n"
            "    ld   t0, 8(sp)\n"
            "    sd   t0, 0(a0)\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
            # alloc_arr(len: a0) -> untagged record in a0 (length, words)
            ".alloc_arr:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    sd   a0, 8(sp)\n"
            "    slli a0, a0, 3\n"
            "    addi a0, a0, 8\n"
            "    call .alloc\n"
            "    ld   t0, 8(sp)\n"
            "    sd   t0, 0(a0)\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
        )

    @staticmethod
    def emit_autocall() -> str:
        """Emit the read-time auto-call of a zero-parameter closure.

        ``_parse_expr`` consumes ``len(value.params)`` argument
        expressions from the value a name holds, so a name holding a
        nullary function is *called* by the bare read.  Anything else, and
        any closure with parameters, passes through untouched.
        """
        return (
            "# autocall(value: a0) -> a0; call it if it is a nullary closure\n"
            ".autocall:\n"
            f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t1, {_T_FUN}\n"
            "    bne  t0, t1, .autocall_ret\n"
            f"    srli t0, a0, {_TAG_BITS}\n"
            f"    slli t0, t0, {_TAG_BITS}\n"
            "    ld   t1, 8(t0)\n"
            "    bnez t1, .autocall_ret\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    mv   a1, sp\n"
            "    li   a2, 0\n"
            "    call .invoke\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            ".autocall_ret:\n"
            "    ret\n"
        )

    @staticmethod
    def emit_arith() -> str:
        """Emit the four arithmetic builtins over integers and booleans.

        ``_num`` accepts a bool (Python's ``isinstance(True, int)``), so
        ``add yes yes`` is 2 -- the untag below coerces a boolean's
        payload to 0 or 1 and the result is always an integer.  Anything
        else is the ``expected a number`` halt.  ``divide`` is exact
        integer division: the interpreter's ``/`` would produce a float,
        which is outside this compiler's domain, so a nonzero remainder
        aborts rather than printing something the interpreter would not.
        """
        return "".join(
            [
                # num(value: a0) -> a0 untagged, halting on a non-number
                ".num:\n",
                f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n",
                f"    li   t1, {_T_INT}\n",
                "    beq  t0, t1, .num_ok\n",
                f"    li   t1, {_T_BOOL}\n",
                "    bne  t0, t1, .abort\n",
                ".num_ok:\n",
                f"    srai a0, a0, {_TAG_BITS}\n",
                "    ret\n",
                # each builtin takes a0/a1 and returns a tagged integer
                ".b_add:\n",
                _two_numbers(),
                "    add  a0, t5, t6\n",
                _retag_int(),
                ".b_subtract:\n",
                _two_numbers(),
                "    sub  a0, t5, t6\n",
                _retag_int(),
                # `mulint`/`divint` are reached by a `call`, which writes
                # `ra` -- and `_two_numbers` has already restored the
                # caller's.  Saving it around the inner call is what keeps
                # the builtin returning to its own caller.
                ".b_multiply:\n",
                _two_numbers(),
                "    addi sp, sp, -16\n    sd   ra, 0(sp)\n",
                "    mv   a0, t5\n    mv   a1, t6\n    call .mulint\n",
                "    ld   ra, 0(sp)\n    addi sp, sp, 16\n",
                _retag_int(),
                ".b_divide:\n",
                _two_numbers(),
                "    beqz t6, .abort\n",
                "    addi sp, sp, -16\n    sd   ra, 0(sp)\n",
                "    mv   a0, t5\n    mv   a1, t6\n    call .divint\n",
                "    ld   ra, 0(sp)\n    addi sp, sp, 16\n",
                # a nonzero remainder would be a float in the interpreter
                "    bnez a1, .abort\n",
                _retag_int(),
                # mulint(a0, a1) -> a0: shift-and-add, rv64i has no mul
                ".mulint:\n",
                "    mv   t0, a0\n",
                "    mv   t1, a1\n",
                "    li   a0, 0\n",
                ".mul_loop:\n",
                "    beqz t1, .mul_done\n",
                "    andi t3, t1, 1\n",
                "    beqz t3, .mul_skip\n",
                "    add  a0, a0, t0\n",
                ".mul_skip:\n",
                "    slli t0, t0, 1\n",
                "    srli t1, t1, 1\n",
                "    j    .mul_loop\n",
                ".mul_done:\n",
                "    ret\n",
                # divint(a0, a1) -> quotient a0, remainder a1; signed,
                # truncating toward zero the way Python's division of an
                # exact quotient does (the inexact case aborts above)
                ".divint:\n",
                "    li   t6, 0\n",
                "    li   t4, 0\n",
                "    bgez a0, .div_a_pos\n",
                "    sub  a0, zero, a0\n",
                "    xori t6, t6, 1\n",
                "    li   t4, 1\n",
                ".div_a_pos:\n",
                "    bgez a1, .div_b_pos\n",
                "    sub  a1, zero, a1\n",
                "    xori t6, t6, 1\n",
                ".div_b_pos:\n",
                # restoring shift-subtract division over 64 bits
                "    li   t0, 0\n",
                "    li   t1, 0\n",
                "    li   t2, 63\n",
                ".div_loop:\n",
                "    slli t1, t1, 1\n",
                "    srl  t3, a0, t2\n",
                "    andi t3, t3, 1\n",
                "    or   t1, t1, t3\n",
                "    slli t0, t0, 1\n",
                "    bltu t1, a1, .div_skip\n",
                "    sub  t1, t1, a1\n",
                "    ori  t0, t0, 1\n",
                ".div_skip:\n",
                "    beqz t2, .div_done\n",
                "    addi t2, t2, -1\n",
                "    j    .div_loop\n",
                ".div_done:\n",
                "    mv   a0, t0\n",
                "    mv   a1, t1\n",
                # the remainder takes the dividend's sign, the quotient
                # the sign of the operands taken together
                "    beqz t4, .div_rem_done\n",
                "    sub  a1, zero, a1\n",
                ".div_rem_done:\n",
                "    beqz t6, .div_ret\n",
                "    sub  a0, zero, a0\n",
                ".div_ret:\n",
                "    ret\n",
            ]
        )

    @staticmethod
    def emit_compare() -> str:
        """Emit ``equals``, ``less``, ``not``, and the truthiness test.

        ``equals`` is Python's ``==``: numbers compare across the integer
        and boolean tags (``equals yes 1`` is true), strings compare by
        content, and values of unlike kinds are simply unequal.  Two
        arrays would need an elementwise walk that recurses into nested
        ones, so a pair of *distinct* arrays aborts rather than answering
        by address, which would be wrong whenever their contents match.
        """
        return (
            # equals(a0, a1) -> tagged boolean
            ".b_equals:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
            f"    andi t1, a1, {(1 << _TAG_BITS) - 1}\n"
            # two strings: compare their bytes
            f"    li   t2, {_T_STR}\n"
            "    bne  t0, t2, .eq_num\n"
            "    bne  t1, t2, .eq_false\n"
            "    call .streq\n"
            "    j    .eq_out\n"
            ".eq_num:\n"
            # numbers and booleans compare by payload across their tags
            "    call .numeric_pair\n"
            "    beqz a0, .eq_ident\n"
            "    bne  t5, t6, .eq_false\n"
            "    j    .eq_true\n"
            ".eq_ident:\n"
            # anything else: equal exactly when it is the same word
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    beq  a1, a2, .eq_ident_true\n"
            # Two *different* arrays would need an elementwise walk, which
            # nests: the interpreter's `==` recurses into them.  Answering
            # by address would say `no` where the interpreter says `yes`,
            # so this aborts rather than answering wrongly -- the same
            # treatment `say` of an array gets.
            f"    andi t0, a1, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t1, {_T_ARR}\n"
            "    beq  t0, t1, .abort\n"
            f"    andi t0, a2, {(1 << _TAG_BITS) - 1}\n"
            "    beq  t0, t1, .abort\n"
            f"    li   a0, {_tagged(0, _T_BOOL)}\n"
            "    ret\n"
            ".eq_ident_true:\n"
            f"    li   a0, {_tagged(1, _T_BOOL)}\n"
            "    ret\n"
            ".eq_true:\n"
            f"    li   a0, {_tagged(1, _T_BOOL)}\n"
            "    j    .eq_out\n"
            ".eq_false:\n"
            f"    li   a0, {_tagged(0, _T_BOOL)}\n"
            ".eq_out:\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
            # numeric_pair(a0, a1) -> a0 = 1 when both are numbers, with
            # their untagged values in t5/t6; a1/a2 keep the originals so
            # the identity arm can still see them
            ".numeric_pair:\n"
            "    mv   a2, a1\n"
            "    mv   a1, a0\n"
            f"    andi t0, a1, {(1 << _TAG_BITS) - 1}\n"
            f"    andi t1, a2, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t2, {_T_ARR}\n"
            "    beq  t0, t2, .np_no\n"
            f"    li   t2, {_T_STR}\n"
            "    beq  t0, t2, .np_no\n"
            f"    li   t2, {_T_FUN}\n"
            "    beq  t0, t2, .np_no\n"
            f"    li   t2, {_T_NONE}\n"
            "    beq  t0, t2, .np_no\n"
            f"    li   t2, {_T_ARR}\n"
            "    beq  t1, t2, .np_no\n"
            f"    li   t2, {_T_STR}\n"
            "    beq  t1, t2, .np_no\n"
            f"    li   t2, {_T_FUN}\n"
            "    beq  t1, t2, .np_no\n"
            f"    li   t2, {_T_NONE}\n"
            "    beq  t1, t2, .np_no\n"
            f"    srai t5, a1, {_TAG_BITS}\n"
            f"    srai t6, a2, {_TAG_BITS}\n"
            "    li   a0, 1\n"
            "    ret\n"
            ".np_no:\n"
            "    li   a0, 0\n"
            "    ret\n"
            # streq(a0, a1) -> tagged boolean over two string records
            ".streq:\n"
            f"    srli t0, a0, {_TAG_BITS}\n"
            f"    slli t0, t0, {_TAG_BITS}\n"
            f"    srli t1, a1, {_TAG_BITS}\n"
            f"    slli t1, t1, {_TAG_BITS}\n"
            "    ld   t2, 0(t0)\n"
            "    ld   t3, 0(t1)\n"
            "    bne  t2, t3, .streq_no\n"
            "    li   t4, 0\n"
            ".streq_loop:\n"
            "    beq  t4, t2, .streq_yes\n"
            "    add  t5, t0, t4\n"
            "    lbu  t5, 8(t5)\n"
            "    add  t6, t1, t4\n"
            "    lbu  t6, 8(t6)\n"
            "    bne  t5, t6, .streq_no\n"
            "    addi t4, t4, 1\n"
            "    j    .streq_loop\n"
            ".streq_yes:\n"
            f"    li   a0, {_tagged(1, _T_BOOL)}\n"
            "    ret\n"
            ".streq_no:\n"
            f"    li   a0, {_tagged(0, _T_BOOL)}\n"
            "    ret\n"
            # less(a0, a1): both must be numbers, matching _num
            ".b_less:\n" + _two_numbers() + "    blt  t5, t6, .less_yes\n"
            f"    li   a0, {_tagged(0, _T_BOOL)}\n"
            "    ret\n"
            ".less_yes:\n"
            f"    li   a0, {_tagged(1, _T_BOOL)}\n"
            "    ret\n"
            # not(a0): the truthiness test, inverted
            ".b_not:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    call .truthy\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    bnez a0, .not_no\n"
            f"    li   a0, {_tagged(1, _T_BOOL)}\n"
            "    ret\n"
            ".not_no:\n"
            f"    li   a0, {_tagged(0, _T_BOOL)}\n"
            "    ret\n"
            # truthy(a0) -> a0 = 0 or 1, matching _truthy: a number is
            # true when nonzero, a string or array when non-empty, and
            # anything else (a function, none) is true
            ".truthy:\n"
            f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t1, {_T_BOOL}\n"
            "    beq  t0, t1, .truthy_num\n"
            f"    li   t1, {_T_INT}\n"
            "    beq  t0, t1, .truthy_num\n"
            f"    li   t1, {_T_STR}\n"
            "    beq  t0, t1, .truthy_len\n"
            f"    li   t1, {_T_ARR}\n"
            "    beq  t0, t1, .truthy_len\n"
            "    li   a0, 1\n"
            "    ret\n"
            ".truthy_num:\n"
            f"    srai a0, a0, {_TAG_BITS}\n"
            "    beqz a0, .truthy_no\n"
            "    li   a0, 1\n"
            "    ret\n"
            ".truthy_len:\n"
            f"    srli t0, a0, {_TAG_BITS}\n"
            f"    slli t0, t0, {_TAG_BITS}\n"
            "    ld   a0, 0(t0)\n"
            "    beqz a0, .truthy_no\n"
            "    li   a0, 1\n"
            "    ret\n"
            ".truthy_no:\n"
            "    li   a0, 0\n"
            "    ret\n"
        )

    @staticmethod
    def emit_strings() -> str:
        """Emit ``concat`` and the value-to-text conversion it shares with ``say``.

        ``_as_str`` renders a boolean as ``yes``/``no``, ``none`` as
        ``None`` (Python's own spelling, which ``say say "x"`` exposes),
        an integer in decimal, and a string as itself.  An array would
        render through Python's ``str(list)``, printing element reprs, so
        it is outside the domain and aborts.
        """
        return (
            # concat(a0, a1) -> tagged string
            ".b_concat:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            "    sd   a1, 8(sp)\n"
            "    call .to_str\n"
            "    sd   a0, 16(sp)\n"
            "    ld   a0, 8(sp)\n"
            "    call .to_str\n"
            "    mv   t1, a0\n"
            "    ld   t0, 16(sp)\n"
            "    sd   t1, 24(sp)\n"
            "    ld   t2, 0(t0)\n"
            "    ld   t3, 0(t1)\n"
            "    add  a0, t2, t3\n"
            "    call .alloc_str\n"
            "    sd   a0, 8(sp)\n"
            "    ld   t0, 16(sp)\n"
            "    ld   t2, 0(t0)\n"
            "    li   t4, 0\n"
            ".cat_a:\n"
            "    beq  t4, t2, .cat_a_done\n"
            "    add  t5, t0, t4\n"
            "    lbu  t5, 8(t5)\n"
            "    add  t6, a0, t4\n"
            "    sb   t5, 8(t6)\n"
            "    addi t4, t4, 1\n"
            "    j    .cat_a\n"
            ".cat_a_done:\n"
            "    ld   t1, 24(sp)\n"
            "    ld   t3, 0(t1)\n"
            "    li   t4, 0\n"
            ".cat_b:\n"
            "    beq  t4, t3, .cat_b_done\n"
            "    add  t5, t1, t4\n"
            "    lbu  t5, 8(t5)\n"
            "    add  t6, a0, t2\n"
            "    add  t6, t6, t4\n"
            "    sb   t5, 8(t6)\n"
            "    addi t4, t4, 1\n"
            "    j    .cat_b\n"
            ".cat_b_done:\n"
            f"    ori  a0, a0, {_T_STR}\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n"
            # to_str(a0) -> untagged string record
            ".to_str:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
            f"    li   t1, {_T_STR}\n"
            "    beq  t0, t1, .to_str_same\n"
            f"    li   t1, {_T_BOOL}\n"
            "    beq  t0, t1, .to_str_bool\n"
            f"    li   t1, {_T_INT}\n"
            "    beq  t0, t1, .to_str_int\n"
            f"    li   t1, {_T_NONE}\n"
            "    beq  t0, t1, .to_str_none\n"
            # an array or a function has no MyScript spelling here
            "    j    .abort\n"
            ".to_str_same:\n"
            f"    srli a0, a0, {_TAG_BITS}\n"
            f"    slli a0, a0, {_TAG_BITS}\n"
            "    j    .to_str_ret\n"
            ".to_str_bool:\n"
            f"    srai t0, a0, {_TAG_BITS}\n"
            "    beqz t0, .to_str_no\n"
            "    la   a0, .lit_yes\n"
            "    j    .to_str_ret\n"
            ".to_str_no:\n"
            "    la   a0, .lit_no\n"
            "    j    .to_str_ret\n"
            ".to_str_none:\n"
            "    la   a0, .lit_none\n"
            "    j    .to_str_ret\n"
            ".to_str_int:\n"
            f"    srai a0, a0, {_TAG_BITS}\n"
            "    call .int_str\n"
            ".to_str_ret:\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
            # int_str(a0) -> untagged string record of a0 in decimal
            ".int_str:\n"
            "    addi sp, sp, -48\n"
            "    sd   ra, 0(sp)\n"
            "    li   t0, 0\n"
            "    bgez a0, .int_pos\n"
            "    li   t0, 1\n"
            "    sub  a0, zero, a0\n"
            ".int_pos:\n"
            "    sd   t0, 8(sp)\n"
            "    sd   a0, 16(sp)\n"
            # count the digits first, so the record can be sized exactly
            "    li   t1, 1\n"
            "    mv   t2, a0\n"
            ".int_count:\n"
            "    li   t3, 10\n"
            "    bltu t2, t3, .int_counted\n"
            "    mv   a0, t2\n"
            "    li   a1, 10\n"
            "    sd   t1, 24(sp)\n"
            "    call .divint\n"
            "    ld   t1, 24(sp)\n"
            "    mv   t2, a0\n"
            "    addi t1, t1, 1\n"
            "    j    .int_count\n"
            ".int_counted:\n"
            "    ld   t0, 8(sp)\n"
            "    add  a0, t1, t0\n"
            "    sd   t1, 24(sp)\n"
            "    call .alloc_str\n"
            "    sd   a0, 32(sp)\n"
            "    ld   t0, 8(sp)\n"
            "    beqz t0, .int_nosign\n"
            "    li   t1, 45\n"
            "    sb   t1, 8(a0)\n"
            ".int_nosign:\n"
            # fill backward from the last digit
            "    ld   t1, 24(sp)\n"
            "    ld   t2, 16(sp)\n"
            "    ld   t0, 8(sp)\n"
            "    add  t1, t1, t0\n"
            ".int_digits:\n"
            "    addi t1, t1, -1\n"
            "    sd   t1, 40(sp)\n"
            "    mv   a0, t2\n"
            "    li   a1, 10\n"
            "    call .divint\n"
            "    ld   t1, 40(sp)\n"
            "    ld   a2, 32(sp)\n"
            "    addi a1, a1, 48\n"
            "    add  t3, a2, t1\n"
            "    sb   a1, 8(t3)\n"
            "    mv   t2, a0\n"
            "    ld   t0, 8(sp)\n"
            "    ble  t1, t0, .int_done\n"
            "    j    .int_digits\n"
            ".int_done:\n"
            "    ld   a0, 32(sp)\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 48\n"
            "    ret\n"
        )

    @staticmethod
    def emit_arrays() -> str:
        """Emit ``arrlen`` and ``itemat``.

        Both require an array, matching ``_as_list``; an index outside the
        array is the interpreter's ``itemat index out of range`` halt.
        The index may be a boolean, since ``_num`` accepts one.
        """
        return (
            ".b_arrlen:\n"
            + _need_array()
            + "    ld   a0, 0(t0)\n"
            + _retag_int()
            + ".b_itemat:\n"
            + _need_array()
            + "    mv   a0, a1\n"
            + f"    andi t1, a0, {(1 << _TAG_BITS) - 1}\n"
            + f"    li   t2, {_T_INT}\n"
            + "    beq  t1, t2, .item_ok\n"
            + f"    li   t2, {_T_BOOL}\n"
            + "    bne  t1, t2, .abort\n"
            + ".item_ok:\n"
            + f"    srai a0, a0, {_TAG_BITS}\n"
            + "    bltz a0, .abort\n"
            + "    ld   t1, 0(t0)\n"
            + "    bge  a0, t1, .abort\n"
            + "    slli a0, a0, 3\n"
            + "    add  t0, t0, a0\n"
            + "    ld   a0, 8(t0)\n"
            + "    ret\n"
        )

    @staticmethod
    def emit_say() -> str:
        """Emit ``say``: render the value and write it, returning ``none``.

        ``IO.print_value`` adds no trailing newline, so neither does this.
        """
        return (
            ".b_say:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    call .to_str\n"
            "    ld   a2, 0(a0)\n"
            "    addi a1, a0, 8\n"
            "    li   a7, 64\n"
            "    li   a0, 1\n"
            "    ecall\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            f"    li   a0, {_tagged(0, _T_NONE)}\n"
            "    ret\n"
        )

    @staticmethod
    def emit_ask() -> str:
        """Emit ``ask``: read one line, returning it as a string.

        ``IO.input_str`` returns a line without its terminator, and
        ``ScriptedIO`` splits the input into lines -- so a final
        unterminated line is still a line, and only a read that gets no
        bytes at all is past the end.  That case halts the run, matching
        the ``EOFError`` the interpreter lets unwind it.  Bytes are
        buffered into the arena as they arrive and the record is sized
        once the line is known.
        """
        return (
            ".do_ask:\n"
            "    addi sp, sp, -32\n"
            "    sd   ra, 0(sp)\n"
            # the record's length is not known yet, so bytes go straight
            # into the arena and the header is written afterward
            "    mv   t0, s1\n"
            "    sd   t0, 8(sp)\n"
            "    li   t1, 0\n"
            ".ask_loop:\n"
            "    sd   t1, 16(sp)\n"
            "    li   a7, 63\n"
            "    li   a0, 0\n"
            "    addi a1, sp, 24\n"
            "    li   a2, 1\n"
            "    ecall\n"
            "    ld   t1, 16(sp)\n"
            "    blez a0, .ask_eof\n"
            "    lbu  t2, 24(sp)\n"
            "    li   t3, 10\n"
            "    beq  t2, t3, .ask_done\n"
            "    ld   t0, 8(sp)\n"
            "    add  t4, t0, t1\n"
            "    addi t5, t4, 9\n"
            "    bgtu t5, s3, .abort\n"
            "    sb   t2, 8(t4)\n"
            "    addi t1, t1, 1\n"
            "    j    .ask_loop\n"
            ".ask_eof:\n"
            # no bytes at all before the end: the interpreter's EOFError
            "    beqz t1, .halt\n"
            ".ask_done:\n"
            "    ld   t0, 8(sp)\n"
            "    sd   t1, 0(t0)\n"
            "    addi t1, t1, 8\n"
            "    addi t1, t1, 7\n"
            "    andi t1, t1, -8\n"
            "    add  s1, t0, t1\n"
            "    bgtu s1, s3, .abort\n"
            "    mv   a0, t0\n"
            f"    ori  a0, a0, {_T_STR}\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 32\n"
            "    ret\n"
        )

    @staticmethod
    def emit_abort() -> str:
        """Emit the halt path every ``HaltError`` site shares."""
        return (
            "# every HaltError site lands here; the interpreter unwinds the\n"
            "# whole run, and the other compilers exit 0 on a halt\n"
            ".abort:\n"
            ".halt:\n"
            "    li   a0, 0\n"
            "    li   a7, 93\n"
            "    ecall\n"
        )

    def emit_data(self) -> str:
        """Emit the string literals, the fixed words, and the arena."""
        rows = ""
        for text, label in self.strings.items():
            rows += _string_record(label, text)
        return (
            "    .section .rodata\n"
            "    .align 3\n"
            + _string_record(".lit_yes", "yes")
            + _string_record(".lit_no", "no")
            + _string_record(".lit_none", "None")
            + rows
            + "    .bss\n"
            "    .align 3\n"
            "ms_arena:\n"
            f"    .space {_FRAMES * _FRAME_SIZE + _HEAP}\n"
        )


def _string_record(label: str, text: str) -> str:
    """Render a length-prefixed, 8-aligned string record."""
    data = text.encode("latin-1")
    body = "".join(f"    .byte {b}\n" for b in data)
    return f"    .align 3\n{label}:\n    .dword {len(data)}\n{body}"


def _two_numbers() -> str:
    """Emit the untagging both operands of an arithmetic builtin share."""
    return (
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    sd   a1, 8(sp)\n"
        "    call .num\n"
        "    mv   t5, a0\n"
        "    ld   a0, 8(sp)\n"
        "    sd   t5, 8(sp)\n"
        "    call .num\n"
        "    mv   t6, a0\n"
        "    ld   t5, 8(sp)\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
    )


def _retag_int() -> str:
    """Emit the re-tagging that turns a raw result back into a value."""
    return f"    slli a0, a0, {_TAG_BITS}\n    ret\n"


def _need_array() -> str:
    """Emit the array check ``arrlen`` and ``itemat`` share, base in t0."""
    return (
        f"    andi t0, a0, {(1 << _TAG_BITS) - 1}\n"
        f"    li   t1, {_T_ARR}\n"
        "    bne  t0, t1, .abort\n"
        f"    srli t0, a0, {_TAG_BITS}\n"
        f"    slli t0, t0, {_TAG_BITS}\n"
    )


def comp(code: str) -> str:
    """Compile a MyScript program to RISC-V assembly with syscall I/O."""
    return _Compiler().compile(_block_tree(code))


if __name__ == "__main__":  # pragma: no cover
    with open(sys.argv[1]) as _source:
        print(comp(_source.read()), end="")
