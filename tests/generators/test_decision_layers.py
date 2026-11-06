"""Layer edges reconstruct the table in row order, including constant tails."""

from itertools import product

import pytest

from esolangs.generation.decision import decision_layers, fold_subtables


def test_layers_retain_every_input_and_first_occurrence_order():
    with pytest.raises(ValueError, match="Boolean leaves"):
        fold_subtables("01", {"0": "0"}, str.__add__)

    def forbidden(*_parts):
        pytest.fail("an emitter terminal was expanded")

    assert (
        fold_subtables("0000", {"0": "0", "1": "1", "0000": "macro"}, forbidden)
        == "macro"
    )
    for n in range(1, 4):
        for bits in product("01", repeat=1 << n):
            table = "".join(bits)
            calls = []
            terminals = {"0": "0", "1": "1", "01": "01"}

            def combine(zero, one, calls=calls):
                calls.append(zero + one)
                return zero + one

            assert fold_subtables(table, terminals, combine) == table
            assert terminals == {"0": "0", "1": "1", "01": "01"}
            expected = {
                table[at : at + span]
                for depth in range(n)
                for span in (1 << (n - depth),)
                for at in range(0, len(table), span)
            } - terminals.keys()
            assert len(calls) == len(set(calls))
            assert set(calls) == expected
            diagram = decision_layers(table)
            seen = [{} for _ in range(n)]
            assert len(diagram.children) == n
            for row, bit in enumerate(bits):
                node = diagram.root
                for depth, layer in enumerate(diagram.children):
                    seen[depth].setdefault(node)
                    node = layer[node][(row >> (n - depth - 1)) & 1]
                assert node == int(bit)
            assert list(map(list, seen)) == list(map(list, diagram.children))
