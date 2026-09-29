"""Execute an emitted consumer of the fold/decoder setup's live constants."""

import itertools
from collections.abc import Iterator

from address17 import ALL1, ALL2, group_word
from address_gadget import execute_state
from decoder_group import _LABELS, _Group, _setup
from parity_views import STORED_PARITY
from shared_fold import build_shared_fold

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools._malbolge_core import _char_for
from esolangs.tools.malbolge import _Planner


def control_inputs() -> Iterator[tuple[int, ...]]:
    """Return eight selector controls for each leading-bit address family."""
    for prefix in itertools.product((0, 1), repeat=2):
        for tail in itertools.product((0, 1), repeat=3):
            yield prefix + (0,) * 9 + tail


def check_setup_memory(
    memory: list[int],
    groups: tuple[tuple[int, int, int], ...],
    outputs: dict[str, int],
    group: _Group,
    bits: tuple[int, ...],
) -> None:
    """Check labels, constants and actual fold outputs after a consumer runs."""
    assert all(
        memory[cell] == group.hub_values[_LABELS.get(cell, "N")][0]
        for cell in range(34, 128)
    )
    assert tuple(
        memory[outputs[name]]
        for name in ("decoder_zero", "decoder_all1", "decoder_all2")
    ) == (0, ALL1, ALL2)
    pointer = _crazy(ALL2 - 2, group_word(list(bits)))
    assert memory[outputs["pointer"]] == pointer
    assert tuple(memory[cell] for cell in groups[-1]) == tuple(
        STORED_PARITY[(pointer + 1 + offset) % 2] for offset in range(3)
    )


def main() -> None:
    """Append real instructions; check 32 controls without host state injection."""
    outputs: dict[str, int] = {}
    occupied: set[int] = set()
    plans: list[_Planner] = []
    source, groups, _, _ = build_shared_fold(
        decoder_constants=True,
        decoder_plans=plans,
        outputs=outputs,
        occupied=occupied,
    )
    assert len(plans) == 1
    plan = plans[0]
    assert (plan.c, plan.d) == (
        outputs["decoder_continuation_c"],
        outputs["decoder_continuation_d"],
    )
    replaced_halt = plan.c
    data = dict(plan.data)
    expected = (0, ALL1, ALL2)
    cells = tuple(
        outputs[name] for name in ("decoder_zero", "decoder_all1", "decoder_all2")
    )
    for cell, value in zip(cells, expected, strict=True):
        assert plan.mem[cell] == value
        plan.op("*", cell)
        plan.mem[cell] = value
        plan.raw("<")
    plan.raw("v")
    assert set(plan.code) & occupied == {replaced_halt}
    assert plan.data == data
    rendered = list(source)
    for address, operation in plan.code.items():
        rendered[address] = chr(_char_for(operation, address))
    source = "".join(rendered)
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    total = 0
    for bits in control_inputs():
        printed: list[int] = []
        state, memory = execute_state(source, bits, printed)
        assert state[1] == plan.c - 1
        assert printed == [value & 255 for value in expected]
        assert tuple(memory[cell] for cell in cells) == expected
        check_setup_memory(memory, groups, outputs, group, bits)
        total += 1
    print(f"live setup consumer: {total} full-source controls passed")


if __name__ == "__main__":
    main()
