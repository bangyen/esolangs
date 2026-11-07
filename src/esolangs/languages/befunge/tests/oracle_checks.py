"""Bounded byte grids with branches, deterministic draws and self-modification."""

import itertools
import random
from functools import lru_cache
from struct import calcsize

import pytest

from esolangs.languages.befunge.interpreter import _Machine, run
from tests.interpreters.memory_oracles import agrees_memory as _agrees_memory
from tests.interpreters.memory_oracles import befunge
from tests.support.workspace_oracle import (
    charged_bits,
    missing_workspace,
    workspace_model,
)

_WORKSPACE = workspace_model(
    "befunge-v1", "x y dx dy grid stack string stopped input_cursor"
)


@lru_cache(maxsize=1)
def _grid(image):
    return tuple(tuple(image[start : start + 80]) for start in range(0, 2000, 80))


def _parts(row):
    return (
        *row.cursor,
        _grid(row.memory[0]),
        row.stack,
        row.string,
        row.halted,
        row.consumed,
    )


def agrees_memory(*args, **kwargs):
    return _agrees_memory(*args, **kwargs, workspace=(_WORKSPACE, _parts))


def corpus():
    codes = [
        list(map("".join, [words]))
        for n in range(3)
        for words in itertools.product("01+-*:.g,p#_@", repeat=n)
    ]
    codes += [
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
    codes += [
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
        codes.append(
            [
                "".join(rng.choices('0129+-*/%!`:\\$><^v_|#gp,.&~?@" ', k=8))
                for _ in range(rng.randrange(1, 4))
            ]
        )
    for code, stdin in itertools.product(codes, ("", "0 -3 A\n", "λ 9", " \t")):
        yield code, stdin, 0, 32
    cross = ["?@" + " " * 77 + "@", "@"] + [""] * 22 + ["@"]
    for first in range(4):
        yield cross, "", first, 32
    yield ["<"], "", 0, 32
    yield ["~@"], "Q", 0, 32
    bits = calcsize("@l") * 8
    for value, code in itertools.product(
        (
            -(2 ** (bits - 1)),
            2 ** (bits - 1) - 1,
            -(2 ** (bits - 1)) - 1,
            2 ** (bits - 1),
        ),
        ("&1+.@", "&.@"),
    ):
        yield [code], str(value), 0, 32
    for source in ('" "90p@', '"A"90p@', "@"):
        yield [source], "", 0, 32
    for token in ("9" * 5000, "-" + "9" * 5000, "0" * 5000 + "1"):
        yield ["&.@"], token, 0, 32


@pytest.mark.medium
def check_raw_befunge():
    final = [
        agrees_memory(
            _Machine, befunge, code, stdin, grid=True, first=first, runner=run
        )[-1]
        for code, stdin, first, _cap in corpus()
    ]
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

    for component, code, stdin in (
        ("x", ["@"], ""),
        ("y", ["v", "@"], ""),
        ("dx", ["<"], ""),
        ("dy", ["v"], ""),
        ("grid", ['"A"00p@'], ""),
        ("stack", ["1@"], ""),
        ("string", ['"@'], ""),
        ("stopped", ["@"], ""),
        ("input_cursor", ["~@"], "Q"),
    ):
        with pytest.raises(AssertionError):
            agrees_memory(
                missing_workspace(_Machine, component), befunge, code, stdin, grid=True
            )
    for source, changed in (('" "90p@', False), ('"A"90p@', True)):
        trace = agrees_memory(_Machine, befunge, [source], grid=True)
        assert (trace[0].memory != trace[-1].memory) == changed
    halted = agrees_memory(_Machine, befunge, ["@"], grid=True)
    assert halted[-1].cursor == (1, 0, 1, 0)
    for token in ("9" * 5000, "-" + "9" * 5000, "0" * 5000 + "1"):
        agrees_memory(_Machine, befunge, ["&.@"], token, grid=True)
    for code, stdin, bits in (
        (["@"], "", 2),
        (["1@"], "", 4),
        (['" "90p@'], "", 16),
        (['"A"90p@'], "", 16017),
        (["~@"], "Q", 11),
    ):
        rows = agrees_memory(_Machine, befunge, code, stdin, grid=True)
        assert charged_bits(_WORKSPACE, map(_parts, rows)) == bits
