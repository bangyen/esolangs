"""Language-specific generator execution helpers."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import FirstDraw


def run_laserfuck(program: str, inputs: list[str], heading: int) -> str:

    from esolangs.languages.laserfuck.interpreter import run

    buffer = io.StringIO()

    class FakeIO(IO):
        def __init__(self, ins: list[str]) -> None:
            self._ins = list(ins)

        def input_char(self, _prompt: str = "Input: ") -> int:
            return ord(self._ins.pop(0))

        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_str(self, text: str) -> None:
            buffer.write(text)

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

    with redirect_stdout(buffer):
        run(program.splitlines(), FakeIO(inputs), rng=FirstDraw(heading))
    # The generator runs in decimal output mode and drives the input cells
    # negative, which dump() skips, so the tape prints as exactly the answer
    # -- no filtering needed, and asserting on the raw output is stricter.
    return buffer.getvalue()
