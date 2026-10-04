import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other.inject import _Machine
from esolangs.tools.inject import inject
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.inject_cases import edge_cases, finite_cases
from tests.interpreters.inject_observer import check
from tests.interpreters.test_inject import (
    CAT,
    HELLO_WORLD,
    INJECT_TRUTH_MACHINE,
    WIKI_TRUTH_MACHINE,
)


@pytest.mark.parametrize("shard", range(8))
def test_finite_state(shard):
    for source, text in (finite_cases() + edge_cases())[shard::8]:
        check(source, text)


@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_small_generated_state(n, shard):
    for bits in itertools.islice(
        itertools.product("01", repeat=2**n), shard, None, 16 if n == 3 else 1
    ):
        table = "".join(bits)
        for source in dict.fromkeys(inject(table, w) for w in (None, 1, 13, 100)):
            for row, answer in enumerate(table):
                result = check(source, "\n".join(format(row, f"0{n}b")) + "\n")
                assert result["halted"]
                assert result["error"] is None
                assert result["output"] == answer + "\n"
                assert result["reads"] == n


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "family", "shard", "shards"),
    [
        (n, f, s, 32 if n >= 9 else 8)
        for n in range(4, 11)
        for f in ("zero", "one", "parity", "sparse", "dense", "random")
        for s in range(32 if n >= 9 else 8)
    ],
)
def test_wide_generated_state(n, family, shard, shards):
    rng = random.Random(1000 + n)
    tables = {
        "zero": "0" * 2**n,
        "one": "1" * 2**n,
        "parity": "".join(str(i.bit_count() % 2) for i in range(2**n)),
        "sparse": "".join(
            "1" if i in (0, 2**n - 1, 2 ** (n - 1)) else "0" for i in range(2**n)
        ),
        "dense": "".join(
            "0" if i in (0, 2**n - 1, 2 ** (n - 1)) else "1" for i in range(2**n)
        ),
        "random": "".join(rng.choice("01") for _ in range(2**n)),
    }
    table = tables[family]
    for source in dict.fromkeys(inject(table, w) for w in (None, 1, 13, 100)):
        for row in range(shard, 2**n, shards):
            result = check(source, "\n".join(format(row, f"0{n}b")) + "\n")
            assert result["halted"]
            assert result["error"] is None
            assert result["output"] == table[row] + "\n"
            assert result["reads"] == n


@pytest.mark.parametrize(
    ("source", "text", "output", "error"),
    [
        (HELLO_WORLD, "", "Hello, world!\n", None),
        (CAT, "ab\ncd\n\n", "ab\ncd\n", None),
        (CAT, "ab\n", "ab\n", "eof"),
        (WIKI_TRUTH_MACHINE, "1\n", "1\n", None),
        (INJECT_TRUTH_MACHINE, "0\n", "0\n", None),
    ],
)
def test_published_state(source, text, output, error):
    result = check(source, text)
    assert result["output"] == output
    assert result["error"] == error


@pytest.mark.parametrize(
    ("source", "text"),
    [
        (WIKI_TRUTH_MACHINE, "0\n"),
        (INJECT_TRUTH_MACHINE, "1\n"),
        ("loop;\nsend data\nskip\nloop;\ndata;\nx\ndata;", ""),
        (
            "wide;\nnarrow;\nsend mark\nskip\nnarrow;\nsend mark\n"
            "wide;\nmark;\nM\nmark;",
            "",
        ),
    ],
)
def test_cyclic_state(source, text):
    with pytest.raises(AssertionError, match="bound"):
        check(source, text, limit=24)
    assert not run_until_halt_or_cycle(_Machine(source, ScriptedIO(text)), limit=100)


class Cursorless(IO):
    def __init__(self):
        super().__init__()
        self.values = iter(["x"] * 8)
        self.successful = 0

    def _read(self, _prompt):
        try:
            value = next(self.values)
        except StopIteration:
            raise EOFError from None
        self.successful += 1
        return value

    def _write(self, _value):
        pass


def test_cursorless_consumption():
    io = Cursorless()
    vm = _Machine("loop;\nreadto data\nskipif data\nloop;\ndata;\ndata;", io)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(vm, limit=100)
    assert io.successful == 8


def test_fixed_spans_distinguish_future_behavior():
    left = _Machine("inject x=a;/b;\nx;\na;\npayload\na;\nx;\nsend a", ScriptedIO())
    left.step()
    right = _Machine("\n".join(left.lines), ScriptedIO())
    right.step()
    assert left.snapshot() != right.snapshot()
    while not left.halted:
        left.step()
    assert left.io.getvalue() == "payload\n"
    with pytest.raises(ValueError, match="unknown label: a"):
        run_until_halt_or_cycle(right)


@pytest.mark.parametrize(
    ("source", "text", "message", "reads"),
    [
        (
            "readto outer\nouter;\ninner;\nx\ninner;\nouter;\nsend inner",
            "v\n",
            "a rewrite cannot remove another block's delimiters",
            1,
        ),
        (
            "a;\nreadto a\n" + "junk\n" * 9 + "a;",
            "v\n",
            "rewrite would move the pointer before the program",
            1,
        ),
        (
            r"inject data=x/\2" + "\nskip\ndata;\nx\ndata;",
            "",
            r"invalid replacement: \2",
            0,
        ),
        (
            r"inject data=x/\g<missing>" + "\nskip\ndata;\nx\ndata;",
            "",
            r"invalid replacement: \g<missing>",
            0,
        ),
    ],
)
def test_invalid_transition_is_atomic(source, text, message, reads):
    vm = _Machine(source, ScriptedIO(text))
    if source.startswith("a;"):
        vm.step()
    before = (tuple(vm.lines), dict(vm.spans), vm.ind, vm.done)
    with pytest.raises(HaltError) as error:
        vm.step()
    assert str(error.value) == message
    assert (tuple(vm.lines), vm.spans, vm.ind, vm.done) == before
    assert vm.snapshot()[4] == reads
    assert vm.io.getvalue() == ""


def test_skip_before_an_instruction_halts_without_executing_it():
    result = check("skip\nsend data\ndata;\nnever\ndata;", "")
    assert result["halted"]
    assert result["output"] == ""
    assert result["error"] is None
