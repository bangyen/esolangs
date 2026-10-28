"""Painfuck Boolean program generator: a flag-dispatched decision tree.

Uses Painfuck's own commands, not transliterated brainfuck: ``i`` reads and
``o`` prints a *number*, so the ASCII offset brainfuck pays twice per
program (49% of its characters at ``n == 4``, 70% at ``n == 2``) vanishes.
``r`` moves two right, the cell layout's stride.  Bit ``k`` sits in cell
``2k``, its flag in ``2k + 1``: a node sets the flag, tests the bit and clears
the flag inside, then tests the flag for the zero side, so exactly one side
fires and both cells end zero.  The answer accumulates in cell ``2n``, printed
once.  Repeated residuals share through level flags or banks, admitted under a
command bound; inline text stays a candidate; the tree is also built for the
complement, with the result preset to 1 and cleared at each leaf, and the
shorter kept.  An affine table sums its bits and prints the sum mod 2
([ablations.parity_sum]).

Size:
    Banks shrink dense tables (majority 1,257 -> 704 chars at n=8, 4,406 ->
    1,342 at n=10); n=10 parity: 132 chars, n=10 random 1847: 10,156 chars.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    affine_form,
    in_input_order,
)
from esolangs.generation.shared_block import (
    repeated_bank,
    repeated_block,
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


def painfuck(truth_table: str) -> str:
    """Return a Painfuck program for an MSB-first ``2**n`` truth table."""
    tree = in_input_order(truth_table, _painfuck_ordered)
    form = affine_form(truth_table, _validate_truth_table(truth_table))
    if form is None or not any(form[1]):
        return tree
    return min(tree, _parity_sum(*form), key=len)


def _parity_sum(bias: int, coefficients: list[int]) -> str:
    """Sum the counted bits, two cells a step, and print the sum mod 2.

    Each read lands two right of the running sum, which ``asrpsllb`` moves
    onto it; an ignored read is zeroed.  ``rlqh`` halves a copy beside it,
    and ``aslssrlb`` subtracts the half twice ([ablations.parity_sum]).
    """
    code = []
    for k, counted in enumerate(coefficients):
        read = "i" + ("" if counted else "z")
        code.append(read if k == 0 else f"r{read}llasrpsllbr")
    code.append(("ps" if bias else "") + "rlqhaslssrlblo")
    return _encode("".join(code))


def _painfuck_ordered(table: str, perm: tuple[int, ...]) -> str:
    """Return the shorter of the table's tree and its complement's flipped tree.

    Each 1 leaf costs a move and ``ps``; the flipped tree presets the result
    to 1 and subtracts at the complement's 1 leaves, so OR costs what NOR does.
    """
    flipped = table.translate(str.maketrans("01", "10"))
    return min(
        _painfuck_polarity(table, perm, flip=False),
        _painfuck_polarity(flipped, perm, flip=True),
        key=len,
    )


def _painfuck_polarity(table: str, perm: tuple[int, ...], *, flip: bool) -> str:
    """Return the shorter of inline text and the banks.

    Banks are same-level, or the mixed union of one-per-depth picks with the
    greatest bank; all stay under a command bound.
    """
    plain, _ = _painfuck_shared(table, perm, (), (), flip=flip)
    if repeated_block(table) is None:
        return plain
    n = len(perm)
    bound = (3 * n * n + 3) // 4 + 20 * n + 4
    forms = [(plain, 0)]
    # Banks win on majority and thresholds ([ablations.bank_plans]); the
    # one-residual form and the levels plan went ([ablations]).
    plans: list[tuple[tuple[tuple[int, int], ...], tuple[int, ...]]] = []
    plans.extend(repeated_bank(table, ranked=ranked) for ranked in (False, True))
    plans.append(repeated_mixed_bank(table))
    for blocks, flags in dict.fromkeys(plans):
        if len(blocks) > 1:
            forms.append(_painfuck_shared(table, perm, blocks, flags, flip=flip))
    return min((code for code, cost in forms if cost <= bound), key=len)


def _painfuck_shared(
    table: str,
    perm: tuple[int, ...],
    blocks: tuple[tuple[int, int], ...],
    flags: tuple[int, ...] = (),
    *,
    flip: bool = False,
) -> tuple[str, int]:
    """Emit native flag dispatch and return its maximum command count.

    ``flip`` presets the result cell to 1 (``rpsll`` after the reads) and
    clears it at each leaf, so ``table`` is the complement of the answer.
    """
    n = _validate_truth_table(table)
    header = "ir" * (n - 1) + "i" + ("rpsll" if flip else "")
    body, commands = flag_tree_body(
        table,
        perm,
        2 * (n - 1),
        2 * n,
        shared_blocks=blocks,
        flag_levels=flags,
        binary_leaves=True,
        dialect=FlagDialect(
            _reach,
            "ps",
            "s",
            "a",
            "b",
            "s",
            retest=True,
            leaf="s" if flip else "",
            unleaf="ps" if flip else "",
        ),
    )
    return _encode(header + body + "o"), len(header) + commands + 1


LANGUAGE = Language(
    "Painfuck",
    "painfuck",
    category="tape_based",
    random=True,
    boolean=painfuck,
    wrap=wrap_chars,
)
