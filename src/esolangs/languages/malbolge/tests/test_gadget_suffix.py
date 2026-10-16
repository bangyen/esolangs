"""The digit gadget is the unique shortest injective suffix after its wipe prefix."""

from __future__ import annotations

from itertools import product

from esolangs.languages.malbolge.generator.digits import _GADGET
from esolangs.languages.malbolge.interpreter import _crazy

_PREFIX = tuple("/ 0 / 1 K2 0 K2 1 / 2".split())  # noqa: SIM905
_SUFFIX = _GADGET[len(_PREFIX) :]
_ALPHABET = ("0", "1", "2", "K0", "K1", "K2")
_INPUTS = tuple(product((0, 1), repeat=3))
type _Cells = tuple[int, ...]
type _State = tuple[int, _Cells]


def _step(state: _State, op: str) -> _State:
    """Trit 0 after ``op``: ``K`` sets ``A``, a digit runs ``p`` on that cell."""
    a, cells = state
    if op[0] == "K":
        return int(op[1]), cells
    i = int(op)
    a = _crazy(a, cells[i]) % 3  # trit 0 only
    return a, (*cells[:i], a, *cells[i + 1 :])


def _start(ops: tuple[str, ...], bits: _Cells) -> _State:
    """Run ``ops`` from zeroed cells, each ``/`` reading the next of ``bits``."""
    state: _State = 0, (0, 0, 0)
    reads = iter(bits)
    for op in ops:
        state = (next(reads), state[1]) if op == "/" else _step(state, op)
    return state


def _injective_suffixes(length: int) -> list[tuple[str, ...]]:
    """Suffixes of ``length`` ops sending the eight inputs to distinct (c1, c2)."""
    found: list[tuple[str, ...]] = []

    def walk(states: list[_State], suffix: tuple[str, ...]) -> None:
        if len(suffix) == length:
            if len({cells[1:] for _, cells in states}) == len(_INPUTS):
                found.append(suffix)
            return
        for op in _ALPHABET:
            walk([_step(s, op) for s in states], (*suffix, op))

    walk([_start(_PREFIX, bits) for bits in _INPUTS], ())
    return found


def test_suffix_is_unique_shortest() -> None:
    """No suffix up to 5 ops is injective; at 6 only the shipped one is."""
    for length in range(6):
        assert not _injective_suffixes(length), length
    assert _injective_suffixes(6) == [_SUFFIX]


def test_closed_form_matches_gadget() -> None:
    """``(c1, c2) = (u, v)`` mod 3 in closed form, injective on the cube."""
    images = set()
    for bits in _INPUTS:
        x, y, z = bits
        _, (_, c1, c2) = _start(_GADGET, bits)
        u = (1 + x - y - x * y * z) % 3
        v = ((2 - x) * (1 - z) + z * x * y) % 3
        assert (c1, c2) == (u, v), bits
        images.add((u, v))
    assert len(images) == len(_INPUTS)
