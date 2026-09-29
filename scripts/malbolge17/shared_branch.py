"""Execute special address leaves through one selected-cell read block."""

import argparse
import itertools

from address17 import ALL1, ALL2, group_word
from address_gadget import build
from parity_views import STORED_PARITY

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
    _op,
)

_REUNION_D = (128, 222, 316)
_V_ROUTE = ((224, 121, 55), (109, 85, 78), (75, 60, 97))
_COPY_SCRATCH = (85, 202, 92)


def _check(
    source: str,
    groups: tuple[tuple[int, int, int], ...],
    outputs: dict[str, int],
    bits: tuple[int, ...],
    *,
    copy: bool = False,
    handoff: bool = False,
    exact: bool = False,
) -> bool:
    """Check one complete source run; return whether it took the special read."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    inputs = iter(48 + bit for bit in bits)
    printed: list[int] = []
    expected: int | None = None
    selected: tuple[int, int, int] | None = None
    v_after: int | None = None
    for _ in range(100_000):
        if handoff and state[1] == outputs["shared_read_entry"] + 11:
            assert selected is not None
            slot, _, original_v = selected
            assert state[2] == groups[slot][2]
            v_after = _crazy(state[0], original_v)
            expected = v_after & 0xFF
        if state[1] == outputs["shared_read_entry"]:
            assert bits[:2] == (0, 0)
            selector = 2 * bits[11] + bits[12]
            slot = selector if selector < 3 else bits[13]
            assert state[2] == _REUNION_D[slot]
            assert memory[state[2]] == groups[slot][1] - 1
            assert expected is None
            if copy:
                u, v = groups[slot][1:]
                selected = slot, memory[u], memory[v]
                assert memory[_COPY_SCRATCH[slot]] == ALL1
                assert memory[_COPY_SCRATCH[slot] + 1] == ALL2
                if exact:
                    assert memory[_COPY_SCRATCH[slot] + 3] == ALL1
                assert memory[u + 1] == _COPY_SCRATCH[slot] - 1
                if not handoff:
                    expected = memory[u] & 0xFF
            else:
                first, second, result = _V_ROUTE[slot]
                assert memory[groups[slot][1] + 1] == first - 1
                assert memory[first] == second - 1
                assert memory[second] == result - 1
                assert result == groups[slot][2]
                expected = (
                    _crazy(_crazy(state[0], memory[groups[slot][1]]), memory[result])
                    & 0xFF
                )
        char = next(inputs) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, effect = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if effect is not None:
            printed.append(effect)
        if state[3]:
            break
    else:
        raise AssertionError("shared branch did not halt")
    if bits[:2] == (0, 0):
        assert expected is not None
        assert printed == [expected]
        if selected is not None:
            slot, original_u, original_v = selected
            u, v = groups[slot][1:]
            assert memory[u] == original_u
            assert memory[v] == (v_after if handoff else original_v)
            assert memory[_COPY_SCRATCH[slot]] == _crazy(
                original_u if exact else _crazy(ALL2, original_u), ALL1
            )
            if exact:
                assert memory[_COPY_SCRATCH[slot] + 3] == original_u
        return True
    assert expected is None
    assert not printed
    pointer = _crazy(ALL2 - 2, group_word(list(bits)))
    assert memory[outputs["pointer"]] == pointer
    assert tuple(memory[cell] for cell in groups[-1]) == tuple(
        STORED_PARITY[(pointer + 1 + offset) % 2] for offset in range(3)
    )
    return False


def main(
    *,
    full: bool = False,
    copy: bool = False,
    handoff: bool = False,
    exact: bool = False,
) -> None:
    """Check eight selector leaves and optionally the full address domain."""
    copy |= handoff or exact
    outputs: dict[str, int] = {}
    source, groups, _, size = build(
        None,
        dispatch_ab=True,
        parity=True,
        high_pointer=True,
        high_parity=True,
        guard_scratch=True,
        prepare_returns=True,
        result_first=True,
        slot_pointers=True,
        shared_special_read=True,
        shared_special_copy=copy,
        shared_v_handoff=handoff,
        shared_exact_copy=exact,
        outputs=outputs,
    )
    samples = tuple(
        (0, 0) + (0,) * 9 + tail for tail in itertools.product((0, 1), repeat=3)
    )
    cases = itertools.product((0, 1), repeat=14) if full else samples
    special = ordinary = 0
    for bits in cases:
        if _check(
            source, groups, outputs, bits, copy=copy, handoff=handoff, exact=exact
        ):
            special += 1
        else:
            ordinary += 1
    assert (special, ordinary) == ((4096, 12288) if full else (8, 0))
    mode = (
        "exact copy"
        if exact
        else "V handoff"
        if handoff
        else "copy"
        if copy
        else "read"
    )
    print(f"shared {mode}: {special} special, {ordinary} ordinary; {size} code cells")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="check every address path")
    parser.add_argument("--copy", action="store_true", help="check selected U copy")
    parser.add_argument(
        "--v-handoff", action="store_true", help="check selected V route"
    )
    parser.add_argument("--exact-copy", action="store_true", help="check exact U copy")
    args = parser.parse_args()
    main(full=args.full, copy=args.copy, handoff=args.v_handoff, exact=args.exact_copy)
