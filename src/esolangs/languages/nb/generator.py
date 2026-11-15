"""Compile truth tables into NB's nested if/else statements.

Read every bit as an integer and skip equal cofactors. When two
successive inputs pick the same pair of subtrees in opposite order,
flip the second bit under the first and print each subtree once.
The deepest tests get the shortest variable names. Each false leaf
clears the final input variable before printing it.

Size:
    O(T) characters, n=4 parity: 290 chars.
"""

from esolangs.generation.helpers import essential_inputs, subtree_ids, subtree_slot
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_space_delimited
from esolangs.runtime._program import Program

_DIGITS = str.maketrans("01", "BN")


def _name(rank: int) -> str:
    return "NN" + (format(rank, "b").translate(_DIGITS) if rank else "")


def nb_request(request: GenerationRequest) -> Program:
    """Emit a reduced tree and reads in the original input order."""
    table = request.table
    ids = subtree_ids(table)
    arity = len(ids) - 1
    essential = set(essential_inputs(table, arity))
    names = [_name(rank) for rank in reversed(range(arity))]
    lines = [
        f"BNB {name}" if level in essential else "BNB NN"
        for level, name in enumerate(names)
    ]

    def emit(level: int, block: int) -> None:
        level, block, (_, key) = subtree_slot(ids, level, block, skip=True)
        if key == 0:
            lines.extend(("NN BBBBB NN", "NBN NN"))
        elif key == 1:
            lines.append("NBN NB")
        else:
            zero, one = 2 * block, 2 * block + 1
            if level + 2 <= arity:
                start = 4 * block
                aa, ab, ba, bb = ids[level + 2][start : start + 4]
                if aa == bb and ab == ba and aa != ab:
                    first, second = names[level : level + 2]
                    lines.extend(
                        (
                            f"NBB {first}",
                            f"NBB {second}",
                            f"{second} BBBBB {second}",
                            "BNN",
                            f"{second} BBBB NB",
                            "BBB",
                            "BNB",
                        )
                    )
                    level += 1
                    zero, one = start, start + 1
            lines.append(f"NBB {names[level]}")
            emit(level + 1, one)
            lines.append("BNN")
            emit(level + 1, zero)
            lines.append("BBB")

    emit(0, 0)
    return "\n".join(lines)


def nb_balance_request(request: BalanceRequest) -> Program:
    """Fit the multiline source without splitting a unary literal or name."""
    source = request.text_source()
    width = balanced_token_width(source.split(), " ")
    return min(source, wrap_space_delimited(source, width), key=balance_score)
