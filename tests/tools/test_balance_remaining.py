"""Analytic balance rules match all supported layouts and execute every row."""

import random
from itertools import product

import pytest

import esolangs
from esolangs.tools.fish import balance_fish, fish
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import balance_program, balance_score, wrap_program


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


@pytest.mark.medium
@pytest.mark.parametrize("language", ["sbleq", "slow_acv_mammalian"])
def test_multicell_and_trimmed_grid_fits_match_every_width(language):
    assert balance_program("", language) == ""
    for lengths in product((1, 2, 4, 9), repeat=5):
        program = " ".join("1" * length for length in lengths)
        balanced = balance_program(program, language)
        optimum = min(
            [program]
            + [
                wrap_program(program, language, width)
                for width in range(1, 4 * len(program) + 1)
            ],
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
        assert balanced.split() == program.split()


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_intercal_larger_statement_formats(inputs):
    from esolangs.tools.intercal import _intercal_narrow

    rng = random.Random(1016 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("INTERCAL", table)
    balanced = esolangs.generate("INTERCAL", table, balance=True)
    # Larger widths repeat this fitted format until the default starts fitting.
    widest = max(map(len, _intercal_narrow(table, simplify=False).splitlines()))
    layouts = [default] + [
        esolangs.generate("INTERCAL", table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            "INTERCAL", esolangs.instantiate("INTERCAL", balanced, bits)
        )
        assert esolangs.read_answer("INTERCAL", output) == table[row]


def test_polynomial_quotient_transitions_match_every_width():
    programs = ["", "1", "+ - 1"]
    programs.extend(
        "f(x) = " + " + ".join("1" * length for length in lengths)
        for lengths in product(range(1, 13), repeat=3)
    )
    for program in programs:
        balanced = balance_program(program, "polynomial")
        layouts = [program] + [
            wrap_program(program, "polynomial", width)
            for width in range(1, len(program) + 1)
        ]
        assert balanced in layouts
        assert balance_score(balanced) == min(map(balance_score, layouts))


@pytest.mark.parametrize("separator", ["", " "])
def test_token_fit_lattice_matches_every_width(separator):
    from esolangs.tools.wrap import _join_tokens

    assert balanced_token_width([], separator) == 1
    for lengths in product(range(1, 5), repeat=6):
        tokens = ["x" * length for length in lengths]
        width = balanced_token_width(tokens, separator)
        balanced = _join_tokens(tokens, width, separator)
        optimum = min(
            (_join_tokens(tokens, width, separator) for width in range(1, 30)),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)


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


@pytest.mark.parametrize("separator", ["", " "])
def test_token_fit_lattice_larger_unequal_tokens(separator):
    from esolangs.tools.wrap import _join_tokens

    rng = random.Random(1014)
    for _ in range(20):
        tokens = ["x" * rng.randrange(1, 61) for _ in range(rng.randrange(30, 81))]
        width = balanced_token_width(tokens, separator)
        optimum = min(
            (
                _join_tokens(tokens, width, separator)
                for width in range(1, len(separator.join(tokens)) + 1)
            ),
            key=balance_score,
        )
        assert balance_score(_join_tokens(tokens, width, separator)) == balance_score(
            optimum
        )


def test_fractran_parity_representation_omits_empty_width_regimes():
    from esolangs.tools.balance import _fractran

    parity = esolangs.generate("FRACTRAN", "0110", 4)
    balanced = _fractran("0110", parity)
    assert balanced in [
        esolangs.generate("FRACTRAN", "0110", width) for width in range(1, 9)
    ]
    assert esolangs.evaluate("FRACTRAN", balanced, inputs=2) == "0110"


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
@pytest.mark.parametrize("inputs", range(4, 7))
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
    assert esolangs.evaluate("BIO", balanced, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(7, 11))
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
        esolangs.evaluate("Polynomial", balanced, inputs=len(table).bit_length() - 1)
        == table
    )


@pytest.mark.parametrize("language", ["AddSubJump", "Decleq", "S*bleq"])
@pytest.mark.parametrize("table", ["0110", "0001", "10010110"])
def test_aligned_balanced_programs_compute_the_table(language, table):
    balanced = esolangs.generate(language, table, balance=True)
    default = esolangs.generate(language, table)
    optimum = min(
        [default]
        + [esolangs.generate(language, table, width) for width in range(1, 129)],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert (
        esolangs.evaluate(language, balanced, inputs=len(table).bit_length() - 1)
        == table
    )


def _fish_tables():
    tables = [
        format(value, f"0{1 << inputs}b")
        for inputs in range(1, 4)
        for value in range(1 << (1 << inputs))
    ]
    rng = random.Random(1002)
    for inputs in range(4, 11):
        tables.extend(
            "".join(rng.choice("01") for _ in range(1 << inputs)) for _ in range(4)
        )
        tables.extend(
            "".join(str((row.bit_count() + bias) % 2) for row in range(1 << inputs))
            for bias in (0, 1)
        )
    return tables


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
    assert (
        esolangs.evaluate("Fish", balanced, inputs=len(table).bit_length() - 1) == table
    )


def _regime_tables():
    tables = [
        format(value, f"0{1 << inputs}b")
        for inputs in range(1, 4)
        for value in range(1 << (1 << inputs))
    ]
    rng = random.Random(1003)
    tables.extend(
        "".join(rng.choice("01") for _ in range(1 << inputs))
        for inputs in (4, 5)
        for _ in range(2)
    )
    return tables


@pytest.mark.medium
@pytest.mark.parametrize(
    "language",
    [
        "Algebraic Programming Language",
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
        "Jaune",
        "INTERCAL",
        "Minifuck",
        "Minsky Swap",
        "Modulous",
        "Packlang",
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
    assert (
        esolangs.evaluate(language, balanced, inputs=len(table).bit_length() - 1)
        == table
    )


@pytest.mark.medium
@pytest.mark.parametrize(
    "language",
    ["Bitdeque", "FALSE", "Forbin", "FRACTRAN", "Jaune", "Minsky Swap", "RAM0"],
)
def test_larger_token_and_setter_regimes(language):
    rng = random.Random(1015)
    table = "".join(rng.choice("01") for _ in range(64))
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate(language, table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert esolangs.evaluate(language, balanced, inputs=6) == table


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", ["3x", "6-5", "Eval", "Home Row", "Sophie", "Unlambda"]
)
@pytest.mark.parametrize("table", ["0110", "0001", "10010110"])
def test_grammar_and_marked_run_fits_execute(language, table):
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    layouts = [default] + [
        esolangs.generate(language, table, width)
        for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert (
        esolangs.evaluate(language, balanced, inputs=len(table).bit_length() - 1)
        == table
    )


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_back_larger_tree_regimes(inputs):
    rng = random.Random(1010 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("Back", table)
    balanced = esolangs.generate("Back", table, balance=True)
    layouts = [default] + [
        esolangs.generate("Back", table, width) for width in range(1, 65)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = list(map(int, format(row, f"0{inputs}b")))
        source = esolangs.instantiate("Back", balanced, bits)
        output = esolangs.run("Back", source)
        assert esolangs.read_answer("Back", output) == table[row]


@pytest.mark.medium
def test_taglate_larger_seed_and_bootstrap_crossings():
    from esolangs.tools.taglate import _seed_commands

    table = "".join(str(row.bit_count() % 2) for row in range(64))
    default = esolangs.generate("Taglate", table)
    balanced = esolangs.generate("Taglate", table, balance=True)
    seed, _, commands = default.partition("\n")
    bootstrapped = "\n" + _seed_commands(seed) + commands
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        wrap_program(bootstrapped if width < len(seed) else default, "taglate", width)
        for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, 32, 63):
        stdin = esolangs.encode_inputs("Taglate", list(map(int, format(row, "06b"))))
        output = esolangs.run("Taglate", balanced, stdin)
        assert esolangs.read_answer("Taglate", output) == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
@pytest.mark.parametrize("affine", [False, True])
def test_container_larger_rule_transitions(inputs, affine):
    rng = random.Random(1011 + inputs)
    table = "".join(
        str(row.bit_count() % 2) if affine else rng.choice("01")
        for row in range(1 << inputs)
    )
    default = esolangs.generate("Container", table)
    balanced = esolangs.generate("Container", table, balance=True)
    widest = max(map(len, default.splitlines()))
    layouts = [default] + [
        esolangs.generate("Container", table, width)
        for width in range(1, max(65, widest + 1))
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        stdin = esolangs.encode_inputs("Container", bits)
        assert (
            esolangs.read_answer(
                "Container", esolangs.run("Container", balanced, stdin)
            )
            == table[row]
        )


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_thue_payload_crossing_matches_every_width(inputs):
    table = "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
    default = esolangs.generate("Thue", table)
    balanced = esolangs.generate("Thue", table, balance=True)
    optimum = min(
        [default]
        + [
            esolangs.generate("Thue", table, width)
            for width in range(1, len(table) + 12)
        ],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        stdin = esolangs.encode_inputs("Thue", bits)
        assert (
            esolangs.read_answer("Thue", esolangs.run("Thue", balanced, stdin))
            == table[row]
        )


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
    assert esolangs.evaluate("Streetcode", balanced, inputs=6) == table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_collatz_statement_thresholds_match_every_width(inputs):
    rng = random.Random(1004 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("Collatz Multiverse", table)
    balanced = esolangs.generate("Collatz Multiverse", table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate("Collatz Multiverse", table, width)
        for width in range(1, max(65, widest + 1))
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        stdin = esolangs.encode_inputs("Collatz Multiverse", bits)
        assert (
            esolangs.read_answer(
                "Collatz Multiverse",
                esolangs.run("Collatz Multiverse", balanced, stdin),
            )
            == table[row]
        )


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_modulous_literal_chunk_quotients(inputs):
    rng = random.Random(1017 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("Modulous", table)
    balanced = esolangs.generate("Modulous", table, balance=True)
    layouts = [default] + [
        esolangs.generate("Modulous", table, width)
        for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            "Modulous", balanced, esolangs.encode_inputs("Modulous", bits)
        )
        assert esolangs.read_answer("Modulous", output) == table[row]


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
            esolangs.evaluate("Packlang", balanced, inputs=len(table).bit_length() - 1)
            == table
        )


@pytest.mark.medium
@pytest.mark.parametrize("inputs", range(6, 11))
def test_packlang_larger_statement_fits(inputs):
    rng = random.Random(1018 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("Packlang", table)
    balanced = esolangs.generate("Packlang", table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate("Packlang", table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            "Packlang", balanced, esolangs.encode_inputs("Packlang", bits)
        )
        assert esolangs.read_answer("Packlang", output) == table[row]


@pytest.mark.slow
def test_minifuck_larger_paired_token_fits():
    inputs = 6
    rng = random.Random(1019 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate("Minifuck", table)
    balanced = esolangs.generate("Minifuck", table, balance=True)
    layouts = [default] + [
        esolangs.generate("Minifuck", table, width)
        for width in range(1, len(default) + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert esolangs.evaluate("Minifuck", balanced, inputs=inputs) == table


@pytest.mark.slow
def test_apl_larger_frame_budget_transitions():
    from esolangs.tools.algebraic_programming_language import _apl_tree_ordered
    from esolangs.tools.helpers import input_orders, permute_truth_table

    inputs = 6
    rng = random.Random(1020 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    language = "Algebraic Programming Language"
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    # No frame can split once the complete source fits, for either input order.
    widest = max(
        len(_apl_tree_ordered(permute_truth_table(table, perm), perm))
        for perm in input_orders(table)
    )
    layouts = [default] + [
        esolangs.generate(language, table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    assert esolangs.evaluate(language, balanced, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [8, 10])
def test_apl_large_frame_names_execute(inputs):
    language = "Algebraic Programming Language"
    rng = random.Random(1020 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    balanced = esolangs.generate(language, table, balance=True)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        output = esolangs.run(
            language, balanced, esolangs.encode_inputs(language, bits)
        )
        assert esolangs.read_answer(language, output) == table[row]


@pytest.mark.slow
@pytest.mark.parametrize(
    "language", ["Crement", "Dimensional", "EGL", "Smallfuck", "Underload"]
)
@pytest.mark.parametrize("inputs", [6, 8])
def test_larger_setter_and_header_regimes(language, inputs):
    rng = random.Random(1021 + inputs)
    table = "".join(rng.choice("01") for _ in range(1 << inputs))
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate(language, table, width) for width in range(1, widest + 1)
    ]
    assert balanced in layouts
    assert balance_score(balanced) == min(map(balance_score, layouts))
    if language == "Crement":
        assert (
            esolangs.evaluate(language, balanced, inputs=inputs, timeout=None) == table
        )
        return
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        if esolangs.describe(language)["parameterized"]:
            program, stdin = esolangs.instantiate(language, balanced, bits), ""
        else:
            program, stdin = balanced, esolangs.encode_inputs(language, bits)
        output = esolangs.run(language, program, stdin)
        assert esolangs.read_answer(language, output) == table[row]


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
