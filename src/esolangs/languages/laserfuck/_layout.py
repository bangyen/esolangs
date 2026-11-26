"""Orient and assemble Laserfuck drawing blocks."""

# The leftmost column code may use.  Columns 0..2 carry the funnel (``|o^``
# and the ``_`` beneath it), which every initial heading is routed through
# at startup, so code there would drop the beam back onto the funnel and
# start the program over.
MARGIN = 3


# Rotating or mirroring a LaserFuck block is a character substitution: the
# ops are direction-agnostic and only the mirrors and heading-setters carry
# an orientation.  Rotating a quarter turn clockwise turns a rightward beam
# into a downward one, which is how a block too wide for a width is made
# tall instead.
_LASER_ROTATE = str.maketrans(
    {
        "/": "\\",
        "\\": "/",
        "_": "|",
        "|": "_",
        "(": ")",
        ")": "(",
        "{": "^",
        "}": "v",
        "^": "}",
        "v": "{",
    }
)


def _laserfuck_rotate(rows: list[str]) -> list[str]:
    r"""Turn ``rows`` a quarter turn, so a rightward block becomes downward.

    Cells move as in any rotation (the last row becomes the first column)
    and are then substituted, since a mirror or heading-setter means
    something different once the beam runs the other way.  ``,``, ``+``,
    ``-``, ``<``, ``>``, ``#`` and ``x`` are unchanged: they act on the tape,
    not the beam.

    A reader laid flat is forty-odd columns by two rows; rotated, two columns
    by forty-odd rows, which meets a narrow width.
    """
    height = len(rows)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    return [
        "".join(padded[height - 1 - row][col] for row in range(height)).translate(
            _LASER_ROTATE
        )
        for col in range(width)
    ]


_LASER_FLIP_H = str.maketrans({"/": "\\", "\\": "/", "{": "}", "}": "{"})


def _laserfuck_flip(rows: list[str]) -> list[str]:
    r"""Mirror ``rows`` left to right, so a rightward block runs leftward.

    Like the rotation, this is a substitution: only the mirrors and the two
    horizontal heading-setters mean something different once the beam runs
    the other way, and the tape ops do not.  The rows are padded to a
    rectangle first, for the same reason -- a short row would mirror to a
    block whose cells no longer line up with the ones they pair with.
    """
    width = max(len(line) for line in rows)
    return [line.ljust(width)[::-1].translate(_LASER_FLIP_H) for line in rows]


def _laserfuck_join(marks: list[tuple[int, str]]) -> str:
    """Join ``(column, text)`` runs left to right, padding gaps with blanks."""
    parts: list[str] = []
    cursor = 0
    for col, text in marks:
        parts.append(" " * (col - cursor) + text)
        cursor = col + len(text)
    return "".join(parts)
