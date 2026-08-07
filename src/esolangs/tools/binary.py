import sys
from collections.abc import Callable
from inspect import signature

# Dig blocks for one level of the decision tree.
BRANCH = ">2$~;#@"  # read a bit, store it, then turn on it
CONTINUE = "> "  # a child of a branch: keep facing right into its own block
LEAF = ">$3{}:@"  # set the mole to the result and print it


def convert(func: Callable[..., int], num: int | None = None) -> str:
    """Build a Dig decision tree that computes ``func`` over ``num`` inputs.

    The tree is laid out so the mole starts in the top-left corner (``'``)
    facing down into the root.  Each ``BRANCH`` block reads one input bit:
    ``~`` inputs it, ``;`` stores it in the grid, and ``#`` turns the mole
    down or up on that bit.  The two children of a node keep facing right
    (``CONTINUE``) into the next level's ``BRANCH``, and the leaves print the
    function's value for the input combination they stand for.
    """
    if num is None:
        num = len(signature(func).parameters)
    total = 2 ** (num + 1) - 1
    lines = ["" for _ in range(total)]
    rows = [total // 2]

    for level in range(num + 1):
        if level < num:
            step = 2 ** (num - level - 1)
            children = [row + step for row in rows] + [row - step for row in rows]
            for row in range(total):
                if row in rows:
                    block = BRANCH
                elif row in children:
                    # the mole arrives here vertically from the parent's "#";
                    # right-justify the turn so the ">" sits under that "#"
                    block = CONTINUE.rjust(len(BRANCH))
                else:
                    block = " " * len(BRANCH)
                lines[row] += block
            rows = children
        else:
            for k in range(2**num):
                bits = [(k >> (num - 1 - b)) & 1 for b in range(num)]
                lines[2 * k] += LEAF.format(func(*bits))

    # the mole starts at the top-left corner facing down into the root
    lines[0] = "'" + lines[0][1:]
    return "\n".join(lines)


def main() -> None:
    """Generate a Dig program for the boolean function given as a truth table."""
    if len(sys.argv) < 2:
        print("usage: python -m esolangs.tools.binary <truth table>")
        print("example: python -m esolangs.tools.binary 0111  # 2-input OR gate")
        sys.exit(1)

    table = sys.argv[1]
    num = len(table).bit_length() - 1
    if 2**num != len(table):
        print("error: truth table length must be a power of 2")
        sys.exit(1)

    bits = [int(c) for c in table]

    def fn(*args: bool) -> int:
        index = 0
        for arg in args:
            index = index * 2 + int(arg)
        return bits[index]

    print(convert(fn, num))


if __name__ == "__main__":
    main()
