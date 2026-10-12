"""Executed complete-cofactor banks and conservative public admission."""

import importlib

import pytest

from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.generator.banks import (
    _cofactor_bank_candidate,
    _cofactor_bank_layout,
    _repeated_cofactor_bank,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense


@pytest.mark.medium
@pytest.mark.parametrize("prefix", [2, 3])
def test_every_function_through_three_inputs_executes(prefix):
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            _execute(table, _cofactor_bank_layout(table, prefix).render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("prefix", [2, 3])
def test_sampled_small_banks_execute(n, prefix):
    for seed in range(4):
        table = dense(n, f"bank:{seed}".encode())
        _execute(table, _cofactor_bank_layout(table, prefix).render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 9])
def test_public_repeated_cofactors_select_the_smaller_bank(n):
    a, b = dense(n - 2, b"bank-a"), dense(n - 2, b"bank-b")
    table = a + b + b + a
    model = _cofactor_bank_candidate(table)
    code = circuit_diagram(table)
    lines = code.splitlines()
    height, width = model.bounds()
    assert len(lines) * max(map(len, lines)) <= height * width
    if n == 9:
        assert len(model.render()) == 1_273_998
    assert sum(char in "ao~" for char in model.glyphs.values()) <= (
        2 * len(table) + 8 * n + 111
    )
    _execute(table, code)
    _execute(table, model.render())


@pytest.mark.medium
def test_unique_cofactors_share_internal_residuals_in_eight_banks():
    table = dense(8)
    assert _repeated_cofactor_bank(table) is None
    model = _cofactor_bank_layout(table, 3)
    code = circuit_diagram(table)
    lines = code.splitlines()
    height, width = model.bounds()
    assert len(lines) * max(map(len, lines)) < height * width
    assert len(model.render()) == 270_688
    _execute(table, code)
    _execute(table, model.render())


@pytest.mark.medium
def test_oversized_bank_cannot_displace_existing_output(monkeypatch):
    table = dense(8)
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: None)
    expected = circuit_diagram(table)

    class Oversized:
        def bounds(self):
            return len(expected) + 1, len(expected) + 1

        def render(self):
            pytest.fail("oversized bank must not be emitted")

    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: Oversized())
    assert circuit_diagram(table) == expected


@pytest.mark.medium
def test_explicit_width_never_builds_a_bank(monkeypatch):
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(
        module,
        "_cofactor_bank_candidate",
        lambda *_args: pytest.fail(
            "width-constrained construction must remain independent"
        ),
    )
    a, b = dense(6, b"bank-a"), dense(6, b"bank-b")
    table = a + b + b + a
    _execute(table, circuit_diagram(table, width=80), (0, 255))


@pytest.mark.medium
def test_equal_area_bank_preserves_existing_output(monkeypatch):
    from esolangs.languages.circuit_diagram.generator.hpool import _h_pool_layout

    pools = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.hpool"
    )
    monkeypatch.setattr(pools, "_large_pool_layout", lambda *_args, **_kwargs: None)
    table = dense(8)
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: None)
    expected = circuit_diagram(table)
    bounds = _h_pool_layout(table).bounds()

    class EqualArea:
        def bounds(self):
            return bounds

        def render(self):
            pytest.fail("area ties must preserve the existing candidate")

    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: EqualArea())
    assert circuit_diagram(table) == expected


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(8, 10, 12), (9, 11, 13)])
def test_bank_scaling_retains_native_contracts(arities):
    sizes = []
    for n in arities:
        a, b = dense(n - 2, b"bank-a"), dense(n - 2, b"bank-b")
        table = a + b + b + a
        code = _cofactor_bank_layout(table).render()
        sizes.append(len(code))
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) < 4.4


@pytest.mark.parametrize("prefix", [-1, 1, 4])
def test_unsupported_prefix_sizes_abort(prefix):
    with pytest.raises(ValueError, match="two or three prefix inputs"):
        _cofactor_bank_layout(dense(8), prefix)


@pytest.mark.medium
@pytest.mark.parametrize(("n", "cap"), [(8, 511), (9, 1015)])
def test_eight_distinct_bodies_obey_small_arity_workspace_caps(n, cap):
    table = "".join(dense(n - 3, f"eight:{i}".encode()) for i in range(8))
    model = _cofactor_bank_layout(table, 3)
    assert sum(char in "ao~" for char in model.glyphs.values()) <= cap
    _execute(table, model.render())


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10])
def test_repeats_below_distinct_four_bank_cofactors_share(n):
    a, b, c = [dense(n - 3, f"deep-bank:{i}".encode()) for i in range(3)]
    table = a + b + a + c + b + c + a + a
    assert _repeated_cofactor_bank(table) is None
    model = _cofactor_bank_layout(table, 3)
    code = circuit_diagram(table)
    lines = code.splitlines()
    height, width = model.bounds()
    assert len(lines) * max(map(len, lines)) <= height * width
    assert len(code) == {9: 125_374, 10: 278_281}[n]
    rows = None if n == 9 else sorted({0, len(table) - 1, *range(0, len(table), 32)})
    _execute(table, code, rows)
    _execute(table, model.render(), rows)


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(9, 11, 13), (10, 12, 14)])
def test_eight_bank_growth_with_native_positive_controls(arities):
    sizes = []
    for n in arities:
        a, b, c = [dense(n - 3, f"deep-bank:{i}".encode()) for i in range(3)]
        table = a + b + a + c + b + c + a + a
        code = _cofactor_bank_layout(table, 3).render()
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
        sizes.append(len(code))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.medium
@pytest.mark.parametrize("prefix", [2, 3])
def test_bank_glyph_floor_never_rejects_a_fitting_native_layout(prefix):
    from esolangs.languages.circuit_diagram.generator.banks import _bank_exceeds_area

    table = dense(10, b"bank-floor")
    model = _cofactor_bank_layout(table, prefix)
    height, width = model.bounds()
    assert not _bank_exceeds_area(table, prefix, height * width)
    _execute(table, model.render(), (0, len(table) - 1))


def test_bank_glyph_floor_skips_provably_oversized_bodies(monkeypatch):
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(
        module,
        "_cofactor_bank_layout",
        lambda *_args: pytest.fail("a body exceeding the ceiling must not be routed"),
    )
    assert _cofactor_bank_candidate(dense(10), 1) is None
