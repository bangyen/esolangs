"""Compiler that turns Forþ programs into RISC-V Linux assembly.

Forþ's ``(``/``[``/``{`` bodies are lexically delimited (matched the same
way the interpreter matches them: nesting counts only same-type brackets,
so a ``(`` inside a ``[...]`` does not affect the ``[``'s match), so unlike
the self-modifying-memory languages this compiles to a real call graph
instead of a fetch-decode-execute loop: each bracketed body becomes its own
labeled subroutine, reached through ``call``/``ret`` (matching the
interpreter's explicit call-stack of frames).  ``;`` is the one genuinely
dynamic construct -- ``{`` stores a body keyed by whatever runtime value is
on top of the stack, and ``;`` looks a body up by a popped runtime value --
so it lowers to a small runtime association list (``.bss`` array of
``(key, address)`` pairs) scanned backward on lookup so the most recent
``{`` for a given key wins, matching the Python dict's overwrite semantics;
a key with no entry is the interpreter's ``table.get(key, "")``, an empty
scope that returns immediately.

Registers: ``s1`` = data-stack pointer (points at the current top word,
growing down from a fixed high base -- ``s2`` holds that base so an empty
stack is detected as ``s1 == s2``), ``s3`` = table pointer (one past the
last stored association).  Every value is a sign-extended 32-bit word
stored in an 8-byte stack slot, matching the other compilers' ``.dword``
convention.

Two abort behaviors, matching ``_Machine._abort``/``_pop``:
- an empty-stack pop is fatal at any nesting depth (the interpreter's
  :class:`HaltError` unwinds every frame) -- compiles to a direct jump to
  the program's halt label from wherever it occurs, including inside a
  called subroutine;
- every other invalid operation (a binary op or ``c`` with too few
  operands, division/modulo by zero, an unterminated bracket) aborts the
  *whole current scope*, not just the failing instruction -- the
  interpreter's ``_abort`` sets the frame's cursor straight to the end of
  its code, discarding whatever the scope would otherwise still have done.
  ``emit_body`` threads an ``abort_to`` label through every recursive call
  (a bracket body's own exit label, or ``.halt`` at the true top level) so
  a failing op's call site -- not the shared op subroutine, which only
  reports success/failure in ``a0`` -- jumps straight past the rest of the
  scope on failure; an unterminated bracket goes through the same
  ``abort_to`` jump, since it is a compile-time instance of the same "finish
  this frame early" case (brackets are matched at compile time the same way
  the interpreter matches them at run time, so a dangling bracket and
  everything after it in the enclosing scope is simply not emitted).
"""

import sys

# Fixed-size data-stack and association-table capacity.  The interpreter's
# stack and table grow without bound; a compiled program gets generous
# preallocated arrays instead, the same tradeoff the other compilers make
# for their memory models.
_STACK_CELLS = 65536
_TABLE_CELLS = 4096


def _match(code: str, start: int) -> int:
    """Return the index just past the bracket body starting at ``start``.

    ``code[start]`` must be ``(``, ``[``, or ``{``.  Nesting counts only the
    same open character, matching ``_Machine.step``'s bracket handling, so
    e.g. a ``(`` inside a ``[...]`` body does not affect the ``[``'s match.
    Returns ``-1`` if the bracket is never closed.
    """
    add = code[start]
    sub = ")" if add == "(" else "]" if add == "[" else "}"
    depth = 1
    i = start + 1
    while i < len(code):
        if code[i] == add:
            depth += 1
        elif code[i] == sub:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


class _Compiler:
    """Emits one RISC-V subroutine per bracketed Forþ scope."""

    def __init__(self) -> None:
        self.subs: list[str] = []
        self.sub_count = 0

    def new_label(self) -> str:
        self.sub_count += 1
        return f".scope{self.sub_count}"

    def emit_body(self, code: str, abort_to: str) -> str:
        """Compile ``code`` to straight-line instructions.

        ``code`` is a top-level program or a bracket body; nested scopes are
        recursively emitted as their own subroutines appended to
        ``self.subs``.  ``abort_to`` is where an invalid operation (a binary
        op or ``c`` with too few operands, division/modulo by zero) jumps:
        the interpreter's ``_abort`` finishes the *whole* current frame, not
        just the failing instruction, so op call sites -- not the shared
        op subroutines themselves -- test the returned status and jump
        straight past the rest of this body to ``abort_to`` (this body's own
        exit label, or ``.halt`` at the true top level, which has no exit
        label to fall into).
        """
        out = []
        i = 0
        n = len(code)
        while i < n:
            char = code[i]
            i += 1

            if "0" <= char <= "9":
                out.append(f"    li   t0, {ord(char) - 48}\n    call push\n")
            elif "A" <= char <= "F":
                out.append(f"    li   t0, {ord(char) - 55}\n    call push\n")
            elif char == ":":
                out.append("    call dup\n")
            elif char == "~":
                out.append("    call complement\n")
            elif char == ".":
                out.append("    call print_top\n")
            elif char == ",":
                out.append("    call read_line\n")
            elif char == "o":
                out.append("    call reverse\n")
            elif char == "c":
                out.append(f"    call rotate3\n    beqz a0, {abort_to}\n")
            elif char in "+-*/%v":
                out.append(f"    call op_{_OP_NAMES[char]}\n    beqz a0, {abort_to}\n")
            elif char in "([{":
                end = _match(code, i - 1)
                if end == -1:
                    # Unmatched bracket: the interpreter only reaches this by
                    # running off the end of the source, which means nothing
                    # after it in this scope is reachable either -- the same
                    # "finish this whole frame" abort as a failed operator.
                    out.append(f"    j    {abort_to}\n")
                    break
                body = code[i : end - 1]
                i = end
                label = self.new_label()
                exit_label = f"{label}_exit"
                inner = self.emit_body(body, exit_label)
                self.subs.append(
                    label + ":\n"
                    "    addi sp, sp, -16\n"
                    "    sd   ra, 0(sp)\n" + inner + exit_label + ":\n"
                    "    ld   ra, 0(sp)\n"
                    "    addi sp, sp, 16\n"
                    "    ret\n"
                )
                if char == "(":
                    # fmt: off
                    # One source line per emitted instruction, matching the
                    # surrounding assembly templates; collapsing these into a
                    # single string would hide the generated code's shape.
                    out.append(
                        "    call peek\n"
                        "    beqz t0, 1f\n"
                        f"    call {label}\n"
                        "1:\n"
                    )
                    # fmt: on
                elif char == "[":
                    loop = self.new_label()
                    out.append(
                        f"{loop}:\n"
                        "    call peek\n"
                        "    beqz t0, 1f\n"
                        f"    call {label}\n"
                        f"    j    {loop}\n"
                        "1:\n"
                    )
                else:  # "{"
                    out.append(
                        "    call peek\n"
                        "    mv   a0, t0\n"
                        f"    la   a1, {label}\n"
                        "    call table_store\n"
                    )
            elif char == ";":
                out.append("    call pop\n    mv   a0, t0\n    call table_call\n")
            # any other character is ignored, matching the interpreter
        return "".join(out)

    def compile_program(self, code: str) -> str:
        main = self.emit_body(code, ".halt")
        return main + "    j    .halt\n" + "".join(self.subs)


_OP_NAMES = {
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "div",
    "%": "mod",
    "v": "swap",
}


def _read_line(body: str) -> str:
    r"""Emit ``read_line``, or nothing when ``,`` never appears.

    ``,`` is the only command that calls it, so a program without one can
    never reach the routine -- the same ``used``-flag gate the tape
    compilers apply to their subroutines, keyed off the emitted call site
    rather than a separate flag threaded through the compiler.
    """
    if "call read_line\n" not in body:
        return ""

    return (
        "# read_line() -- read one byte at a time until '\\n' or EOF, pushing\n"
        "# each byte (rightmost/last-read on top), matching io.input_str's\n"
        "# whole-line reads: ScriptedIO.splitlines() lets a final line with\n"
        "# no trailing newline through as one valid (short) read, so EOF\n"
        "# only halts the whole program (matching EOFError, uncaught by\n"
        "# run()) when it is hit before this call has read any byte at all\n"
        "# -- EOF after at least one byte just ends that last, unterminated\n"
        "# line normally, the same as hitting '\\n'.\n"
        "read_line:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    li   t2, 0\n"  # any byte read yet for this call?
        "1:\n"
        "    li   a7, 63\n"
        "    li   a0, 0\n"
        "    addi a1, sp, 8\n"
        "    li   a2, 1\n"
        "    ecall\n"
        "    bgtz a0, 3f\n"
        "    beqz t2, .halt\n"
        "    j    2f\n"
        "3:\n"
        "    li   t2, 1\n"
        "    lbu  t0, 8(sp)\n"
        "    li   t1, 10\n"
        "    beq  t0, t1, 2f\n"
        "    call push\n"
        "    j    1b\n"
        "2:\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
    )


def comp(code: str) -> str:
    """Compile a Forþ program to RISC-V assembly."""
    compiler = _Compiler()
    body = compiler.compile_program(code)

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    la   s2, stack_base\n"
        "    mv   s1, s2\n"
        "    la   s3, table\n"
        "\n"
    )
    res += body
    res += (
        "\n"
        ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
        "\n"
        "# push(value: t0) -- push t0 onto the data stack\n"
        "push:\n"
        "    addi s1, s1, -8\n"
        "    sd   t0, 0(s1)\n"
        "    ret\n"
        "\n"
        "# pop() -> t0; an empty-stack pop halts the whole program\n"
        "pop:\n"
        "    beq  s1, s2, .halt\n"
        "    ld   t0, 0(s1)\n"
        "    addi s1, s1, 8\n"
        "    ret\n"
        "\n"
        "# peek() -> t0; an empty-stack peek halts the whole program\n"
        "peek:\n"
        "    beq  s1, s2, .halt\n"
        "    ld   t0, 0(s1)\n"
        "    ret\n"
        "\n"
        "dup:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call peek\n"
        "    call push\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "\n"
        "complement:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call pop\n"
        "    not  t0, t0\n"
        "    call wrap32\n"
        "    call push\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "\n"
        "# print_top() -- pop and print the low byte\n"
        "print_top:\n"
        "    addi sp, sp, -32\n"
        "    sd   ra, 0(sp)\n"
        "    call pop\n"
        "    andi a0, t0, 0xff\n"
        "    sd   a0, 16(sp)\n"
        "    li   a7, 64\n"
        "    li   a0, 1\n"
        "    addi a1, sp, 16\n"
        "    li   a2, 1\n"
        "    ecall\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 32\n"
        "    ret\n"
        "\n" + _read_line(body) + "\n"
        "# reverse() -- reverse the whole data stack in place\n"
        "reverse:\n"
        "    mv   t3, s1\n"
        "    mv   t4, s2\n"
        "    addi t4, t4, -8\n"
        "1:\n"
        "    bge  t3, t4, 2f\n"
        "    ld   t0, 0(t3)\n"
        "    ld   t1, 0(t4)\n"
        "    sd   t1, 0(t3)\n"
        "    sd   t0, 0(t4)\n"
        "    addi t3, t3, 8\n"
        "    addi t4, t4, -8\n"
        "    j    1b\n"
        "2:\n"
        "    ret\n"
        "\n"
        "# rotate3() -> a0 (1 ok, 0 aborted); moves the third-from-top value\n"
        "# to the top, or reports abort if fewer than three values are on\n"
        "# the stack.  On abort the caller must unwind its whole current\n"
        "# scope (see emit_body's abort_to), not just skip this call, so it\n"
        "# only reports status here and never touches ra/sp/s4 itself.\n"
        "rotate3:\n"
        "    mv   t1, s2\n"
        "    addi t1, t1, -24\n"
        "    blt  t1, s1, .rotate3_abort\n"
        "    ld   t0, 16(s1)\n"
        "    ld   t1, 8(s1)\n"
        "    ld   t2, 0(s1)\n"
        "    sd   t1, 16(s1)\n"
        "    sd   t2, 8(s1)\n"
        "    sd   t0, 0(s1)\n"
        "    li   a0, 1\n"
        "    ret\n"
        ".rotate3_abort:\n"
        "    li   a0, 0\n"
        "    ret\n"
        "\n"
        "# binary ops -> a0 (1 ok, 0 aborted): pop two (one=second-from-top,\n"
        "# two=top), push the result; fewer than two values, or a zero\n"
        "# divisor for div/mod, aborts without pushing.  Like rotate3, only\n"
        "# status is reported -- the abort itself unwinds the whole calling\n"
        "# scope at the call site, not just this op.  rv64i has no M\n"
        "# extension, so mul/div/mod are software (mul32/divmod32 below);\n"
        "# every result is truncated to a sign-extended 32-bit word, matching\n"
        "# the interpreter's _wrap32.\n"
        "op_add:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    add  t0, t1, t2\n"
        "    call wrap32\n"
        "    call push\n"
        "    j    .op_ok\n"
        "op_sub:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    sub  t0, t1, t2\n"
        "    call wrap32\n"
        "    call push\n"
        "    j    .op_ok\n"
        "op_mul:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    mv   a0, t1\n"
        "    mv   a1, t2\n"
        "    call mul32\n"
        "    mv   t0, a0\n"
        "    call push\n"
        "    j    .op_ok\n"
        "op_div:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    beqz t2, .op_abort\n"
        "    mv   a0, t1\n"
        "    mv   a1, t2\n"
        "    call divmod32\n"
        "    mv   t0, a0\n"
        "    call push\n"
        "    j    .op_ok\n"
        "op_mod:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    beqz t2, .op_abort\n"
        "    mv   a0, t1\n"
        "    mv   a1, t2\n"
        "    call divmod32\n"
        "    mv   t0, a1\n"
        "    call push\n"
        "    j    .op_ok\n"
        "op_swap:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call binary_operands\n"
        "    beqz t3, .op_abort\n"
        "    mv   t0, t2\n"
        "    call push\n"
        "    mv   t0, t1\n"
        "    call push\n"
        ".op_ok:\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    li   a0, 1\n"
        "    ret\n"
        ".op_abort:\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    li   a0, 0\n"
        "    ret\n"
        "\n"
        "# binary_operands() -> t1 (one), t2 (two), t3 (1 if both present else 0)\n"
        "binary_operands:\n"
        "    mv   t4, s2\n"
        "    addi t4, t4, -16\n"
        "    blt  t4, s1, .no_operands\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call pop\n"
        "    mv   t2, t0\n"
        "    call pop\n"
        "    mv   t1, t0\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    li   t3, 1\n"
        "    ret\n"
        ".no_operands:\n"
        "    li   t3, 0\n"
        "    ret\n"
        "\n"
        "# wrap32() -- truncate t0 to a signed 32-bit value, sign-extended\n"
        "# back to 64 bits (matching the interpreter's _wrap32)\n"
        "wrap32:\n"
        "    slli t0, t0, 32\n"
        "    srai t0, t0, 32\n"
        "    ret\n"
        "\n"
        "# mul32(a0, a1) -> a0 = (a0 * a1), wrapped to signed 32-bit\n"
        "# (rv64i has no M extension; shift-and-add is sign-agnostic on\n"
        "# two's-complement operands as long as the result is truncated)\n"
        "mul32:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    mv   t4, a0\n"
        "    mv   t5, a1\n"
        "    li   a0, 0\n"
        "1:\n"
        "    beqz t5, 2f\n"
        "    andi t6, t5, 1\n"
        "    beqz t6, 3f\n"
        "    add  a0, a0, t4\n"
        "3:\n"
        "    slli t4, t4, 1\n"
        "    srli t5, t5, 1\n"
        "    j    1b\n"
        "2:\n"
        "    mv   t0, a0\n"
        "    call wrap32\n"
        "    mv   a0, t0\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "\n"
        "# divmod32(a0, a1) -> a0 = quotient, a1 = remainder, truncating\n"
        "# toward zero (matching the interpreter's _trunc_div/_trunc_mod);\n"
        "# a1 (divisor) must be nonzero -- checked by the caller\n"
        "divmod32:\n"
        "    li   t4, 0\n"  # sign of the result (1 if operand signs differ)
        "    mv   t5, a0\n"  # keep the dividend's sign for the remainder
        "    bgez a0, 1f\n"
        "    sub  a0, x0, a0\n"
        "    xori t4, t4, 1\n"
        "1:\n"
        "    bgez a1, 2f\n"
        "    sub  a1, x0, a1\n"
        "    xori t4, t4, 1\n"
        "2:\n"
        "    li   t0, 0\n"  # unsigned quotient
        "3:\n"
        "    bltu a0, a1, 4f\n"
        "    sub  a0, a0, a1\n"
        "    addi t0, t0, 1\n"
        "    j    3b\n"
        "4:\n"  # a0 now holds the unsigned remainder
        "    beqz t4, 5f\n"
        "    sub  t0, x0, t0\n"
        "5:\n"
        "    bgez t5, 6f\n"
        "    sub  a0, x0, a0\n"
        "6:\n"
        "    mv   a1, a0\n"
        "    mv   a0, t0\n"
        "    ret\n"
        "\n"
        "# table_store(key: a0, addr: a1) -- append (key, addr) to the table\n"
        "table_store:\n"
        "    sd   a0, 0(s3)\n"
        "    sd   a1, 8(s3)\n"
        "    addi s3, s3, 16\n"
        "    ret\n"
        "\n"
        "# table_call(key: a0) -- scan the table backward for the most recent\n"
        "# entry with this key and call it; a key with no entry is a no-op\n"
        '# (the interpreter\'s table.get(key, "") is an empty scope)\n'
        "table_call:\n"
        "    la   t0, table\n"
        "    mv   t1, s3\n"
        "1:\n"
        "    beq  t1, t0, 2f\n"
        "    addi t1, t1, -16\n"
        "    ld   t2, 0(t1)\n"
        "    bne  t2, a0, 1b\n"
        "    ld   t3, 8(t1)\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    jalr ra, t3, 0\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "2:\n"
        "    ret\n"
        "\n"
        "    .bss\n"
        "    .align 3\n"
        f"table:\n    .space {_TABLE_CELLS * 16}\n"
        f"stack:\n    .space {_STACK_CELLS * 8}\n"
        "stack_base:\n"
    )
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
