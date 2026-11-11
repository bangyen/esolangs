"""Executed tests for the INTERCAL Shannon-expression generator."""

import random
import re

import pytest

import esolangs
from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
)
from esolangs.languages.intercal import generator
from esolangs.languages.intercal.descriptor import PAIR, TEMPLATE_CHAR
from esolangs.languages.intercal.generator import (
    _ONE,
    _ZERO,
    _Expr,
    _pack_rows,
    _program,
    _reference,
    _spill,
    _wrap_intercal,
    intercal,
)
from esolangs.languages.intercal.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.proofs._witnesses import _intercal_worst
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.event_io import count_steps
from tests.support.generator_support import (
    constant_artifacts,
    measure_run,
    run_filled,
    three_input_corpus_size,
)


def _run(table: str, row: int) -> str:
    n = len(table).bit_length() - 1
    output = run_filled(run, intercal(table), [PAIR] * n, row, n, TEMPLATE_CHAR)
    assert output in {"_\n\n", "I\n"}
    return "1" if output == "I\n" else "0"


@pytest.mark.parametrize("table", ["0001", "0111", "1110", "1000", "0101", "1010"])
def test_constant_mux_folds_preserve_assignments_and_execute(
    table: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    folded = intercal(table)

    def raw_mux(selector, zero, one, negated=None, mask=None):
        negated = negated or _Expr("not", children=(selector,))
        mask = mask or _Expr("mingle", children=(selector, negated))
        return _Expr("select", children=(zero, one, mask))

    with monkeypatch.context() as patch:
        patch.setattr(generator, "_mux", raw_mux)
        unfolded = intercal(table)
    targets = r"(?m)^(DO|PLEASE) (.*?) <- "
    assert re.findall(targets, folded) == re.findall(targets, unfolded)
    assert len(folded) < len(unfolded)
    for row, expected in enumerate(table):
        for template in (folded, unfolded):
            output = run_filled(run, template, [PAIR] * 2, row, 2, TEMPLATE_CHAR)
            assert output == ("I\n" if expected == "1" else "_\n\n")


def test_setters_are_equal_width_and_embedded_once() -> None:
    _check_select_bits()
    assert not hasattr(generator, "TEMPLATE_CHAR")
    assert len(PAIR[0]) == len(PAIR[1]) == 2
    for n in range(1, 8):
        template = intercal("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 2 * n


def test_levels_select_inputs_in_the_shorter_order() -> None:
    """Assignments stay in name order; only the selectors move."""
    template = intercal("10101010")
    assert template.index(".3 <- @@") < template.index(".1 <- @@")
    expression = template.split(".4 <- ", 1)[1].split("\n", 1)[0]
    assert {name for name in (".1", ".2", ".3") if name in expression} == {".1"}


def _five_input_sample() -> list[str]:
    """Return the sharing catalogue's 200 five-input tables, seed 0."""
    rng, found = random.Random(0), set[str]()
    while len(found) < 200:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)


def _unshared(table: str) -> str:
    return intercal_plain(table, tuple(range(len(table).bit_length() - 1)))


def test_repeated_subexpressions_are_assigned_once() -> None:
    assert_analysis_complement("INTERCAL", "reduced_diagram")
    parity = "01101001100101101001011001101001"
    template = intercal(parity)
    assert [k for k in range(7, 14) if f".{k} <- " in template] == [7, 8]
    assert (len(template), len(_unshared(parity))) == (345, 583)
    for tables, pinned in (
        ([f"{value:08b}" for value in range(256)], (37487, 34795)),
        (_five_input_sample(), (89545, 69392)),
    ):
        old = new = 0
        for table in tables:
            before, after = len(_unshared(table)), len(intercal(table))
            old, new = old + before, new + after
        assert (old, new) == pinned


@pytest.mark.parametrize("n", range(4, 7))
@pytest.mark.medium
def test_shared_templates_execute_on_sampled_tables(n: int) -> None:
    rng = random.Random(n)
    for _ in range(3):
        table = format(rng.getrandbits(1 << n), f"0{1 << n}b")
        assert "".join(_run(table, row) for row in range(1 << n)) == table


@pytest.mark.parametrize(("cap", "n"), [(12, 7), (20, 8), (30, 9)])
@pytest.mark.medium
def test_names_past_the_cap_spill_to_arrays_and_execute(
    cap: int, n: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lowered variable cap spills the top names; every row still computes."""
    monkeypatch.setattr(generator, "_VARIABLE_MAX", cap)
    table = _intercal_worst(n)
    template = intercal(table)
    assert " SUB #" in template
    assert max(int(k) for k in re.findall(r"\.(\d+)", template)) <= cap
    assert "".join(_run(table, row) for row in range(1 << n)) == table


def test_spill_width_is_zero_at_the_cap_and_a_ceiling_root_past_it() -> None:
    """``_spill``: nothing past the cap -> 0; S past it -> ceil(sqrt(S))."""
    from esolangs.languages.intercal.generator import _VARIABLE_MAX

    assert _spill(_VARIABLE_MAX) == 0
    assert _spill(_VARIABLE_MAX + 288) == 17
    assert _spill(_VARIABLE_MAX + 289) == 17
    assert _spill(_VARIABLE_MAX + 295) == 18


def test_program_declares_one_array_per_spill_width_of_names() -> None:
    """289 names past the cap at width 17 declare 17 arrays, not 18."""
    from esolangs.languages.intercal.generator import _VARIABLE_MAX

    program = _program(2, [(_VARIABLE_MAX + 289, _ZERO)], _ZERO, width=17).source
    assert re.findall(r",(\d+) <- #17", program) == [str(j) for j in range(1, 18)]


@pytest.mark.medium
def test_every_name_of_the_widest_witness_is_a_legal_variable() -> None:
    """The large witness respects scalar limits; small lowered caps force spills."""
    program = intercal(_intercal_worst(21))
    assert max(int(k) for k in re.findall(r"\.(\d+)", program)) <= 65535
    widths = re.findall(r"^\S+ ,(\d+) <- #(\d+)$", program, re.MULTILINE)
    assert [int(j) for j, _ in widths] == list(range(1, len(widths) + 1))
    if widths:
        assert len({w for _, w in widths}) == 1
        assert max(int(i) for i in re.findall(r" SUB #(\d+)", program)) <= int(
            widths[0][1]
        )


@pytest.mark.parametrize("table", ["00"])
def test_narrow_balance_regime_edge_executes(table) -> None:
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("INTERCAL", table, balance=True)
    assert _evaluate("INTERCAL", balanced, inputs=len(table).bit_length() - 1) == table


def intercal_plain(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` selects input ``perm[k]``."""
    from esolangs.languages.intercal.generator import _mux

    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)

    def tree(level: int, lo: int, hi: int) -> _Expr:
        if constant(lo, hi):
            return _Expr("constant", int(truth_table[lo]))
        mid = (lo + hi) // 2
        # In name order large variable numbers occur near the root, where
        # their decimal spelling is repeated least; this keeps source size
        # linear in T.  A reorder moves them only through the greedy cap
        # (n = 10), where no name is longer than two digits.
        zero, one = tree(level + 1, lo, mid), tree(level + 1, mid, hi)
        return _mux(_Expr("input", n - 1 - perm[level]), zero, one)

    return _program(n, [], tree(0, 0, len(truth_table))).source


@pytest.mark.medium
def test_constants_reuse_one_variable_and_print_the_literal() -> None:
    _check_emitted_resource_routes()
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("INTERCAL")["workspace"].formula

    for n, bit, options, template in constant_artifacts("INTERCAL", range(1, 13)):
        assert template.source.count(TEMPLATE_CHAR) == 2 * n
        if not options:
            assert template.source.count(".1 <-") == n
            assert f"READ OUT #{bit}" in template.source
            if n == 8:
                assert len(template.source) == 129
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            inputs = list(map(int, format(row, f"0{n}b")))
            program = esolangs.instantiate("INTERCAL", template, inputs)
            assert len(program.source) == len(template.source)
            stream = ScriptedIO()
            machine = _Machine(program.source, stream)
            steps, written = measure_run(machine, limit=n + 2)
            assert machine.halted
            assert steps == n + 2
            assert esolangs.read_answer("INTERCAL", stream.getvalue()) == bit
            if not options:
                assert written.bits == workspace(n, template.source)
    assert three_input_corpus_size("INTERCAL") == 34795


def _check_emitted_resource_routes() -> None:
    """Check high-arity write-set syntax without building exponential tables."""
    from esolangs.languages.intercal.generator import _VARIABLE_MAX
    from esolangs.languages.intercal.proof_formulas import (
        global_execution,
        global_workspace,
    )
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("INTERCAL")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    for n in (13, 16, 20, 21, 22, 25, 26, 27):
        selector = _Expr("input", n - 1)
        mask = _Expr("mingle", children=(selector, _Expr("not", children=(selector,))))
        assigned: list[tuple[int | str, _Expr]] = [
            (_VARIABLE_MAX, _ONE),
            (f":{n}", mask),
        ]
        assigned += [(_VARIABLE_MAX + i, _ONE if i % 2 else _ZERO) for i in range(1, 6)]
        width = _spill(_VARIABLE_MAX + 5)
        result = _reference(_VARIABLE_MAX + 5, width)
        assert result is not None
        template = _program(n, assigned, result, width).source
        for layout in (
            template,
            _wrap_intercal(template, 12),
            _pack_rows(template, 1000),
        ):
            assert layout.count(TEMPLATE_CHAR) == 2 * n
            for bit in (0, 1):
                program = layout.replace(TEMPLATE_CHAR * 2, PAIR[bit])
                io = ScriptedIO("Q")
                machine = _Machine(program, io)
                written = WrittenState(machine.workspace_snapshot())
                steps = count_steps(machine, 999, written=written)
                assert io.getvalue() == "I\n"
                assert io.reads == 0
                assert io.input_char() == ord("Q")
                assert steps == execution(n, layout)
                assert steps <= global_execution(n)
                assert written.bits <= global_workspace(n)
                assert written.bits <= workspace(n, layout)
                if bit:
                    assert written.bits == workspace(n, layout)


def _check_select_bits() -> None:
    """Both mask spellings select one bit; exchanging the mask fires the oracle."""
    selector, zero, one = (_Expr("input", i) for i in range(3))
    complement = _Expr("not", children=(selector,))
    correct = _Expr("mingle", children=(selector, complement))
    reversed_mask = _Expr("mingle", children=(complement, selector))
    wrong = 0
    for named in (False, True):
        for mask in (correct, reversed_mask):
            assigned: list[tuple[int | str, _Expr]] = [(":1", mask)] if named else []
            reference = _Expr("element", text=":1") if named else mask
            result = _Expr("select", children=(zero, one, reference))
            template = _program(3, assigned, result).source
            for row in range(8):
                # Setters run .3,.2,.1: one, zero, selector.
                bits = tuple(map(int, f"{row:03b}"))
                expected = bits[0] if bits[2] else bits[1]
                output = run_filled(run, template, [PAIR] * 3, row, 3, TEMPLATE_CHAR)
                answer = "I\n" if expected else "_\n\n"
                if mask == correct:
                    assert output == answer
                else:
                    wrong += output != answer
    assert wrong == 8
