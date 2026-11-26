"""Measure and rank rectangular text layouts."""


def grid_width(program: str) -> int:
    """Return the widest rendered row, including its padding."""
    return max(map(len, program.split("\n")))


def grid_area(program: str) -> int:
    """Return the cells of the program's bounding rectangle."""
    return grid_width(program) * (program.count("\n") + 1)


def grid_rank(program: str) -> tuple[int, int]:
    """Rank a 2D grid by area, then characters: grids are judged by area."""
    return grid_area(program), len(program)


def narrowest_grid(*candidates: str) -> str:
    """Return the narrowest layout, keeping the earlier one on a tie."""
    return min(candidates, key=grid_width)
