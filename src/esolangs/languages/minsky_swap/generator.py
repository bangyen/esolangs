"""Minsky Swap Boolean program generator: weighted stages, then a ``~`` cascade.

Each input is a uniform ``++``/``**`` run. Weighted stages index the higher
essential bits; the last essential input stays at 0/2 in the other register.
A ``~`` cascade routes row pairs to four fixed leaves. Symmetric tables keep
their popcount reader ([ablations.symmetric_count]); a narrow ``width``
switches to RMSN, one command per line.

Size:
    O(T): one ``~`` per row pair; n=8 random 1847: 684 chars, n=10 random 1847:
    2,343 chars, n=12 random 1847: 8,913 chars. Constants: n=8: 27/30
    chars, two/five commands including the dump.

Decisions:
    Pair leaves target 2, 4, 9 or 13, independent of T. Trailing ignored
    slots preserve the held bit without changing setter order.
    A zero leaf may leave scratch at 2; the answer is still the second register.
"""

from collections.abc import Callable, Sequence
from typing import Any

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_width,
    input_weights,
    same_up_to_wrapping,
    symmetric_weights,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
    layout_tokens,
)
from esolangs.generation.wrap import balance_score

__all__ = ["MINSKY_SWAP_PAIR", "minsky_swap", "minsky_swap_setters"]


MINSKY_SWAP_PAIR = ("**", "++")

# Setters eight wide sharing an increment.
_MINSKY_SHORT_RMSN_PAIR = ("decnz();", "inc();  ")

_MINSKY_SMALL_RMSN_PAIR = ("decnz(2);", "inc();   ")

_RMSN = {"+": "inc();", "*": "swap();"}


def minsky_swap(truth_table: str, width: int | None = None) -> str:
    """Return a Minsky Swap template for ``truth_table`` (MSB first).

    A ``width`` the program exceeds switches to RMSN.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    constant = truth_table == truth_table[0] * len(truth_table)
    if constant:
        bit = int(truth_table[0])
        run = InputSlot(len(MINSKY_SWAP_PAIR[0]))
        tokens: list[TemplateToken] = [
            "*+*~" if bit else "~",
            *(run, "*") * (n - 1),
            run,
        ]
        resolved = [3 * n + 1 + 3 * bit]
    else:
        # Symmetric tables count inputs into n+1 rows instead of a binary index.
        symmetric = symmetric_weights(truth_table, n)
        if symmetric:
            tokens, resolved = _cascade(*symmetric)
        else:
            tokens, resolved = _pair_cascade(*input_weights(truth_table, n))
    program = _render(tokens, resolved)
    if width is None or grid_width(program.source) <= width:
        return program
    if n <= 2 and width < 10 and not constant:
        return _rmsn_small(truth_table, n)
    return _rmsn_expand(tokens, resolved)


def _render(tokens: list[TemplateToken], resolved: list[int]) -> TemplateLayout:
    """Return the compact program: the commands, then the jump targets.

    The wiki splits the code line into characters, each a command, so no
    separator; a jump names a command (1-based), so none is 0.
    """
    return layout_fragments((*tokens, "\n", " ".join(map(str, resolved))))


def _cascade(
    weights: Sequence[int], table: str
) -> tuple[list[TemplateToken], list[int]]:
    """Return the stages adding each input's weight, then the ``~`` cascade."""
    # Two shared leaves sit behind a line-1 ``~`` that jumps over them at
    # start: line 2 halts (a ``~`` targeting one past the end), lines 3-5
    # (``+ * ~``) set ``reg[1]`` first.
    zero_leaf, one_leaf = 2, 3
    tokens: list[TemplateToken] = ["~", "~", "+", "*", "~"]
    targets: list[int | None] = [6, None, None]  # None: one past the end
    pos = 5  # instantiated command index of the next command

    # load: one stage per input, MSB first; the run is read off the setters
    # themselves, so the offsets count exactly the text the fill emits.  A run
    # is ``++`` (``reg[0] = 2``) or ``**`` (swap away and back); the stage
    # ``~ ~ * +...+ *`` has both ``~`` target the command after it, so a one
    # falls through to the ``+`` block and a zero jumps it, and either way
    # ``reg[0]`` is zero with the pointer on it.  An ignored input's stage is
    # just ``~ ~``, so every table of one arity whose inputs all matter is
    # one length.
    run = InputSlot(len(MINSKY_SWAP_PAIR[0]))
    for weight in weights:
        if not weight:
            # An ignored input's two decrements drain its run, both jumping
            # to the command after them (a fall-through either way), so
            # ``reg[0]`` is zero and nothing is added.
            skip = pos + len(run) + 2 + 1
            tokens += [run, "~", "~"]
            targets += [skip, skip]
            pos = skip - 1
            continue
        # run, 2 tildes, 2 stars, the + block, then +1 for the 1-based line
        skip = pos + len(run) + 2 + 2 + weight + 1
        tokens += [run, "~", "~", "*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1

    # pointer onto reg[1], which holds the index; the ``~``s route it to a leaf
    tokens.append("*")
    pos += 1
    tokens += ["~"] * len(table)
    targets += [one_leaf if bit == "1" else zero_leaf for bit in table]
    pos += len(table)

    end = pos + 1
    return tokens, [end if t is None else t for t in targets]


def _pair_cascade(
    weights: Sequence[int], table: str
) -> tuple[list[TemplateToken], list[int]]:
    """Hold the last essential input; trailing ignored runs preserve its bit."""
    held = max(i for i, weight in enumerate(weights) if weight)
    weights = [weight // 2 for weight in weights]
    pairs = [table[i : i + 2] for i in range(0, len(table), 2)]
    # Entry pointer is on the zero index register. Mixed leaves test the
    # held 0/2; the one leaf's three decrements drain either before halting.
    # Target 13 is two digits; see [ablations.low_bit_leaf_split].
    tokens: list[TemplateToken] = list("~~*+*~~~*~*~*~~~")
    targets: list[int | None] = [17, None, None, None, None, None, 4, 3, None, None]
    pos = 16
    run = InputSlot(len(MINSKY_SWAP_PAIR[0]))
    for weight in weights[:held]:
        skip = pos + len(run) + (4 + weight if weight else 2) + 1
        tokens += [run, "~", "~"]
        if weight:
            tokens += ["*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1
    tokens.append(run)
    pos += len(run)
    for _ in weights[held + 1 :]:
        # Rescale held 0/2 to 0/4, read the ignored bit, then erase its
        # contribution; neither the index register nor the pointer changes.
        run_start, plus_start, end = pos + 7, pos + 15, pos + 17
        tokens += ["~~++++", run, "~~~~~~++"]
        targets += [run_start, run_start, end, end, end, end, plus_start, plus_start]
        pos += 16
    tokens.append("*")
    pos += 1
    tokens += ["~"] * len(pairs)
    leaves = {"00": 2, "11": 4, "01": 9, "10": 13}
    targets += [leaves[pair] for pair in pairs]
    end = pos + len(pairs) + 1
    return tokens, [end if target is None else target for target in targets]


def _rmsn_small(truth_table: str, n: int) -> TemplateLayout:
    """Decision-chain RMSN for ``n <= 2``, whose lines stay under 10 columns.

    Nine commands at ``n = 2``; the first register is scratch, the answer
    stays in the second.
    """
    # One bit contributes 1, the other 2: common inc plus decnz/inc
    # adds 0/2 without branching. All leaves fit single-digit targets.
    slot = InputSlot(len(_MINSKY_SMALL_RMSN_PAIR[0]))
    lines: list[TemplateToken] = [slot] if n == 1 else [slot, "inc();", slot]
    one = len(lines) + len(truth_table) + 1
    for value in range(len(truth_table)):
        # the chain adds the low bit as 2 and the high bit as 1: swap them
        row = value if n == 1 else (value & 1) * 2 + (value >> 1)
        lines.append(f"decnz({one if truth_table[row] == '1' else one + 1});")
    return layout_tokens([*lines, "swap();", "inc();"], 1)


def _rmsn_expand(tokens: list[TemplateToken], jumps: list[int]) -> TemplateLayout:
    """One RMSN command per line: short setters, ``~`` taking ``jumps`` in order."""
    lines: list[TemplateToken] = []
    targets = iter(jumps)
    slot = InputSlot(len(_MINSKY_SHORT_RMSN_PAIR[0]))
    for token in tokens:
        if isinstance(token, InputSlot):
            # Both fills still execute two commands, preserving every target.
            lines.extend(("inc();", slot))
        else:
            lines.extend(
                f"decnz({next(targets)});" if command == "~" else _RMSN[command]
                for command in token
            )
    return layout_tokens(lines, 1)


def minsky_swap_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform pair for compact or line-oriented RMSN notation."""
    pair = MINSKY_SWAP_PAIR
    if template.startswith(TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])):
        pair = _MINSKY_SMALL_RMSN_PAIR
    elif template.startswith(("decnz(", "swap();")):
        pair = _MINSKY_SHORT_RMSN_PAIR
    return (pair,) * n


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Match whole 1-, 10- and 15-wide representation switches."""
    return template in (layout(1), layout(10), layout(15)) or same_up_to_wrapping(
        template, plain
    )


def minsky_swap_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def minsky_swap_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Compare compact source and the three line-oriented setter regimes."""
    default = request.source
    if not isinstance(default, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    return min(
        default,
        _layout(request.table, 1),
        key=lambda layout: balance_score(layout.source),
    )
