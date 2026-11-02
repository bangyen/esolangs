"""Bounded byte grids with branches, deterministic draws and self-modification."""

import itertools
import random
from struct import calcsize

import pytest

from esolangs.languages.befunge.interpreter import _Machine, run
from tests.interpreters.memory_oracles import agrees_memory, befunge


def check_raw_befunge():
    corpus = [
        list(map("".join, [words]))
        for n in range(3)
        for words in itertools.product("01+-*:.g,p#_@", repeat=n)
    ]
    corpus += [
        [source]
        for source in (
            "07-2/.@",
            "07-2%.@",
            "10/.@",
            "10%.@",
            "~,@",
            "&.@",
            "&~,.@",
            '"@"60p1@',
            '"9"00p00g.@',
            '"ABC"\\:,,,@',
            '"~&?"',
            "99*99**.@",
            "9:*:*:*:*:*:*:*:.@",
            "80g.@",
            "01-0g.@",
            '"Z"01-0p@',
            '"Z"089*p@',
            "1_@",
            "0|@",
            '"\xff",@',
            "0!1`$.@",
            '"unterminated',
            "@" + " " * 81,
        )
    ]
    corpus += [
        [],
        ["", ""],
        ["@" * 81],
        [" "] * 26,
        ["λ"],
        ["v  @", ">12+.@"],
        ["<@" + " " * 77 + "@"],
        ["^"] + [""] * 23 + ["@"],
    ]
    rng = random.Random(20261102)
    for _ in range(48):
        corpus.append(
            [
                "".join(rng.choices('0129+-*/%!`:\\$><^v_|#gp,.&~?@" ', k=8))
                for _ in range(rng.randrange(1, 4))
            ]
        )
    final = []
    for code in corpus:
        for stdin in ("", "0 -3 A\n", "λ 9", " \t"):
            final.append(
                agrees_memory(_Machine, befunge, code, stdin, grid=True, runner=run)[-1]
            )
    assert {row.error for row in final} == {None, "syntax", "input", "argument", "halt"}
    assert any(not row.halted and not row.error for row in final)
    assert any(row.string for row in final)
    assert any(row.draws for row in final)
    rewritten = befunge(['"@"60p1@'], "")[-1]
    assert rewritten.halted
    assert rewritten.memory[0][6] == "@"
    cross = ["?@" + " " * 77 + "@", "@"] + [""] * 22 + ["@"]
    for first in range(4):
        trace = agrees_memory(
            _Machine, befunge, cross, grid=True, first=first, runner=run
        )
        assert trace[-1].halted
        assert trace[-1].draws == 1
    loop = agrees_memory(_Machine, befunge, ["<"], grid=True)
    assert len(loop) == 33
    assert loop[-1].cursor == (48, 0, -1, 0)
    assert not loop[-1].halted
    bits = calcsize("@l") * 8
    for value in (
        -(2 ** (bits - 1)),
        2 ** (bits - 1) - 1,
        -(2 ** (bits - 1)) - 1,
        2 ** (bits - 1),
    ):
        agrees_memory(_Machine, befunge, ["&1+.@"], str(value), grid=True)
        agrees_memory(_Machine, befunge, ["&.@"], str(value), grid=True)

    class MissingPut(_Machine):
        def step(self):
            before = self.state
            x, y, _dx, _dy = before.cursor
            super().step()
            if not before.string and before.grid[y][x] == "p":
                self.state = self.state._replace(grid=before.grid)

    with pytest.raises(AssertionError):
        agrees_memory(MissingPut, befunge, ['"@"60p1@'], grid=True)

    class FloorDivision(_Machine):
        def step(self):
            before = self.state
            x, y, _dx, _dy = before.cursor
            values = self.stack
            super().step()
            if (
                not before.string
                and before.grid[y][x] == "/"
                and len(values) >= 2
                and values[-1]
            ):
                wrong = values[-2] // values[-1]
                self.state = self.state._replace(stack=(wrong, self.state.stack[1]))

    with pytest.raises(AssertionError):
        agrees_memory(FloorDivision, befunge, ["07-2/.@"], grid=True)
