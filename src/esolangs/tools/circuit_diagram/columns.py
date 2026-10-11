"""Successor allocation of recycled columns through a Fenwick tree."""


class _FreeColumns:
    def __init__(self) -> None:
        self._values = [0]
        self._tree = [0, 0]
        self._count = 0

    def clear(self) -> None:
        self._values = [0]
        self._tree = [0, 0]
        self._count = 0

    def _update(self, column: int, delta: int) -> None:
        self._values[column] += delta
        self._count += delta
        index = column + 1
        while index < len(self._tree):
            self._tree[index] += delta
            index += index & -index

    def add(self, column: int) -> None:
        """Release a column in O(log width) amortized work."""
        if column >= len(self._values):
            capacity = len(self._values)
            while capacity <= column:
                capacity *= 2
            self._values.extend([0] * (capacity - len(self._values)))
            self._tree = [0, *self._values]
            for index in range(1, capacity + 1):
                parent = index + (index & -index)
                if parent <= capacity:
                    self._tree[parent] += self._tree[index]
        if self._values[column]:
            raise AssertionError("column released twice")
        self._update(column, 1)

    def first_after(self, column: int) -> int | None:
        """Return the least free column strictly greater than ``column``."""
        index = max(0, min(column + 1, len(self._values)))
        before = 0
        while index:
            before += self._tree[index]
            index -= index & -index
        if before == self._count:
            return None
        rank = before + 1
        step = len(self._values)
        while step:
            target = index + step
            if target < len(self._tree) and self._tree[target] < rank:
                index = target
                rank -= self._tree[target]
            step //= 2
        return index

    def take_after(self, column: int) -> int | None:
        """Remove and return the next free column, if one exists."""
        result = self.first_after(column)
        if result is not None:
            self._update(result, -1)
        return result
