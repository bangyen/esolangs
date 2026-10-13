"""Native bounded suffix-class banks across arbitrary prefix occurrences."""

import importlib

import pytest

from esolangs.languages.circuit_diagram.generator import (
    _linear_shared_layout,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.generator.banks import (
    _repeated_cofactor_bank,
    _residual_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense


def _three_classes(n):
    tail = 7 if n % 2 else 8
    atoms = [dense(tail, f"class:{i}".encode()) for i in range(3)]
    selector = dense(n - tail, b"class-selector")
    return "".join(
        atoms[(2 * int(bit) + row % 2) % 3] for row, bit in enumerate(selector)
    )


def _eight_classes(n):
    tail = 7 if n % 2 else 8
    prefix = n - tail
    atoms = [dense(tail, f"eight-class:{i}".encode()) for i in range(8)]
    selectors = [dense(prefix, f"class-bit:{i}".encode()) for i in range(3)]
    return "".join(
        atoms[sum(int(selectors[bit][row]) << bit for bit in range(3))]
        for row in range(1 << prefix)
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10])
def test_repeated_classes_execute_every_row(n) -> None:
    table = _three_classes(n)
    model = _residual_class_bank_candidate(table)
    assert model is not None
    assert len(model.render()) == {9: 123_502, 10: 253_082}[n]
    _execute(table, model.render())


@pytest.mark.medium
def test_public_abba_class_bank_executes_every_row() -> None:
    a, b = dense(8, b"bank-a"), dense(8, b"bank-b")
    table = a + b + b + a
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 387_711
    _execute(table, code)


@pytest.mark.medium
def test_classes_cross_distinct_banks_beyond_all_fold_orders() -> None:
    table = _eight_classes(13)
    complete = _linear_shared_layout(table, 13)
    assert complete is not None
    assert _repeated_cofactor_bank(table) is None
    chunks = [table[start : start + 1024] for start in range(0, len(table), 1024)]
    assert len(set(chunks)) == 8
    code = circuit_diagram(table)
    assert code == _residual_class_bank_candidate(table).render()
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 1_160_811
    rows = sorted({0, len(table) - 1, *range(0, len(table), 256)})
    h, w = complete.bounds()
    assert h * w >= len(lines) * max(map(len, lines))
    _execute(table, complete.render(), rows)
    _execute(table, code, rows)


@pytest.mark.medium
def test_constant_classes_and_projected_suffix_ports_execute() -> None:
    atom = "".join(str(((row >> 6) & 1) ^ (row & 1)) for row in range(128))
    for table in ("0" * 128 + "1" * 128 + atom + atom, atom * 4):
        model = _residual_class_bank_candidate(table)
        assert model is not None
        _execute(table, model.render())


def test_unrepeated_and_excess_classes_reject_before_routing(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("ineligible classes must be rejected before building masks")

    monkeypatch.setattr(module, "_large_pool_layout", unexpected)
    assert _residual_class_bank_candidate(dense(10)) is None
    atoms = [dense(7, f"too-many:{i}".encode()) for i in range(257)]
    assert (
        _residual_class_bank_candidate("".join(atoms[row % 257] for row in range(1024)))
        is None
    )
    assert _residual_class_bank_candidate("0" * 512) is None
    assert _residual_class_bank_candidate(dense(8)) is None


@pytest.mark.medium
def test_class_area_ceiling_preserves_a_fitting_native_layout(monkeypatch) -> None:
    table = _three_classes(9)
    model = _residual_class_bank_candidate(table)
    height, width = model.bounds()
    assert (
        _residual_class_bank_candidate(table, height * width).render() == model.render()
    )
    assert _residual_class_bank_candidate(table, height * width - 1) is None
    _execute(table, model.render(), (0, len(table) - 1))
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("an oversized body must reject before copying banks")

    monkeypatch.setattr(module, "_assemble_banks", unexpected)
    assert _residual_class_bank_candidate(table, 1) is None


@pytest.mark.medium
@pytest.mark.parametrize("extra_height", [0, 1])
def test_public_class_admission_preserves_existing_area_ties(
    monkeypatch, extra_height
) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    monkeypatch.setattr(module, "_cofactor_bank_candidate", lambda *_args: None)
    monkeypatch.setattr(module, "_residual_class_bank_candidate", lambda *_args: None)
    table = dense(9)
    expected = circuit_diagram(table)

    class Rejected:
        def __init__(self, ceiling):
            self.ceiling = ceiling

        def bounds(self):
            return 1, self.ceiling + extra_height

        def render(self):
            pytest.fail("an equal or larger class bank must preserve the old candidate")

    monkeypatch.setattr(
        module,
        "_residual_class_bank_candidate",
        lambda _table, ceiling: Rejected(ceiling),
    )
    assert circuit_diagram(table) == expected
    _execute(table, expected, (0, len(table) - 1))


@pytest.mark.medium
def test_explicit_width_never_builds_class_masks(monkeypatch) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("class masks must not run in the width-constrained fold")

    monkeypatch.setattr(module, "_residual_class_bank_candidate", unexpected)
    table = _three_classes(9)
    _execute(table, circuit_diagram(table, width=80), (0, len(table) - 1))


@pytest.mark.weekly
@pytest.mark.cost_evidence(
    "seventeen-input H masks retain their local complement drivers"
)
def test_large_h_masks_keep_their_local_complement_drivers() -> None:
    table = _three_classes(17)
    model = _residual_class_bank_candidate(table)
    assert model is not None
    rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
    _execute(table, model.render(), rows)


@pytest.mark.medium
def test_nine_input_atom_shares_internal_residuals_of_distinct_roots() -> None:
    table = dense(9)
    assert len({table[i : i + 128] for i in range(0, 512, 128)}) == 4
    model = _residual_class_bank_candidate(table)
    assert model is not None
    code = model.render()
    assert len(code) == 258_216
    assert model.bounds()[0] * model.bounds()[1] == 367_633
    assert _execute(table, code) == 18


@pytest.mark.medium
@pytest.mark.parametrize("shared", [False, True])
def test_online_class_rectangle_rejects_before_copying(monkeypatch, shared) -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    table = _three_classes(9)
    model = module._class_bank_layout(table, shared=shared)  # noqa: SLF001
    assert model is not None
    height, width = model.bounds()

    def unexpected(*_args, **_kwargs):
        pytest.fail("the output rectangle must reject before copying")

    monkeypatch.setattr(module, "_assemble_banks", unexpected)
    assert module._class_bank_layout(table, height * width - 1, shared=shared) is None  # noqa: SLF001


@pytest.mark.medium
def test_single_class_preserves_its_native_area_ceiling() -> None:
    module = importlib.import_module(
        "esolangs.languages.circuit_diagram.generator.banks"
    )
    table = dense(7, b"single-class-ceiling") * 4
    model = module._class_bank_layout(table, shared=False)  # noqa: SLF001
    assert model is not None
    height, width = model.bounds()
    admitted = module._class_bank_layout(table, height * width, shared=False)  # noqa: SLF001
    assert admitted is not None
    assert admitted.render() == model.render()
    _execute(table, admitted.render())
