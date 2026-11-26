"""Store one Alight call frame and its pending expression."""

from esolangs.languages.alight.interpreter._parse import _Expr, _Value


class _Walker:
    """One walk in progress: where it is, what it can see, and its call.

    A call is a *separate walk* with its own pointer and namespace, so the
    Evil Hack -- a function's code sharing cells with the caller's -- needs
    nothing special: each walker reads the cell in its own direction.

    ``pending`` is the current command's expression with already-returned
    calls rewritten into it as literals; ``returned`` is the value a
    just-finished callee hands back.  Together they let a call inside an
    expression suspend: the command is re-entered once per call it
    contains, each time with one more resolved.

    The grid is not here: no command writes to the program.  ``vars`` is
    frozen to an alias-preserving graph by :func:`_freeze` before a snapshot
    stores it, since lists can be aliased and a live reference would let a
    later command mutate a snapshot the cycle detector already banked.
    """

    __slots__ = ("col", "heading", "pending", "returned", "row", "vars")

    def __init__(
        self,
        row: int,
        col: int,
        heading: tuple[int, int],
        variables: dict[str, "_Value"],
    ) -> None:
        self.row = row
        self.col = col
        self.heading = heading
        self.vars = variables
        self.pending: _Expr | None = None
        self.returned: _Value | None = None

    def key(self) -> tuple[object, ...]:
        """Return the walker fields for the shared snapshot graph."""
        return (
            self.row,
            self.col,
            self.heading,
            self.vars,
            self.pending,
            self.returned,
        )
