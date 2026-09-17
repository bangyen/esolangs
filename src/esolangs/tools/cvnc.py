"""Boolean-function generator for CV(N)(C).

One accumulator, one input at a time, so a table is a decision tree.
The read is ``so`` (``o``, isqrt, is identity on 0/1, as the wiki's
truth machine uses it).  The branch is ``ɰ̊o`` ... ``ʋo``: ``ɰ̊`` jumps
past ``ʋ`` on zero.  Every leaf halts with a computed goto past the
program end, ``ci ci cæ cæ ɹi`` (48/49 -> 50, squared to 6,250,000; one
squaring reaches 2500, through ``n == 4``; zero fails), or it would hit
``ʋ`` and loop.  A leaf prints a digit, climbing ``48 + answer - bit``.
A constant subtree folds to one leaf but keeps its reads; ``cə`` floors
the unknown last bit.

A second construction hoists the reads into the deque (``m``/``n``
push, ``ŋ``/``ɲ`` pop either end) so :func:`_ordered` can test in any
order; each read is pushed to the end it will be popped from
(:func:`_deque_schedule`), which serves exactly the unimodal
permutations.  A stored read costs one more character and a fetch three
vs two, but a folded subtree then owes nothing; the shorter of the two
is kept: 13.8% shorter at ``n <= 3``, 17.9% at ``n == 4``, no table grows.
"""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
)

__all__ = ["cvnc"]

_READ = "so"

# Open/close the "bit is one" arm: ``ɰ̊`` jumps past ``ʋ`` on zero.
_IF_ONE = "ɰ̊o"
_END_IF = "ʋo"

_INCREMENT = "ci"

# Decrement, floored at 0: sends 0 and 1 both to 0.
_NORMALIZE = "cə"

# Print; the ``u`` applies an empty function.
_PRINT = "fu"

_PUSH_FRONT = "m"
_PUSH_BACK = "n"

# Pop front / back into the accumulator; ``cu`` is inert.
_FETCH_FRONT = "cuŋ"
_FETCH_BACK = "cuɲ"

# Accumulator entering the halt gadget; reach is computed from the smaller.
_HALT_ENTRY = _ASCII_ZERO

_HALT_SQUARINGS = 2


def _halt(squarings: int) -> str:
    """Return the gadget that jumps past the end of the program, which halts.

    Two increments, ``cæ`` squarings, then ``ɹ``; its ``i`` is unreachable.
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

    Always a climb: the target is 48 or 49 and the bit 0 or 1.
    """
    target = _ASCII_ZERO + int(answer)
    return _INCREMENT * (target - accumulator) + _PRINT + _HALT


def _tree(table: str, accumulator: int) -> str:
    """Build the program for ``table``, given what the last read left behind.

    A constant table stops branching but still owes every read below it.
    """
    if table.count(table[0]) == len(table):
        # Folded: reads still owed; ``cə`` floors the unknown last bit.
        reads = _bit_count(len(table))
        if not reads:
            return _leaf(table[0], accumulator)
        return _READ * reads + _NORMALIZE + _leaf(table[0], 0)
    half = len(table) // 2
    # ``ɰ̊`` jumps on zero, so the arm between the markers is the second
    # (bit 1) half; swapped, every odd-weight table inverts.
    return _READ + _IF_ONE + _tree(table[half:], 1) + _END_IF + _tree(table[:half], 0)


def _bit_count(size: int) -> int:
    """Return how many inputs a subtable of ``size`` rows still selects on."""
    return size.bit_length() - 1


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

    Every input is read up front and each node fetches the bit it tests; a
    folded subtree owes nothing, which is where the reorder pays.
    """
    schedule = _deque_schedule(perm)
    if schedule is None:
        return None
    pushes, pops = schedule
    load = "".join(_READ + push for push in pushes)

    def walk(table: str, level: int, accumulator: int | None) -> str:
        if table.count(table[0]) == len(table):
            # Below a branch the accumulator is a known bit; at an
            # immediately-folding root it is the last read, so ``cə`` floors it.
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

    An unservable order returns ``""`` (skipped, as ZTOALC L's are).
    Substituting another program would compute a different function, since
    ``truth_table`` is already permuted.
    """
    return _stored(truth_table, perm) or ""


def _ordered(truth_table: str, perm: tuple[int, ...]) -> str | None:
    """Build the shortest read strategy available for ``perm``.

    Stream order may read at its nodes or store first; other orders store.
    Ties keep the direct tree.
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

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program reads ``n`` lines and prints ``0`` or ``1``.  One ``so`` read and
    one ``ɰ̊o``/``ʋo`` branch per level, every leaf halting.  Every input
    order is measured and the shortest wins.  A program not shorter than the
    halt gadget's reach gets one more squaring in every gadget, repeated
    until it fits; the contest is run once with the starting gadget.
    """
    # For the refusal only; the arity is not needed below.
    _validate_truth_table(truth_table)
    program = best_input_order(truth_table, _ordered_candidate)
    squarings = _HALT_SQUARINGS
    while len(program) >= _reach(squarings):
        squarings += 1
        program = program.replace(_halt(squarings - 1), _halt(squarings))
    return program
