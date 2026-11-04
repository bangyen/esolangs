"""Raw instruction memories, including code writes and missing operands."""

import itertools
import random

import pytest

from esolangs.languages.decleq.interpreter import _Machine, run
from tests.interpreters.memory_oracles import agrees_memory, decleq


def check_raw_decleq():
    corpus = [
        " ".join(map(str, words))
        for words in itertools.product(
            (-3, -2, -1, 0, 1, 3, 7), (-7, -3, -1, 0, 2, 3, 7), (-1, 0, 1, 3, 6, 9)
        )
    ]
    corpus += [
        "",
        "# only a comment",
        "0",
        "-1",
        "-2",
        "0 0",
        "1 1 x",
        "1, 2 3",
        "1 1 3 # ignored\n-2 1 0",
        "6 2 9 0 0 99 1",
        "-1 5 0 -2 5",
        "-1 3 99",
        "0 -3 -1",
        "0 -4 -1",
        f"0 {2**24} 0",
        f"-1 {2**24} 0",
        "3 3 0 5",
        "3 7 -1 1",
        "0 -1 -1",
    ]
    corpus += ["6 7 0 0 0 0 0 0", "+1_0 0 -1", "٣ 0 -1"]
    rng = random.Random(20261102)
    for _ in range(64):
        corpus.append(
            " ".join(
                map(
                    str,
                    rng.choices(
                        (-3, -2, -1, 0, 1, 2, 3, 7, 12), k=rng.randrange(1, 13)
                    ),
                )
            )
        )
    final = []
    final.extend(
        agrees_memory(_Machine, decleq, source, stdin, runner=run)[-1]
        for source in corpus
        for stdin in ("", "\0Z", "λ\n")
    )
    assert {row.error for row in final} == {None, "syntax", "input", "halt", "limit"}
    assert any(not row.halted and not row.error for row in final)
    assert any(len(row.memory) > 12 for row in final)
    changed = decleq("6 2 9 0 0 99 1", "")[-1]
    assert changed.memory[2] == 0
    assert changed.cursor == (9,)  # jump was fetched before its cell was rewritten
    assert decleq("-1 5 0 -2 5", "Z")[-1].output == "Z"

    loop = agrees_memory(_Machine, decleq, "6 7 0 0 0 0 0 0")
    assert len(loop) == 33
    assert not loop[-1].halted
    assert loop[-1].error is None

    class OldEnd(_Machine):
        def __init__(self, code, io):
            super().__init__(code, io)
            self.old_end = len(self.memory)

        @property
        def halted(self):
            return self.pc < 0 or self.pc >= self.old_end

    with pytest.raises(AssertionError):
        agrees_memory(OldEnd, decleq, "-1 3 99", "\0")
