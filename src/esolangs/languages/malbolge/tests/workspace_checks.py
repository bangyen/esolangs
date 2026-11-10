"""Full finite-word Malbolge observations on the preserved prefix corpus."""

from io import StringIO
from itertools import chain

from esolangs.languages.malbolge.interpreter import _Machine
from tests.support import workspace_oracle as workspace

from . import full_oracle
from .reference_cases import cases

MODEL = workspace.workspace_model(
    "malbolge-v1", "accumulator instruction data stopped memory input_cursor"
)


def parts(row):
    return (*row[0], row[3])


def io_rows(rows, stdin):
    reads = past = 0
    character_reads = newline = False
    expected = []
    for index, row in enumerate(rows):
        if index and rows[index - 1][0] is not None:
            old = rows[index - 1]
            _a, c, _d, halted, pages = old[0]
            word = pages[c // 64][c % 64]
            if not halted and 33 <= word <= 126 and (word + c) % 94 == 23:
                character_reads = True
                if old[3] < len(stdin):
                    reads += 1
                    newline = False
                else:
                    past += 1
            if row[2] != old[2]:
                newline = not row[2].endswith("\n")
        expected.append(
            {
                "_source": stdin,
                "_supplied": stdin.count("\n")
                + int(bool(stdin) and not stdin.endswith("\n")),
                "_offset": row[3],
                "_line_reads": 0,
                "_character_reads": character_reads,
                "_past_end": past,
                "_pending": "",
                "_reads": reads,
                "_consumed": row[3],
                "_newline": newline,
                "_buffer": (row[2], "\n", len(row[2]), None),
            }
        )
    return expected


def exact_io(port, wanted):
    actual = vars(port).copy()
    assert type(actual["_buffer"]) is StringIO
    assert not actual["_buffer"].closed
    actual["_buffer"] = actual["_buffer"].__getstate__()
    assert actual.keys() == wanted.keys()
    assert all(type(actual[k]) is type(v) and actual[k] == v for k, v in wanted.items())


def check(factory, source, stdin, cap=128):
    assert cap == 128
    expected = full_oracle._full_model(source, stdin)
    ios = iter(io_rows(expected[1], stdin))
    expected_rows = iter(expected[1])
    keys = []

    def state(machine):
        wanted_io = next(ios)
        row = next(expected_rows)
        exact_io(machine.io, wanted_io)
        assert type(machine.state) is tuple
        assert len(machine.state) == 4
        a, c, d, halted = machine.state
        assert all(type(value) is int for value in (a, c, d))
        assert type(halted) is bool
        assert type(machine.memory) is list
        assert len(machine.memory) == 59049
        assert set(map(type, machine.memory)) == {int}
        assert type(machine.halted) is bool
        assert machine.halted == halted
        assert (
            machine.ip is None
            if halted
            else type(machine.ip) is int and machine.ip == c
        )
        captured = machine.workspace_snapshot()
        assert type(captured.parts) is tuple
        assert len(captured.parts) == 6
        assert all(type(value) is int for value in captured.parts[:3])
        assert type(captured.parts[3]) is bool
        assert type(captured.parts[5]) is int
        pages = captured.parts[4]
        assert type(pages) is tuple
        assert len(pages) == 923
        assert all(type(page) is tuple for page in pages)
        assert all(len(page) == 64 for page in pages[:-1])
        assert len(pages[-1]) == 41
        assert set(map(type, chain.from_iterable(pages))) == {int}
        key = machine.snapshot()
        assert type(key) is tuple
        assert len(key) == 6
        assert all(type(v) is int for v in key[:3])
        assert type(key[3]) is bool
        assert type(key[4]) is tuple
        assert type(key[5]) is int
        assert all(type(chunk) is tuple for chunk in key[4])
        assert set(map(type, chain.from_iterable(key[4]))) == {int}
        chunks = tuple(
            part for page in row[0][4] for part in (page[:32], page[32:]) if part
        )
        reference_key = (*row[0][:4], chunks, row[3])
        assert key == reference_key
        keys.append((key, reference_key, hash(key)))
        return (
            *machine.state,
            tuple(
                tuple(machine.memory[start : start + 64])
                for start in range(0, 59049, 64)
            ),
        )

    def checked_factory(code, port):
        try:
            return factory(code, port)
        except ValueError:
            exact_io(port, next(ios))
            assert next(expected_rows)[0] is None
            raise

    result = workspace.agrees(
        expected, (checked_factory, source, stdin), (MODEL, parts), state, cap=cap
    )
    assert next(ios, None) is None
    assert next(expected_rows, None) is None
    assert all(
        key == wanted and hash(key) == saved_hash for key, wanted, saved_hash in keys
    )
    return result


def check_workspace_malbolge(corpus=None):
    for source, stdin, cap in cases() if corpus is None else corpus:
        assert cap == 128
        check(_Machine, source, stdin, cap)
    error, rows = full_oracle._full_model("ubO", "A")
    assert error is None
    assert rows[-1][2] == "A"
    assert workspace.charged_bits(MODEL, (parts(row) for row in rows)) == 649540
    workspace.check_erasures(MODEL, check, _Machine, "ubO", "A")
