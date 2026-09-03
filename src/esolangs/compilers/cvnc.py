r"""Compiler that turns CV(N)(C) programs into RISC-V Linux assembly.

CV(N)(C) is the first compiler here whose program *builds a function at
runtime and applies it*, and that is the fact the whole lowering turns on.
``d``/``b``/``t``/``ɡ``/``q``/``ʔ``/``ʡ`` append symbols to an array,
``p``/``k`` append a *number popped from the deque* as a literal, ``c``
empties it, and ``u`` parses and evaluates whatever that array currently
spells.  Nothing about the applied expression is known at compile time --
not its shape, not its length, not even its alphabet, since a popped
literal is an arbitrary 64-bit value -- so ``u`` lowers to a real
recursive-descent evaluator over the array rather than to emitted
arithmetic.  That evaluator is a transcription of the interpreter's
``_Parser``: ``_expression`` over ``+``/``-``, ``_term`` over ``*``/``/``,
``_factor`` over ``a``, a literal, and a parenthesized expression, with a
parse failure meaning *the function is invalid* and leaving the accumulator
alone.

**Every token is a jump target.**  ``ɹ`` jumps to the accumulator-th
*codepoint* of the source and ``j`` to the accumulator-th *syllable*, both
computed at runtime, so control can land on any command.  Two static tables
carry that: ``cvnc_offsets`` maps each codepoint offset to its token index
and ``cvnc_starts`` maps each syllable index to the token index it begins
at.  A token index is turned into an address through ``cvnc_labels``, a
table of per-token label addresses, and the dispatch is one indexed load
and a ``jr``.  A ``ɰ̊`` spans two codepoints and both map to it -- there is
no command to resume at in the middle of one -- and any index past the end
lands on ``.halt``, which is what running off the end already does.  The
loop commands need no such table: ``_match_loops`` pairs them statically,
so ``ɰ̊``/``ɰ``/``ʋ`` become direct branches.

**Values are unsigned**, which the interpreter is explicit about, so every
comparison is ``bltu``/``bgeu`` and every subtraction floors at zero -- in
``ə``, and again in the evaluator's ``-``.  Container went signed because
its literals may be negative; nothing here may be.

The parser is the interpreter's own ``_tokenize``/``_syllabify``/
``_match_loops`` rather than a rewrite, so the compiler accepts exactly the
programs the interpreter accepts: the ring-joining, the ASCII ``g`` fold,
the greedy syllabification, and the unbalanced-loop rejection all come from
one shared implementation.

``rv64i`` has no hardware multiply or divide, so ``æ`` and the evaluator's
``*`` go through a shift-and-add ``mul64``, ``/`` through a restoring
``divu64``, and ``θ``'s decimal print through that same divider.  ``o``
(integer square root) is a bit-at-a-time restoring square root, which needs
only shifts, adds, and comparisons.

**Input is line-faithful**, derived from the interpreter's refill rather
than from a default.  ``s`` calls ``IO.input_str`` and parses the whole
line; ``ʒ`` calls ``IO.input_char``, which takes a line and returns its
*first* character, so a line's remaining bytes are discarded and an empty
line reads as the ``\n`` that ended it.  Both are Forbin's convention, not
Container's: a byte reader would make identical stdin produce different
output from the interpreter, which is the point of the differential.  EOF
halts the run, matching the interpreter's ``EOFError`` unwinding it.

``s``'s parse follows ``_as_int`` composed with the unsigned floor: the
line is stripped, an optional sign is taken, and anything that is not then
all digits reads as 0 -- an empty line and a line of junk are both input a
user can legitimately type, not invalid operations.  A negative line floors
at 0.

**Agreement there is over ASCII input, and the narrowing is measured
rather than assumed.**  ``_as_int`` is Python's ``int()`` after
``str.strip()``, and both are Unicode-aware in ways the assembly is not:
``int("4_2")`` is 42, since underscores are legal between digits, and
``str.strip()`` removes any character ``str.isspace()`` accepts, which
includes NBSP (U+00A0).  The compiled reader strips only the ASCII
space/tab family and accepts only ASCII digits, so ``4_2`` and ``\xa042``
each read as 0 where the interpreter reads 42.  Chasing ``int()``'s full
grammar -- Unicode decimal digits, the underscore placement rules, every
``isspace`` codepoint -- into assembly buys nothing any program here
reaches, so the domain is stated instead, the way Container's value bound
is.  Everything ASCII agrees, including the sign forms, leading zeros,
interior tabs, and a 19-digit value.

**Runtime errors halt with exit 0** through ``.halt``, the convention every
compiler here shares for the interpreter's ``HaltError``: popping an empty
deque (``p``, ``k``, ``ŋ``, ``ɲ``) and dividing by zero inside the function
are the two sites.

**The compiled program is not total**, and two fixed buffers are why.  The
interpreter's accumulator, deque, and function are unbounded; here a value
is a 64-bit unsigned word, the deque holds :data:`_DEQUE` entries, and the
function holds :data:`_FN` symbols.  Agreement is therefore bounded, the
rule stated in ``docs/limitations.md`` that every compiler here shares.
The value bound bites first and is the interesting one: ``æ`` squares, so
an accumulator past ``2**32`` wraps where the interpreter grows.  Both
generators stay far inside every bound, measured rather than assumed: the
text generator's accumulator is a byte (peak 255) and never touches the
deque or the function, and the boolean generator peaks at an accumulator
of 6,765,201 -- its halt gadget, which squares twice to jump past the end
of the program -- with a deque that holds one entry per input read
(depth 4 at ``n == 4``) and a function that stays empty, since it builds
none.  So this bounds hand-written programs only.  Overflowing either
buffer aborts rather than corrupting memory.

Registers: ``s1`` = the accumulator, ``s2`` = the deque base, ``s3`` = the
deque's front index, ``s4`` = its length, ``s5`` = the function base, ``s6``
= the function's length.  The deque is a *circular* buffer, so ``m``
(push-front) costs the same as ``n`` (push-back) rather than shifting every
entry.  ``s7`` is the evaluator's cursor into the function.
"""

from esolangs.compilers import _riscv_common as _common
from esolangs.compilers._riscv_common import PUTBYTE
from esolangs.interpreters.other.cvnc import (
    _FUNCTION_SYMBOLS,
    _LOOP_END,
    _WHILE_NONZERO,
    _WHILE_ZERO,
    _match_loops,
    _syllabify,
    _tokenize,
)

# Fixed capacities for the two unbounded structures.  Both are far past
# anything the generators reach (each stays empty), so these bound
# hand-written programs; overflowing either aborts through `.halt`.
_DEQUE = 4096
_FN = 4096

# The evaluator's symbol tags.  A function entry is two words -- a tag and
# a value -- because `p`/`k` append an arbitrary popped number, so a
# literal cannot be squeezed into the tag the way the seven fixed symbols
# can.  `_FUNCTION_SYMBOLS` maps each plosive to the character the
# interpreter appends, and these tag that same alphabet.
_TAGS = {"a": 0, "+": 1, "-": 2, "*": 3, "/": 4, "(": 5, ")": 6}
_LITERAL = 7

# The commands, named so each emit reads as the operation it performs
# rather than as a comparison against a bare IPA character.
_PRINT_NUM = "θ"
_PRINT_CHAR = "f"
_READ_NUM = "s"
_READ_CHAR = "ʒ"
_CLEAR_FUNCTION = "c"
_POP_FRONT_APPEND = "p"
_POP_BACK_APPEND = "k"
_INCREMENT = "i"
_DECREMENT = "ə"
_SQUARE = "æ"
_SQRT = "o"
_APPLY = "u"
_PUSH_FRONT = "m"
_PUSH_BACK = "n"
_POP_FRONT = "ŋ"
_POP_BACK = "ɲ"
_GOTO = "ɹ"
_GOTO_LINE = "j"


def _label(index: int) -> str:
    """Return the assembler label for the token at ``index``."""
    return f".t{index}"


def _emit_vowel(token: str) -> str:
    """Emit one accumulator command.

    ``ə`` floors at zero rather than wrapping, matching the interpreter's
    explicit "decrement if it is greater than zero" over unsigned memory.
    """
    if token == _INCREMENT:
        return "    addi s1, s1, 1\n"
    if token == _DECREMENT:
        return "    beqz s1, 1f\n    addi s1, s1, -1\n1:\n"
    if token == _SQUARE:
        return "    mv   a0, s1\n    mv   a1, s1\n    call mul64\n    mv   s1, a0\n"
    if token == _SQRT:
        return "    mv   a0, s1\n    call isqrt64\n    mv   s1, a0\n"
    return "    call apply\n"


def _emit_nasal(token: str) -> str:
    """Emit one deque command: a push to either end, or a pop into ``s1``."""
    if token == _PUSH_FRONT:
        return "    mv   a0, s1\n    call push_front\n"
    if token == _PUSH_BACK:
        return "    mv   a0, s1\n    call push_back\n"
    if token == _POP_FRONT:
        return "    call pop_front\n    mv   s1, a0\n"
    return "    call pop_back\n    mv   s1, a0\n"


def _emit_fricative(token: str) -> str:
    """Emit one I/O command."""
    if token == _PRINT_NUM:
        return "    mv   a0, s1\n    call printnum\n"
    if token == _PRINT_CHAR:
        return "    andi a0, s1, 0xff\n    call putbyte\n"
    if token == _READ_NUM:
        return "    call readnum\n    mv   s1, a0\n"
    return "    call readchar\n    andi s1, a0, 0xff\n"


def _emit_plosive(token: str) -> str:
    """Emit one function-building command.

    The seven fixed symbols append a tag with no value; ``p`` and ``k``
    pop an end of the deque and append that number as a literal.
    """
    if token == _CLEAR_FUNCTION:
        return "    li   s6, 0\n"
    if token in _FUNCTION_SYMBOLS:
        return (
            f"    li   a0, {_TAGS[_FUNCTION_SYMBOLS[token]]}\n"
            "    li   a1, 0\n"
            "    call fn_append\n"
        )
    call = "pop_front" if token == _POP_FRONT_APPEND else "pop_back"
    return (
        f"    call {call}\n"
        "    mv   a1, a0\n"
        f"    li   a0, {_LITERAL}\n"
        "    call fn_append\n"
    )


def _emit_approximant(token: str, index: int, pairs: dict[int, int]) -> str:
    """Emit one control-flow command.

    ``ɰ̊``/``ɰ`` branch *past* their matching ``ʋ`` when their test holds,
    and ``ʋ`` jumps back *onto* its opener to re-test; the pairing is
    static, so all three are direct branches.  The two gotos are computed
    and go through the dispatch tables.
    """
    if token == _WHILE_ZERO:
        return f"    beqz s1, {_label(pairs[index] + 1)}\n"
    if token == _WHILE_NONZERO:
        return f"    bnez s1, {_label(pairs[index] + 1)}\n"
    if token == _LOOP_END:
        return f"    j    {_label(pairs[index])}\n"
    table = "cvnc_offsets" if token == _GOTO else "cvnc_starts"
    limit = "cvnc_noffsets" if token == _GOTO else "cvnc_nstarts"
    return (
        f"    la   t0, {limit}\n"
        "    ld   t0, 0(t0)\n"
        "    bgeu s1, t0, .halt\n"
        f"    la   t1, {table}\n"
        "    slli t2, s1, 3\n"
        "    add  t1, t1, t2\n"
        "    ld   t1, 0(t1)\n"
        "    j    dispatch\n"
    )


def _emit_token(token: str, index: int, pairs: dict[int, int]) -> str:
    """Emit the body of one command, labelled so a goto can land on it."""
    from esolangs.interpreters.other.cvnc import (
        _FRICATIVES,
        _NASALS,
        _PLOSIVES,
        _VOWELS,
    )

    body = f"{_label(index)}:\n"
    if token in _FRICATIVES:
        return body + _emit_fricative(token)
    if token in _PLOSIVES:
        return body + _emit_plosive(token)
    if token in _VOWELS:
        return body + _emit_vowel(token)
    if token in _NASALS:
        return body + _emit_nasal(token)
    return body + _emit_approximant(token, index, pairs)


def _dispatch() -> str:
    """Emit the indexed jump every computed goto lands in.

    ``t1`` holds a token index; ``cvnc_labels`` turns it into the address
    of that token's label.  Past the end is a halt, which is what running
    off the end already does.
    """
    return (
        "# dispatch(t1 = token index) -- jump to that token's code\n"
        "dispatch:\n"
        "    la   t2, cvnc_ntokens\n"
        "    ld   t2, 0(t2)\n"
        "    bgeu t1, t2, .halt\n"
        "    la   t3, cvnc_labels\n"
        "    slli t4, t1, 3\n"
        "    add  t3, t3, t4\n"
        "    ld   t3, 0(t3)\n"
        "    jr   t3\n"
    )


def _deque() -> str:
    """Emit the circular deque: two pushes, two pops, and their guards.

    ``s3`` is the front index and ``s4`` the length, both modulo the
    capacity, so pushing either end is O(1).  Popping an empty deque is the
    interpreter's ``HaltError`` and halts the run.
    """
    return (
        "# push_front(a0) / push_back(a0); pop_front() / pop_back() -> a0\n"
        "# A circular buffer indexed by (s3 + i) % _DEQUE, so both ends are\n"
        "# O(1); overflow aborts rather than wrapping onto live entries.\n"
        "push_front:\n"
        f"    li   t0, {_DEQUE}\n"
        "    bgeu s4, t0, .halt\n"
        "    addi s3, s3, -1\n"
        "    bgez s3, 1f\n"
        f"    li   s3, {_DEQUE - 1}\n"
        "1:\n"
        "    slli t1, s3, 3\n"
        "    add  t1, s2, t1\n"
        "    sd   a0, 0(t1)\n"
        "    addi s4, s4, 1\n"
        "    ret\n"
        "push_back:\n"
        f"    li   t0, {_DEQUE}\n"
        "    bgeu s4, t0, .halt\n"
        "    add  t1, s3, s4\n"
        "    bltu t1, t0, 1f\n"
        "    sub  t1, t1, t0\n"
        "1:\n"
        "    slli t1, t1, 3\n"
        "    add  t1, s2, t1\n"
        "    sd   a0, 0(t1)\n"
        "    addi s4, s4, 1\n"
        "    ret\n"
        "pop_front:\n"
        "    beqz s4, .halt\n"
        "    slli t1, s3, 3\n"
        "    add  t1, s2, t1\n"
        "    ld   a0, 0(t1)\n"
        "    addi s3, s3, 1\n"
        f"    li   t0, {_DEQUE}\n"
        "    bltu s3, t0, 1f\n"
        "    li   s3, 0\n"
        "1:\n"
        "    addi s4, s4, -1\n"
        "    ret\n"
        "pop_back:\n"
        "    beqz s4, .halt\n"
        "    add  t1, s3, s4\n"
        "    addi t1, t1, -1\n"
        f"    li   t0, {_DEQUE}\n"
        "    bltu t1, t0, 1f\n"
        "    sub  t1, t1, t0\n"
        "1:\n"
        "    slli t1, t1, 3\n"
        "    add  t1, s2, t1\n"
        "    ld   a0, 0(t1)\n"
        "    addi s4, s4, -1\n"
        "    ret\n"
    )


def _fn_append() -> str:
    """Emit the function-array append: a (tag, value) pair, or abort."""
    return (
        "# fn_append(tag: a0, value: a1) -- push one function symbol\n"
        "fn_append:\n"
        f"    li   t0, {_FN}\n"
        "    bgeu s6, t0, .halt\n"
        "    slli t1, s6, 4\n"
        "    add  t1, s5, t1\n"
        "    sd   a0, 0(t1)\n"
        "    sd   a1, 8(t1)\n"
        "    addi s6, s6, 1\n"
        "    ret\n"
    )


def _arithmetic() -> str:
    """Emit software multiply, divide, and integer square root for ``rv64i``.

    ``mul64`` is shift-and-add and ``divu64`` restoring long division, both
    over the full 64 bits.  ``isqrt64`` is the bit-at-a-time restoring
    square root, which uses only shifts, adds, and comparisons -- the same
    reason ``forth`` carries its own ``mul32``.
    """
    return (
        "# mul64(a0, a1) -> a0, unsigned shift-and-add\n"
        "mul64:\n"
        "    mv   t0, a0\n"
        "    li   a0, 0\n"
        "1:\n"
        "    beqz a1, 3f\n"
        "    andi t1, a1, 1\n"
        "    beqz t1, 2f\n"
        "    add  a0, a0, t0\n"
        "2:\n"
        "    slli t0, t0, 1\n"
        "    srli a1, a1, 1\n"
        "    j    1b\n"
        "3:\n"
        "    ret\n"
        "# divu64(a0, a1) -> a0 quotient; a1 == 0 is the caller's problem\n"
        "divu64:\n"
        "    li   t0, 0\n"  # quotient
        "    li   t1, 0\n"  # remainder
        "    li   t2, 63\n"
        "1:\n"
        "    slli t1, t1, 1\n"
        "    srl  t3, a0, t2\n"
        "    andi t3, t3, 1\n"
        "    or   t1, t1, t3\n"
        "    slli t0, t0, 1\n"
        "    bltu t1, a1, 2f\n"
        "    sub  t1, t1, a1\n"
        "    ori  t0, t0, 1\n"
        "2:\n"
        "    beqz t2, 3f\n"
        "    addi t2, t2, -1\n"
        "    j    1b\n"
        "3:\n"
        "    mv   a0, t0\n"
        "    ret\n"
        "# isqrt64(a0) -> a0, the restoring bit-at-a-time integer root\n"
        "isqrt64:\n"
        "    mv   t0, a0\n"  # remainder
        "    li   a0, 0\n"  # root
        "    li   t1, 1\n"
        "    slli t1, t1, 62\n"  # highest even-positioned bit
        "1:\n"
        "    bltu t0, t1, 3f\n"
        "    j    2f\n"
        "3:\n"
        "    beqz t1, 4f\n"
        "    srli t1, t1, 2\n"
        "    j    1b\n"
        "2:\n"
        "    beqz t1, 5f\n"
        "    add  t2, a0, t1\n"
        "    bltu t0, t2, 6f\n"
        "    sub  t0, t0, t2\n"
        "    srli a0, a0, 1\n"
        "    add  a0, a0, t1\n"
        "    j    7f\n"
        "6:\n"
        "    srli a0, a0, 1\n"
        "7:\n"
        "    srli t1, t1, 2\n"
        "    j    2b\n"
        "4:\n"
        "5:\n"
        "    ret\n"
    )


def _evaluator() -> str:
    """Emit the runtime recursive-descent evaluator behind ``u``.

    A transcription of the interpreter's ``_Parser``: ``expr`` folds terms
    over ``+``/``-``, ``term`` folds factors over ``*``/``/``, and
    ``factor`` reads ``a``, a literal, or a parenthesized expression.
    ``s7`` is the cursor and ``s1`` supplies every ``a``.

    A parse failure jumps to ``.invalid``, which restores the saved
    accumulator: the spec's "if the function is valid, else do nothing".
    Division by zero is a runtime *operation* rather than a malformed
    function, so it halts instead.
    """
    return (
        "# apply() -- s1 = function(s1), or unchanged if it does not parse\n"
        "apply:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    sd   s7, 8(sp)\n"
        # `.unwind` abandons `factor`'s nested frames in one jump, so the
        # stack pointer to return through is recorded here rather than
        # threaded back through every call that failed.
        "    la   t0, cvnc_sp\n"
        "    sd   sp, 0(t0)\n"
        "    li   s7, 0\n"
        "    beqz s6, .invalid\n"
        "    call expr\n"
        "    bne  s7, s6, .invalid\n"  # trailing symbols: not a whole parse
        "    mv   s1, a0\n"
        "    ld   ra, 0(sp)\n"
        "    ld   s7, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        ".invalid:\n"
        "    ld   ra, 0(sp)\n"
        "    ld   s7, 8(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
        "# peek() -> a0 = tag at s7, or -1 past the end\n"
        "peek:\n"
        "    li   a0, -1\n"
        "    bgeu s7, s6, 1f\n"
        "    slli t0, s7, 4\n"
        "    add  t0, s5, t0\n"
        "    ld   a0, 0(t0)\n"
        "1:\n"
        "    ret\n"
        "# expr() -> a0; a sum of terms, left to right\n"
        "expr:\n"
        "    addi sp, sp, -32\n"
        "    sd   ra, 0(sp)\n"
        "    call term\n"
        "    sd   a0, 8(sp)\n"
        "1:\n"
        "    call peek\n"
        f"    li   t0, {_TAGS['+']}\n"
        "    beq  a0, t0, 2f\n"
        f"    li   t0, {_TAGS['-']}\n"
        "    bne  a0, t0, 4f\n"
        "2:\n"
        "    sd   a0, 16(sp)\n"
        "    addi s7, s7, 1\n"
        "    call term\n"
        "    ld   t1, 8(sp)\n"
        "    ld   t2, 16(sp)\n"
        f"    li   t0, {_TAGS['+']}\n"
        "    bne  t2, t0, 3f\n"
        "    add  t1, t1, a0\n"
        "    sd   t1, 8(sp)\n"
        "    j    1b\n"
        "3:\n"
        # unsigned: a subtraction that would go below zero floors at zero
        "    bltu t1, a0, 5f\n"
        "    sub  t1, t1, a0\n"
        "    sd   t1, 8(sp)\n"
        "    j    1b\n"
        "5:\n"
        "    sd   zero, 8(sp)\n"
        "    j    1b\n"
        "4:\n"
        "    ld   a0, 8(sp)\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 32\n"
        "    ret\n"
        "# term() -> a0; a product of factors, left to right\n"
        "term:\n"
        "    addi sp, sp, -32\n"
        "    sd   ra, 0(sp)\n"
        "    call factor\n"
        "    sd   a0, 8(sp)\n"
        "1:\n"
        "    call peek\n"
        f"    li   t0, {_TAGS['*']}\n"
        "    beq  a0, t0, 2f\n"
        f"    li   t0, {_TAGS['/']}\n"
        "    bne  a0, t0, 4f\n"
        "2:\n"
        "    sd   a0, 16(sp)\n"
        "    addi s7, s7, 1\n"
        "    call factor\n"
        "    ld   t2, 16(sp)\n"
        "    mv   a1, a0\n"
        "    ld   a0, 8(sp)\n"
        f"    li   t0, {_TAGS['*']}\n"
        "    bne  t2, t0, 3f\n"
        "    call mul64\n"
        "    sd   a0, 8(sp)\n"
        "    j    1b\n"
        "3:\n"
        # division by zero is an invalid *operation*, so it halts the run
        "    beqz a1, .halt\n"
        "    call divu64\n"
        "    sd   a0, 8(sp)\n"
        "    j    1b\n"
        "4:\n"
        "    ld   a0, 8(sp)\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 32\n"
        "    ret\n"
        "# factor() -> a0; `a`, a literal, or a parenthesized expression\n"
        "factor:\n"
        "    addi sp, sp, -16\n"
        "    sd   ra, 0(sp)\n"
        "    call peek\n"
        f"    li   t0, {_TAGS['a']}\n"
        "    bne  a0, t0, 1f\n"
        "    addi s7, s7, 1\n"
        "    mv   a0, s1\n"
        "    j    9f\n"
        "1:\n"
        f"    li   t0, {_LITERAL}\n"
        "    bne  a0, t0, 2f\n"
        "    slli t0, s7, 4\n"
        "    add  t0, s5, t0\n"
        "    ld   a0, 8(t0)\n"
        "    addi s7, s7, 1\n"
        "    j    9f\n"
        "2:\n"
        f"    li   t0, {_TAGS['(']}\n"
        "    bne  a0, t0, 8f\n"
        "    addi s7, s7, 1\n"
        "    call expr\n"
        "    sd   a0, 8(sp)\n"
        "    call peek\n"
        f"    li   t0, {_TAGS[')']}\n"
        "    bne  a0, t0, 8f\n"
        "    addi s7, s7, 1\n"
        "    ld   a0, 8(sp)\n"
        "    j    9f\n"
        # an operator, a `)`, or the end of the array where a factor was
        # required: the function is invalid, so unwind to `apply`
        "8:\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    j    .unwind\n"
        "9:\n"
        "    ld   ra, 0(sp)\n"
        "    addi sp, sp, 16\n"
        "    ret\n"
    )


def _io(body: str) -> str:
    r"""Emit the line-faithful readers and the decimal printer.

    ``readchar`` is ``IO.input_char``: it takes a whole line and returns its
    first byte, so an empty line reads as the ``\n`` that ended it and a
    longer line's remaining bytes are discarded.  ``readnum`` is
    ``IO.input_str`` plus the interpreter's ``_as_int``: the line is read to
    its end, leading and trailing whitespace stripped, an optional sign
    taken, and anything that is not then all digits reads as 0.  A negative
    value floors at 0, since the accumulator is unsigned.  EOF -- nothing
    read at all -- halts the run, matching the interpreter's ``EOFError``.

    ``printnum`` is ``IO.print_num``: the accumulator's decimal digits, with
    no terminator, built by repeated division into a small stack buffer.
    "

    Each routine is emitted only when ``body`` actually calls it, the same
    ``used``-flag gate the tape compilers apply to their subroutines.  The
    computed gotos cannot reach one: ``cvnc_labels`` holds per-*token*
    labels only, so a helper is reachable through its ``call`` sites alone.
    ``readline`` follows either reader, since both call it.
    """
    wants_char = "    call readchar\n" in body
    wants_num = "    call readnum\n" in body
    wants_print = "    call printnum\n" in body

    res = ""
    if wants_char or wants_num:
        res += (
            "# readline(buf: a0, cap: a1) -> a0 = length; reads to \\n or EOF.\n"
            "# Bytes past the buffer are consumed and dropped, so the reader\n"
            "# stays line-faithful however long the line is.\n"
            "readline:\n"
            "    addi sp, sp, -48\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s8, 8(sp)\n"
            "    sd   s9, 16(sp)\n"
            "    mv   s8, a0\n"
            "    mv   s9, a1\n"
            "    li   t5, 0\n"
            "1:\n"
            # The one-byte read lands in its own slot: the count lives at 24
            # and a byte written into that dword would corrupt it.
            "    sd   t5, 24(sp)\n"
            "    li   a7, 63\n"
            "    li   a0, 0\n"
            "    addi a1, sp, 32\n"
            "    li   a2, 1\n"
            "    ecall\n"
            "    ld   t5, 24(sp)\n"
            "    blez a0, 3f\n"
            "    lbu  t0, 32(sp)\n"
            "    li   t1, 10\n"
            "    beq  t0, t1, 4f\n"
            "    bgeu t5, s9, 1b\n"
            "    add  t2, s8, t5\n"
            "    sb   t0, 0(t2)\n"
            "    addi t5, t5, 1\n"
            "    j    1b\n"
            # EOF with nothing read at all is past the end of the input
            "3:\n"
            "    bnez t5, 4f\n"
            "    j    .halt\n"
            "4:\n"
            "    mv   a0, t5\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s8, 8(sp)\n"
            "    ld   s9, 16(sp)\n"
            "    addi sp, sp, 48\n"
            "    ret\n"
        )
    if wants_char:
        res += (
            "# readchar() -> a0; the line's first byte, or '\\n' for an empty\n"
            "# line -- IO.input_char, which is line-faithful\n"
            "readchar:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    la   a0, cvnc_line\n"
            "    li   a1, 64\n"
            "    call readline\n"
            "    li   t1, 10\n"
            "    beqz a0, 1f\n"
            "    la   t0, cvnc_line\n"
            "    lbu  t1, 0(t0)\n"
            "1:\n"
            "    mv   a0, t1\n"
            "    ld   ra, 0(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
        )
    if wants_num:
        res += (
            "# readnum() -> a0; the line as an unsigned integer, junk as 0\n"
            "readnum:\n"
            "    addi sp, sp, -16\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s8, 8(sp)\n"
            "    la   a0, cvnc_line\n"
            "    li   a1, 64\n"
            "    call readline\n"
            "    mv   s8, a0\n"
            "    la   t6, cvnc_line\n"
            "    li   t5, 0\n"
            # strip leading whitespace, as the interpreter's `.strip()` does
            "1:\n"
            "    bgeu t5, s8, 8f\n"
            "    add  t0, t6, t5\n"
            "    lbu  t0, 0(t0)\n"
            "    li   t1, 32\n"
            "    beq  t0, t1, 2f\n"
            "    li   t1, 9\n"
            "    bltu t0, t1, 3f\n"
            "    li   t1, 14\n"
            "    bltu t0, t1, 2f\n"
            "    j    3f\n"
            "2:\n"
            "    addi t5, t5, 1\n"
            "    j    1b\n"
            # strip trailing whitespace
            "3:\n"
            "    bgeu t5, s8, 8f\n"
            "    addi t0, s8, -1\n"
            "    add  t0, t6, t0\n"
            "    lbu  t0, 0(t0)\n"
            "    li   t1, 32\n"
            "    beq  t0, t1, 4f\n"
            "    li   t1, 9\n"
            "    bltu t0, t1, 5f\n"
            "    li   t1, 14\n"
            "    bltu t0, t1, 4f\n"
            "    j    5f\n"
            "4:\n"
            "    addi s8, s8, -1\n"
            "    j    3b\n"
            # an optional sign; a negative value floors at 0, so `-` marks the
            # whole line dead once its digits are confirmed
            "5:\n"
            "    li   t4, 0\n"
            "    add  t0, t6, t5\n"
            "    lbu  t0, 0(t0)\n"
            "    li   t1, 45\n"
            "    bne  t0, t1, 6f\n"
            "    li   t4, 1\n"
            "    addi t5, t5, 1\n"
            "    j    7f\n"
            "6:\n"
            "    li   t1, 43\n"
            "    bne  t0, t1, 7f\n"
            "    addi t5, t5, 1\n"
            "7:\n"
            # the remainder must be all digits and non-empty, or the line is 0
            "    bgeu t5, s8, 8f\n"
            "    li   t3, 0\n"
            "9:\n"
            "    bgeu t5, s8, 10f\n"
            "    add  t0, t6, t5\n"
            "    lbu  t0, 0(t0)\n"
            "    li   t1, 48\n"
            "    bltu t0, t1, 8f\n"
            "    li   t1, 58\n"
            "    bgeu t0, t1, 8f\n"
            "    slli t1, t3, 1\n"
            "    slli t2, t3, 3\n"
            "    add  t3, t1, t2\n"
            "    addi t0, t0, -48\n"
            "    add  t3, t3, t0\n"
            "    addi t5, t5, 1\n"
            "    j    9b\n"
            "10:\n"
            "    bnez t4, 8f\n"
            "    mv   a0, t3\n"
            "    j    11f\n"
            "8:\n"
            "    li   a0, 0\n"
            "11:\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s8, 8(sp)\n"
            "    addi sp, sp, 16\n"
            "    ret\n"
        )
    if wants_print:
        res += (
            "# printnum(a0) -- the value's decimal digits, no terminator\n"
            "printnum:\n"
            "    addi sp, sp, -48\n"
            "    sd   ra, 0(sp)\n"
            "    sd   s8, 8(sp)\n"
            "    sd   s9, 16(sp)\n"
            "    mv   s8, a0\n"
            "    li   s9, 0\n"
            "1:\n"
            "    mv   a0, s8\n"
            "    li   a1, 10\n"
            "    call divu64\n"
            "    sd   a0, 24(sp)\n"
            "    li   a1, 10\n"
            "    call mul64\n"
            "    sub  t0, s8, a0\n"
            "    addi t0, t0, 48\n"
            "    la   t1, cvnc_digits\n"
            "    add  t1, t1, s9\n"
            "    sb   t0, 0(t1)\n"
            "    addi s9, s9, 1\n"
            "    ld   s8, 24(sp)\n"
            "    bnez s8, 1b\n"
            "2:\n"
            "    addi s9, s9, -1\n"
            "    la   t1, cvnc_digits\n"
            "    add  t1, t1, s9\n"
            "    lbu  a0, 0(t1)\n"
            "    sd   s9, 32(sp)\n"
            "    call putbyte\n"
            "    ld   s9, 32(sp)\n"
            "    bnez s9, 2b\n"
            "    ld   ra, 0(sp)\n"
            "    ld   s8, 8(sp)\n"
            "    ld   s9, 16(sp)\n"
            "    addi sp, sp, 48\n"
            "    ret\n"
        )
    return res


def _tables(tokens: list[str], starts: list[int]) -> str:
    """Emit the three static tables the computed gotos index.

    ``cvnc_labels`` turns a token index into an address; ``cvnc_offsets``
    maps each *codepoint* offset to the token index it belongs to, since
    ``ɹ`` counts characters and ``ɰ̊`` spans two of them; ``cvnc_starts``
    maps each syllable index to the token it begins at, for ``j``.
    """
    offsets: list[int] = []
    for index, token in enumerate(tokens):
        offsets.extend([index] * len(token))

    res = "    .data\n    .align 3\n"
    res += f"cvnc_ntokens:\n    .dword {len(tokens)}\n"
    res += f"cvnc_noffsets:\n    .dword {len(offsets)}\n"
    res += f"cvnc_nstarts:\n    .dword {len(starts)}\n"
    res += "cvnc_labels:\n"
    res += "".join(f"    .dword {_label(i)}\n" for i in range(len(tokens)))
    res += "cvnc_offsets:\n"
    res += "".join(f"    .dword {i}\n" for i in offsets)
    res += "cvnc_starts:\n"
    res += "".join(f"    .dword {i}\n" for i in starts)
    res += "    .align 3\n"
    res += f"cvnc_deque:\n    .zero {_DEQUE * 8}\n"
    res += f"cvnc_function:\n    .zero {_FN * 16}\n"
    res += "cvnc_line:\n    .zero 64\n"
    res += "cvnc_digits:\n    .zero 32\n"
    # The stack pointer `apply` entered on, so an invalid function can
    # unwind `factor`'s nested frames without threading a failure code
    # back through each of them.  One slot suffices: a function holds only
    # arithmetic, so `apply` is never re-entered from inside itself.
    res += "cvnc_sp:\n    .zero 8\n"
    return res


def comp(code: str) -> str:
    """Compile a CV(N)(C) program to RISC-V assembly with syscall I/O."""
    tokens = _tokenize(code)
    if not tokens:
        raise ValueError("program is empty")
    starts = _syllabify(tokens)
    pairs = _match_loops(tokens)

    body = "".join(
        _emit_token(token, index, pairs) for index, token in enumerate(tokens)
    )

    io_routines = _io(body)

    # `.option norelax` for the reason Forbin and Container need it: the
    # assembler otherwise relaxes `la` to a gp-relative `addi`, and nothing
    # initializes `gp` under `-nostdlib`, so every table read would land
    # outside mapped memory.
    return (
        "    .text\n"
        "    .option norelax\n"
        "    .global _start\n"
        "_start:\n"
        "    li   s1, 0\n"
        "    la   s2, cvnc_deque\n"
        "    li   s3, 0\n"
        "    li   s4, 0\n"
        "    la   s5, cvnc_function\n"
        "    li   s6, 0\n"
        "    li   s7, 0\n"
        + body
        # Running off the end of the program halts, and so does every
        # runtime error: the interpreter's HaltError unwinds the whole run.
        + ".halt:\n"
        "    li   a0, 0\n"
        "    li   a7, 93\n"
        "    ecall\n"
        # An invalid function unwinds `factor`'s nested calls in one jump,
        # which is why `apply` saves the stack pointer to return through.
        ".unwind:\n"
        "    la   t0, cvnc_sp\n"
        "    ld   sp, 0(t0)\n"
        "    j    .invalid\n"
        + _dispatch()
        + _deque()
        + _fn_append()
        + _arithmetic()
        + _evaluator()
        + io_routines
        + (PUTBYTE if "call putbyte\n" in body + io_routines else "")
        + _tables(tokens, starts)
    )


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
