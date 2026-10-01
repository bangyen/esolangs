"""Probe an injected fold/decoder handoff, not a packed standalone source."""

import itertools

from address_gadget import execute_state
from decoder_group import _build, _expected, _setup
from runtime_decoder import _finish, _prefill, _prepare
from shared_fold import build_shared_fold


def main() -> None:
    """Execute both address families and all decoder rows and meaning triples."""
    outputs: dict[str, int] = {}
    source, groups, _, _ = build_shared_fold(outputs=outputs)
    interface = (outputs["pointer"], *groups[-1])
    assert interface == (142, 145, 139, 144)
    folds = []
    for prefix in ((0, 0), (1, 1)):
        for tail in itertools.product((0, 1), repeat=3):
            bits = prefix + (0,) * 9 + tail
            _, memory = execute_state(source, bits)
            folds.append((bits, memory))
    group = _setup(frozenset(interface), external_pointer=True, runtime_base=True)
    total = 0
    for row in range(8):
        emission = _build(
            row,
            group,
            row_offset=200 * row,
            external_pointer=True,
            external_parity=True,
        )
        state, prepared = _prepare(emission)
        for bits, folded in folds:
            base = folded[interface[0]] + 1
            assert not any(
                base + offset in emission.code or base + offset in emission.data
                for offset in range(4)
            ), (row, bits, base)
            entry: dict[int, int] = {}
            triples = tuple(itertools.product(range(7), repeat=3))
            for triple in triples:
                memory = list(prepared)
                prefill = _prefill(base, triple)
                assert all(prefill[cell] == folded[cell] for cell in interface)
                for address, value in prefill.items():
                    memory[address] = value
                assert _finish(
                    state, memory, entry=entry, dynamic=frozenset(prefill)
                ) == [ord(_expected(row, triple))]
            assert not set(interface) & set(entry)
            for triple in triples:
                memory = list(folded)
                for address, value in entry.items():
                    memory[address] = value
                for address, value in _prefill(base, triple).items():
                    if address not in interface:
                        memory[address] = value
                assert _finish(state, memory) == [ord(_expected(row, triple))], (
                    row,
                    bits,
                    triple,
                )
                total += 1
        print(f"row {row}: {len(folds) * 343} injected handoffs passed")
    assert total == 8 * 16 * 343
    print(f"fold/decoder interface: {total} cases; setup and entry injected")


if __name__ == "__main__":
    main()
