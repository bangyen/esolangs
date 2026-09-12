r"""Boolean-function generator for CV(N)(C)."""

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
)

__all__ = ["cvnc"]

# Read one input bit.
# it is the no-op vowel that.
_READ = "so"

# Open the "bit is one" arm and.
# the accumulator is zero, so.
_IF_ONE = "ɰ̊o"
_END_IF = "ʋo"

# Increment, the only way to.
_INCREMENT = "ci"

# Force a just-read bit to a.
# so it sends both 0 and 1 to 0.
# a fixed starting point.
_NORMALIZE = "cə"

# Print the accumulator as a.
# empty here -- every syllable.
# parse and does nothing.
_PRINT = "fu"

# Push the accumulator to the.
# read's own syllable --.
# storing a bit costs one.
_PUSH_FRONT = "m"
_PUSH_BACK = "n"

# Fetch a stored bit from the.
# the (already empty) function.
# does nothing; the pop then.
# what makes the inert vowel.
_FETCH_FRONT = "cuŋ"
_FETCH_BACK = "cuɲ"

# The accumulator entering the.
# still holds the ASCII digit.
# from the smaller (48) is what.
_HALT_ENTRY = _ASCII_ZERO

# Squarings in the gadget.
# reaches only 50 and lands.
# the generator's arity rather.
# and caps it at n == 4, two.
# characters per leaf.
_HALT_SQUARINGS = 2

# Jump past the end of the.
# digit to 50 and two squarings.
# that character offset.
# and is unreachable, since the.
_HALT = _INCREMENT * 2 + "cæ" * _HALT_SQUARINGS + "ɹi"

# The offset _HALT reaches, and.
# Checked against the emitted.
_HALT_REACH = (_HALT_ENTRY + 2) ** (2**_HALT_SQUARINGS)


def _leaf(answer: str, accumulator: int) -> str:
    r"""Print ``answer`` as a digit and halt, climbing from ``accumulator``."""
    target = _ASCII_ZERO + int(answer)
    return _INCREMENT * (target - accumulator) + _PRINT + _HALT


def _tree(table: str, accumulator: int) -> str:
    r"""Build the program for ``table``, given what the last read left."""
    if table.count(table[0]) == len(table):
        # Folded.
        # the branching is dead.
        # bit, so ``cə`` floors it to a.
        # from -- and when nothing is.
        # already the bit the caller's.
        reads = _bit_count(len(table))
        if not reads:
            return _leaf(table[0], accumulator)
        return _READ * reads + _NORMALIZE + _leaf(table[0], 0)
    half = len(table) // 2
    # The table is indexed.
    # rows where this input is 0.
    # ``ɰ̊`` jumps away on zero, so.
    # that runs when the bit is 1.
    # them is the first.
    # inverts every table with an.
    return _READ + _IF_ONE + _tree(table[half:], 1) + _END_IF + _tree(table[:half], 0)


def _bit_count(size: int) -> int:
    r"""Return how many inputs a subtable of ``size`` rows still selects on."""
    return size.bit_length() - 1


def _deque_schedule(
    perm: tuple[int, ...],
) -> tuple[list[str], list[str]] | None:
    r"""Return the push and pop ends that serve ``perm``, or None if none."""
    n = len(perm)
    for assignment in range(1 << n):
        # Bit ``i`` of the assignment.
        front = [i for i in range(n) if assignment >> i & 1]
        back = [i for i in range(n) if not assignment >> i & 1]
        # Front pushes reverse (each.
        # keep their order, so the.
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
    r"""Build the stored-read CV(N)(C) program for ``perm``."""
    schedule = _deque_schedule(perm)
    if schedule is None:
        return None
    pushes, pops = schedule
    load = "".join(_READ + push for push in pushes)

    def walk(table: str, level: int, accumulator: int | None) -> str:
        if table.count(table[0]) == len(table):
            # No reads are owed -- the load.
            # leaf is the leaf alone.
            # a branch ran: below one, the.
            # fetched and is known.
            # folds immediately, nothing.
            # is still the *last bit the.
            # so ``cə`` floors it to zero.
            # node-read tree does, for the.
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
    r"""Adapt :func:`_stored` to :func:`best_input_order`'s contract."""
    return _stored(truth_table, perm) or ""


def _ordered(truth_table: str, perm: tuple[int, ...]) -> str | None:
    r"""Build the shortest read strategy available for ``perm``."""
    if perm != tuple(range(len(perm))):
        return _stored(truth_table, perm)
    direct = _tree(truth_table, 0)
    stored = _stored(truth_table, perm)
    return stored if stored is not None and len(stored) < len(direct) else direct


def _ordered_candidate(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Adapt :func:`_ordered` to :func:`best_input_order`'s contract."""
    return _ordered(truth_table, perm) or ""


def cvnc(truth_table: str) -> str:
    r"""Build a CV(N)(C) program computing the given truth table."""
    # Called for the refusal: a.
    # branch on, and the arity.
    _validate_truth_table(truth_table)
    program = best_input_order(truth_table, _ordered_candidate)
    if len(program) >= _HALT_REACH:
        raise GeneratorCapError("program outgrew the halting goto's reach")
    return program
