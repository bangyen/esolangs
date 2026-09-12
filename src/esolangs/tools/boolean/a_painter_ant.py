r"""Boolean-function generator for A Painter Ant (parameterized."""

from esolangs.tools.boolean.helpers import _validate_truth_table, instantiate

__all__ = ["a_painter_ant"]


# --- A Painter Ant (no-input.
# .
# Boolean generators for A.
# .
# A Painter Ant is a single ant.
# (all black to start).
# that direction only if the.
# ``W`` move only if the.
# cell black/white.
# instruction the pointer.
# .
# The wiki defines no I/O, so.
# convention (like.
# carries ``{X0}`` and ``{X1}``.
# :func:`instantiate` fills.
# **colour of the cell the ant.
# black is zero), read by a.
# is the visited-cell bounding.
# .
# The construction paints the.
# leaf for its inputs.
# and returns to the origin;.
# table entry and left.
# zero.
# so the white cells are.
# every later cycle only.
# cycle-stable.
# ends cycle 2 at) to a.
# embedding does the last.
# .
# The head is built.
# the axes (the final input on.
# ``0``) and the cycle-2 ant.
# ``docs/generators/a_painter_an.
# the leaves sit on one row ``y.
# apart so adjacent stars share.
# y-axis.
# just the three above -- XOR.
# through ``n == 7`` (34788.
# not a ceiling.
# .
# The template routes the first.
# for a one bit, east/south for.
# east/west after it.
# zero, an 8-character.
# leaf).
# program is a cycle-stable.
# any whole number of cycles).

# ``{XF}``: the final.
_XF = {1: "WWwWWEEe", 0: "NENEESWw"}
# The inverse of each move.
_OPP = {
    "n": "s",
    "s": "n",
    "e": "w",
    "w": "e",
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
}


def _bit_is_horizontal(n: int, k: int) -> bool:
    r"""Return whether bit ``k`` (of ``n``, most-significant first) moves."""
    return k % 2 != n % 2


def _bit_move(n: int, k: int, bit: int) -> str:
    r"""Return the moves that input bit ``k`` contributes."""
    mag: int = 2 ** (n - k)
    if _bit_is_horizontal(n, k):
        return ("w" if bit else "e") * mag
    return ("n" if bit else "s") * mag


def _reverse_moves(moves: str) -> str:
    r"""Return ``moves`` reversed with every direction inverted."""
    return "".join(_OPP[c] for c in reversed(moves))


def _leaf_color(truth_table: str, bits: list[int]) -> bool:
    r"""Return whether to paint the leaf for the input ``bits``."""
    index = 0
    for n, b in enumerate(bits):
        index += b << (len(bits) - n - 1)
    return truth_table[index] == "1"


def _leaf_positions(n: int) -> list[tuple[int, int, tuple[int, ...]]]:
    r"""Return ``(x, y, bits)`` for every leaf in head-visit order."""
    out: list[tuple[int, int, tuple[int, ...]]] = []

    for i in range(2**n):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        x = 0
        y = 0

        for k, b in enumerate(bits):
            mag = 2 ** (n - k) if b else -(2 ** (n - k))
            if _bit_is_horizontal(n, k):
                x += mag
            else:
                y += mag

        out.append((x, y, tuple(bits)))

    return out


def _head(truth_table: str, bits: list[int]) -> str:
    r"""Build the A Painter Ant head for an ``n``-input table."""
    n = len(bits)
    out = ["N"]

    for _x, _y, leaf_bits in _leaf_positions(n):
        if not _leaf_color(truth_table, list(leaf_bits)):
            out.append(" ")
            continue
        # Odd n starts on a horizontal.
        # NE and the reverse path would.
        # leading WS (no moves) flips.
        outbound = "WS" if n >= 3 and n % 2 == 1 else ""
        outbound += "".join(
            (
                ("NE" if _bit_is_horizontal(n, k) else "WS") + _bit_move(n, k, b)
                if n >= 2
                else _bit_move(n, k, b)
            )
            for k, b in enumerate(leaf_bits)
        )
        out.append(outbound + "P" + _reverse_moves(outbound))

    out.append("Ssn")
    return "".join(out)


def _body() -> str:
    r"""Generate the routing body."""
    # West star, entered from the.
    # clockwise spiral (single ring.
    # cells, and blocked-uppercase.
    # the south-east diagonal.
    west = ("wP", "nP", "wnP", "EsP", "wP", "swP", "WWeP", "sP", "esP", "SSnP", "eP")
    # East (mirror) star, entered.
    # and walked clockwise to the.
    east = ("NNseP", "SSnP", "eP", "neP", "EEwP", "nP", "wnP", "NNsP", "wP", "sP", "wP")
    gap = 4 - 2  # star centres 4 apart; each.
    return "N" + "".join(west) + "e" * gap + "P" + "".join(east) + "S"


def a_painter_ant(truth_table: str) -> str:
    r"""Build an A Painter Ant template for an ``n``-input Boolean function."""
    n = _validate_truth_table(truth_table)

    # The head paints every leaf,.
    # n-1 inputs route by weight.
    # (least-significant) input.
    head = _head(truth_table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"

    return head + prefix + _body() + suffix


def _instantiate_apa(template: str, bits: list[int]) -> str:
    r"""Fill an A Painter Ant template's ``{Xi}`` placeholders."""
    n = len(bits)

    def replace(i: int, bit: int) -> str:
        if i == len(bits) - 1:
            return _XF[bit]
        return _bit_move(n, i, bit)

    return instantiate(
        template,
        bits,
        replace,
    )
