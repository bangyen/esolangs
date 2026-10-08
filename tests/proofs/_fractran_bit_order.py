"""Packed-counter selector; counts bit accesses, excluding metadata and addressing."""


class BitAvailable:
    def __init__(self, size: int) -> None:
        self.size = size
        self.remaining = size
        self.storage_bits = 2 * size - size.bit_count()
        self.cells = bytearray((self.storage_bits + 7) // 8)
        self.widths = [0, *((i & -i).bit_length() for i in range(1, size + 1))]
        self.reads = dict.fromkeys(("compare", "subtract", "decrement"), 0)
        self.writes = dict.fromkeys(("subtract", "decrement"), 0)
        self.locations = 0
        for index in range(1, size + 1):
            position = self._locate(index) + self.widths[index] - 1
            self.cells[position // 8] |= 1 << (position % 8)

    def _locate(self, index: int) -> int:
        self.locations += 1
        return 2 * (index - 1) - (index - 1).bit_count()

    def _read(self, data: bytearray, position: int, phase: str) -> int:
        self.reads[phase] += 1
        return (data[position // 8] >> (position % 8)) & 1

    def _write(self, data: bytearray, position: int, value: int, phase: str) -> None:
        self.writes[phase] += 1
        mask = 1 << (position % 8)
        if value:
            data[position // 8] |= mask
        else:
            data[position // 8] &= ~mask

    def _le(self, rank: bytearray, rank_width: int, offset: int, width: int) -> bool:
        if width != rank_width:
            return width < rank_width
        for position in range(width - 2, -1, -1):
            left = self._read(self.cells, offset + position, "compare")
            right = self._read(rank, position, "compare")
            if left != right:
                return left < right
        return True

    def _subtract(
        self, rank: bytearray, rank_width: int, offset: int, width: int
    ) -> int:
        borrow = 0
        for position in range(width):
            left = self._read(rank, position, "subtract")
            right = self._read(self.cells, offset + position, "subtract")
            value = left - right - borrow
            self._write(rank, position, value & 1, "subtract")
            borrow = int(value < 0)
        position = width
        while borrow:
            assert position < self.size.bit_length()
            left = self._read(rank, position, "subtract")
            self._write(rank, position, left ^ 1, "subtract")
            borrow = 1 - left
            position += 1
        while rank_width and not self._read(rank, rank_width - 1, "subtract"):
            rank_width -= 1
        return rank_width

    def _decrement(self, index: int) -> None:
        offset = self._locate(index)
        width = self.widths[index]
        position = 0
        while not self._read(self.cells, offset + position, "decrement"):
            self._write(self.cells, offset + position, 1, "decrement")
            position += 1
            assert position < width
        self._write(self.cells, offset + position, 0, "decrement")
        if position == width - 1:
            self.widths[index] -= 1

    def pop(self, rank: int) -> int:
        assert 0 <= rank < self.remaining
        limit = self.size.bit_length()
        bits = bytearray(rank.to_bytes((limit + 7) // 8, "little"))
        rank_width = rank.bit_length()
        index = 0
        bit = 1 << (limit - 1)
        while bit:
            candidate = index + bit
            if candidate <= self.size:
                offset = self._locate(candidate)
                width = self.widths[candidate]
                if self._le(bits, rank_width, offset, width):
                    rank_width = self._subtract(bits, rank_width, offset, width)
                    index = candidate
            bit >>= 1
        position = index + 1
        while position <= self.size:
            self._decrement(position)
            position += position & -position
        self.remaining -= 1
        return index
