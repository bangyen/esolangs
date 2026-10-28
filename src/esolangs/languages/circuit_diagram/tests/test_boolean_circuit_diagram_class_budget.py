"""The complete two-input basis through the suffix forest."""

from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


def test_complete_two_input_basis_has_fourteen_gates_plus_complements() -> None:
    words = [f"{value:04b}" for value in range(1, 15)]
    model, endpoints = _suffix_forest(words, 2)
    assert sum(char in "ao~xX" for char in model.glyphs.values()) == 16
    outputs = {point for point, char in model.glyphs.items() if char == ":"}
    for word, endpoint in zip(words, endpoints, strict=True):
        assert endpoint is not None
        chosen = endpoint[0] + 2, endpoint[1]
        for point in outputs:
            model.glyphs[point] = ":" if point == chosen else "-"
        code = model.render().splitlines()
        for row in range(4):
            io = ScriptedIO(f"{row:02b}")
            vm = _Machine(code, io)
            for _ in range(6):
                if vm.halted:
                    break
                vm.step()
            assert vm.halted
            assert io.progress() == 2
            assert io.getvalue() == word[row]
