"""Analytic balance rules match all supported layouts and execute every row."""

import random
from itertools import product

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.tools.fish import balance_fish, fish
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import balance_program, balance_score, wrap_program
from tests.witness_tables import witnesses


@pytest.mark.parametrize("language", ["addsubjump", "decleq", "sbleq"])
def test_mixed_digit_operands_share_one_grid_cell(language):
    for count in range(3, 65):
        program = " ".join(("1", "22", "333")[index % 3] for index in range(count))
        balanced = balance_program(program, language)
        optimum = min(
            [program]
            + [
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ],
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
        assert balanced.split() == program.split()


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 5), (2, 9), (6, 15)])
def test_token_fit_lattice_respects_width_regimes(minimum, maximum):
    from esolangs.tools.wrap import _join_tokens

    rng = random.Random(1013)
    for _ in range(100):
        tokens = ["x" * rng.randrange(1, 12) for _ in range(rng.randrange(1, 30))]
        width = balanced_token_width(tokens, " ", minimum=minimum, maximum=maximum)
        assert minimum <= width <= maximum
        optimum = min(
            (_join_tokens(tokens, width, " ") for width in range(minimum, maximum + 1)),
            key=balance_score,
        )
        assert balance_score(_join_tokens(tokens, width, " ")) == balance_score(optimum)


def test_fractran_parity_representation_omits_empty_width_regimes():
    from esolangs.tools.balance import _fractran

    parity = esolangs.generate("FRACTRAN", "0110", 4)
    balanced = _fractran("0110", parity)
    assert balanced in [
        esolangs.generate("FRACTRAN", "0110", width) for width in (1, 4, 8)
    ]
    assert _evaluate("FRACTRAN", balanced, inputs=2) == "0110"


def test_bio_balance_keeps_source_that_does_not_tile_commands():
    assert balance_program("not BIO", "bio") == "not BIO"


def test_bio_nested_spaced_commands_keep_their_structural_runs():
    program = "0ix{0ox; 0ix{0oy;};};"
    balanced = balance_program(program, "bio")
    layouts = [program] + [
        wrap_program(program, "bio", width) for width in range(1, len(program) + 1)
    ]
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert esolangs.run("BIO", balanced) == esolangs.run("BIO", program) == ""


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [4, 6])
def test_bio_padding_caps_match_every_width(inputs):
    rng = random.Random(1017 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("BIO", table)
    balanced = esolangs.generate("BIO", table, balance=True)
    layouts = [default] + [
        esolangs.generate("BIO", table, width) for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert _evaluate("BIO", balanced, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [7, 10])
def test_bio_saturated_runs_attain_both_geometry_bounds(inputs):
    rng = random.Random(1018 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("BIO", table)
    balanced = esolangs.generate("BIO", table, balance=True)
    full = esolangs.generate("BIO", table, 3 * len(table))
    # Deep runs contain at most three four-cell commands; the last has at
    # least one. A cap over four levels below the deepest cannot attain Wmax.
    depth = len(table) - 1
    lower = 2 * (depth - 4) + 2 * (depth - 4) // 3
    upper = 2 * (depth + 1) + 2 * (depth + 1) // 3
    layouts = [default, full] + [
        esolangs.generate("BIO", table, width) for width in range(lower, upper + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert len(balanced.split("\n")) == 2 * len(table) + 6 * (inputs - 1)
    assert max(map(len, balanced.split("\n"))) == max(map(len, full.split("\n")))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run("BIO", esolangs.instantiate("BIO", balanced, bits))
        assert esolangs.read_answer("BIO", output) == table[row]


@pytest.mark.medium
@pytest.mark.parametrize(
    "table", ["01", "10", "0110", "0001", "10010110", "0110100110010110"]
)
def test_polynomial_balanced_folds_compute_the_table(table):
    from esolangs.tools.wrap import _polynomial_terms

    default = esolangs.generate("Polynomial", table)
    balanced = esolangs.generate("Polynomial", table, balance=True)
    layouts = [default] + [
        wrap_program(default, "polynomial", width)
        for width in range(1, max(map(len, _polynomial_terms(default))) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert (
        _evaluate("Polynomial", balanced, inputs=len(table).bit_length() - 1) == table
    )


@pytest.mark.parametrize("language", ["AddSubJump", "Decleq", "S*bleq"])
@pytest.mark.parametrize("table", ["0110", "10010110"])
def test_aligned_balanced_programs_compute_the_table(language, table):
    balanced = esolangs.generate(language, table, balance=True)
    default = esolangs.generate(language, table)
    optimum = min(
        [default]
        + [esolangs.generate(language, table, width) for width in range(1, 129)],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


def _fish_tables():
    return [table for inputs in (1, 6) for table in witnesses(inputs)]


@pytest.mark.medium
@pytest.mark.parametrize("table", _fish_tables())
def test_fish_balance_matches_all_power_of_two_folds(table):
    default = fish(table)
    balanced = balance_fish(table, default)
    layouts = [default, fish(table, 1)] + [
        fish(table, (1 << exponent) + 2) for exponent in range(len(table).bit_length())
    ]
    optimum = min(layouts, key=balance_score)
    assert balance_score(balanced) == balance_score(optimum)
    assert esolangs.generate("Fish", table, balance=True) == balanced
    assert _evaluate("Fish", balanced, inputs=len(table).bit_length() - 1) == table


def _regime_tables():
    # XOR, majority and one wide irregular table; the primitive fit oracles
    # cover the exhaustive geometry.
    return ["0110", witnesses(5)[-1]]


@pytest.mark.medium
@pytest.mark.parametrize(
    "language",
    [
        "Algebraic Programming Language",
        "Alight",
        "ArrowQueue",
        "Back",
        "B-tapemark",
        "Bitdeque",
        "BrainIf",
        "BIO",
        "Circuit Diagram",
        "Clockwise",
        "Collatz Multiverse",
        "Container",
        "Crement",
        "Dimensional",
        "EGL",
        "Smallfuck",
        "Underload",
        "Dig",
        "Fargo",
        "FALSE",
        "Forbin",
        "FRACTRAN",
        "LaserFuck",
        "Jaune",
        "INTERCAL",
        "Minifuck",
        "Minsky Swap",
        "Modulous",
        "Packlang",
        "Qoibl",
        "RAM0",
        "Streetcode",
        "Thue",
        "Taglate",
        "Flowchart",
        "Inject",
        "thisthat",
        "Vandevelo",
    ],
)
@pytest.mark.parametrize("table", _regime_tables())
def test_discrete_regimes_reach_the_supported_minimum(language, table):
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate(language, table, width)
        for width in range(1, max(65, widest + 1))
    ]
    optimum = min(layouts, key=balance_score)
    assert balanced in layouts
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", ["3x", "6-5", "Eval", "Home Row", "Sophie", "Unlambda"]
)
@pytest.mark.parametrize("table", ["0110", "10010110"])
def test_grammar_and_marked_run_fits_execute(language, table):
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    layouts = [default] + [
        esolangs.generate(language, table, width)
        for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


@pytest.mark.medium
@pytest.mark.parametrize("table", ["01" * 32, "0" * 64])
def test_streetcode_indexed_regimes_are_balanced_and_execute(table):
    default = esolangs.generate("Streetcode", table)
    balanced = esolangs.generate("Streetcode", table, balance=True)
    widest = max(map(len, default.split("\n")))
    optimum = min(
        [default]
        + [
            esolangs.generate("Streetcode", table, width)
            for width in range(1, widest + 1)
        ],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate("Streetcode", balanced, inputs=6) == table


@pytest.mark.parametrize("indent", [0, 4, 16, 64])
def test_packlang_reduced_indent_crossing(indent):
    from esolangs.tools.packlang import _balance_form

    for table in ("0110", "0001", "10010110"):
        default = esolangs.generate("Packlang", table)
        program = "\n".join(
            " " * indent + row.lstrip() if row else row for row in default.split("\n")
        )
        widest = max(map(len, program.split("\n")))
        balanced = _balance_form(program, 1, widest)
        layouts = [
            wrap_program(program, "packlang", width) for width in range(1, widest + 1)
        ]
        assert balanced in layouts
        assert balance_score(balanced) == min(map(balance_score, layouts))
        assert (
            _evaluate("Packlang", balanced, inputs=len(table).bit_length() - 1) == table
        )


@pytest.mark.slow
@pytest.mark.parametrize("inputs", [6, 8])
@pytest.mark.parametrize("affine", [False, True])
def test_circuit_gate_column_and_band_fit_transitions(inputs, affine):
    from esolangs.tools.circuit_diagram import _circuit_diagram_at, _selector_orders

    language = "Circuit Diagram"
    rng = random.Random(1022 + inputs)
    table = (
        "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
        if affine
        else "".join(rng.choice("01") for _ in range(1 << inputs))
    )
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    # Once any possible flat order fits, all larger widths repeat the selected flat.
    widest = max(
        max(map(len, _circuit_diagram_at(table, None, order).split("\n")))
        for order in _selector_orders(table, compact=False)
    )
    layouts = [default] + [
        esolangs.generate(language, table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            language, balanced, esolangs.encode_inputs(language, bits)
        )
        assert esolangs.read_answer(language, output) == table[row]


@pytest.mark.parametrize("language", ["Alight", "Qoibl"])
def test_native_balance_preserves_answers(language):
    program = esolangs.generate(language, "0110", balance=True)
    assert _evaluate(language, program, inputs=2) == "0110"


def test_qoibl_affine_row_envelope_minima():
    from esolangs.tools.qoibl.balance import _best_width

    for negative, constant, positive, extra in product(
        [32, 45, 60], [1, 5, 15], [-1, 4, 12], [0, 10, 30]
    ):
        rows = [(-2, negative), (0, constant), (1, positive)] + [(0, 1)] * extra
        length = (
            sum(slope for slope, _ in rows),
            sum(offset for _, offset in rows) + len(rows) - 1,
        )
        width = _best_width(rows, length, 1, 15)
        layouts = [
            "\n".join("x" * (slope * columns + offset) for slope, offset in rows)
            for columns in range(1, 16)
        ]
        assert balance_score(layouts[width - 1]) == min(map(balance_score, layouts))


def test_native_width_generators_have_balance_rules():
    from esolangs.registry import LANGUAGES
    from esolangs.tools.balance import BALANCERS
    from esolangs.tools.wrap import takes_width

    assert not [
        name
        for name, language in LANGUAGES.items()
        if (generator := language.boolean) is not None
        and takes_width(generator)
        and language.id not in BALANCERS
    ]


def test_alight_affine_fold_comparisons_and_empty_turn_rows():
    from esolangs.tools.alight import _alight_folded, _dimensions
    from esolangs.tools.alight.balance import _fold_shape

    pieces = [(0, 6)] * 3 + [(0, 8), (1, 20), (1, 20), (0, 6), (0, 4)]
    assert _fold_shape(pieces, (1, 90), 1, 31)[3] == 4
    for size in range(1, 31):
        units = [[command] for command in ("begin", "var r", "var i", "set i 0")]
        units += [[f'set r at{{"{"0" * size}", i+0.5}}']] * 2
        units += [["out r"], ["end"]]
        program = _alight_folded(units, size + 90)
        width, height, length, _ = _fold_shape(pieces, (1, 90), size, 31)
        assert (*_dimensions(program), len(program)) == (width, height, length)
        assert esolangs.run("Alight", program) == "0"


def test_alight_planned_layouts_render_and_execute():
    from esolangs.tools.alight.balance import _emit, _plans

    for plan in _plans(2):
        program = _emit("0110", 2, plan)
        assert _evaluate("Alight", program, inputs=2) == "0110"


def test_alight_model_drift_aborts(monkeypatch):
    from esolangs.tools.alight import balance as module

    monkeypatch.setattr(module, "_alight_folded", lambda *_args: "begin;end;")
    with pytest.raises(AssertionError, match="fold model disagrees"):
        esolangs.generate("Alight", "0110", balance=True)


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 4, 8])
def test_alight_native_minimax_records_match_rendered_columns(inputs):
    from esolangs.tools.alight import (
        _alight_chunk,
        _alight_folded,
        _alight_units,
        _dimensions,
    )

    rng = random.Random(1025 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    flat = esolangs.generate("Alight", table)
    # Render each column once; this retains the old selector's full candidate set.
    forms = [(1, 0, "\n".join(flat)), (len(flat), 1, flat)]
    for columns in range(1, len(flat) + 1):
        program = _alight_folded(
            _alight_units(table, inputs, _alight_chunk(len(table), columns)), columns
        )
        width, _ = _dimensions(program)
        forms.append((max(width, columns), columns + 1, program))
        assert (
            esolangs.run(
                "Alight", program, esolangs.encode_inputs("Alight", [0] * inputs)
            )
            == table[0]
        )
    ranked = []
    for ready, priority, program in forms:
        width, height = _dimensions(program)
        ranked.append(
            (
                ready,
                (max(width, height), width * height, len(program), priority),
                program,
            )
        )
    for width in range(1, max(ready for ready, _, _ in ranked) + 1):
        expected = min(
            (item for item in ranked if item[0] <= width), key=lambda item: item[1]
        )[2]
        assert esolangs.generate("Alight", table, width) == expected
    balanced = esolangs.generate("Alight", table, balance=True)
    winners = [flat] + [
        min((item for item in ranked if item[0] <= width), key=lambda item: item[1])[2]
        for width in range(1, max(ready for ready, _, _ in ranked) + 1)
    ]
    assert balance_score(balanced) == min(map(balance_score, winners))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            "Alight", balanced, esolangs.encode_inputs("Alight", bits)
        )
        assert esolangs.read_answer("Alight", output) == table[row]
