"""
WII2D (Why Is It 2D?) interpreter implementation.

2D esoteric language inspired by Befunge.
Pointer moves on a 2D grid with wrap-around behavior and an accumulator.
"""

import copy
import secrets
import sys
from typing import Callable, List, Optional, Tuple


def init(code: List[str]) -> Callable[[int, int, int], Tuple[int, int]]:
    """Initialize movement function for WII2D grid navigation."""
    n = len(code)
    m = len(code[0])
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # North, South, West, East

    def move(x: int, y: int, vel: int) -> Tuple[int, int]:
        dx, dy = directions[vel]
        x = (x + dx) % n
        y = (y + dy) % m
        return x, y

    return move


def close(code: List[str]) -> Callable[[int, int], Optional[Tuple[int, int]]]:
    """Create a function to find the closest @ command for jump operations."""

    def start(x: int, y: int) -> Callable[[Tuple[int, int]], int]:
        """Create a distance function for sorting @ positions."""

        def dist(c: Tuple[int, int]) -> int:
            return abs(c[0] - x) + abs(c[1] - y)

        return dist

    # Find all @ positions (excluding the first row)
    at_positions = []
    for row_idx, row in enumerate(code):
        for col_idx, char in enumerate(row):
            if row_idx > 0 and char == "@":
                at_positions.append((row_idx, col_idx))

    def find(x: int, y: int) -> Optional[Tuple[int, int]]:
        """Find the closest @ position to the given coordinates."""
        positions = copy.deepcopy(at_positions)
        positions.sort(key=start(x, y))
        current_pos = (x, y)
        if current_pos in positions:
            positions.remove(current_pos)
        return positions[0] if positions else None

    return find


def update(op: str, acc: int) -> int:
    """Update the accumulator based on the current operation."""
    if op.isdigit():
        return int(op)
    elif op == "+":
        return acc + 1
    elif op == "-":
        return acc - 1
    elif op == "*":
        return acc * 2
    elif op == "/":
        return acc // 2
    elif op == "s":
        return acc**2
    elif op == "~":
        print(chr(acc), end="")
    return acc


def run(code: List[str]) -> None:
    """Execute a WII2D program."""
    # Find the start marker (!)
    for row_idx, row in enumerate(code):
        if "!" in row:
            x, y = row_idx, row.find("!")
            break
    else:
        return  # No start marker found

    # Normalize code grid to uniform width
    max_width = max(len(row) for row in code)
    code = [row.ljust(max_width) for row in code]

    # Initialize helper functions
    find_closest_at = close(code)
    move_pointer = init(code)

    # Start above the ! marker, moving northward
    x -= 1
    vel = 0  # 0 = north, 1 = south, 2 = west, 3 = east
    acc = 0  # Accumulator

    while True:
        op = code[x][y]

        # Movement commands
        if op in "^v<>":
            vel = "^v<>".index(op)
        # Random direction
        elif op == "?":
            vel = secrets.randbelow(4)
        # Reverse direction
        elif op == "|":
            if vel % 2:  # If moving vertically
                vel -= 1
            else:  # If moving horizontally
                vel += 1
        # Jump to closest @
        elif op == "@":
            if target := find_closest_at(x, y):
                x, y = target
                x -= 1  # Move to position above the @
                continue
        # Halt program
        elif op == ".":
            return

        # Update accumulator and move
        acc = update(op, acc)
        x, y = move_pointer(x, y, vel)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
