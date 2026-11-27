"""Bifunge Boolean generator with an alternating horizontal and vertical tree.

XOR-fold each essential ASCII digit and AND-fold each ignored digit to zero.
OR discards that zero without changing the previous bit. A leading ignored
digit leaves its explicit zero below the routing bits. The stack routes
the IP through the tree from the last input to the first. Each leaf writes
its answer byte and halts. Midpoint splits leave each subtree in its own
rectangle. The final split enters either leaf immediately. The tree area
is O(T), and the reader adds O(n√T) characters, also O(T). Each cell is
placed and rendered once.

Size:
    O(T) characters, n=4 parity: 4,487 chars.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.projection import input_weights
from esolangs.generation.requests import GenerationRequest
from esolangs.languages.bifunge._commands import Command
from esolangs.runtime._program import Program

_BYTE = (Command.INPUT,) * 8
_READ = _BYTE + (Command.XOR,) * 7
_DISCARD = _BYTE + (Command.AND,) * 7 + (Command.OR,)
_DIGITS = (Command.ZERO, Command.ONE)
_TAIL = (
    (
        Command.ZERO,
        Command.ZERO,
        Command.ZERO,
        Command.ONE,
        Command.ONE,
        Command.ZERO,
        Command.ZERO,
    )
    + (Command.OUTPUT,) * 8
    + (Command.HALT,)
)
_LEAF_LENGTH = 1 + len(_TAIL)
_TOP = tuple(f"{opcode >> 2:02b}" for opcode in range(16))
_BOTTOM = tuple(f"{opcode & 3:02b}" for opcode in range(16))


def _render(grid: list[bytearray]) -> str:
    return "\n".join(
        "".join(pairs[opcode] for opcode in row)
        for row in grid
        for pairs in (_TOP, _BOTTOM)
    )


def bifunge(truth_table: str) -> str:
    """Emit a loop-less playfield with one halting leaf per table row."""
    inputs = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, inputs)
    reader = bytearray(
        command for weight in weights for command in (_READ if weight else _DISCARD)
    )
    if not weights[0]:
        # No previous bit exists. Keep the explicit zero and the reader
        # length, which fixes the locations and distances of the branches.
        reader[len(_DISCARD) - 1] = Command.NOP
    n = len(table).bit_length() - 1
    if not n:
        reader.extend((_DIGITS[int(table[0])], *_TAIL))
        return _render([reader])

    # The last split and its two adjacent tails take 2 * _LEAF_LENGTH + 1
    # rows. One spare row lets each earlier vertical split double the span.
    x_radius = 1 << (n // 2)
    y_radius = (_LEAF_LENGTH + 1) << ((n - 1) // 2)
    prefix = len(reader)
    root_y = prefix + y_radius
    grid = [bytearray(2 * x_radius) for _ in range(prefix + 2 * y_radius)]
    # Approach the root across its split axis so the reader stays off both arms.
    reader_x = 0 if n % 2 else x_radius
    grid[0][reader_x] = Command.DOWN
    for y, command in enumerate(reader, 1):
        grid[y][reader_x] = command
    if n % 2:
        grid[root_y][0] = Command.RIGHT

    def place(
        x: int, y: int, rx: int, ry: int, depth: int, index: int, dx: int, dy: int
    ) -> None:
        if depth == n:
            for offset, opcode in enumerate((_DIGITS[int(table[index])], *_TAIL)):
                grid[y + offset * dy][x + offset * dx] = opcode
            return
        if (n - depth) % 2:
            grid[y][x] = Command.VERTICAL
            half = 1 if depth == n - 1 else ry // 2
            place(x, y + half, rx, half, depth + 1, index, 0, 1)
            place(x, y - half, rx, half, depth + 1, index | (1 << depth), 0, -1)
        else:
            grid[y][x] = Command.HORIZONTAL
            half = rx // 2
            place(x + half, y, half, ry, depth + 1, index, 1, 0)
            place(x - half, y, half, ry, depth + 1, index | (1 << depth), -1, 0)

    place(x_radius, root_y, x_radius, y_radius, 0, 0, 0, 1)
    return _render(grid)


def bifunge_request(request: GenerationRequest) -> Program:
    """Emit source through the registered Boolean backend."""
    return bifunge(request.table)
