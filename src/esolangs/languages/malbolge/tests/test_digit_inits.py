"""``_D_INITS``'s gadget outputs are the first completing sequence of a trit rule.

``crazy`` works trit by trit, so at each trit ``k >= 1`` the gadget maps the
three cells' init trits to constant ``(u_k, v_k)``.  From trit 4 up the
input trit is 0 and every init trit 0 or 1, giving ``(1, 2)``: the digit
constants.  Only trits 1..3 choose, 81 ways a group.  A group keeps ``S``
alive when ``S_0 = 1`` (``p`` over ``S`` bijective in ``v``), ``crazy(v_1,
S_1) = 2`` (rotated trit 0 is 2: ``p`` over ``u`` bijective), ``v_k = 2``
under a digit of ``S`` and ``u_k = 1`` under a digit of the rotated ``S``.
Which init values spell the outputs is a placement tie-break, not pinned.
"""

from __future__ import annotations

from functools import cache
from itertools import product

import pytest

from esolangs.languages.malbolge.generator import digits
from esolangs.languages.malbolge.interpreter import _crazy

_DIGIT = -1
#: Trit ``k`` of the reads ``'0'``/``'1'`` (48, 49) for ``k`` = 1..3.
_READ = (1, 2, 1)
type _Uv = tuple[int, int]
type _Choice = tuple[_Uv, _Uv, _Uv]


def _c(a: int, m: int) -> int:
    return _crazy(a, m) % 3


def _trit(value: int, k: int) -> int:
    return int(value // 3**k % 3)


def _gadget(cells: tuple[int, ...], read: int) -> _Uv:
    """``(u, v)`` at one trit from the cells' init trits."""
    c, a = list(cells), 0
    for op in digits._GADGET:  # noqa: SLF001
        if op == "/":
            a = read
        elif op[0] == "K":
            a = int(op[1])
        else:
            a = c[int(op)] = _c(a, c[int(op)])
    return c[1], c[2]


def _step(s: tuple[int, ...], choice: _Choice, group: int) -> tuple[int, ...] | None:
    """``S``'s trits after a group (``_DIGIT`` marks digits), or ``None``."""
    u = [0, *(uv[0] for uv in choice), *[1] * 6]
    v = [0, *(uv[1] for uv in choice), *[2] * 6]
    # swap12 is crazy(2, .): A's trits above 0 are 0, which keeps 1s and 2s.
    if group == digits._D_SWAP_V:  # noqa: SLF001
        v = [_c(0, x) for x in v]
    if group == digits._D_SWAP_U:  # noqa: SLF001
        u = [_c(0, x) for x in u]
    if s[0] != 1:
        return None
    s1 = [
        _DIGIT,
        *(x if x == _DIGIT else _c(v[k], x) for k, x in enumerate(s) if k),
    ]
    if any(x == _DIGIT and v[k] != 2 for k, x in enumerate(s) if k):
        return None
    r = s1[1:] + s1[:1]
    if r[0] != 2:
        return None
    s2 = [
        _DIGIT,
        *(x if x == _DIGIT else _c(x, u[k]) for k, x in enumerate(r) if k),
    ]
    if any(x == _DIGIT and u[k] != 1 for k, x in enumerate(r) if k):
        return None
    return tuple(s2[1:] + s2[:1])


_UV13 = ((0, 1), (1, 2), (2, 2))  # every output under read trit 1
_UV2: tuple[_Uv, ...] = tuple((u, v) for u in range(3) for v in range(3))
_CHOICES: tuple[_Choice, ...] = tuple(product(_UV13, _UV2, _UV13))


@cache
def _completions(s: tuple[int, ...], group: int) -> int:
    if group == len(digits._D_INITS):  # noqa: SLF001
        return int(all(x == _DIGIT for x in s))
    total = 0
    for choice in _CHOICES:
        nxt = _step(s, choice, group)
        if nxt is not None:
            total += _completions(nxt, group + 1)
    return total


def _outputs(init: tuple[int, ...]) -> _Choice:
    out = (_gadget(tuple(_trit(x, k) for x in init), _READ[k - 1]) for k in (1, 2, 3))
    return tuple(out)  # type: ignore[return-value]


_START: tuple[int, ...] = (1,) * 10  # 29524


def test_high_trits_are_the_digit_constants() -> None:
    """From trit 4 up every init trit pattern gives ``(u, v) = (1, 2)``."""
    assert {_gadget(c, 0) for c in product((0, 1), repeat=3)} == {(1, 2)}
    assert {_gadget(c, 1) for c in product(range(3), repeat=3)} == set(_UV13)


def test_shipped_outputs_are_the_first_completing_sequence() -> None:
    """2,464 sequences complete; each group takes the first that still does."""
    assert _completions(_START, 0) == 2464
    s = _START
    for group, init in enumerate(digits._D_INITS):  # noqa: SLF001
        first = next(
            c
            for c in _CHOICES
            if (n := _step(s, c, group)) is not None and _completions(n, group + 1)
        )
        assert _outputs(init) == first, group
        nxt = _step(s, first, group)
        assert nxt is not None
        s = nxt
    assert all(x == _DIGIT for x in s)


@pytest.mark.parametrize(("cell", "value"), [((4, 2), 33), ((0, 0), 42)])
def test_a_broken_output_fails_rule_and_build(
    monkeypatch: pytest.MonkeyPatch, cell: tuple[int, int], value: int
) -> None:
    """Positive control: an init the rule rejects collides in the real build."""
    inits = [list(t) for t in digits._D_INITS]  # noqa: SLF001
    inits[cell[0]][cell[1]] = value
    s: tuple[int, ...] | None = _START
    for group, init in enumerate(inits):
        if s is None:
            break
        s = _step(s, _outputs(tuple(init)), group)
    assert s is None or not all(x == _DIGIT for x in s)
    monkeypatch.setattr(digits, "_D_INITS", tuple(map(tuple, inits)))
    digits._readouts.cache_clear()  # noqa: SLF001
    digits._readouts_cells.cache_clear()  # noqa: SLF001
    try:
        with pytest.raises(AssertionError, match="collide or wrap"):
            digits._digits.__wrapped__(digits._DIGITS_N)  # noqa: SLF001
    finally:
        monkeypatch.undo()
        digits._readouts.cache_clear()  # noqa: SLF001
        digits._readouts_cells.cache_clear()  # noqa: SLF001
