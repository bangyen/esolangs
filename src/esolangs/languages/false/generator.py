"""FALSE Boolean generator: shared diagram, formula and 32-bit literal lookup.

The diagram reads along a reduced path; its leaves drain unread inputs before
printing. The formula and lookup read every input first, storing essential
bits and draining ignored ones. Formulas combine their bits with Boolean
operators or ``A x;[%B]?``; lookup selects a 32-bit chunk and multiplies the
wanted bit into its sign position. Both print a normalized answer digit.

Exact chosen formula residuals may share lambdas. Their keys retain ordered
input positions, and a command budget preserves the execution cap. Existing
diagram/formula routes protect structured classes, including linear parity;
the alphabet bounds both stored-input routes. See the 2026-11-02 ablations.

Size:
    O(n) for parity, O(T) for random tables; n=10 parity: 100 chars,
    n=10 random 1847: 604 chars.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from string import ascii_lowercase
from sys import maxsize
from typing import NamedTuple

from esolangs.generation.decision import decision_layers
from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _FALSE_COMMAND,
    _join_tokens,
    balance_score,
    wrap_program,
)

#: ``'0`` and ``'1`` differ in their low bit, so ``1&`` is the bit and ``?``
#: takes any nonzero flag; ``$`` leaves a copy under it for the ``0`` test.
_TEST_ONE = "^1&$["
_SKIP = "^%"
Key = tuple[int, int]  # (level, subtable id)


class _Fold(NamedTuple):
    """A node with equal halves: the one half, run bare."""

    child: Key


class _Split(NamedTuple):
    """A node over two different halves."""

    zero: Key
    one: Key


def false(truth_table: str, width: int | None = None) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` characters, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)
    program = _shared(truth_table, n)
    ess = essential_inputs(truth_table, n)
    # The expression build names its variables by input position, and
    # FALSE variables are a-z: past the alphabet it cannot be built.
    if ess and ess[-1] < len(ascii_lowercase):
        # The complement build trades 1 char (``~`` on the body) for the
        # cheap polarity of the combines, which favour a clear cofactor.
        for flip_out in (False, True):
            expression = _expression(truth_table, n, ess, flip_out=flip_out)
            if len(expression) < len(program):
                program = expression
        # [ablations.literal_lookup_build_trick_20261102]; existing routes
        # protect their structured classes, including linear parity.
        literal = _lookup(truth_table, n, ess)
        if len(literal) < len(program):
            program = literal
    if width is None:
        return program
    return wrap_program(program, "false", width)


#: A node around its two halves, whether written ``[...]`` or fetched ``x;``.
_OPEN, _BETWEEN, _CLOSE = _TEST_ONE[:-1], "?0=", "?"


def _shared(truth_table: str, n: int) -> str:
    """Return the tree with repeated halves stored in variables and fetched.

    A half is a lambda either way, so ``[text]`` becomes ``x;`` wherever it
    repeats and ``[text]x:`` runs once up front; ``?`` pops a fetched lambda
    as it does a written one, and the reads stay in the lambdas, in order.
    A half is keyed by (level, subtable id) -- a leaf's text depends on its
    level -- and stored bottom-up while its in-degree in the diagram pays for
    the store: ``k`` uses save ``k * len(text)`` against ``len(text) + 4``.
    Every use in the text is an edge of the diagram, so a store only gains.
    A node with equal halves drops its bit with ``^%`` and runs the half
    bare, fetched as ``x;!``; the read still happens where the tree had it.
    26 variables, handed out deepest first, cap the stores.
    """
    root, layers = decision_layers(truth_table)
    nodes: dict[Key, _Fold | _Split] = {}
    uses: dict[Key, int] = {}
    inner: dict[Key, int] = {}  # of those uses, the ones that are a body
    found: list[list[Key]] = [[] for _ in range(n + 1)]

    def use(child: Key, depth: int) -> None:
        if child not in uses:
            found[depth].append(child)
        uses[child] = uses.get(child, 0) + 1

    for depth, children in enumerate(layers):
        for node, (low, high) in children.items():
            key = (depth, node)
            if node < 2:
                continue  # constant leaves drain the remaining reads
            zero, one = (depth + 1, low), (depth + 1, high)
            if zero == one:  # the test changes nothing: drop the bit, run it
                nodes[key] = _Fold(zero)
                inner[zero] = inner.get(zero, 0) + 1
                use(zero, depth + 1)
                continue
            nodes[key] = _Split(zero, one)
            use(zero, depth + 1)
            use(one, depth + 1)

    sizes: dict[Key, int] = {}
    names: dict[Key, str] = {}
    free = iter(ascii_lowercase)

    def half_size(key: Key) -> int:
        return 2 if key in names else 2 + sizes[key]

    # Price bottom-up without copying each ancestor's full text.
    for key in (key for level in reversed(found) for key in level):
        level, node = key
        if node < 2:
            size = 2 * (n - level) + 2
        else:
            branch = nodes[key]
            if isinstance(branch, _Fold):
                child = branch.child
                size = 2 + (3 if child in names else sizes[child])
            else:
                zero, one = branch
                size = 8 + half_size(one) + half_size(zero)
        sizes[key] = size
        gain = uses[key] * size - 3 * inner.get(key, 0) - size - 4
        if gain > 0 and (name := next(free, None)):
            names[key] = name

    def render(key: Key) -> str:
        return _render_diagram(key, n, nodes, names)

    stores = "".join(
        "[" + render(key) + "]" + name + ":" for key, name in names.items()
    )
    return stores + _root_text((0, root), nodes, names, render, n)


def _render_diagram(
    key: Key, n: int, nodes: dict[Key, _Fold | _Split], names: dict[Key, str]
) -> str:
    """Emit one diagram body without materializing its ancestors."""
    output: list[str] = []

    def half(key: Key) -> None:
        if key in names:
            output.append(names[key] + ";")
        else:
            output.append("[")
            emit(key)
            output.append("]")

    def emit(key: Key) -> None:
        level, node = key
        if node < 2:
            output.append(_SKIP * (n - level) + str(node) + ".")
            return
        branch = nodes[key]
        if isinstance(branch, _Fold):
            child = branch.child
            output.append(_SKIP)
            if child in names:
                output.append(names[child] + ";!")
            else:
                emit(child)
        else:
            zero, one = branch
            output.append(_OPEN)
            half(one)
            output.append(_BETWEEN)
            half(zero)
            output.append(_CLOSE)

    emit(key)
    return "".join(output)


def _root_text(
    key: Key,
    nodes: dict[Key, _Fold | _Split],
    names: dict[Key, str],
    render: Callable[[Key], str],
    n: int,
) -> str:
    """Render the root, draining bare at the end of a fold chain.

    A leaf reached from the root through folds only is the
    last text the program runs, so it reads the remaining inputs with bare
    ``^`` instead of ``^%`` and then prints (a constant
    table: 2n+2 -> n+2, measured n = 2..8).  Under a split the same end
    stays stack-neutral: the split's ``?0=`` plumbing resumes above it
    and expects its bit back on top.
    """
    parts: list[str] = []
    while key[1] >= 2:
        node = nodes[key]
        if not isinstance(node, _Fold) or node.child in names:
            break
        parts.append(_SKIP)
        key = node.child
    level, sub = key
    parts.append("^" * (n - level) + str(sub) + "." if sub < 2 else render(key))
    return "".join(parts)


def _cofactor(table: str, j: int) -> tuple[str, str]:
    """Split ``table`` on its j-th remaining input (0 = MSB)."""
    rows = len(table)
    vars_left = rows.bit_length() - 1
    stride = 1 << (vars_left - 1 - j)
    zero = "".join(table[i : i + stride] for i in range(0, rows, 2 * stride))
    one = "".join(
        table[i + stride : i + 2 * stride] for i in range(0, rows, 2 * stride)
    )
    return zero, one


def _complement(table: str) -> str:
    return table.translate(str.maketrans("01", "10"))


def _splits(table: str, positions: tuple[int, ...]) -> range | tuple[int, ...]:
    """Split variables worth trying at this node.

    Trying every split variable is exponential in the number of
    distinct (subtable, split-set) states on random tables; it pays
    only where subtables are small or structured.  Above 512 rows
    split the first remaining variable (random tables are
    split-order-insensitive in expectation).
    """
    # Every state has 2**len(positions) rows.
    if len(table) <= 512:
        return range(len(positions))
    return (0,)


def _expression(
    truth_table: str,
    n: int,
    ess: list[int],
    *,
    flip_out: bool = False,
) -> str:
    """Return the expression-form build: stored inputs, a formula, a print.

    Each essential input is read, bit-extracted and stored
    (``^1&x:``, 5 chars); each remaining input is drained (``^%``,
    2 chars).  The body is a Boolean formula over the stored bits,
    built by memoized Shannon decomposition over the table projected
    onto its essential inputs: at each node the cheapest combine
    wins -- a dropped input when the halves agree, the xor collapse
    (``+b&``) for complementary halves, a one-char ``&`` or ``|``
    step when a cofactor is constant, else ``A x;[%B]?`` (six characters
    over the two halves).  Variable letters are
    the inputs' own positions.  In the combines a bare letter is a
    variable reference, whose integer is its index -- ``a`` is the
    constant 0 and ``b`` the constant 1 -- so ``+b&`` folds a
    fetch into a sum's parity.

    A formula may skip a conditional half, where the diagram executes one
    path; the race in :func:`false` keeps whichever text is shorter.
    The body's value can be -1 where the answer is 1 (a combine's
    true value), so ``1&`` masks it to the bit before ``.`` prints:
    +2 chars on every expression-form program.

    ``flip_out`` builds the complement and ends the body with ``~``, whose
    low bit is the complement's (``~0`` = -1, ``~1`` = -2, ``~-1`` = 0).
    """
    # Project the table onto its essential inputs, in original order.
    sub = read_at(truth_table, ess, n)
    if flip_out:
        sub = _complement(sub)
    letters = {pos: chr(ord("a") + pos) for pos in ess}

    search = _ExpressionSearch(letters)
    prologue = "".join(f"^1&{letters[i]}:" if i in letters else "^%" for i in range(n))
    budget = (
        (9 * (1 << n)) // 2 + 5 * n - 7 - len(prologue) - 3 - flip_out
        if n >= 3
        else None
    )
    return (
        prologue + search.text(sub, tuple(ess), budget=budget) + "~" * flip_out + "1&."
    )


_ExpressionKey = tuple[str, tuple[int, ...]]


def _formula_commands(
    nodes: dict[_ExpressionKey, tuple[str | _ExpressionKey, ...]],
    order: list[_ExpressionKey],
    names: dict[_ExpressionKey, str],
    root: _ExpressionKey,
) -> int:
    """A path-independent execution upper bound, including definition setup."""
    costs: dict[_ExpressionKey, int] = {}
    for key in order:
        costs[key] = sum(
            len(part) - part.count("]")
            if isinstance(part, str)
            else costs[part] + (3 if part in names else 0)
            for part in nodes[key]
        )
    return costs[root] + 3 * len(names)


class _ExpressionSearch:
    """One projected table's memoized Shannon decomposition.

    ``size`` prices each (subtable, remaining inputs) state once and
    ``text`` materialises the cheapest body over the same states.
    The caches live on the instance: one search serves one table
    and is dropped with it.
    """

    def __init__(self, letters: dict[int, str]) -> None:
        self._letters = letters
        self._sizes: dict[tuple[str, tuple[int, ...]], int] = {}

    def size(self, table: str, positions: tuple[int, ...]) -> int:
        """The cheapest body length for ``table`` over ``positions``."""
        key = (table, positions)
        if key not in self._sizes:
            self._sizes[key] = self._price(table, positions)
        return self._sizes[key]

    def _price(self, table: str, positions: tuple[int, ...]) -> int:
        if table == "0" * len(table) or table == "1" * len(table):
            return 1
        if len(positions) == 1:
            return 2 if table == "01" else 4  # fetch; or 1<fetch>-
        best = maxsize
        for j in _splits(table, positions):
            rest = positions[:j] + positions[j + 1 :]
            a, b = _cofactor(table, j)
            if a == b:
                best = min(best, self.size(a, rest))
                continue
            if b == _complement(a):
                best = min(best, self.size(a, rest) + 5)
            if a == "0" * len(a):
                best = min(best, self.size(b, rest) + 3)
            if b == "1" * len(b):
                best = min(best, self.size(a, rest) + 3)
            best = min(best, self.size(a, rest) + self.size(b, rest) + 6)
        return best

    def _parts(
        self, table: str, positions: tuple[int, ...]
    ) -> tuple[str | _ExpressionKey, ...]:
        """The first minimum-priced combine, without materializing alternatives."""
        parts: tuple[str | _ExpressionKey, ...]
        if len(set(table)) == 1:
            parts = (table[0],)
        elif len(positions) == 1:
            fetch = self._letters[positions[0]] + ";"
            parts = (fetch if table == "01" else "1" + fetch + "-",)
        else:
            options: list[tuple[int, tuple[str | _ExpressionKey, ...]]] = []
            for j in _splits(table, positions):
                rest = positions[:j] + positions[j + 1 :]
                a, b = _cofactor(table, j)
                ka, kb = (a, rest), (b, rest)
                fetch = self._letters[positions[j]] + ";"
                if a == b:
                    options.append((self.size(a, rest), (ka,)))
                    continue
                if b == _complement(a):
                    options.append((self.size(a, rest) + 5, (ka, fetch + "+b&")))
                if a == "0" * len(a):
                    options.append((self.size(b, rest) + 3, (kb, fetch + "&")))
                if b == "1" * len(b):
                    options.append((self.size(a, rest) + 3, (ka, fetch + "|")))
                options.append(
                    (
                        self.size(a, rest) + self.size(b, rest) + 6,
                        (ka, fetch + "[%", kb, "]?"),
                    )
                )
            parts = min(options, key=lambda option: option[0])[1]
        return parts

    def text(
        self, table: str, positions: tuple[int, ...], *, budget: int | None = None
    ) -> str:
        """Render the chosen formula, extracting identical residual subtrees.

        Keys retain ordered input positions; equal text alone is not a sharing
        test. A command budget preserves the inherited execution cap. Each
        accepted store needs one linear reprice, at most 26 times.
        """
        nodes: dict[_ExpressionKey, tuple[str | _ExpressionKey, ...]] = {}

        def plan(table: str, positions: tuple[int, ...]) -> _ExpressionKey:
            key = (table, positions)
            if key in nodes:
                return key
            parts = self._parts(table, positions)
            for part in parts:
                if not isinstance(part, str):
                    plan(*part)
            nodes[key] = parts
            return key

        root = plan(table, positions)
        order = sorted(nodes, key=lambda key: len(key[1]))
        names: dict[_ExpressionKey, str] = {}
        free = iter(c for c in ascii_lowercase if c not in self._letters.values())

        def lengths() -> dict[_ExpressionKey, int]:
            sizes: dict[_ExpressionKey, int] = {}
            for key in order:
                sizes[key] = sum(
                    len(part)
                    if isinstance(part, str)
                    else 3
                    if part in names
                    else sizes[part]
                    for part in nodes[key]
                )
            return sizes

        def uses() -> dict[_ExpressionKey, int]:
            counts = {root: 1}
            for key in reversed(order):
                factor = 1 if key in names else counts.get(key, 0)
                for part in nodes[key]:
                    if not isinstance(part, str):
                        counts[part] = counts.get(part, 0) + factor
            return counts

        # Exact residual sharing is canonical; the runtime guard preserves
        # the original cap ([ablations.formula_subtree_sharing_trick_20261102]).
        sizes, counts = lengths(), uses()
        runtime_counts = dict(counts)
        runtime = _formula_commands(nodes, order, names, root)
        for key in order:
            count = counts.get(key, 0)
            if count * sizes[key] <= 3 * count + sizes[key] + 4:
                continue
            extra = 3 * (runtime_counts[key] + 1)
            if budget is not None and runtime + extra > budget:
                continue
            letter = next(free, None)
            if letter is None:
                break
            names[key] = letter
            runtime += extra
            sizes, counts = lengths(), uses()
        output: list[str] = []

        def emit(key: _ExpressionKey) -> None:
            for part in nodes[key]:
                if isinstance(part, str):
                    output.append(part)
                elif part in names:
                    output.append(names[part] + ";!")
                else:
                    emit(part)

        for key in names:
            output.append("[")
            emit(key)
            output.append("]" + names[key] + ":")
        emit(root)
        return "".join(output)


def _lookup(truth_table: str, n: int, ess: list[int]) -> str:
    """Select a signed 32-bit chunk and multiply its selected bit into the sign.

    Stored inputs restrict this route to the same alphabet as the formula.
    The five-factor product wraps only at its exact 2**31 endpoint.
    """
    sub = read_at(truth_table, ess, n)
    letters = {pos: ascii_lowercase[pos] for pos in ess}
    low = min(len(ess), 5)
    size = 1 << low
    chunks = [sub[i : i + size] for i in range(0, len(sub), size)]

    def literal(bits: str) -> str:
        value = int(bits, 2)
        return str((~value) & 0xFFFFFFFF) + "~" if value >> 31 else str(value)

    ids = subtree_ids(sub)
    packet_depth = len(ess) - low
    selected: list[str] = []

    def select(depth: int, index: int) -> None:
        if depth == packet_depth:
            selected.append(literal(chunks[index]))
            return
        zero, one = ids[depth + 1][2 * index : 2 * index + 2]
        select(depth + 1, 2 * index)
        if zero == one:
            return
        selected.append(letters[ess[depth]] + ";[%")
        select(depth + 1, 2 * index + 1)
        selected.append("]?")

    select(0, 0)

    prologue = "".join(
        "^1&" + letters[i] + ":" if i in letters else "^%" for i in range(n)
    )
    power = [str(1 << (32 - size))]
    for j, pos in enumerate(ess[-low:]):
        weight = 1 << (low - 1 - j)
        power.append(letters[pos] + ";" + str((1 << weight) - 1) + "*1+*")
    return prologue + "".join(power) + "".join(selected) + "*0\\>1&."


def _balance(_table: str, default: str) -> str:
    """Compare the default with its balanced token fit."""
    tokens = re.findall(_FALSE_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(default, _join_tokens(tokens, width, ""), key=balance_score)
