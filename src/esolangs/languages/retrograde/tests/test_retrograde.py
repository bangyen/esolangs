"""Each Retrograde opcode in both directions and at both tape signs."""

import pytest

from esolangs.languages.retrograde import interpreter as native
from esolangs.languages.retrograde.interpreter import _advance, _Machine, _parse, _State
from esolangs.runtime.io import ScriptedIO
from tests.support.prepared_support import check_image_reuse


def check_instruction_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs.languages.retrograde.tests.oracle_checks import check_raw_retrograde

    check_raw_retrograde()
    for pointer in (-1, 0, 1):
        for direction in (-1, 1):
            for bit in (0, 1):
                left = bit if pointer == -1 else 0
                right = bit << pointer if pointer >= 0 else 0
                for c in "*<>/\\":
                    state = _State(0, pointer, direction, left, right)
                    after = _advance(state, c, (0,))
                    if c in "<>":
                        assert after.pointer == pointer + direction * (
                            1 if c == ">" else -1
                        )
                        assert after.left == left
                        assert after.right == right
                    else:
                        toggle = (
                            c == "*"
                            or (c == "/" and direction == 1)
                            or (c == "\\" and direction == -1)
                        )
                        mask = after.left if pointer < 0 else after.right >> pointer
                        assert mask & 1 == bit ^ toggle
                    assert after.cursor == direction
                    assert after.direction == direction
    code, pairs, _ = _parse("{*}")
    for cursor in (0, 2):
        for direction in (-1, 1):
            for bit in (0, 1):
                after = _advance(_State(cursor, 0, direction, 0, bit), code, pairs)
                expected_direction = -direction if bit else direction
                assert (
                    after.cursor == (2 - cursor if bit else cursor) + expected_direction
                )
                assert after.direction == expected_direction
                assert after.right == bit
    for source in ("?", "{", "}", "{*}{"):
        with pytest.raises(ValueError, match=r"command|brace"):
            _Machine(source, ScriptedIO())
    vm = _Machine("< * > /", ScriptedIO())
    for _ in range(5):
        vm.step()
    assert vm.halted
    assert vm.memory == [1, 1]
    assert vm.ptr == 0
    assert vm.io.getvalue() == "1"
    check_image_reuse(
        "Retrograde", "< * > /", native, "_parse", monkeypatch, cases=(("", "1"),) * 3
    )
