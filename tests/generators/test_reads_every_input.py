"""Every generated program reads all n inputs, then prints; ignored ones are dropped."""

from dataclasses import replace

import pytest

import esolangs
from esolangs import vm
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from tests.support.evaluation import _row_answerer
from tests.support.execution import run_observed
from tests.support.generator_support import assert_proved_resource_cap
from tests.support.reference import REFERENCE
from tests.support.witness_tables import witnesses

IGNORING = [
    "00000000",
    "11111111",
    "01101001",  # parity keeps every branch, unlike constants
    "0101",
    "01100110",
    "0011",
    "00111100",
    "00001111",  # first-input projection distinguishes reversed reads
    "00101101",  # asymmetric, with every input essential
    "".join(c * 2 for c in "0110" * 8),
]
INFOS = {n: esolangs.describe(n) for n in esolangs.list_languages()}


def _audit(
    name,
    program,
    n,
    _mp,
    *,
    table=None,
    selected=None,
    sentinel=False,
    whole_stream=None,
):
    """Run every row; return rows, unread rows, past-end reads, early-output rows."""
    made, early = [], []

    def new(stdin=""):
        io = made.append(ScriptedIO(stdin + ("Q\n" if sentinel else ""))) or made[-1]
        read_all = io.input_all

        def all_input(*args, **kwargs):
            if whole_stream is not None:
                whole_stream.append(True)
            return read_all(*args, **kwargs)

        io.input_all = all_input
        write = io._write

        def checked(value):
            if str(value).strip() and stdin[io.position() :].strip():
                early.append(len(made))
            write(value)

        io._write = checked
        return io

    rows = unread = past = 0
    for row in range(1 << n) if selected is None else selected:
        stdin = esolangs.encode_inputs(name, [row >> s & 1 for s in reversed(range(n))])
        if INFOS[name].answer_mode != "termination":
            output = run_observed(
                name, program, stdin=stdin, timeout=10, io_factory=new
            ).output
            if table is not None:
                assert esolangs.read_answer(name, output) == table[row], (name, row)
        else:
            # A proven cycle is an answer too; its input must still be consumed.
            if table is None:
                vm.run_until_halt_or_cycle(
                    vm._make_vm(name, program, stdin=stdin, io_factory=new)
                )
            else:
                answer = _row_answerer(
                    name,
                    terminating=True,
                    isolated=False,
                    settings=None,
                    scale=None,
                    max_output=None,
                    max_memory=None,
                    io_factory=new,
                )
                assert answer(program, stdin, 10) == table[row], (name, row)
        if sentinel:
            assert made[-1].position() <= len(stdin), (name, row, "over-read")
        rows += 1
        unread += bool(stdin[made[-1].position() :].strip())
        past += made[-1].past_end
    return rows, unread, past, len(set(early))


GENERATED = [n for n, i in INFOS.items() if i.boolean_generator and not i.parameterized]


@pytest.mark.medium
def test_the_audit_sees_unread_input(monkeypatch) -> None:
    assert _audit(REFERENCE, ",.", 2, monkeypatch) == (4, 4, 0, 4)


@pytest.mark.medium
def test_the_audit_sees_early_output(monkeypatch) -> None:
    assert _audit("brainfuck", ",+.,", 2, monkeypatch) == (4, 0, 0, 4)


@pytest.mark.medium
def test_the_audit_checks_cycling_answers(monkeypatch) -> None:
    info = replace(INFOS[REFERENCE], answer_mode="termination")
    monkeypatch.setitem(INFOS, REFERENCE, info)
    assert _audit(REFERENCE, ",[]", 1, monkeypatch) == (2, 0, 0, 0)


@pytest.mark.medium
@pytest.mark.parametrize("table", ["00000000", "01101001"])
@pytest.mark.parametrize("failure", [RuntimeError, SystemExit])
def test_the_audit_rejects_a_crash_after_the_final_read(monkeypatch, table, failure):
    program = esolangs.generate(REFERENCE, table)
    hits = []

    class CrashIO(ScriptedIO):
        def input_char(self, prompt="Input: "):
            value = super().input_char(prompt)
            if self.reads == 3:
                hits.append(self.reads)
                raise failure("input-audit crash control")
            return value

    monkeypatch.setattr(__name__ + ".ScriptedIO", CrashIO)
    with pytest.raises(failure, match="input-audit crash control"):
        _audit(REFERENCE, program, 3, monkeypatch, table=table)
    assert hits == [3], "the control never reached the final input"


# One case per language and path: the whole sweep in one test overran its band.
@pytest.mark.medium
@pytest.mark.parametrize(
    ("name", "path"),
    [
        (name, path)
        for path in ({}, {"width": 1}, {"balance": True})
        for name in GENERATED
        if "width" not in path or INFOS[name].width_effect != "none"
    ],
    ids=str,
)
def test_every_input_is_read(monkeypatch, name, path) -> None:
    built = 0
    controls = load_certification(LANGUAGES[name]).benchmark_tables if not path else ()
    if controls:
        assert_proved_resource_cap(name)
    for table in dict.fromkeys((*IGNORING, *controls)):
        n = (len(table) - 1).bit_length()
        if n <= (INFOS[name].generator_max_inputs or 6):
            try:
                program = esolangs.generate(name, table, **path)
            except esolangs.GeneratorCapError:
                if table in controls:
                    raise
                assert_proved_resource_cap(name)
                continue
            built += 1
            whole_stream = []
            rows, unread, past, early = _audit(
                name, program, n, monkeypatch, table=table, whole_stream=whole_stream
            )
            assert rows > 0
            assert unread == 0, (name, table)
            assert early == 0, (name, table)  # output follows the last read
            # A language that ends at EOF probes it once a row, no more.
            assert past in (0, rows), (name, table)
            if past == 0 and not whole_stream:
                assert _audit(
                    name, program, n, monkeypatch, table=table, sentinel=True
                ) == (rows, 0, 0, 0)
    assert built, f"{name} never built an input-consumption control"


@pytest.mark.medium
def test_the_audit_sees_overreading(monkeypatch) -> None:
    with pytest.raises(AssertionError, match="over-read"):
        _audit(REFERENCE, ",,", 1, monkeypatch, sentinel=True)


def _audit_tables(monkeypatch, name, n, tables):
    executed = attempted = 0
    selected = sorted({0, 1, (1 << n) - 1, *[1 << bit for bit in range(n)]})
    for table in tables:
        attempted += 1
        try:
            program = esolangs.generate(name, table)
        except esolangs.GeneratorCapError:
            assert_proved_resource_cap(name)
            continue
        rows, unread, past, early = _audit(
            name, program, n, monkeypatch, table=table, selected=selected
        )
        assert rows > 0, (name, n, "no rows executed")
        assert (unread, early) == (0, 0), (name, n)
        assert past in (0, rows), (name, n)
        executed += rows
    assert attempted, (name, n, "empty witness corpus")
    if not executed:
        pytest.skip(f"{name}: no executable witness at n={n}; proved resource cap")
    return executed


@pytest.mark.slow
@pytest.mark.parametrize(
    ("name", "n"),
    [
        (name, n)
        for name in GENERATED
        for n in sorted(
            {min(arity, INFOS[name].generator_max_inputs or 6) for arity in (4, 6)}
        )
    ],
)
def test_contract_at_larger_arities(monkeypatch, name, n) -> None:
    """Sample rows at n=4 and n=6 (or the declared cap)."""
    _audit_tables(monkeypatch, name, n, witnesses(n))


@pytest.mark.medium
def test_the_audit_rejects_wrong_input_order(monkeypatch) -> None:
    with pytest.raises(AssertionError):
        _audit(REFERENCE, ",>,.", 2, monkeypatch, table="0011")


@pytest.mark.slow
@pytest.mark.parametrize(
    ("name", "n"),
    [
        (name, n)
        for name in GENERATED
        if (cap := INFOS[name].generator_max_inputs)
        for n in (cap - 1, cap)
    ],
)
def test_contract_at_declared_cap(monkeypatch, name, n) -> None:
    """Exercise constants and either-end projections at and below the cap."""
    size = 1 << n
    tables = (
        "0" * size,
        "1" * size,
        "01" * (size // 2),
        "0" * (size // 2) + "1" * (size // 2),
    )
    _audit_tables(monkeypatch, name, n, tables)


@pytest.mark.parametrize(
    "audit", [test_contract_at_larger_arities, test_contract_at_declared_cap]
)
def test_arity_audits_report_complete_refusal(monkeypatch, audit):
    name = next(
        n for n in GENERATED if load_certification(LANGUAGES[n]).benchmark_tables
    )
    n = INFOS[name].generator_max_inputs
    refused = []

    def decline(*_args, **_options):
        refused.append(True)
        raise esolangs.GeneratorCapError("arity-audit refusal control")

    monkeypatch.setattr(esolangs, "generate", decline)
    with pytest.raises(pytest.skip.Exception, match=f"no executable witness at n={n}"):
        audit(monkeypatch, name, n)
    assert refused, "the control never attempted generation"


def test_arity_audit_rejects_an_unproved_refusal(monkeypatch):
    def decline(*_args, **_options):
        raise esolangs.GeneratorCapError("unproved refusal control")

    monkeypatch.setattr(esolangs, "generate", decline)
    with pytest.raises(AssertionError):
        _audit_tables(monkeypatch, REFERENCE, 1, ["01"])


def test_arity_audit_rejects_zero_executed_rows(monkeypatch):
    monkeypatch.setattr(__name__ + "._audit", lambda *_args, **_options: (0, 0, 0, 0))
    with pytest.raises(AssertionError, match="no rows executed"):
        _audit_tables(monkeypatch, REFERENCE, 1, ["01"])


def test_arity_audit_rejects_an_empty_corpus(monkeypatch):
    with pytest.raises(AssertionError, match="empty witness corpus"):
        _audit_tables(monkeypatch, REFERENCE, 1, [])


@pytest.mark.medium
def test_arity_audit_executes_remaining_witnesses(monkeypatch):
    name = next(
        n for n in GENERATED if load_certification(LANGUAGES[n]).benchmark_tables
    )
    generate = esolangs.generate

    def partial(language, table, **options):
        if table == "00":
            raise esolangs.GeneratorCapError("partial refusal control")
        return generate(language, table, **options)

    monkeypatch.setattr(esolangs, "generate", partial)
    try:
        assert _audit_tables(monkeypatch, name, 1, ["00", "01"]) == 2
    except pytest.skip.Exception as error:
        raise AssertionError("an executable witness was skipped") from error
