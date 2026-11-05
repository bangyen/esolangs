"""Layer edges reconstruct the table in row order, including constant tails."""

from itertools import product

from esolangs.generation.decision import decision_layers


def test_layers_retain_every_input_and_first_occurrence_order():
    for n in range(1, 4):
        for bits in product("01", repeat=1 << n):
            diagram = decision_layers("".join(bits))
            seen = [{} for _ in range(n)]
            assert len(diagram.children) == n
            for row, bit in enumerate(bits):
                node = diagram.root
                for depth, layer in enumerate(diagram.children):
                    seen[depth].setdefault(node)
                    node = layer[node][(row >> (n - depth - 1)) & 1]
                assert node == int(bit)
            assert list(map(list, seen)) == list(map(list, diagram.children))
