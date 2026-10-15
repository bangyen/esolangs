"""Malbolge's machine helpers: address arithmetic, rendering and the mixer ops."""

from __future__ import annotations

from esolangs.languages.malbolge.interpreter import _XLAT1, _XLAT2, _crazy

_WORDS = 3**10
#: Weight of the top trit, which ``_rot`` moves the low trit to.
_ROTATE = 3**9
#: The all-1 and all-2 words, and the constants cells 5..7 hold: 0, all-1, all-2.
_ALL1 = 29524
_ALL2 = 59048
_CONSTS = (0, _ALL1, _ALL2)
#: The eight instructions a cell can hold, in the order ``_table_char`` tries.
_ACTIVE = "ji*p</vo"
#: ``_ops`` kinds: 0 is ``p``, 1 is ``*``.
_OPS = "p*"


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


def _render(program: dict[int, int]) -> str:
    """Return the full store: ``program``, every other cell an ``o``."""
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))


def _addr_of(value: int, avoid: tuple[int, ...], low: int = 34) -> int:
    """Return an address whose ``g`` value is ``value``, clear of ``avoid``.

    Addresses below ``low`` are skipped because ``value - 1`` has to be a
    source character too, so the address the navigation reaches must exceed
    the value it names.
    """
    candidates = [
        address
        for address in _G_ADDRESSES.get(value, ())
        if low <= address <= 126 and address not in avoid
    ]
    if not candidates:  # pragma: no cover - the first pass always finds one
        candidates = [
            address
            for address in _G_ADDRESSES.get(value, ())
            if address + 94 <= 126 and address + 94 not in avoid
        ]
    if not candidates:  # pragma: no cover - the layout always has one
        raise AssertionError(f"no address for value {value}")
    return candidates[0]


def _rot(value: int) -> int:
    return value // 3 + (value % 3) * _ROTATE


def _apply(cells: list[int], a: int, ops: tuple[tuple[int, int], ...]) -> int:
    """Run ``ops`` over ``cells`` in place, returning the final ``A``."""
    for kind, index in ops:
        value = _crazy(a, cells[index]) if kind == 0 else _rot(cells[index])
        a = cells[index] = value
    return a
