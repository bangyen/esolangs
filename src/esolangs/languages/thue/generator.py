"""Thue Boolean program generator: nineteen rules that halve one table.

The table is the starting state, one character an entry; reading a bit
replaces each adjacent *pair* with one of the two, so the state halves per
input and the last character is the answer.  Entries are bit-reversed: pairs
differ in the *least* significant index bit, inputs arrive most significant
first, and no rewrite can select a half.

Thue draws which rewrite to make; these rules leave nothing to draw (every
state reached has one rule at one position), so the answer is reproducible
unpinned, as the classics tests assert to ``n = 3`` under several draws.

A constant half is stored once (:func:`_fold`, shorter from nine inputs) on
every path; and/or n=9/10 -19%/-32% chars, 0% balanced (the balancer's
chunked layout wins).

Size:
    ``T + 187`` characters; n=4 random 1847: 203 chars, n=10 random 1847:
    1,211 chars, n=10 and: 821 chars (constant half folded).

Decisions:
    A named repeated block, expanded before lookup, saved 0% on random tables
    and 7.9% at n=12 on exact repeats of a 2^10-row block, but 10.2% / 11.5%
    at n=14 with 2^11 / 2^12-row blocks, so it races the lookup.
"""

from __future__ import annotations

from collections import Counter
from math import isqrt
from string import ascii_letters

from esolangs.generation.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    read_at,
    subtree_ids,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

#: Entries are ``a``/``b`` so a ``0``/``1`` input line is never mistaken for
#: one; ``L``/``E`` are sentinels, ``M``/``R`` and the read ``0``/``1`` markers.
_RULES = "\n".join(
    [
        # One entry left: print it and empty the state, which halts.
        "LRaE::=~0",
        "LRbE::=~1",
        # Start a round, over two entries so neither print rule above can also
        # match: one ``LR`` rule collided, and a draw then read an n+1st input.
        "LRaa::=LMaa",
        "LRab::=LMab",
        "LRba::=LMba",
        "LRbb::=LMbb",
        "M::=:::",
        # The line read is the marker: ``0`` keeps the first of each pair, ``1``
        # the second; the suffix left stays even, so none meets one entry.
        "0aa::=a0",
        "0ab::=a0",
        "0ba::=b0",
        "0bb::=b0",
        "0E::=RE",
        "1aa::=a1",
        "1ab::=b1",
        "1ba::=a1",
        "1bb::=b1",
        "1E::=RE",
        # Carry the marker back to the left sentinel for the next round.
        "aR::=Ra",
        "bR::=Rb",
        "::=",
    ]
)

#: The rules for a queue of rounds between ``L`` and ``R``, the next one
#: beside ``R``: ``K`` starts a halving round where ``LR`` did, and ``S``
#: reads a line and deletes it -- the digit lands beside ``R``, never an
#: entry, so no halving rule can fire on it.
_QUEUED_RULES = "\n".join(
    [
        *(
            "K" + rule[1:].replace("::=LM", "::=M") if "::=LM" in rule else rule
            for rule in _RULES.splitlines()[:-1]
        ),
        "SR::=JR",
        "J::=:::",
        "0R::=R",
        "1R::=R",
        "::=",
    ]
)


#: Chunk-name symbols: no table or control symbol.  A queued layout also
#: leaves out ``K``, ``S`` and ``J``, which its rules match.
_NAME_ALPHABET = "".join(c for c in ascii_letters if c not in "abLMRECD")
_QUEUED_NAME_ALPHABET = "".join(c for c in _NAME_ALPHABET if c not in "KSJ")
_FOLD_NAME_ALPHABET = "".join(c for c in _QUEUED_NAME_ALPHABET if c not in "ZYWV")


def _chunk_marker(index: int, digits: int, alphabet: str) -> str:
    """Return a fixed-width name containing no table or control symbol."""
    name = []
    for _ in range(digits):
        index, digit = divmod(index, len(alphabet))
        name.append(alphabet[digit])
    return "".join(reversed(name))


def _width_limit(width: int | None) -> int | None:
    """Return ``width`` when it constrains the layout, else ``None``."""
    return width if width and width > 0 else None


def thue(truth_table: str, width: int | None = None) -> str:
    """Return a Thue program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit. Narrow layouts expand named chunks before reading.
    An ignored input's round reads and halves nothing, so the table is laid
    out at the rest; the queue's five rules lose below that saving.  Plain
    and queued layouts compete on every path, nearest the width first.
    """
    n = _validate_truth_table(truth_table)
    tables = _tables(truth_table)
    layouts = [_thue_layout(*layout, width) for layout in tables]
    layouts.extend(
        shared
        for layout in tables
        if (shared := _shared_layout(*layout, n)) is not None
    )
    limit = _width_limit(width)

    def overshoot(layout: str) -> int:
        return 0 if limit is None else max(0, grid_width(layout) - limit)

    return min(layouts, key=lambda layout: (overshoot(layout), len(layout)))


#: Rules for a constant half, on top of :data:`_QUEUED_RULES`.  ``Z`` reads the
#: first essential line: the half that survives is left whole, the other digit
#: deletes the entries to one (``V``) which the constant restores.  A queued
#: ``K`` meeting that single entry only reads and deletes its line, as ``S`` does.
_FOLD_RULES = (
    "ZR::=YWR",
    "Y::=:::",
    "VRa::=VR",
    "VRb::=VR",
    "KRaE::=JRaE",
    "KRbE::=JRbE",
)


def _fold(truth_table: str) -> tuple[str, str, tuple[str, ...]] | None:
    """Return ``(kept half, rounds, extra rules)`` storing one half of a table.

    The fold's nine rules cost about 110 characters, so it wins from nine
    inputs (-19% at n=9, -32% at n=10 on a constant half); ``None`` when no
    half is constant.
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    if len(essential) < 2:
        return None
    table = read_at(truth_table, essential, n)
    half = len(table) // 2
    low, high = table[:half], table[half:]
    if len(set(high)) == 1:
        kept, constant, keep = low, high[0], "0"
    elif len(set(low)) == 1:
        kept, constant, keep = high, low[0], "1"
    else:
        return None
    other = "1" if keep == "0" else "0"
    rounds = "".join(
        "Z" if i == essential[0] else "K" if i in essential else "S"
        for i in reversed(range(n))
    )
    extra = (
        *_FOLD_RULES,
        f"{keep}WR::=R",
        f"{other}WR::=VR",
        f"VRE::=R{'ab'[constant == '1']}E",
    )
    return kept, rounds, extra


_Layout = tuple[str, str | None, tuple[str, ...]]


def _tables(truth_table: str) -> list[_Layout]:
    """Return the ``(table, rounds, extra rules)`` layouts.

    Queued only if an input is ignored; folded only if a half is constant.
    """
    n = _validate_truth_table(truth_table)
    layouts: list[_Layout] = [(truth_table, None, ())]
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        rounds = "".join("K" if i in essential else "S" for i in reversed(range(n)))
        layouts.append((read_at(truth_table, essential, n), rounds, ()))
    if (fold := _fold(truth_table)) is not None:
        layouts.append(fold)
    return layouts


def _contracted(rules: str, *, queued: bool) -> str:
    """Return ``rules`` with the start rules shortened to one symbol.

    Only a completed return sweep contracts: ``D`` restores ``L`` before
    reading, so the shorter start rules cannot fire on ``R`` in the interior.
    """
    if queued:
        # ``KR`` and ``LR`` contract once a sweep completes.
        short = rules.replace("KR", "C").replace("LR", "C")
        return short.removesuffix("::=") + "KR::=C\nLR::=C\n::="
    short = rules.replace("LR", "C").replace("::=LM", "::=D")
    return short.removesuffix("::=") + "LR::=C\nD::=LM\n::="


def _chunked(
    rules_text: str,
    entries: str,
    rounds: str | None,
    extra: tuple[str, ...],
    limit: int,
) -> str:
    """Return a program expanding named chunks of ``entries`` before reading."""
    length = len(entries)
    alphabet = _alphabet(rounds, extra)
    digits = _marker_digits(length, len(alphabet))
    # Payload covers its names' overhead, keeping even the narrowest source O(T).
    payload = max(digits, limit - digits - max(digits, 2) - 3)
    rules = rules_text.splitlines()[:-1]
    for index, offset in enumerate(range(0, length, payload)):
        marker = _chunk_marker(index, digits, alphabet)
        following = (
            _chunk_marker(index + 1, digits, alphabet)
            if offset + payload < length
            else "RE"
        )
        rules.append(f"{marker}::={entries[offset : offset + payload]}{following}")
    # No input marker exists until expansion finishes and R sweeps back to L.
    head = "L" + (rounds or "")
    return "\n".join([*rules, "::=", head + _chunk_marker(0, digits, alphabet)])


def _thue_layout(
    table: str, rounds: str | None, extra: tuple[str, ...], width: int | None
) -> str:
    """Return one layout: plain, or queued with a ``K``/``S`` round per input."""
    queued = rounds is not None
    entries = _thue_entries(table)
    base = _QUEUED_RULES if queued else _RULES
    if extra:
        base = "\n".join([base.removesuffix("\n::="), *extra, "::="])
    start = f"L{rounds}R" if queued else "LM"
    program = f"{base}\n{start}{entries}E"
    limit = _width_limit(width)
    if limit is None or grid_width(program) <= limit:
        return program
    # Contracting would merge the fold's ``KRaE`` with the final ``LRaE``.
    rules_text = base if extra else _contracted(base, queued=queued)
    narrow = f"{rules_text}\n{start}{entries}E"
    if grid_width(narrow) <= limit:
        return narrow
    # One-symbol nodes fit only bounded arities (-40% at n=3, widths 1-8;
    # -22% at width 9); larger trees retain chunks.
    if not queued and len(entries) <= 8 and limit < 10:
        return _thue_short_tree(table)
    return _chunked(rules_text, entries, rounds, extra, limit)


def _alphabet(rounds: str | None, extra: tuple[str, ...]) -> str:
    """Return the chunk-name symbols no rule of the layout matches."""
    if extra:
        return _FOLD_NAME_ALPHABET
    return _NAME_ALPHABET if rounds is None else _QUEUED_NAME_ALPHABET


def _shared_layout(
    table: str, rounds: str | None, extra: tuple[str, ...], n: int
) -> str | None:
    """Expand one named aligned block through a unique frontier before lookup."""
    entries = _thue_entries(table)
    if len(entries) < 2:
        return None
    ids = subtree_ids(entries.translate(str.maketrans("ab", "01")))
    best: tuple[int, int, int] | None = None
    saved = 0
    for depth, layer in enumerate(ids[:-1]):
        span = 1 << (len(ids) - 1 - depth)
        counts = Counter(layer)
        for index, state in enumerate(layer):
            copies = counts[state]
            saving = (copies - 1) * span - copies - 31
            if state >= 2 and copies > 1 and saving > saved:
                best, saved = (index * span, span, copies), saving
    if best is None:
        return None
    row, span, copies = best
    length = len(entries)
    # Expand, then return R across the expanded table. Lookup itself costs
    # at most 2L+8n+32, including queued reads and the constant-half rules.
    startup = length + (length - copies * span) + copies + 1
    if (
        2 * length + 8 * n + 32 + startup > 2 * (1 << n) + 2 * n - 1
        or length + n + 8 > 1 << n
    ):
        return None
    alphabet = _alphabet(rounds, extra)
    front, name = alphabet[0], alphabet[1]
    body = entries[row : row + span]
    encoded = "".join(
        name if entries[i : i + span] == body else entries[i : i + span]
        for i in range(0, length, span)
    )
    base = _QUEUED_RULES if rounds is not None else _RULES
    rules = [
        *base.splitlines()[:-1],
        *extra,
        f"{front}a::=a{front}",
        f"{front}b::=b{front}",
        f"{front}{name}::={body}{front}",
        f"{front}E::=RE",
        "::=",
    ]
    return "\n".join([*rules, "L" + (rounds or "") + front + encoded + "E"])


def _thue_entries(truth_table: str) -> str:
    """Return the table as ``a``/``b`` entries in bit-reversed row order."""
    length = len(truth_table)
    # Increment the row counter in bit-reversed order.
    entries = []
    row = 0
    for _ in range(length):
        entries.append("ab"[truth_table[row] == "1"])
        carry = length >> 1
        while row & carry:
            row ^= carry
            carry >>= 1
        row |= carry
    return "".join(entries)


def _thue_short_tree(truth_table: str) -> str:
    """Return seven-column interned residuals, consuming every input."""
    n = _validate_truth_table(truth_table)
    levels, children, _ = _residual_ids(truth_table, n)
    nodes = [state for level in levels[:-1] for state in level]
    names = ascii_letters.replace("I", "")
    count = len(nodes)
    ready = dict(zip(nodes, names[:count], strict=True))
    waiting = dict(zip(nodes, names[count : 2 * count], strict=True))
    leaves = dict(
        zip(levels[-1], names[2 * count : 2 * count + len(levels[-1])], strict=True)
    )
    rules = ["I::=:::", *(f"{name}::=~{bit}" for bit, name in leaves.items())]
    for node in nodes:
        # Ready and waiting symbols differ: a read can never expand twice.
        rules.append(f"{ready[node]}::={waiting[node]}I")
        for bit in range(2):
            child = children[node][bit]
            target = ready[child] if child in ready else leaves[child]
            rules.append(f"{waiting[node]}{bit}::={target}")
    return "\n".join([*rules, "::=", ready[levels[0][0]]])


def _marker_digits(length: int, base: int) -> int:
    """Return the name length, in ``base``-letter symbols, covering the table."""
    digits, capacity = 1, base
    while capacity < length:
        digits += 1
        capacity *= base
    return digits


def balance_thue(truth_table: str, default: str) -> str:
    """Balance chunk payloads at their quadratic crossing, plus the small tree.

    H=23+ceil(T/p). Above the rule floor, W=p+2d+3, plus at most one cell for d=1.
    W=CELL_ASPECT*H is quadratic in p; each layout takes the root. A +-CELL_ASPECT
    sweep around it saved 8 of 13,486 side over the corpus (0.06%).
    Each layout (see :func:`_tables`) is tuned at its own rule count.
    """
    plain = min(
        (_thue_layout(*layout, None) for layout in _tables(truth_table)), key=len
    )
    candidates = [default, plain, thue(truth_table, 1)]
    cap = max(grid_width(default), grid_width(plain))
    for table, rounds, extra in _tables(truth_table):
        size = len(table)
        digits = _marker_digits(size, len(_alphabet(rounds, extra)))
        base = _RULES if rounds is None else _QUEUED_RULES
        rules = len(base.splitlines()) + len(extra)
        offset = CELL_ASPECT * rules - 2 * digits
        root = (offset + isqrt(offset * offset + 4 * CELL_ASPECT * size)) // 2
        overhead = digits + max(digits, 2) + 3
        maximum = max(digits, cap - 1 - overhead)
        candidates.append(
            _thue_layout(
                table, rounds, extra, min(maximum, max(digits, root)) + overhead
            )
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Thue",
    "thue",
    category="program_based",
    reader_checked=True,
    random=True,
    boolean=thue,
    # Not a tree: the table is the state, and each read halves it.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        note="Thue draws which rewrite to make, by spec, and the "
        "interpreter draws too; this program's rules are written so that "
        "every state it reaches has exactly one, leaving the draw nothing "
        "to change",
    ),
    balance=balance_thue,
    no_wrap="a newline ends a rule, and the state's own newlines are part of it",
    empty_program=(
        "a Thue program needs a '::=' line with nothing but whitespace on "
        "either side, to separate its rules from its starting state"
    ),
)
