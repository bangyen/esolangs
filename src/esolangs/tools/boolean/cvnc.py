"""Boolean-function generator for CV(N)(C).

CV(N)(C) reads one input at a time into a single accumulator, so a truth
table is evaluated as a **decision tree**: read a bit, branch on it, and
recurse into the half of the table that bit selects.  Each of the ``2**n``
leaves knows its row outright and simply prints the answer.

The construction turns on three facts about the language, each of them
forced rather than chosen:

**The read is ``so``.**  Every command needs a partner of the other class to
make a syllable, and ``o`` -- integer square root -- is identity on 0 and 1,
which is exactly the range an input bit spans.  The wiki's own truth machine
uses ``o`` this way, so the pairing is the page's idiom and not an invention.

**The branch is ``ɰ̊o`` ... ``ʋo``.**  ``ɰ̊`` jumps past the matching ``ʋ``
when the accumulator is zero, so the code between them is the *bit is one*
arm and the code after them is the *bit is zero* arm.  The ``o`` partnering
each is again identity on the bit.

**Every leaf ends by halting**, which is what makes the tree a tree.  Were a
leaf to fall off its own arm it would run straight into the ``ʋ`` and loop
back to the test it already passed -- the failure the first draft of this
generator hit.  The halt is a *computed goto past the end of the program*::

    ci ci cæ cæ cæ cæ ɹi

two increments to reach 2, four squarings to reach ``2**16``, then ``ɹ``,
which jumps to that character offset; any offset past the end halts, and
65536 characters is far beyond any program this generator emits.  ``ɹ``'s
own syllable needs a vowel, and the jump makes that vowel dead code.

Because the then-arm always halts, the ``ʋ`` is never executed at all: it
exists only so the ``ɰ̊`` has something to match against, which the language
requires structurally.

**The leaf prints a digit, not a bit.**  ``f`` prints the accumulator modulo
256 as a character, so the answer is the ASCII digit: 48 or 49.  The
accumulator arriving at a leaf holds the last bit that leaf read -- which the
tree knows statically -- so the climb is ``48 + answer - bit`` increments and
no reset is needed.  The root of a zero-input table has read nothing and
starts from 0.

**A subtree whose entries all agree folds to one leaf, but keeps its
reads.**  Those are two separate things, and conflating them is the trap:
the answer no longer depends on the remaining inputs, so the *branches* are
dead weight, but every path must still consume its ``n`` input lines or the
caller's bits are left on the stream for whatever runs next.  A folded
subtree therefore emits its remaining ``so`` reads in a row and then a
single leaf, which is what makes an ``n``-input table that depends on one
input cost two leaves instead of ``2**n``.

Folding is cheap here because of what a decrement does.  The accumulator
after the last read holds a bit the folded leaf cannot predict, and ``cə``
-- decrement, flooring at zero -- sends both 0 and 1 to 0, so two
characters normalize it and the leaf climbs from a known zero.  Without
that the leaf would need a branch just to learn what it was holding, which
is the cost that would have made folding not worth doing.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["cvnc"]

# Read one input bit.  ``o`` is integer square root, identity on 0 and 1, so
# it is the no-op vowel that completes ``s``'s syllable.
_READ = "so"

# Open the "bit is one" arm and close it.  ``ɰ̊`` jumps past its ``ʋ`` when
# the accumulator is zero, so falling through means the bit was one.
_IF_ONE = "ɰ̊o"
_END_IF = "ʋo"

# Increment, the only way to raise the accumulator one step inside a syllable.
_INCREMENT = "ci"

# Force a just-read bit to a known zero.  ``ə`` decrements but floors at zero,
# so it sends both 0 and 1 to 0 -- which is what lets a folded leaf climb from
# a fixed starting point without branching to discover what it holds.
_NORMALIZE = "cə"

# Print the accumulator as a character.  ``u`` applies the function, which is
# empty here -- every syllable in a leaf has a ``c`` onset -- so it does not
# parse and does nothing.
_PRINT = "fu"

# Jump past the end of the program, which halts.  Two increments reach 2 and
# four squarings take that to 2**16; ``ɹ`` then jumps to that character
# offset.  The ``i`` after ``ɹ`` is the vowel its syllable needs and is
# unreachable, since the jump has already left.
_HALT = _INCREMENT * 2 + "cæ" * 4 + "ɹi"

# The offset _HALT reaches, and so the longest program it can escape from.
# Asserted against the emitted program rather than assumed.
_HALT_REACH = 2 ** (2**4)


def _leaf(answer: str, accumulator: int) -> str:
    """Print ``answer`` as a digit and halt, climbing from ``accumulator``.

    The accumulator holds the last bit the tree read on the way here, so the
    climb starts from that rather than from zero.  It is always a climb: the
    target is 48 or 49 and the bit is 0 or 1.
    """
    target = _ASCII_ZERO + int(answer)
    return _INCREMENT * (target - accumulator) + _PRINT + _HALT


def _tree(table: str, accumulator: int) -> str:
    """Build the program for ``table``, given what the last read left behind.

    ``accumulator`` is the bit the branch above just tested, which the leaf
    needs in order to know how far it must climb.  A table whose entries all
    agree stops branching here, but still owes every read below it.
    """
    if table.count(table[0]) == len(table):
        # Folded.  The reads are the interface and are all still owed; only
        # the branching is dead.  The last of them leaves an unpredictable
        # bit, so ``cə`` floors it to a known zero for the leaf to climb
        # from -- and when nothing is left to read, the accumulator is
        # already the bit the caller's branch handed down.
        reads = _bit_count(len(table))
        if not reads:
            return _leaf(table[0], accumulator)
        return _READ * reads + _NORMALIZE + _leaf(table[0], 0)
    half = len(table) // 2
    # The table is indexed most-significant-first, so its *first* half is the
    # rows where this input is 0 and its second half the rows where it is 1.
    # ``ɰ̊`` jumps away on zero, so the arm between the markers is the one
    # that runs when the bit is 1 -- the second half -- and the arm after
    # them is the first.  Getting this the other way round is the bug that
    # inverts every table with an odd number of 1s in it.
    return _READ + _IF_ONE + _tree(table[half:], 1) + _END_IF + _tree(table[:half], 0)


def _bit_count(size: int) -> int:
    """Return how many inputs a subtable of ``size`` rows still selects on."""
    return size.bit_length() - 1


def cvnc(truth_table: str) -> str:
    """Build a CV(N)(C) program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program reads ``n`` integers, one per line, and prints ``0`` or ``1``.

    The result is the table's decision tree (see the module docstring): one
    ``so`` read and one ``ɰ̊o``/``ʋo`` branch per level, with every leaf
    ending in the halting goto that keeps the arms from running into each
    other.
    """
    n = _validate_truth_table(truth_table)
    if n == 0:
        # No inputs to read and nothing to branch on: the answer is the
        # whole program, printed from a fresh accumulator.
        return _leaf(truth_table, 0)
    program = _tree(truth_table, 0)
    if len(program) >= _HALT_REACH:  # pragma: no cover - needs a 2**16 table
        raise ValueError("program outgrew the halting goto's reach")
    return program
