"""Leftmost free circuit columns in logarithmic time."""


class _FreeColumns:
    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.size = 1
        self.tree = [False, False]

    def add(self, column: int) -> None:
        if column < 0:
            raise ValueError("column must be nonnegative")
        if column >= self.size:
            old_size, old = self.size, self.tree
            while column >= self.size:
                self.size *= 2
            self.tree = [False] * (2 * self.size)
            self.tree[self.size : self.size + old_size] = old[old_size:]
            for node in range(self.size - 1, 0, -1):
                self.tree[node] = self.tree[2 * node] or self.tree[2 * node + 1]
        self._set(column, free=True)

    def _set(self, column: int, *, free: bool) -> None:
        node = self.size + column
        self.tree[node] = free
        while node > 1:
            node //= 2
            self.tree[node] = self.tree[2 * node] or self.tree[2 * node + 1]

    def discard(self, column: int) -> None:
        if 0 <= column < self.size:
            self._set(column, free=False)

    def first_after(self, threshold: int) -> int | None:
        def visit(node: int, lo: int, hi: int) -> int | None:
            if not self.tree[node] or hi <= threshold + 1:
                return None
            if hi - lo == 1:
                return lo
            mid = (lo + hi) // 2
            left = visit(2 * node, lo, mid)
            return visit(2 * node + 1, mid, hi) if left is None else left

        return visit(1, 0, self.size)
