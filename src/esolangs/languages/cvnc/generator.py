"""CV(N)(C) Boolean program generator: a decision tree on one accumulator.

One read ``s`` and one ``ɰ`` ... ``ʋ`` branch per input (``ɰ`` jumps past ``ʋ``
on nonzero; one codepoint where the prologue's voiceless ``ɰ̊`` is two).  A leaf
prints with ``θ`` (the number print, so the output is the digit), leaves the
accumulator at 1 and ``j``-jumps to syllable 1, where one shared gadget squares
past the end of the program and halts.  A constant subtree folds to one leaf but
keeps its reads, the last floored by ``ə``.  :func:`_render` spells commands as
the fewest syllables: a consonant takes the next syllable's coda or opens it.
Fillers ``c`` and ``u`` are inert (empty function cleared or applied).  ``j``
also shares a repeated subtree (:class:`_Stream`): a later copy climbs to the
first copy's syllable with ``i``, ``æ``, ``ə`` and jumps, where shorter.

Size:
    O(T) for dense tables, near-linear in n for parity; n=10 parity: 317
    chars, n=10 random 1847: 5,215 chars, n=12 random 1847: 22,086 chars.

Decisions:
    Hoisting the reads into the deque to test in any order saves 4.87% at n=8,
    under the 10% bar, and is not built.
"""

import math
from collections import Counter
from functools import partial

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    input_weights,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._language import Language

__all__ = ["cvnc"]

# The command classes the syllable shape distinguishes.  Everything that is
# not a vowel or a nasal is a consonant, which is all :func:`_render` needs.
_VOWELS = frozenset("iəæou")
_NASALS = frozenset("mnŋɲ")


def _is_consonant(token: str) -> bool:
    """Return whether ``token`` is neither a vowel nor a nasal."""
    return token not in _VOWELS and token not in _NASALS


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
    the closing ``ʋ``, so the gadget never runs in-line.  Syllable 1 opens
    the gadget, where every leaf's ``j`` lands: it climbs to
    :data:`_HALT_BASE`, squares, and ``ɹ`` jumps past the end of the program,
    which halts.  The ``ʋ`` is the coda of the gadget's last syllable, sound
    because a body always opens with a consonant.
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


def _syllable_options(tokens: list[str], index: int) -> list[tuple[str, int]]:
    """Return the ways to spell one syllable starting at ``tokens[index]``.

    Each option is the characters to emit and the token index left over.
    The onset, vowel (a filler stands in when the next command is the wrong
    class) and nasal (the parser always takes one) are forced.  The *coda*
    is the choice: a following consonant either closes this syllable or
    opens the next, and either reading is stable, since an onset follows a
    coda and a vowel follows a declined coda.
    """
    total = len(tokens)
    chars: list[str] = []
    cursor = index
    token = tokens[cursor]
    if _is_consonant(token):
        chars.append(token)
        cursor += 1
    else:
        chars.append(_FILLER_ONSET)
    if cursor < total and tokens[cursor] in _VOWELS:
        chars.append(tokens[cursor])
        cursor += 1
    else:
        chars.append(_FILLER_VOWEL)
    if cursor < total and tokens[cursor] in _NASALS:
        chars.append(tokens[cursor])
        cursor += 1
    options = [("".join(chars), cursor)]
    if cursor < total and _is_consonant(tokens[cursor]):
        options.append(("".join(chars) + tokens[cursor], cursor + 1))
    return options


def _syllables(tokens: list[str]) -> list[str]:
    """Spell a command sequence as the shortest syllabifiable source.

    A backward pass prices the tail from every syllable boundary, so the
    forward pass can take the coda only where it pays; the commands
    themselves are emitted in order and untouched.  One string a syllable,
    so a caller can count them.
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
    return pieces


def _render(tokens: list[str]) -> str:
    """Spell a command sequence as the shortest syllabifiable source."""
    return "".join(_syllables(tokens))


def _climb(start: int, target: int) -> list[tuple[str, int]]:
    """Return runs of commands taking the accumulator from ``start`` to ``target``.

    ``start`` is 0 or 1, the bit a branch arm opens on.  Past three, the
    target is the nearer square of ``isqrt`` or one more, reached by
    climbing to its root, squaring and stepping the rest: a closed form,
    not a search.  Runs, since a step count can be ``O(sqrt(target))`` and
    is only spelled out when the jump is taken; there are ``O(log log
    target)`` of them.
    """
    root = math.isqrt(target)
    if root <= 1:
        return [(_INCREMENT, target - start)]
    below, above = target - root * root, (root + 1) ** 2 - target
    if below <= above:
        return [*_climb(start, root), (_SQUARE, 1), (_INCREMENT, below)]
    return [*_climb(start, root + 1), (_SQUARE, 1), (_NORMALIZE, above)]


class _Stream:
    """Commands in written order, cut where a repeated subtree is entered.

    Without ``offset`` it only collects commands.  With it (the syllable the
    body starts on, after the prologue) the first copy of a subtable that
    recurs at its depth opens a new segment, rendered at once so its syllable
    is known; a later copy climbs to that syllable and ``j``-jumps into it
    where that is shorter.  Copies run the same commands from the same deque
    whichever arm entered them, and each opens with a read or a pop, so the
    accumulator it is entered with is never used.
    """

    def __init__(self, table: str, offset: int | None = None) -> None:
        """Start an empty stream for ``table``, sharing if given ``offset``."""
        self.tokens: list[str] = []
        self._text: list[str] = []
        self._syllable = offset or 0
        self._chars = 0
        self._ids = subtree_ids(table) if offset is not None else []
        # A subtable that appears once at its depth has nothing to share.
        self._recurs = Counter(
            (level, node) for level, ids in enumerate(self._ids) for node in ids
        )
        self._copies: dict[tuple[int, int], tuple[int, int]] = {}

    def _flush(self) -> None:
        pieces = _syllables(self.tokens)
        self._text.append("".join(pieces))
        self._chars += len(self._text[-1])
        self._syllable += len(pieces)
        self.tokens = []

    def jump(self, level: int, block: int, accumulator: int) -> bool:
        """Jump into an earlier copy of this subtree if that is shorter.

        The copy is its own run of whole syllables, so what it spent is
        known to the character, and so is the jump that would replace it.
        """
        if not self._ids:
            return False
        copy = self._copies.get((level, self._ids[level][block]))
        if copy is None:
            return False
        climb = _climb(accumulator, copy[0])
        # Each step is a vowel, so an onset and a syllable of its own; the
        # ``j`` closes the last of them as its coda.
        if 2 * sum(count for _step, count in climb) + 1 >= copy[1]:
            return False
        for step, count in climb:
            self.tokens.extend([step] * count)
        self.tokens.append(_GOTO_SYLLABLE)
        return True

    def enter(self, level: int, block: int) -> tuple[int, int, int, int] | None:
        """Open a segment if this is the first copy of a recurring subtree.

        Returns what :meth:`leave` needs: the copy's key, its syllable and
        the characters spelled before it.
        """
        if not self._ids:
            return None
        node = self._ids[level][block]
        if self._recurs[level, node] < 2 or (level, node) in self._copies:
            return None
        self._flush()
        return level, node, self._syllable, self._chars

    def leave(self, entered: tuple[int, int, int, int] | None) -> None:
        """Close the copy :meth:`enter` opened and record what it spent."""
        if entered is not None:
            level, node, syllable, start = entered
            self._flush()
            spent = self._chars - start
            self._copies[level, node] = (syllable, spent)

    def text(self) -> str:
        """Return the whole body, spelled."""
        self._flush()
        return "".join(self._text)


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


def _consumed(weights: list[int]) -> list[int]:
    """Return the stream reads made before each indexed level, then in all."""
    return (
        [0] + [at + 1 for at, weight in enumerate(weights) if weight] + [len(weights)]
    )


def _tree(
    table: str, stream: _Stream | None = None, weights: list[int] | None = None
) -> list[str]:
    """Build the command sequence for ``table``, reading at every node.

    A constant table stops branching but still owes every read below it.
    Spans of the one table, an O(1) constant test and one flat token list:
    O(2**n).  Returns the commands not yet spelled: all of them unless
    ``stream`` shares, whose :meth:`_Stream.text` is then the body.
    ``weights`` names the stream inputs, zero for an ignored one: ``table``
    indexes the rest, and a node first reads the ignored inputs ahead of its
    own, which its read then overwrites.
    """
    constant = constant_span_test(table)
    stream = stream or _Stream(table)
    before = _consumed(weights or [1] * (len(table).bit_length() - 1))

    def walk(lo: int, hi: int, level: int, accumulator: int | None) -> None:
        if constant(lo, hi):
            reads = before[-1] - before[level]
            stream.tokens.extend([_READ] * reads)
            stream.tokens.extend(_leaf(table[lo], None if reads else accumulator))
            return
        block = lo // (hi - lo)
        if accumulator is not None and stream.jump(level, block, accumulator):
            return
        entered = stream.enter(level, block)
        mid = (lo + hi) // 2
        # ``ɰ`` jumps past ``ʋ`` on *nonzero*, so the arm between the
        # markers is the first (bit 0) half; swapped, every odd-weight
        # table inverts.
        stream.tokens.extend([_READ] * (before[level + 1] - before[level]))
        stream.tokens.append(_IF_ZERO)
        walk(lo, mid, level + 1, 0)
        stream.tokens.append(_END_IF)
        walk(mid, hi, level + 1, 1)
        stream.leave(entered)

    walk(0, len(table), 0, None)
    return stream.tokens


def _direct(
    truth_table: str,
    _perm: tuple[int, ...],
    offset: int | None = None,
    weights: list[int] | None = None,
) -> str:
    """Spell the direct tree; ``offset``, the first syllable, turns sharing on."""
    stream = _Stream(truth_table, offset)
    _tree(truth_table, stream, weights)
    return stream.text()


def _prologue_syllables(squarings: int) -> int:
    """Return how many syllables :func:`_halt` spells, where the body starts.

    ``ɰ̊u``, the climb's ``ci``, one ``cæ`` a squaring and ``ɹuʋ``.
    """
    return 3 + squarings


def cvnc(truth_table: str) -> str:
    """Build a CV(N)(C) program; it reads ``n`` lines, splits in input order."""
    # A tree over the inputs that matter, its ignored reads bare, against the
    # full tree, whose sharing is sometimes the shorter; a tie keeps the full.
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    shapes = [(truth_table, [1] * n)]
    if 1 < len(table) < len(truth_table):
        shapes.append((table, weights))
    # The gadget must reach past the program.  Sharing only shortens a body
    # (a jump is taken only where shorter), so the unshared body bounds it
    # whatever the prologue, and the squarings follow from that length at
    # once; the 64 covers the gadget itself (8 + 2 per squaring).
    unshared = min(
        len(in_input_order(shape, partial(_direct, offset=None, weights=named)))
        for shape, named in shapes
    )
    # 2**(2**s) > m exactly when 2**s >= m.bit_length().
    bits = (unshared + 64).bit_length()
    squarings = max(_HALT_SQUARINGS, (bits - 1).bit_length())
    offset = _prologue_syllables(squarings)
    body = min(
        (
            in_input_order(shape, partial(_direct, offset=offset, weights=named))
            for shape, named in shapes
        ),
        key=len,
    )
    program = _halt(squarings) + body
    if len(program) >= _reach(squarings):  # pragma: no cover - sharing never grows
        raise AssertionError("shared body outgrew the unshared bound")
    return program


LANGUAGE = Language(
    "CV(N)(C)",
    "cvnc",
    category="other",
    # The parentheses mark optional slots; the language is written as one word.
    id="cvnc",
    boolean=cvnc,
    # LF-only source-format deviation: discard breaks before parsing or addressing.
    wrap=wrap_chars,
    empty_program="program is empty",
)
