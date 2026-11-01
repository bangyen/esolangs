"""Every generated program reads all n inputs, then prints; ignored ones are dropped."""

import pytest

import esolangs
from esolangs import vm
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import assert_proved_resource_cap
from tests.support.reference import REFERENCE

IGNORING = [
    "00000000",
    "11111111",
    "0101",
    "01100110",
    "0011",
    "00111100",
    "".join(c * 2 for c in "0110" * 8),
]
INFOS = {n: esolangs.describe(n) for n in esolangs.list_languages()}


def _audit(name, program, n, mp):
    """Run every row; return rows, unread rows, past-end reads, early-output rows."""
    made, early = [], []

    def new(stdin=""):
        io = made.append(ScriptedIO(stdin)) or made[-1]
        write = io._write  # noqa: SLF001

        def checked(value):
            if str(value).strip() and stdin[io.position() :].strip():
                early.append(len(made))
            write(value)

        io._write = checked  # noqa: SLF001
        return io

    mp.setattr(esolangs, "ScriptedIO", new)
    mp.setattr(vm, "ScriptedIO", new)
    rows = unread = past = 0
    for row in range(1 << n):
        stdin = esolangs.encode_inputs(name, [row >> s & 1 for s in reversed(range(n))])
        if INFOS[name]["answer_mode"] != "termination":
            esolangs.run(name, program, stdin=stdin, timeout=10)
        else:
            # A proven cycle is an answer too; its input must still be consumed.
            vm.run_until_halt_or_cycle(vm.make_vm(name, program, stdin=stdin))
        rows += 1
        unread += bool(stdin[made[-1].position() :].strip())
        past += made[-1].past_end
    return rows, unread, past, len(set(early))


GENERATED = [
    n for n, i in INFOS.items() if i["boolean_generator"] and not i["parameterized"]
]


@pytest.mark.medium
def test_the_audit_sees_unread_input(monkeypatch) -> None:
    assert _audit(REFERENCE, ",.", 2, monkeypatch) == (4, 4, 0, 4)


@pytest.mark.medium
def test_the_audit_sees_early_output(monkeypatch) -> None:
    assert _audit("brainfuck", ",+.,", 2, monkeypatch) == (4, 0, 0, 4)


@pytest.mark.medium
def test_the_audit_checks_cycling_answers(monkeypatch) -> None:
    info = {**INFOS[REFERENCE], "answer_mode": "termination"}
    monkeypatch.setitem(INFOS, REFERENCE, info)
    assert _audit(REFERENCE, ",[]", 1, monkeypatch) == (2, 0, 0, 0)


# One case per language and path: the whole sweep in one test overran its band.
@pytest.mark.medium
@pytest.mark.parametrize(
    ("name", "path"),
    [
        (name, path)
        for path in ({}, {"width": 1}, {"balance": True})
        for name in GENERATED
        if "width" not in path or INFOS[name]["width_effect"] == "layout"
    ],
    ids=str,
)
def test_every_input_is_read(monkeypatch, name, path) -> None:
    built = 0
    for table in IGNORING:
        n = (len(table) - 1).bit_length()
        if n <= (INFOS[name]["generator_max_inputs"] or 6):
            try:
                program = esolangs.generate(name, table, **path)
            except esolangs.GeneratorCapError:
                assert_proved_resource_cap(name)
                continue
            built += 1
            rows, unread, past, early = _audit(name, program, n, monkeypatch)
            assert rows > 0
            assert unread == 0, (name, table)
            assert early == 0, (name, table)  # output follows the last read
            # A language that ends at EOF probes it once a row, no more.
            assert past in (0, rows), (name, table)
    assert built, f"{name} never built an input-consumption control"
