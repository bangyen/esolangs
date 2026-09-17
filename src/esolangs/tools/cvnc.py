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

    ci ci cæ cæ ɹi

The gadget runs *after* the leaf has printed, so the accumulator entering it
is not zero: it still holds the ASCII digit, 48 or 49.  Two increments take
that to 50, two squarings to 6,250,000, and ``ɹ`` jumps to that character
offset; any offset past the end halts.  ``ɹ``'s own syllable needs a vowel,
and the jump makes that vowel dead code.

The squaring count is what *bounds the program the gadget can escape*, so
it is chosen against the emitted program rather than fixed.  One squaring
reaches 2500 and suffices through ``n == 4`` (1801 characters); ``n == 5``
is 3673 characters and needs the second, which costs two characters per
leaf and reaches 6,250,000, past ``n == 15``.  Zero squarings genuinely
fails -- the gadget reaches only 50 and lands back inside the program --
which is what makes this a measured floor and not a guess.  Two is the
floor every program starts from, and :func:`cvnc` adds a squaring whenever
the program is not shorter than the reach: each one squares the reach and
lengthens the program by two characters per leaf, so the loop stops for
every finite table, and the program never outgrows its own halt.

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

**A second construction hoists the reads, which frees the split order.**
Reading at the node forces the tree to test its inputs in the order the
stream delivers them, and that order decides how much folds: ``11110000``
folds after one split where the same function written ``10101010`` folds
only at the bottom.  The deque is what unsticks it -- ``m``/``n`` push the
accumulator to either end and ``ŋ``/``ɲ`` pop either end back into it, so
a bit read early can be retrieved late. :func:`_ordered` reads every input
up front into the deque and has each node *fetch* the bit it tests, which
lets :func:`~esolangs.tools.helpers.best_input_order` try every
order and keep the shortest.

The bridge between the two orders costs nothing: rather than rotating the
deque, each read is pushed to whichever *end* it will be popped from, and
:func:`_deque_schedule` searches the ``2**n`` such assignments.  What that
buys is exactly the unimodal permutations -- every order through ``n == 3``,
20 of 24 at ``n == 4`` -- and the rest are skipped rather than paid for.

The hoist is not free and so does not replace the node-read tree: a stored
read costs a character more (the nasal) and a fetch costs three where a
node read costs two.  What pays for it is that a folded subtree then owes
*nothing* -- no run of ``so``, no ``cə`` -- where the node-read build still
owes every read below it.  Both are built and the shorter returned, the
while stream order keeps its direct reads.
Measured over every table at ``n <= 3`` and 300 sampled at ``n == 4``, that
is 13.8% and 17.9% shorter respectively, and no table grows.
"""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
)

__all__ = ["cvnc"]

# Read one bit; ``o`` (isqrt) is identity on 0/1, the no-op vowel for ``s``.
_READ = "so"

# Open/close the "bit is one" arm: ``ɰ̊`` jumps past ``ʋ`` on zero.
_IF_ONE = "ɰ̊o"
_END_IF = "ʋo"

# Increment.
_INCREMENT = "ci"

# ``ə`` decrements with a floor at 0, so it sends 0 and 1 both to 0: a
# folded leaf climbs from a known point without branching.
_NORMALIZE = "cə"

# Print; ``u`` applies the (empty, every leaf syllable has a ``c`` onset)
# function, which does nothing.
_PRINT = "fu"

# Push front / back.  A nasal rides the read's syllable (``som`` is one
# syllable, three commands), so storing costs one character, not a syllable.
_PUSH_FRONT = "m"
_PUSH_BACK = "n"

# Pop front / back into the accumulator.  ``cu`` is inert and runs before
# the pop, which overwrites the accumulator anyway.
_FETCH_FRONT = "cuŋ"
_FETCH_BACK = "cuɲ"

# Accumulator entering the halt gadget: the printed ASCII digit.  Reach is
# computed from the smaller, 48.
_HALT_ENTRY = _ASCII_ZERO

# Squarings per gadget.  None reaches only 50 (inside the program); one is
# the floor; two reach 6.25M.  :func:`cvnc` adds more only when needed.
_HALT_SQUARINGS = 2


def _halt(squarings: int) -> str:
    """Return the gadget that jumps past the end of the program, which halts.

    Two increments take the digit to 50 and each ``cæ`` squares it; ``ɹ``
    then jumps to that character offset.  The ``i`` after ``ɹ`` is the vowel
    its syllable needs and is unreachable, since the jump has already left.
    """
    return _INCREMENT * 2 + "cæ" * squarings + "ɹi"


def _reach(squarings: int) -> int:
    """Return the offset the gadget lands on: the longest program it escapes."""
    reach = _HALT_ENTRY + 2
    for _ in range(squarings):
        reach *= reach
    return reach


# ``ɹ`` occurs nowhere else, so replacing this string replaces every gadget.
_HALT = _halt(_HALT_SQUARINGS)


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
        # Folded: reads are still owed, only branching is dead.  The last
        # read leaves an unknown bit, so ``cə`` floors it; with nothing to
        # read, the accumulator is the bit the caller's branch handed down.
        reads = _bit_count(len(table))
        if not reads:
            return _leaf(table[0], accumulator)
        return _READ * reads + _NORMALIZE + _leaf(table[0], 0)
    half = len(table) // 2
    # MSB-first: first half is bit 0, second half bit 1.  ``ɰ̊`` jumps on
    # zero, so the arm between the markers is the second half.  Swapped,
    # every table with an odd number of 1s inverts.
    return _READ + _IF_ONE + _tree(table[half:], 1) + _END_IF + _tree(table[:half], 0)


def _bit_count(size: int) -> int:
    """Return how many inputs a subtable of ``size`` rows still selects on."""
    return size.bit_length() - 1


def _deque_schedule(
    perm: tuple[int, ...],
) -> tuple[list[str], list[str]] | None:
    """Return the push and pop ends that serve ``perm``, or None if none do.

    The reads run in stream order and the tree tests in ``perm`` order, so
    something has to bridge the two.  The deque does it without a single
    rotation: each read is pushed to whichever end it must be popped from
    later, and level ``k`` pops whichever end is holding ``perm[k]``.

    Both ends are chosen by search rather than by formula, over the ``2**n``
    push assignments -- the pops are then forced, since only one end can be
    holding the input the level wants.  A permutation no assignment serves is
    rejected here rather than paid for with rotation syllables: the servable
    ones are exactly the unimodal permutations (those descending to a minimum
    then ascending), which is all of them through ``n == 3``, 20 of 24 at
    ``n == 4``, and 252 of 720 at ``n == 6``.  Since the caller *measures*
    every candidate and keeps the shortest, dropping the unservable ones
    costs only the orders whose folds were not the best available anyway.
    """
    n = len(perm)
    for assignment in range(1 << n):
        # Bit ``i`` sends input ``i`` to the front.
        front = [i for i in range(n) if assignment >> i & 1]
        back = [i for i in range(n) if not assignment >> i & 1]
        # Front pushes reverse, back pushes keep order.
        held = list(reversed(front)) + back
        pops = []
        for wanted in perm:
            if held and held[0] == wanted:
                pops.append(_FETCH_FRONT)
                held.pop(0)
            elif held and held[-1] == wanted:
                pops.append(_FETCH_BACK)
                held.pop()
            else:
                break
        else:
            pushes = [
                _PUSH_FRONT if assignment >> i & 1 else _PUSH_BACK for i in range(n)
            ]
            return pushes, pops
    return None


def _stored(truth_table: str, perm: tuple[int, ...]) -> str | None:
    """Build the stored-read CV(N)(C) program for ``perm``.

    ``truth_table`` is already permuted, so level ``k`` splits on ``perm[k]``.
    Every input is read once up front and stored, and each node fetches the
    bit it tests instead of reading it -- which is what lets the tree split in
    an order the input stream does not dictate.

    Two things pay for the hoist and one thing buys it back.  A stored read
    costs one character more than a bare one (the nasal), and a fetch costs
    three where a node read costs two.  Against that, a folded subtree owes
    *nothing*: the reads are all already done, so the run of ``so`` a folded
    leaf used to emit -- and the ``cə`` that normalized the bit it was left
    holding -- both disappear.  Deep folds are where the win is, which is
    also why the reorder matters: it is what makes the folds deep.
    """
    schedule = _deque_schedule(perm)
    if schedule is None:
        return None
    pushes, pops = schedule
    load = "".join(_READ + push for push in pushes)

    def walk(table: str, level: int, accumulator: int | None) -> str:
        if table.count(table[0]) == len(table):
            # The load block did every read.  Below a branch the accumulator
            # is that branch's known bit; at a root that folds immediately it
            # is the load block's last read, unknown, so ``cə`` floors it.
            if accumulator is None:
                return _NORMALIZE + _leaf(table[0], 0)
            return _leaf(table[0], accumulator)
        half = len(table) // 2
        return (
            pops[level]
            + _IF_ONE
            + walk(table[half:], level + 1, 1)
            + _END_IF
            + walk(table[:half], level + 1, 0)
        )

    return load + walk(truth_table, 0, None)


def _stored_candidate(truth_table: str, perm: tuple[int, ...]) -> str:
    """Adapt :func:`_stored` to :func:`best_input_order`'s contract.

    The search wants a program for every order, but the deque serves only
    the unimodal ones (see :func:`_deque_schedule`).  An unservable order
    returns the empty string, which is :func:`best_input_order`'s own
    spelling of "this order could not be built" -- it is skipped rather than
    winning on length zero, the same way ZTOALC L's orders without a
    collision-free placement are.

    Substituting some *other* program for an unservable order would be the
    bug to avoid here: ``truth_table`` arrives already in the permuted
    frame, so the node-read tree over it reads in stream order while testing
    as if permuted, and computes a different function.
    """
    return _stored(truth_table, perm) or ""


def _ordered(truth_table: str, perm: tuple[int, ...]) -> str | None:
    """Build the shortest read strategy available for ``perm``.

    Stream order can read at its nodes or store inputs first; other orders
    require storage. Ties preserve the direct tree.
    """
    if perm != tuple(range(len(perm))):
        return _stored(truth_table, perm)
    direct = _tree(truth_table, 0)
    stored = _stored(truth_table, perm)
    return stored if stored is not None and len(stored) < len(direct) else direct


def _ordered_candidate(truth_table: str, perm: tuple[int, ...]) -> str:
    """Adapt :func:`_ordered` to :func:`best_input_order`'s contract."""
    return _ordered(truth_table, perm) or ""


def cvnc(truth_table: str) -> str:
    """Build a CV(N)(C) program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program reads ``n`` integers, one per line, and prints ``0`` or ``1``.

    The result is the table's decision tree (see the module docstring): one
    ``so`` read and one ``ɰ̊o``/``ʋo`` branch per level, with every leaf
    ending in the halting goto that keeps the arms from running into each
    other.

    The input order selects the read strategy. Stream order reads at its
    nodes; a reordered tree reads every input into the deque first. Every
    order is measured and the shortest emitted program wins.

    The halt gadget must land past the end of the program it is in, so a
    program that is not shorter than the gadget's reach gets one more
    squaring in every gadget, and again until it fits.  The contest is run
    once, with the starting gadget: a squaring adds the same two characters
    to every leaf, and the reach it buys dwarfs the length it adds.
    """
    # For the refusal only; the arity is not needed below.
    _validate_truth_table(truth_table)
    program = best_input_order(truth_table, _ordered_candidate)
    squarings = _HALT_SQUARINGS
    while len(program) >= _reach(squarings):
        squarings += 1
        program = program.replace(_halt(squarings - 1), _halt(squarings))
    return program
