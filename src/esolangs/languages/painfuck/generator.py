"""Painfuck Boolean program generator: a flag-dispatched decision tree.

Uses Painfuck's own commands, not transliterated brainfuck: ``i`` reads and
``o`` prints a *number*, so the ASCII offset brainfuck pays twice per
program (49% of its characters at ``n == 4``, 70% at ``n == 2``) vanishes.
``r`` moves two right, the cell layout's stride, and ``d`` resets the
pointer, so returning to the reads costs one character instead of one per
cell.  Bit ``k`` sits in cell ``2k``, its flag in ``2k + 1``: a node sets the
flag, tests the bit and clears the flag inside, then tests the flag for the
zero side, so exactly one side fires and both cells end zero.  The answer
accumulates in cell ``2n``, printed once.  Repeated residuals share through
level flags or banks, admitted under a command bound; inline text stays a
candidate.

Size:
    Shared residuals shrink dense tables: three seeded dense n=16 tables
    average 831,265 -> 650,200 characters (-21.78%), five rows executed per
    table; n=10 parity: 1,005 chars, n=10 random 1847: 10,160 chars.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.generation.shared_block import (
    repeated_bank,
    repeated_block,
    repeated_blocks,
    repeated_mixed_bank,
)
from esolangs.generation.shared_flag import FlagDialect, flag_tree_body
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.painfuck.interpreter import _CYCLES
from esolangs.registry._language import Language

__all__ = ["painfuck"]


def _encode(code: str) -> str:
    """Pre-shift ``code`` so the interpreter's trans table recovers it.

    Each command is rotated ``k`` steps *back* along its own cycle, ``k``
    the number of commands emitted so far, inverting :func:`_translate`.
    """
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            position = cycle.find(char)
            if position != -1:
                out.append(cycle[(position - k) % len(cycle)])
                k += 1
                break
        else:  # pragma: no cover - every emitted command is in a cycle
            raise ValueError(f"Painfuck command {char!r} is not in a cycle")
    return "".join(out)


def _reach(start: int, target: int) -> str:
    """Move from ``start`` to ``target`` with ``r`` (+2) and ``l`` (-1).

    Rightward is two cells a character, so an odd gap overshoots by one
    and steps back; leftward is one cell a character.
    """
    delta = target - start
    if delta < 0:
        return "l" * -delta
    return "r" * ((delta + 1) // 2) + ("l" if delta % 2 else "")


def _move(start: int, target: int) -> str:
    """Return the shorter of walking to ``target`` and restarting at 0.

    ``d`` resets the pointer, which brainfuck cannot do: a leaf deep in
    the tree reaches the result cell in ``1 + target // 2`` characters
    however far right it has walked, instead of one per cell walked back.
    """
    # Restart wins on skewed tables: or 17.8/18.9/20.1% at n=7/8/9; random 0.6%.
    relative = _reach(start, target)
    absolute = "d" + _reach(0, target)
    return relative if len(relative) <= len(absolute) else absolute


def painfuck(truth_table: str) -> str:
    """Return a Painfuck program for an MSB-first ``2**n`` truth table."""
    return in_input_order(truth_table, _painfuck_ordered)


def _painfuck_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Return the shortest of inline text, one residual, levels and banks.

    Banks are same-level, or the mixed union of one-per-depth picks with the
    greatest bank; all stay under a command bound.
    """
    plain, _ = _painfuck_tree(table, perm)
    shared = repeated_block(table)
    if shared is None:
        return plain
    candidate, commands = _painfuck_tree(table, perm, shared)
    n = len(perm)
    bound = (3 * n * n + 3) // 4 + 20 * n + 4
    forms = [(plain, 0), (candidate, commands)]
    # Levels and banks over one residual: random n=8 6.0% (n=7..9 5.4-6.0%), but
    # parity n=8 -77%/-20% (levels/banks) and majority -44%/-23%.
    plans: list[tuple[tuple[tuple[int, int], ...], tuple[int, ...]]] = [
        (repeated_blocks(table), ())
    ]
    plans.extend(repeated_bank(table, ranked=ranked) for ranked in (False, True))
    plans.append(repeated_mixed_bank(table))
    for blocks, flags in dict.fromkeys(plans):
        if len(blocks) > 1:
            forms.append(_painfuck_shared(table, perm, blocks, flags))
    return min((code for code, cost in forms if cost <= bound), key=len)


def _painfuck_shared(
    table: str,
    perm: tuple[int, ...],
    blocks: tuple[tuple[int, int], ...],
    flags: tuple[int, ...] = (),
) -> tuple[str, int]:
    """Emit native flag dispatch and return its maximum command count."""
    n = _validate_truth_table(table)
    header = "ir" * (n - 1) + "i"
    body, commands = flag_tree_body(
        table,
        perm,
        2 * (n - 1),
        2 * n,
        shared_blocks=blocks,
        flag_levels=flags,
        binary_leaves=True,
        dialect=FlagDialect(_move, "ps", "s", "a", "b", "s", retest=True),
    )
    return _encode(header + body + "o"), len(header) + commands + 1


def _painfuck_tree(
    table: str, perm: tuple[int, ...], shared: tuple[int, int] | None = None
) -> tuple[str, int]:
    """Emit an inline tree or one deferred residual with the native flag dialect."""
    return _painfuck_shared(table, perm, () if shared is None else (shared,))


LANGUAGE = Language(
    "Painfuck",
    "painfuck",
    category="tape_based",
    random=True,
    boolean=painfuck,
    wrap=wrap_chars,
)
