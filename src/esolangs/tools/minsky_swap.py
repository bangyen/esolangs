"""Boolean template for minsky swap; a row is one ``~``, so no span shrinks."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, input_weights
from esolangs.tools.wrap import balance_score

__all__ = ["MINSKY_SWAP_PAIR", "minsky_swap", "minsky_swap_setters"]


MINSKY_SWAP_PAIR = ("**", "++")

_MINSKY_SHORT_RMSN_PAIR = ("decnz();", "inc();  ")

_MINSKY_SMALL_RMSN_PAIR = ("decnz(2);", "inc();   ")

_RMSN = {"+": "inc();", "*": "swap();"}


def minsky_swap(truth_table: str, width: int | None = None) -> str:
    """Build a Minsky Swap template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Every
    run is ``++`` (``reg[0] = 2``) or ``**`` (swap away and back), and each
    is followed by a stage ``~ ~ * +...+ *`` adding ``2**(n-1-i)`` to
    ``reg[1]``: both ``~`` target the command after the stage, so a one
    falls through to the ``+`` block and a zero jumps it, and either way
    ``reg[0]`` is zero with the pointer on it.  A ``*`` then puts the
    pointer on ``reg[1]`` and ``2**n`` ``~``s route value ``v`` to one of
    two shared leaves behind a line-1 ``~`` that jumps over them at start:
    line 2 halts (a ``~`` targeting one past the end), lines 3-5
    (``+ * ~``) set ``reg[1]`` first.  Every target is the digit 2 or 3 (a
    leaf per row was ``Theta(T log T)`` of addresses), every table of one
    arity whose inputs all matter is one length (an ignored input's stage is
    just ``~ ~`` draining its run), and the dump reads ``0 {answer}``.  A ``width`` the
    program exceeds switches to RMSN, one command per line, setters eight
    wide sharing an increment; below 10 with ``n <= 2`` a decision chain
    (nine commands at ``n = 2``) uses the first register as scratch, the
    answer staying in the second.  A zero tail stays: trimming it failed 60/134.
    """
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)

    zero_leaf, one_leaf = 2, 3
    tokens: list[str] = ["~", "~", "+", "*", "~"]
    targets: list[int | None] = [6, None, None]  # None: one past the end
    pos = 5  # instantiated command index of the next command

    # load: one stage per input, MSB first; the run is read off the setters
    # themselves, so the offsets count exactly the text the fill emits.
    run = TEMPLATE_CHAR * len(MINSKY_SWAP_PAIR[0])
    for weight in weights:
        if not weight:
            # An ignored input's two decrements drain its run, jumping nowhere
            # (target 0), so ``reg[0]`` is zero either way and nothing is added.
            tokens += [run, "~", "~"]
            targets += [0, 0]
            pos += len(run) + 2
            continue
        # run, 2 tildes, 2 stars, the + block, then +1 for the 1-based line
        skip = pos + len(run) + 2 + 2 + weight + 1
        tokens += [run, "~", "~", "*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1

    tokens.append("*")  # pointer onto reg[1], which holds the index
    pos += 1
    tokens += ["~"] * len(table)
    targets += [one_leaf if bit == "1" else zero_leaf for bit in table]
    pos += len(table)

    end = pos + 1
    resolved = [end if t is None else t for t in targets]
    program = " ".join(tokens) + "\n" + " ".join(map(str, resolved))
    if width is None or width <= 0 or max(map(len, program.splitlines())) <= width:
        return program
    if n <= 2 and width < 10:
        # Essential: otherwise lines reach 10 columns.
        # One bit contributes 1, the other 2: common inc plus decnz/inc
        # adds 0/2 without branching. All leaves fit single-digit targets.
        slot = TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])
        lines = [slot] if n == 1 else [slot, "inc();", slot]
        one = len(lines) + len(truth_table) + 1
        for value in range(len(truth_table)):
            # the chain adds the low bit as 2 and the high bit as 1: swap them
            row = value if n == 1 else (value & 1) * 2 + (value >> 1)
            lines.append(f"decnz({one if truth_table[row] == '1' else one + 1});")
        return "\n".join([*lines, "swap();", "inc();"])
    lines = []
    jumps = iter(resolved)
    for token in tokens:
        if token.startswith(TEMPLATE_CHAR):
            # Both fills still execute two commands, preserving every target.
            lines.extend(("inc();", TEMPLATE_CHAR * len(_MINSKY_SHORT_RMSN_PAIR[0])))
        else:
            for command in token:
                lines.append(
                    f"decnz({next(jumps)});" if command == "~" else _RMSN[command]
                )
    return "\n".join(lines)


def minsky_swap_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform pair for compact or line-oriented RMSN notation."""
    pair = MINSKY_SWAP_PAIR
    if template.startswith(TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])):
        pair = _MINSKY_SMALL_RMSN_PAIR
    elif template.startswith("decnz("):
        pair = _MINSKY_SHORT_RMSN_PAIR
    return (pair,) * n


def _balance(table: str, default: str) -> str:
    """Compare compact source and the three line-oriented setter regimes."""
    return min(
        default,
        minsky_swap(table, 1),
        minsky_swap(table, 10),
        minsky_swap(table, 15),
        key=balance_score,
    )


LANGUAGE = Language(
    "Minsky Swap",
    "register_based.minsky_swap",
    boolean=minsky_swap,
    contract=BooleanContract(
        answer_mode="dump",
        note="Minsky Swap has no output instruction and dumps its "
        "registers at halt; the answer is the second one",
        parameterized=True,
    ),
    balance=_balance,
)
