"""Boolean-function generators for languages in the ``other`` category."""

from collections import deque

__all__ = ["nevermind", "taglate", "three_x"]

_ZERO = "333x"  # (3-3)//3 = 0
_ONE = "3333x3x"  # (3-0)//3 = 1

# Minimal 3x programs pushing each small integer onto a clean stack, found by
# a breadth-first search over the operations {3, x, #} (see _fill_minimal).
# Seeded with the hand-verified 0/1/3 encodings; _const() extends the search
# lazily and falls back to a general recurrence for integers it cannot reach.
_CONST: dict[int, str] = {0: _ZERO, 1: _ONE, 3: "3"}

# BFS safety bounds: programs are explored only to this length and through
# stacks of at most this depth holding values of at most this magnitude.  The
# search is monotone in these caps (verified: widening them does not shorten
# any encoding), so within the bounds the results are genuinely minimal.
_BFS_LEN, _BFS_DEPTH, _BFS_VALUE = 52, 8, 100
_BFS_DONE = False


def _fill_minimal() -> None:
    """Populate ``_CONST`` with the shortest clean-stack encodings reachable.

    A program over ``{3, x, #}`` is a stack machine: ``3`` pushes 3, ``x``
    replaces the top three items ``a, b, c`` (c on top) with ``(c-b)//a``,
    and ``#`` swaps the top two.  BFS from the empty stack finds, in length
    order, every single-value state ``(n,)``; the first time one is reached
    is its shortest program.  Runs at most once per process.
    """
    global _BFS_DONE
    if _BFS_DONE:
        return
    _BFS_DONE = True
    queue: deque[tuple[tuple[int, ...], str]] = deque([((), "")])
    seen: set[tuple[int, ...]] = {()}
    while queue:
        state, prog = queue.popleft()
        if len(state) == 1:
            _CONST.setdefault(state[0], prog)
        if len(prog) >= _BFS_LEN:
            continue
        pushed = (*state, 3)
        if len(pushed) <= _BFS_DEPTH and pushed not in seen:
            seen.add(pushed)
            queue.append((pushed, prog + "3"))
        if len(state) >= 2:
            swapped = (*state[:-2], state[-1], state[-2])
            if swapped not in seen:
                seen.add(swapped)
                queue.append((swapped, prog + "#"))
        if len(state) >= 3:
            a, b, c = state[-3], state[-2], state[-1]
            if a and (c - b) % a == 0:
                reduced = (*state[:-3], (c - b) // a)
                if abs(reduced[-1]) <= _BFS_VALUE and reduced not in seen:
                    seen.add(reduced)
                    queue.append((reduced, prog + "x"))


def _const(n: int) -> str:
    """3x code pushing ``n`` on a clean stack, for any integer ``n``.

    Small integers use the BFS-minimal program from ``_CONST``; integers the
    search cannot reach (or would only reach through values outside the BFS
    bounds) are built from the smaller ``n-3``: all nonnegative integers are
    reachable from 3 and 0 via ``(A-B)//C``, as ``n = (3 - (-(n-3))) // 1``,
    where ``-(n-3) = (0 - (n-3)) // 1``.
    """
    if n not in _CONST:
        _fill_minimal()
        if n not in _CONST:
            _CONST[n] = (
                _const(n - 3) + _ONE + "#" + _ZERO + "x" + _ONE + "#" + "3" + "x"
            )
    return _CONST[n]


def three_x(truth_table: str, n: int) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    3x reads an integer with ``?`` and has no direct boolean literals or
    conditionals, so the generator builds a decision tree with variables:

    - each ``?`` reads one input bit and stores it in a variable (the
      cheapest names after 0 and 3);
    - a ``( ... )`` loop runs while its guard is nonzero: the guard value is
      popped into a trash variable (0), the body stores the table entry into
      the result variable (3), and a sentinel zero exits the loop.

    The result variable defaults to the majority table value (so the
    ``( ... )`` loop emits no override at all when every row matches), and
    only the input combinations whose table entry differs from the default
    get an override block.  Each override's ``( ... )`` guard leaves the
    stack balanced via the trash pop, so arbitrary ``n`` works.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    # Variable allocation: var 0 is the loop-trash (its constant, 333x, is
    # short and emitted twice per guard), var 3 is the result (its constant
    # is the single char `3`, emitted once per table entry), and the inputs
    # live in the cheapest remaining names by actual constant length (the
    # encodings are non-monotonic: 6 is cheaper than 5).  Every input is read
    # once per override block, so any assignment of the n cheapest names to
    # the inputs costs the same.
    trash = _const(0) + "#v"  # pop the stack top into variable 0
    result = 3
    used = {0, 3}
    input_vars = sorted(
        (v for v in range(3 + n) if v not in used),
        key=lambda v: len(_const(v)),
    )[:n]

    def store(var: int) -> str:
        return _const(var) + "#v"  # var = stack top, stack ends empty

    def read(var: int) -> str:
        return _const(var) + "^"

    def not_bit() -> str:
        return _ONE + "#" + _ONE + "x"  # from [b] leave [1-b]

    def guard(i: int, body: str) -> str:
        """If bit i is 1, run ``body``; leaves the stack balanced."""
        return read(i) + "(" + trash + body + _ZERO + ")" + trash

    def guard_not(i: int, body: str) -> str:
        """If bit i is 0, run ``body``; leaves the stack balanced."""
        return read(i) + not_bit() + "(" + trash + body + _ZERO + ")" + trash

    prog = "".join("?" + store(v) for v in input_vars)

    # Default the result to the majority value so only the minority rows
    # need an override block (combos matching the default are skipped).
    default = "1" if truth_table.count("1") >= truth_table.count("0") else "0"
    prog += (_ONE if default == "1" else _ZERO) + store(result)

    for combo in range(2**n):
        if truth_table[combo] == default:
            continue
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        body = (_ONE if truth_table[combo] == "1" else _ZERO) + store(result)
        for i in range(n - 1, -1, -1):
            body = (
                guard(input_vars[i], body)
                if bits[i]
                else guard_not(input_vars[i], body)
            )
        prog += body

    prog += read(result) + "!"
    return prog


def nevermind(truth_table: str, n: int) -> str:
    """Build a Nevermind program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Nevermind reads each input with ``input,?`` into its own variable, then a
    decision tree of nested ``if``/``endif`` blocks prints the result for the
    matching combination.
    """
    lines: list[str] = []
    for i in range(n):
        lines.append("input,?")
        lines.append(f"make,{chr(ord('a') + i)},$answer")

    def build(k: int, row: int) -> None:
        if k == n:
            lines.append(f"print,{truth_table[row]}")
            return
        for bit in (0, 1):
            lines.append(f"if,${chr(ord('a') + k)},==,{bit}")
            build(k + 1, row * 2 + bit)
            lines.append("endif")

    build(0, 0)
    return "\n".join(lines)


def _reorder_tt(tt: str, n: int) -> str:
    """Reorder truth table entries into the slot order the reduces expect.

    Each entry sits in a value slot ``[0, s_i, 0, s_j, ...]``; an even
    reduce must be able to drop an entire contiguous run of slots without
    splitting a pair.  Sorting the input index ``i`` by ``(-(i >> 1),
    i & 1)`` puts the 1-group of the current input first, then the 0-group,
    with the two sub-cases of the next input adjacent inside each group.
    Odd-reduce levels (which branch the other way) then re-apply the same
    ordering, so the sort key serves both.
    """
    indices = sorted(range(2**n), key=lambda i: (-(i >> 1), i & 1))
    return "".join(tt[i] for i in indices)


def _even_reduce(pairs: int, level: int, n: int) -> str:
    """Even-reduction block: select half the value pairs, keep all inputs.

    The queue holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then
    two 48s, then the ``n`` input chars.  The ``rot`` rotation brings the
    next input to the front; ``gy ... gz`` branches on it so the ``e^pairs``
    strides past the half of the value slots the input rejects; ``e^ahead``
    skips the untouched half and ``f^pairs`` drops it.  Every input stays on
    the queue, so the level that follows still sees all ``n`` of them.
    """
    processed = level
    ahead = n - level
    total = n
    rot = 2 * pairs + 2 + processed
    return (
        "e" * rot
        + "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )


# Final odd-reduce block: the committed n==2 pattern.  Given the 8-cell
# queue [0, v0, 0, v1, 48, 48, prev, curr] (v0/v1 the two candidate values,
# prev/curr the two remaining inputs), it rotates curr and prev to the front,
# drops the candidate the inputs reject, adds the surviving value to one of
# the two 48s (48 + bit), and prints it with ``i``.
_SEL1_N2: str = (
    "e" * 7
    + "gy"
    + "e" * 3
    + "gz"
    + "e" * 3
    + "gy"
    + "e" * 3
    + "gz"
    + "ff"
    + "gy"
    + "e" * 4
    + "gz"
    + "e"
    + "a"
    + "e" * 4
    + "i"
)


def _build_padded_tt(truth_table: str, n_effective: int) -> str:
    """Pad a ``2**(n_effective - 1)``-entry truth table to ``n_effective`` bits.

    Odd ``n`` is computed with ``n_effective = n + 1`` inputs whose leading
    (ghost) digit is always 0.  The real table covers the ghost=0 half; the
    entries the ghost=1 would select are padded with 0 so the never-taken
    rows stay harmless.
    """
    half = 2 ** (n_effective - 1)
    return truth_table.ljust(half * 2, "0")


def _validate_tt(truth_table: str, n: int) -> None:
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def _odd_reduce(pairs: int, level: int, n: int) -> str:
    """Odd-reduction block: retire one input, reduce, keep the rest.

    ``level`` is the 0-based reduce level (odd here: 1, 3, ...).  The queue
    holds ``2*pairs`` value slots ``[0, s0, 0, s1, ...]``, then two 48s,
    then the ``n`` input chars.  Unlike the even reduce, the odd level
    branches on a *retired* (previous) input whose bit has already been
    used, so ``e^rot`` brings that input to the front and the block runs
    ``zero`` (``gy j e^(qlen-1) gz``) to fold it away, ``swap`` (``e gy j
    e^(qlen-2) j gz``) to encode the current input as the ghost cell the
    even-reduce branches on, and ``bring`` (``e^(qlen-1)``) to put the
    value slots back at the front before ``er`` runs the even-reduce body.

    The ZS adds an extra ghost cell at the front, so the even-reduce body
    uses ``ahead = n - level + 1`` instead of ``n - level``.  No input is
    popped; the final ``f^pairs`` in ``er`` drops only the rejected value
    slots.
    """
    processed = level
    ahead = n - level + 1  # +1 for the ghost cell added by the swap
    total = n
    qlen = 2 * pairs + 2 + total
    rot = 2 * pairs + 2 + (processed - 1) if processed > 0 else 0
    zero = "gy" + "j" + "e" * (qlen - 1) + "gz"
    swap = "e" + "gy" + "j" + "e" * (qlen - 2) + "j" + "gz"
    bring = "e" * (qlen - 1)
    er = (
        "gy"
        + "e" * pairs
        + "gz"
        + "e" * ahead
        + "f" * pairs
        + "gy"
        + "e" * (total + 2)
        + "gz"
    )
    return "e" * rot + zero + swap + bring + er


def taglate(truth_table: str, n: int) -> str:
    r"""Build a Taglate program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    ``n == 1`` reads the single input with ``h`` and computes the affine
    combination ``base + bit * coeff`` with the ``b``/``c``/``a`` queue
    arithmetic, then prints it.

    For ``n >= 2`` the program is ``seed\\n<commands>``.  The seed holds
    ``n_effective`` literal ``'1'``s (``n_effective - 1`` leading, one
    trailing) around a run of ``'0'``s; the prefix of ``h``/``e``/``b``/
    ``d``/``j`` commands reads ``n_effective`` inputs and interleaves the
    (reordered) truth-table bits into ``[0, s0, 0, s1, 0, s2, ...]`` value
    slots, followed by two 48s and the inputs.  Odd ``n`` prepends a fake
    zero input (ghost digit) so the slot stride lands on a separator, and
    pads the table to ``n_effective = n + 1`` inputs.

    The command list alternates even-reduce blocks (select half the
    value slots on an input bit, keep all inputs) and odd-reduce blocks
    (retire the previous input, swap the current one in, even-reduce).
    Neither reduce pops inputs; ``e^6 f^(n_effective - 2) e^2`` reshapes
    the queue into the 8-cell ``[0, v0, 0, v1, 48, 48, prev, curr]``
    layout, and ``_SEL1_N2`` selects between the last two candidate
    values on the two remaining inputs and prints ``48 + bit``.
    """
    if n == 1:
        _validate_tt(truth_table, n)
        base = 48 + int(truth_table[0])
        coeff = (int(truth_table[1]) - int(truth_table[0])) % 65536
        seed = "0" + chr(coeff) + chr(base)
        return seed + "\n" + "h" + "e" * 3 + "b" + "e" * 2 + "ca" + "i"

    _validate_tt(truth_table, n)

    # For odd n, prepend a fake zero-input (ghost) to make the stride land
    # on a separator.  n_effective is the number of h-reads and levels.
    if n % 2 == 1 and n > 1:
        n_eff = n + 1
        full_tt = _build_padded_tt(truth_table, n_eff)
    else:
        n_eff = n
        full_tt = truth_table

    seed = "1" * (n_eff - 1) + "0" * (2 ** (n_eff + 2) + 2) + "1"

    ordered = _reorder_tt(full_tt, n_eff)
    selectors = "".join("bd" if c == "1" else "bb" for c in ordered)

    prefix = (
        "he" * (n_eff - 1)
        + "h"
        + selectors
        + "ee"
        + "b" * n_eff
        + "e" * (2 ** (n_eff + 1) + 2)
        + "j" * n_eff
    )

    select_parts: list[str] = []
    for level in range(n_eff - 1):
        pairs = 2 ** (n_eff - level)
        if level % 2 == 0:
            select_parts.append(_even_reduce(pairs, level, n_eff))
        else:
            select_parts.append(_odd_reduce(pairs, level, n_eff))

    if n_eff > 2:
        # Drop the first n_eff-2 already-used inputs, then rotate the
        # remaining two inputs so the queue matches the 8-cell [0, w0, 0,
        # w1, 48, 48, prev, curr] layout that the committed n=2 odd
        # selector (_SEL1_N2) expects.
        select_parts.append("e" * 6 + "f" * (n_eff - 2) + "e" * 2)
    select_parts.append(_SEL1_N2)

    result: str = seed + "\n" + prefix + "".join(select_parts)
    return result
