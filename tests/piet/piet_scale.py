"""Find the largest uniform square tiling by testing dimension divisors."""


def normalize(rows, factor=None):
    height = len(rows)
    width = len(rows[0])

    def uniform(size):
        if height % size or width % size:
            return False
        return all(
            rows[y + dy][x + dx] == rows[y][x]
            for y in range(0, height, size)
            for x in range(0, width, size)
            for dy in range(size)
            for dx in range(size)
        )

    if factor is None:
        factor = next(
            size
            for size in range(min(height, width), 0, -1)
            if height % size == 0 and width % size == 0 and uniform(size)
        )
    elif type(factor) is not int or factor <= 0 or (not uniform(factor)):
        raise ValueError("invalid codel scale")
    return (
        tuple(
            tuple(rows[y][x] for x in range(0, width, factor))
            for y in range(0, height, factor)
        ),
        factor,
    )
