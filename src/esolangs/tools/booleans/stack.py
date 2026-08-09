"""Boolean-function generators for stack-based languages."""


def modulous(truth_table: str, n: int) -> str:
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """

    def build(S: list[int], k: int) -> str:
        if len(S) == 1:
            return f"[PSH INT {truth_table[S[0]]}][PRT INT][END]"
        g0 = [r for r in S if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in S if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)


def _bfstack_encoder(n: int) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    Each input is read with ``,`` and normalized to 0/1 with 48 ``-``s; if it
    is one, ``[<+w>]`` adds its weight ``w`` to the accumulator below it.
    The ``+1`` offset keeps the result nonzero so the decoder's outer ``[``
    always runs (a ``0`` result would be ambiguous with a skipped loop).
    """
    prog = ">>+"  # result cell (0) below the accumulator (1)
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * 48 + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_decoder(truth_table: str) -> str:
    """BFStack code mapping the encoded number to the table's result.

    The output is 1 for every input except the rows where the table is 0.
    Each such row maps to a distinct value of the ``+1``-offset number, so the
    decoder tests them by cumulative subtraction: ``[`` opens a ``while`` that
    only reaches the inner ``[<+>]`` (setting the result to 1) when the number
    survives every subtraction; hitting a zero row's value subtracts to 0 and
    skips the ``[<+>]`` instead, leaving the result 0.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    if not zeros:
        return "[<+>]"  # always 1
    prog = "["
    prev = 0
    for z in zeros:
        prog += "-" * (z - prev) + "["
        prev = z
    prog += "[<+>]"
    prog += "]" * (len(zeros) + 1)
    return prog


def bfstack(truth_table: str, n: int) -> str:
    """Build a BFStack program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    BFStack is a pure stack machine, so the generator avoids branching
    entirely: it encodes the n inputs as the number ``1 + sum(bit*2^k)``
    (each ``,`` reads and normalizes a bit, ``[<+w>]`` adds its weight), then
    decodes it with nested ``[`` loops that only set the result to 1 when the
    number is not one of the table's zero rows.
    """
    return _bfstack_encoder(n) + _bfstack_decoder(truth_table) + "<" + "+" * 48 + "."
