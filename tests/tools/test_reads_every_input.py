"""Every generated program reads all n inputs; an ignored one is read, then dropped."""

import pytest

import esolangs
from esolangs import vm
from esolangs.interpreters.io import ScriptedIO

IGNORING = ["0101", "01100110", "0011", "00111100", "".join(c * 2 for c in "0110" * 8)]
INFOS = {n: esolangs.describe(n) for n in esolangs.list_languages()}


def _audit(name, program, n, mp):
    """Run every row; return (rows run, rows leaving input unread, past-end reads)."""
    made = []
    new = lambda stdin="": made.append(ScriptedIO(stdin)) or made[-1]  # noqa: E731
    mp.setattr(esolangs, "ScriptedIO", new)
    mp.setattr(vm, "ScriptedIO", new)
    rows = unread = past = 0
    for row in range(1 << n):
        stdin = esolangs.encode_inputs(name, [row >> s & 1 for s in reversed(range(n))])
        if INFOS[name]["answer_mode"] != "termination":
            esolangs.run(name, program, stdin=stdin, timeout=10)
        elif not vm.run_until_halt_or_cycle(vm.make_vm(name, program, stdin=stdin)):
            continue  # a 1 is a hang
        rows += 1
        unread += bool(stdin[made[-1].position() :].strip())
        past += made[-1].past_end
    return rows, unread, past


GENERATED = [
    n for n, i in INFOS.items() if i["boolean_generator"] and not i["parameterized"]
]


@pytest.mark.medium
def test_the_audit_sees_unread_input(monkeypatch):
    assert _audit("brainfuck", ",.", 2, monkeypatch) == (4, 4, 0)


# One case per language and path: the whole sweep in one test overran its band.
@pytest.mark.medium
@pytest.mark.parametrize(
    ("name", "path"),
    [
        (name, path)
        for path in ({}, {"width": 1}, {"balance": True})
        for name in GENERATED
        if "width" not in path or INFOS[name]["width_aware"]
    ],
    ids=str,
)
def test_every_input_is_read(monkeypatch, name, path):
    for table in IGNORING:
        n = (len(table) - 1).bit_length()
        if n <= (INFOS[name]["generator_max_inputs"] or 6):
            program = esolangs.generate(name, table, **path)
            rows, unread, past = _audit(name, program, n, monkeypatch)
            assert rows > 0
            assert unread == 0, (name, table)
            # A language that ends at EOF probes it once a row, no more.
            assert past in (0, rows), (name, table)
