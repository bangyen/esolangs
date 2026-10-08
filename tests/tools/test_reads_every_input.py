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


@pytest.mark.medium
@pytest.mark.parametrize("path", [{}, {"width": 1}, {"balance": True}], ids=str)
def test_every_input_is_read(monkeypatch, path):
    assert _audit("brainfuck", ",.", 2, monkeypatch) == (4, 4, 0)  # positive control
    for name, info in INFOS.items():
        if info["parameterized"] or not info["boolean_generator"]:
            continue
        if "width" in path and not info["width_aware"]:
            continue
        for table in IGNORING:
            n = (len(table) - 1).bit_length()
            if n <= (INFOS[name]["generator_max_inputs"] or 6):
                program = esolangs.generate(name, table, **path)
                rows, unread, past = _audit(name, program, n, monkeypatch)
                assert rows > 0
                assert unread == 0, (name, table)
                # Smu (a bit per run) and Suffolk (ends at EOF) probe EOF once.
                assert past == rows * (name in ("Smu", "Suffolk")), (name, table)
