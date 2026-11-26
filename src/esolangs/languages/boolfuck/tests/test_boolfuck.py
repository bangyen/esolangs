"""Boolfuck byte conventions and generated execution."""

import itertools
import random
from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, Language
from esolangs.languages.boolfuck.generator import boolfuck
from esolangs.languages.boolfuck.interpreter import _Machine, run
from esolangs.registry import Catalog
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.interpreters.semantic_oracles import boolfuck as oracle
from tests.support.bit_lifecycle import check_byte_lifecycle, check_final_byte_retry
from tests.support.certification_barrier import guarded_worker
from tests.support.raises import assert_rejected_with_hint
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("+;", "", "\x01"),
        ("<+;>;<;", "", "\x05"),
        (",;" * 8, "A", "A"),
        (",;" * 8, "", "\x00"),
        ("+[,];", "", "\x00"),
        ("ignored text", "", ""),
    ],
)
def test_byte_conventions(code: str, stdin: str, expected: str) -> None:
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == expected


@pytest.mark.parametrize("n", [1, 2, 3])
def test_all_three_input_tables(n: int) -> None:
    for table in witnesses(n):
        code = boolfuck(table)
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}")
            run(code, io)
            assert io.getvalue() == table[row]


@pytest.mark.medium
def test_hints_for_bad_programs_and_input() -> None:
    assert_rejected_with_hint("Boolfuck", "[", "close this '[' with ']'")
    from .workspace_checks import check_workspace_boolfuck

    check_workspace_boolfuck(_corpus)


def _corpus():
    for n in range(4):
        yield from ("".join(c) for c in itertools.product("+<>;,", repeat=n))
    yield from ["+[+]", "+[]", "[+;]", "+[>+<+]", "+[>+[+] <+]", ",;" * 17]
    yield from ["+" + ";" * 9, "ignored +;", "<+>+<;>;"]
    rng = random.Random(1701)
    pieces = ["+", "<", ">", ",", ";", "[+]", "[>+<+]", "[]"]
    for _ in range(64):
        yield "".join(rng.choices(pieces, k=8))


@pytest.mark.parametrize("stdin", STDINS)
def test_bounded_programs_match_the_oracle(stdin) -> None:
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin)


@pytest.mark.parametrize(
    ("code", "output"), [("[", None), ("]", None), (",;" * 8, "\x81"), ("+;", "\x01")]
)
def test_oracle_controls(code, output) -> None:
    result = agrees(_Machine, oracle, code, "\x81")
    assert result.output == output if output else isinstance(result, ValueError)
    assert not agrees(_Machine, oracle, "+[]", "").halted  # a cap is not a halt


def test_declared_byte_lifecycle(monkeypatch) -> None:
    _check_exact_cycle_preserves_bit_tape_state()
    check_byte_lifecycle("Boolfuck", "+")
    check_final_byte_retry("Boolfuck", "+", monkeypatch)
    from esolangs.runtime.brackets import BracketProgram
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse("Boolfuck", ",;>" * 8, BracketProgram, "parse", monkeypatch)
    check_image_reuse(
        "Boolfuck",
        "+;",
        BracketProgram,
        "parse",
        monkeypatch,
        cases=(("", "\x01"), ("", "\x01"), ("", "\x01")),
    )


def _check_exact_cycle_preserves_bit_tape_state() -> None:
    stock = Language("Boolfuck")
    declaration = stock.catalog.languages[stock.name]
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("diverges", "halts"),
    )
    api = Catalog([replace(declaration, contract=contract)]).bind(stock.name)
    source = api.from_source("+;;;;;;;;[]")
    local = source.evaluate(
        [1], limits=ExecutionLimits(max_steps=20), catalog=api.catalog
    )
    with guarded_worker():
        worker = source.evaluate(
            [1],
            limits=ExecutionLimits(max_steps=20, total_timeout=3),
            catalog=api.catalog,
        )
    assert local == worker
    assert worker.answer == "0"
    assert worker.observation.output == "\xff"
    assert worker.observation.steps == 17
    assert local.termination is not None
    assert local.termination.cycle is not None
    assert worker.termination is not None
    assert worker.termination.cycle is not None
    local_state = local.termination.cycle.state
    worker_state = worker.termination.cycle.state
    assert isinstance(local_state, tuple)
    assert isinstance(worker_state, tuple)
    assert type(worker_state[0]) is type(local_state[0])
    assert worker_state[0].pc == 9
    assert worker_state[0].used == 0
