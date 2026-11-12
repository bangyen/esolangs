"""Analytic balance rules match all supported layouts and execute every row."""

import random

import pytest

import esolangs
from esolangs.generation import wrap as _wrap
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score, wrap_chars, wrap_program
from esolangs.registry import LANGUAGES, SourceKind
from esolangs.registry._certification import load as load_certification
from tests.support.evaluation import _evaluate
from tests.support.exact_token_width import exact_token_width
from tests.support.witness_tables import witnesses

#: ``balanced_token_width`` and ``balance`` may exceed the best side by this much.
TOLERANCE = 1.05


def _assert_token_fit(tokens, separator, **options):
    width = balanced_token_width(tokens, separator, **options)
    exact = exact_token_width(tokens, separator, **options)
    assert (
        balance_score(_wrap._join_tokens(tokens, width, separator))[0]
        <= TOLERANCE * balance_score(_wrap._join_tokens(tokens, exact, separator))[0]
    )
    return width


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 5), (2, 9), (6, 15)])
def test_token_fit_lattice_respects_width_regimes(minimum, maximum) -> None:
    rng = random.Random(1013)
    for _ in range(100):
        tokens = ["x" * rng.randrange(1, 12) for _ in range(rng.randrange(1, 30))]
        width = _assert_token_fit(tokens, " ", minimum=minimum, maximum=maximum)
        assert minimum <= width <= maximum


@pytest.mark.parametrize("separator", ["", " "])
def test_long_token_dominates_packed_row_count(separator) -> None:
    tokens = ["x" * 80, *(["x", "xx"] * 80)]
    assert _assert_token_fit(tokens, separator, minimum=80) >= 80


def test_trimmed_row_ends_keep_the_width_lattice() -> None:
    tokens = [
        "xxxxx   ",
        "xxxxxxxxxxxxx ",
        "x   ",
        "xxxxxxxxxxx   ",
        "xx",
        "x  ",
        "xxxxx",
        "xxxxxxxxxxx   ",
        "xxx   ",
        "x  ",
        "xx   ",
        "xxxxxxx",
        "xxxxxxxxxxxxxxxx   ",
        "xxx  ",
        "xxxxx  ",
        "xxxxxxxxxxxxx    ",
    ]

    def score(width):
        return balance_score(
            "\n".join(
                row.rstrip()
                for row in _wrap._join_tokens(tokens, width, " ").splitlines()
            )
        )

    width = balanced_token_width(tokens, " ", minimum=13, maximum=40, rstrip_rows=True)
    assert 13 <= width <= 40
    assert score(width)[0] <= TOLERANCE * min(score(w)[0] for w in range(13, 41))


def _width_layouts(language, table, default, widths):
    """Yield every requested width, reusing width-independent emission."""
    lang = LANGUAGES[language]
    native = lang.backend.layout_width
    yield default.source
    for width in widths:
        if native or isinstance(default, esolangs.TemplateArtifact):
            yield esolangs.generate(language, table, width=width).source
        else:
            yield wrap_program(default.source, lang.id, width)


# XOR and one wide irregular table; primitive fit oracles exhaust geometry.
_REGIME_TABLES = ("0110", witnesses(5)[-1])
_GRID_TABLES = ("0110", "10010110")


def _balanced_languages() -> list[str]:
    """Text languages whose balance is more than a character reflow."""
    token_wrappers = {
        id(lang.backend.wrap)
        for lang in LANGUAGES.values()
        if lang.backend is not None and lang.backend.wrap_balance
    }
    token_wrappers.update(map(id, (_wrap.wrap_space_delimited, _wrap.wrap_grid)))
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.backend is not None
        and lang.runtime.source_kind is SourceKind.TEXT
        and (
            lang.backend.balance is not None
            or isinstance(lang.backend.wrap, _wrap.TokenWrapper)
            or id(lang.backend.wrap) in token_wrappers
            or (lang.backend.wrap is wrap_chars and lang.parameterized)
        )
        and not load_certification(lang).slow_width_sweep
    )


def _balance_cases():
    cases = {
        (name, table): pytest.mark.medium
        for name in _balanced_languages()
        for table in _REGIME_TABLES
    }
    cases.update(
        ((name, table), ())
        for name, lang in LANGUAGES.items()
        if lang.backend is not None and lang.backend.wrap is _wrap.wrap_grid
        for table in _GRID_TABLES
    )
    return [pytest.param(*case, marks=mark) for case, mark in sorted(cases.items())]


@pytest.mark.parametrize(("language", "table"), _balance_cases())
def test_balance_reaches_the_supported_minimum(language, table) -> None:
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    widest = max(map(len, default.source.split("\n")))
    # Grid cases subsume the former aligned sweep, including every width to 128.
    limit = max(65, widest + 1) if table in _REGIME_TABLES else 0
    if LANGUAGES[language].backend.wrap is _wrap.wrap_grid and table in _GRID_TABLES:
        limit = max(limit, 129)
    optimum = min(
        map(
            balance_score,
            set(_width_layouts(language, table, default, range(1, limit))),
        )
    )
    # Contract relaxed by the user (2026-10-16): balance may be 5% worse in side.
    assert balance_score(balanced.source)[0] <= 1.05 * optimum[0]
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


def test_native_width_generators_have_balance_rules() -> None:
    assert not [
        name
        for name, language in LANGUAGES.items()
        if language.backend is not None
        and language.backend.layout_width
        and language.backend.balance is None
    ]
