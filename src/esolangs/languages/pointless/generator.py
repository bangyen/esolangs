"""Pointless Boolean program generator: a shared decision diagram of functions.

The one ``!`` makes cell 0 a 1, so ``+`` turns cells 1..51+2n from 0 to 1
(the wiki's Hello world setup); with ``tape[v]`` = 1, ``+`` is then an
increment, which builds ``0`` (48) in cell 50 and ``1`` (49) in cell 51
before ``tape[48]`` and cell 0 go back to 0.  Level ``d`` reads its
character into ``X = 52 + 2d`` and ``=`` maps it to its bit; ``[`` tests
``tape[bit]``, so ``[>-<->>"one"<<]`` runs only on 1, clearing ``X`` and
the flag ``X + 1``, and ``>[->"zero"<]<`` runs on the flag left at 1.  Each
distinct subtable (``subtree_ids``) is one function entered and left at its
``X``; equal halves skip the branch, and a constant subtable reads its
remaining characters and prints from cell 50 or 51.

Size:
    O(T) size and build time, 26n + 311 steps at most; n=10 parity: 1,090
    chars, n=10 random 1847: 8,558 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_tokens
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

_OUT = 50  # cell 50 holds "0", cell 51 holds "1"
_X = 52  # level d's character and bit cell is 52 + 2d, its flag 53 + 2d


def _setup(n: int) -> str:
    """Fill cells 1..51+2n with 1, build the two digits, clear 48 and 0."""
    top = _X + 2 * n - 1
    return (
        "!"
        + ">+" * top
        + "<" * (top - _OUT)
        + "+" * 47
        + ">"
        + "+" * 48
        + "<" * (_OUT + 1 - 48)
        + "-"
        + "<" * 48
        + "-"
        + ">" * _X
    )


def _wrap(program: str, width: int) -> str:
    """Break anywhere but inside a quoted name, which a newline would rename."""
    return wrap_tokens(program, width, r'"[^"]*"|[\s\S]')


def pointless(truth_table: str) -> str:
    """Build a Pointless program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    functions: dict[str, str] = {}

    def constant(sub: int, depth: int) -> str:
        key = f"c{sub}d{depth}"
        if key not in functions:
            away = _X + 2 * depth - _OUT - sub
            functions[key] = "," * (n - depth) + "<" * away + "." + ">" * away
        return key

    def build(depth: int, k: int) -> None:
        sub = ids[depth][k]
        functions[str(sub)] = ""  # reserve: children are named first
        zero, one = (child(depth + 1, 2 * k + b) for b in (0, 1))
        if zero == one:
            body = f',>>"{zero}"<<'
        else:
            body = f',=[>-<->>"{one}"<<]>[->"{zero}"<]<'
        functions[str(sub)] = body

    def child(depth: int, k: int) -> str:
        sub = ids[depth][k]
        if sub < 2:
            return constant(sub, depth)
        if str(sub) not in functions:
            build(depth, k)
        return str(sub)

    root = child(0, 0)
    declarations = "".join(f'"{key}"{{{body}}}' for key, body in functions.items())
    return f'{_setup(n)}"{root}"{declarations}'


LANGUAGE = Language(
    "Pointless",
    "pointless",
    category="tape_based",
    boolean=pointless,
    contract=BooleanContract(input_shape="char_stream"),
    # Whitespace is a comment, so a newline anywhere outside a name is harmless.
    wrap=_wrap,
)
