"""Boolean-function generator for CV(N)(C).

One accumulator, one input at a time, so a table is a decision tree.  The
read is ``s``; the branch is ``ɰ`` ... ``ʋ``, since ``ɰ`` jumps past ``ʋ``
on nonzero -- one codepoint, where the voiceless ``ɰ̊`` the prologue still
needs is two.  A leaf prints its answer with ``θ`` -- the *number* print, whose
output is the digit itself, so nothing has to climb to ASCII -- leaves the
accumulator at 1, and jumps with ``j`` to syllable 1, where a single shared
gadget squares its way past the end of the program and halts.  A constant
subtree folds to one leaf but keeps its reads, the last of which is floored
by ``ə``.

Commands are emitted through :func:`_render`, which is the whole size
story: CV(N)(C) admits a nasal and a coda after a syllable's vowel, so a
consonant command does not need a vowel of its own when the next command
can host it.  Spelling every command as its own ``CV`` pair -- which is
what this generator used to do -- pays a filler vowel per consonant.
:func:`_render` chooses, per syllable, between taking the next consonant as
a coda and letting it open the next syllable, and takes the cheaper.  The
two fillers it inserts, ``c`` and ``u``, are inert *because* no command
here ever builds a function: ``c`` clears an already-empty one and ``u``
applies it, which the interpreter defines as leaving the accumulator alone.

A second construction hoists the reads into the deque (``m``/``n`` push,
``ŋ``/``ɲ`` pop either end) so :func:`_ordered` can test in any order; each
read is pushed to the end it will be popped from (:func:`_deque_schedule`),
which serves exactly the unimodal permutations.  A stored read costs one
more character and a fetch three vs one, but a folded subtree then owes
nothing; the shorter of the two is kept.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

__all__ = ["cvnc"]

# The command classes the syllable shape distinguishes.  Everything that is
# not a vowel or a nasal is a consonant, which is all :func:`_render` needs.
_VOWELS = frozenset("iəæou")
_NASALS = frozenset("mnŋɲ")

# The two inert commands used as padding.  ``c`` clears the function, which
# is empty throughout; ``u`` applies it, and an empty function does not
# parse, which the interpreter turns into "leave the accumulator alone".
_FILLER_ONSET = "c"
_FILLER_VOWEL = "u"

_READ = "s"
_PRINT = "θ"
_INCREMENT = "i"
# Decrement, floored at 0: sends 0 and 1 both to 0.
_NORMALIZE = "ə"
_SQUARE = "æ"
_GOTO = "ɹ"
_GOTO_SYLLABLE = "j"
_IF_ZERO = "ɰ"
# The prologue's own skip still has to fire on the *zero* accumulator a run
# starts with, so it is the voiceless ring; every branch below is the plain
# one, which is a codepoint shorter.
_SKIP = "ɰ̊"
_END_IF = "ʋ"
_PUSH_FRONT = "m"
_PUSH_BACK = "n"
_POP_FRONT = "ŋ"
_POP_BACK = "ɲ"

# Every leaf leaves the accumulator here before its ``j``, which is both
# the syllable the shared gadget starts at and the answer ``1``: the bit
# that is already the landing value costs nothing to leave behind.
_LANDING = 1

# What the gadget climbs to before it starts squaring.  Two is the cheapest
# base that grows at all, and each squaring past it costs two characters
# once, not once per leaf.
_HALT_BASE = 2

_HALT_SQUARINGS = 4


def _halt(squarings: int) -> str:
    """Return the prologue: skip the gadget, then the gadget itself.

    Syllable 0 is ``ɰ̊u``, which on the initial zero accumulator jumps past
    the ``ʋ`` that closes the prologue and so never runs the gadget.
    Syllable 1 opens the gadget, which is where every leaf's ``j`` lands: it
    climbs to :data:`_HALT_BASE`, squares, and ``ɹ`` jumps to an offset past
    the end of the program, which halts.  The ``ʋ`` is the coda of the
    gadget's last syllable, which is sound because a body always opens with
    a consonant.
    """
    climb = _FILLER_ONSET + _INCREMENT
    return (
        _SKIP
        + _FILLER_VOWEL
        + climb * (_HALT_BASE - _LANDING)
        + (_FILLER_ONSET + _SQUARE) * squarings
        + _GOTO
        + _FILLER_VOWEL
        + _END_IF
    )


def _reach(squarings: int) -> int:
    """Return the offset the gadget lands on: the longest program it escapes."""
    return int(_HALT_BASE ** (2**squarings))


def _is_vowel(token: str) -> bool:
    """Whether ``token`` can fill a syllable's vowel slot."""
    return token in _VOWELS


def _is_nasal(token: str) -> bool:
    """Whether ``token`` can fill a syllable's nasal slot."""
    return token in _NASALS


def _syllable_options(tokens: list[str], index: int) -> list[tuple[str, int]]:
    """Return the ways to spell one syllable starting at ``tokens[index]``.

    Each option is the characters to emit and the token index left over.
    The onset and the vowel are forced -- a syllable needs a consonant then
    a vowel, and a filler stands in when the next command is the wrong
    class -- and so is the nasal, which the parser always takes when one is
    there.  The *coda* is the choice: a following consonant either closes
    this syllable or opens the next one, and either reading is stable,
    since what follows a coda is always an onset (a consonant) and what
    follows a declined coda is always its own vowel.
    """
    total = len(tokens)
    chars: list[str] = []
    cursor = index
    token = tokens[cursor]
    if _is_vowel(token) or _is_nasal(token):
        chars.append(_FILLER_ONSET)
    else:
        chars.append(token)
        cursor += 1
    if cursor < total and _is_vowel(tokens[cursor]):
        chars.append(tokens[cursor])
        cursor += 1
    else:
        chars.append(_FILLER_VOWEL)
    if cursor < total and _is_nasal(tokens[cursor]):
        chars.append(tokens[cursor])
        cursor += 1
    options = [("".join(chars), cursor)]
    if (
        cursor < total
        and not _is_vowel(tokens[cursor])
        and not _is_nasal(tokens[cursor])
    ):
        options.append(("".join(chars) + tokens[cursor], cursor + 1))
    return options


def _render(tokens: list[str]) -> str:
    """Spell a command sequence as the shortest syllabifiable source.

    A backward pass prices the tail from every syllable boundary, so the
    forward pass can take the coda only where it pays; the commands
    themselves are emitted in order and untouched.
    """
    total = len(tokens)
    tail = [0] * (total + 1)
    for index in range(total - 1, -1, -1):
        tail[index] = min(
            len(chars) + tail[rest] for chars, rest in _syllable_options(tokens, index)
        )
    pieces: list[str] = []
    index = 0
    while index < total:
        chars, rest = min(
            _syllable_options(tokens, index),
            key=lambda option: len(option[0]) + tail[option[1]],
        )
        pieces.append(chars)
        index = rest
    return "".join(pieces)


def _leaf(answer: str, accumulator: int | None) -> list[str]:
    """Print ``answer`` and jump to the shared halt gadget.

    ``θ`` prints the accumulator as a number, so the accumulator *is* the
    digit; ``accumulator`` is what the path already left there, and ``None``
    means an unfolded read whose value has to be floored first.  The
    landing value the ``j`` needs is 1, which is also the answer 1, so the
    one bit costs nothing to leave behind.
    """
    tokens: list[str] = []
    if accumulator is None:
        tokens.append(_NORMALIZE)
        accumulator = 0
    target = int(answer)
    if target != accumulator:
        tokens.append(_INCREMENT if target > accumulator else _NORMALIZE)
    tokens.append(_PRINT)
    tokens.extend([_INCREMENT] * (_LANDING - target))
    tokens.append(_GOTO_SYLLABLE)
    return tokens


def _bit_count(size: int) -> int:
    """Return how many inputs a subtable of ``size`` rows still selects on."""
    return size.bit_length() - 1


def _tree(table: str) -> list[str]:
    """Build the command sequence for ``table``, reading at every node.

    A constant table stops branching but still owes every read below it.
    Spans of the one table, an O(1) constant test and one flat token list:
    O(2**n).
    """
    constant = constant_span_test(table)
    tokens: list[str] = []

    def walk(lo: int, hi: int, accumulator: int | None) -> None:
        if constant(lo, hi):
            reads = _bit_count(hi - lo)
            tokens.extend([_READ] * reads)
            tokens.extend(_leaf(table[lo], None if reads else accumulator))
            return
        mid = (lo + hi) // 2
        # ``ɰ`` jumps past ``ʋ`` on *nonzero*, so the arm between the
        # markers is the first (bit 0) half; swapped, every odd-weight
        # table inverts.
        tokens.extend([_READ, _IF_ZERO])
        walk(lo, mid, 0)
        tokens.append(_END_IF)
        walk(mid, hi, 1)

    walk(0, len(table), None)
    return tokens


def _deque_schedule(
    perm: tuple[int, ...],
) -> tuple[list[str], list[str]] | None:
    """Return the push and pop ends that serve ``perm``, or None if none do.

    The ``2**n`` push assignments are searched; the pops are forced.
    Servable orders are the unimodal ones: all through ``n == 3``, 20 of 24
    at ``n == 4``, 252 of 720 at ``n == 6``.
    """
    n = len(perm)
    for assignment in range(1 << n):
        front = [i for i in range(n) if assignment >> i & 1]
        back = [i for i in range(n) if not assignment >> i & 1]
        # Front pushes reverse, back pushes keep order.
        held = list(reversed(front)) + back
        pops = []
        for wanted in perm:
            if held and held[0] == wanted:
                pops.append(_POP_FRONT)
                held.pop(0)
            elif held and held[-1] == wanted:
                pops.append(_POP_BACK)
                held.pop()
            else:
                break
        else:
            pushes = [
                _PUSH_FRONT if assignment >> i & 1 else _PUSH_BACK for i in range(n)
            ]
            return pushes, pops
    return None


def _stored(truth_table: str, perm: tuple[int, ...]) -> list[str] | None:
    """Build the stored-read command sequence for ``perm``.

    Every input is read up front and each node fetches the bit it tests; a
    folded subtree owes nothing, which is where the reorder pays.
    """
    schedule = _deque_schedule(perm)
    if schedule is None:
        return None
    pushes, pops = schedule
    tokens: list[str] = []
    for push in pushes:
        tokens.extend([_READ, push])
    constant = constant_span_test(truth_table)

    def walk(lo: int, hi: int, level: int, accumulator: int | None) -> None:
        if constant(lo, hi):
            # Below a branch the accumulator is a known bit; at an
            # immediately-folding root it is the last read, so it is floored.
            tokens.extend(_leaf(truth_table[lo], accumulator))
            return
        mid = (lo + hi) // 2
        tokens.extend([pops[level], _IF_ZERO])
        walk(lo, mid, level + 1, 0)
        tokens.append(_END_IF)
        walk(mid, hi, level + 1, 1)

    walk(0, len(truth_table), 0, None)
    return tokens


def _ordered(truth_table: str, perm: tuple[int, ...]) -> str | None:
    """Build the shortest read strategy available for ``perm``.

    Stream order may read at its nodes or store first; other orders store.
    Ties keep the direct tree.
    """
    stored = _stored(truth_table, perm)
    rendered = _render(stored) if stored is not None else None
    if perm != tuple(range(len(perm))):
        return rendered
    direct = _render(_tree(truth_table))
    return rendered if rendered is not None and len(rendered) < len(direct) else direct


def _ordered_candidate(truth_table: str, perm: tuple[int, ...]) -> str:
    """Adapt :func:`_ordered` to :func:`best_input_order`'s contract."""
    return _ordered(truth_table, perm) or ""


def cvnc(truth_table: str) -> str:
    """Build a CV(N)(C) program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program reads ``n`` lines and prints ``0`` or ``1``.  One read and one
    ``ɰ``/``ʋ`` branch per level, every leaf printing with ``θ`` and jumping
    to the one shared halt gadget.  Every input order is measured and the
    shortest wins.  A program not shorter than the gadget's reach gets one
    more squaring, repeated until it fits; the contest is run once, since
    the gadget is a fixed-size prologue rather than part of any leaf.
    """
    # For the refusal only; the arity is not needed below.
    _validate_truth_table(truth_table)
    body = best_input_order(truth_table, _ordered_candidate)
    squarings = _HALT_SQUARINGS
    while len(_halt(squarings)) + len(body) >= _reach(squarings):
        squarings += 1
    return _halt(squarings) + body
