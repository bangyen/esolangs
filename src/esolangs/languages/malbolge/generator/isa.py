"""Malbolge's machine helpers: address arithmetic and rendering."""

from __future__ import annotations

from collections.abc import Container

from esolangs.languages.malbolge.interpreter import _XLAT1, _XLAT2

_WORDS = 3**10
#: Weight of the top trit, which ``_rot`` moves the low trit to.
_ROTATE = 3**9
#: The all-1 and all-2 words, and the constants cells 5..7 hold: 0, all-1, all-2.
_ALL1 = 29524
_ALL2 = 59048
_CONSTS = (0, _ALL1, _ALL2)
#: The eight instructions a cell can hold, in the order ``_table_char`` tries.
_ACTIVE = "ji*p</vo"


def _f(address: int) -> int:
    """Return the unique NOP character at ``address``."""
    return 33 + ((35 - address) % 94)


def _g(address: int) -> int:
    """Return a cell's value after the instruction pointer has executed it."""
    return ord(_XLAT2[_f(address) - 33])


def _char_for(op: str, address: int) -> int:
    """Return a source character that deciphers to ``op`` at ``address``."""
    return 33 + ((_XLAT1.index(op) - address) % 94)


#: ``value -> addresses with that ``g`` value``; ``g`` has period 94 and
#: every value in 33..126 occurs, so each value has one or two addresses.
_G_ADDRESSES: dict[int, tuple[int, ...]] = {}
for _address in range(127):
    _G_ADDRESSES.setdefault(_g(_address), ())
    _G_ADDRESSES[_g(_address)] += (_address,)


def _program(code: dict[int, str]) -> dict[int, int]:
    """Return each code cell's source character."""
    return {a: _char_for(op, a) for a, op in code.items()}


def _render(program: dict[int, int], words: int = _WORDS) -> str:
    """Return the first ``words`` cells: ``program``, every other cell an ``o``."""
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(words))


def _progression(value: int, lo: int, hi: int) -> range:
    """Return the addresses in ``lo <= a < hi`` with ``g(a) == value``.

    ``g`` has period 94, so they are ``lo + (r - lo) % 94`` and every 94th
    after it, ``r`` being the value's first address.
    """
    return range(lo + (_G_ADDRESSES[value][0] - lo) % 94, hi, 94)


def _first_free(value: int, lo: int, hi: int, blocked: Container[int] = ()) -> int:
    """Return the least unblocked address of :func:`_progression`."""
    for address in _progression(value, lo, hi):
        if address not in blocked:
            return address
    raise AssertionError(f"no address for value {value}")


def _rot(value: int) -> int:
    return value // 3 + (value % 3) * _ROTATE
