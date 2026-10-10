"""Thue boolean program builder: nineteen rules that halve one table.

The table is the starting state, one character an entry; reading a bit
replaces each adjacent *pair* with one of the two, so the state halves per
input and the last character is the answer, for ``T + 187`` characters.
Entries are bit-reversed: pairs differ in the *least* significant index bit,
inputs arrive most significant first, and no rewrite can select a half.

Thue draws which rewrite to make; these rules leave nothing to draw (every
state reached has one rule at one position), so the answer is reproducible
unpinned, as the classics tests assert to ``n = 3`` under several draws.

A constant half is stored once (:func:`_fold`, shorter from nine inputs) on
every path; balanced n=9/10 -24%/-35%.  A repeated block is not shared: the
rules rewrite every pair of the one string, and none can name a block to reuse.
"""

from __future__ import annotations

from math import isqrt
from string import ascii_letters

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.tools.wrap import balance_score

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


def _chunk_marker(index: int, digits: int, alphabet: str = _NAME_ALPHABET) -> str:
    """Return a fixed-width name containing no table or control symbol."""
    name = []
    for _ in range(digits):
        index, digit = divmod(index, len(alphabet))
        name.append(alphabet[digit])
    return "".join(reversed(name))


def _widest(program: str) -> int:
    return max(map(len, program.splitlines()))


def thue(truth_table: str, width: int | None = None) -> str:
    """Return a Thue program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit. Narrow layouts expand named chunks before reading.
    An ignored input's round reads and halves nothing, so the table is laid
    out at the rest; the queue's five rules lose below that saving.  Plain
    and queued layouts compete on every path, nearest the width first.
    """
    layouts = [_thue_layout(*layout, width) for layout in _tables(truth_table)]
    limit = width if width and width > 0 else None

    def overshoot(layout: str) -> int:
        return 0 if limit is None else max(0, _widest(layout) - limit)

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
    if width is None or width <= 0 or _widest(program) <= width:
        return program
    if extra:
        # Contracting would merge the fold's ``KRaE`` with the final ``LRaE``.
        rules_text = base
    elif queued:
        # ``KR`` and ``LR`` contract once a sweep completes, as ``LR`` does below.
        rules_text = _QUEUED_RULES.replace("KR", "C").replace("LR", "C")
        rules_text = rules_text.removesuffix("::=") + "KR::=C\nLR::=C\n::="
    else:
        # Contract only a completed return sweep. D restores L before reading,
        # so the shorter start rules cannot fire on R in the table's interior.
        rules_text = _RULES.replace("LR", "C").replace("::=LM", "::=D")
        rules_text = rules_text.removesuffix("::=") + "LR::=C\nD::=LM\n::="
    narrow = f"{rules_text}\n{start}{entries}E"
    if _widest(narrow) <= width:
        return narrow
    length = len(entries)
    # One-symbol nodes fit only bounded arities; larger trees retain chunks.
    if not queued and length <= 8 and width < 9:
        return _thue_short_tree(table)
    alphabet = _alphabet(rounds, extra)
    digits = _marker_digits(length, len(alphabet))
    # Payload covers its names' overhead, keeping even the narrowest source O(T).
    payload = max(digits, width - digits - max(digits, 2) - 3)
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


def _alphabet(rounds: str | None, extra: tuple[str, ...]) -> str:
    """Return the chunk-name symbols no rule of the layout matches."""
    if extra:
        return _FOLD_NAME_ALPHABET
    return _NAME_ALPHABET if rounds is None else _QUEUED_NAME_ALPHABET


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
    """Return a seven-column decision tree for at most three inputs."""
    size = len(truth_table)
    names = ascii_letters.replace("I", "")
    ready = names[: size - 1]
    waiting = names[size - 1 : 2 * (size - 1)]
    leaves = names[2 * (size - 1) : 2 * size]
    rules = ["I::=:::", *(f"{name}::=~{bit}" for bit, name in enumerate(leaves))]
    for node in range(size - 1):
        # Ready and waiting symbols differ: a read can never expand twice.
        rules.append(f"{ready[node]}::={waiting[node]}I")
        for bit in range(2):
            child = 2 * node + 1 + bit
            target = (
                ready[child]
                if child < size - 1
                else leaves[int(truth_table[child - size + 1])]
            )
            rules.append(f"{waiting[node]}{bit}::={target}")
    return "\n".join([*rules, "::=", ready[0]])


def _marker_digits(length: int, base: int = len(_NAME_ALPHABET)) -> int:
    """Return the fixed base-44 name length covering the table."""
    digits, capacity = 1, base
    while capacity < length:
        digits += 1
        capacity *= base
    return digits


def balance_thue(truth_table: str, default: str) -> str:
    """Balance chunk payloads at their quadratic crossing, plus the small tree.

    H=23+ceil(T/p). Above the rule floor, W=p+2d+3, plus at most one cell for d=1.
    The ceiling and extra cell put the crossing within one payload of the root.
    Each layout (see :func:`_tables`) is tuned at its own rule count.
    """
    candidates = [default, thue(truth_table, 1)]
    cap = max(map(len, default.split("\n")))
    for table, rounds, extra in _tables(truth_table):
        size = len(table)
        digits = _marker_digits(size, len(_alphabet(rounds, extra)))
        base = _RULES if rounds is None else _QUEUED_RULES
        offset = len(base.splitlines()) + len(extra) + 3 - 2 * digits - 3
        root = (offset + isqrt(offset * offset + 4 * size)) // 2
        overhead = digits + max(digits, 2) + 3
        maximum = max(digits, cap - 1 - overhead)
        candidates.extend(
            _thue_layout(
                table, rounds, extra, min(maximum, max(digits, payload)) + overhead
            )
            for payload in (root - 1, root, root + 1, root + 2)
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Thue",
    "other.thue",
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
