"""Analytic balance rules match all supported layouts and execute every row."""

import random

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES, SourceKind
from esolangs.tools import wrap as _wrap
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import balance_score, wrap_chars
from tests.witness_tables import witnesses


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


@pytest.mark.parametrize(
    "language",
    [
        n
        for n, lang in LANGUAGES.items()
        if lang.boolean and lang.wrap is _wrap.wrap_grid
    ],
)
@pytest.mark.parametrize("table", ["0110", "10010110"])
def test_aligned_balanced_programs_compute_the_table(language, table):
    balanced = esolangs.generate(language, table, balance=True)
    default = esolangs.generate(language, table)
    optimum = min(
        [default]
        + [esolangs.generate(language, table, width=width) for width in range(1, 129)],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


def _regime_tables():
    # XOR, majority and one wide irregular table; the primitive fit oracles
    # cover the exhaustive geometry.
    return ["0110", witnesses(5)[-1]]


def _balances_whole_tokens(wrapper: object) -> bool:
    """Whether ``balance_program`` fits ``wrapper``'s tokens, not characters."""
    return wrapper in _wrap._TOKEN_PATTERNS or wrapper in (  # noqa: SLF001
        _wrap._polynomial,  # noqa: SLF001
        _wrap._bio,  # noqa: SLF001
        _wrap.wrap_space_delimited,
        _wrap.wrap_grid,
        _wrap._mammalian,  # noqa: SLF001
    )


def _balanced_languages() -> list[str]:
    """Text languages whose balance is more than a character reflow."""
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None
        and lang.source_kind is SourceKind.TEXT
        and (
            lang.balance is not None
            or _balances_whole_tokens(lang.wrap)
            or (lang.wrap is wrap_chars and lang.contract.parameterized)
        )
        # A width sweep takes minutes; each has its own balance tests.
        and name not in {"Polynomial", "SLOW ACV MAMMALIAN"}
    )


@pytest.mark.medium
@pytest.mark.parametrize("language", _balanced_languages())
@pytest.mark.parametrize("table", _regime_tables())
def test_balance_reaches_the_supported_minimum(language, table):
    default = esolangs.generate(language, table)
    balanced = esolangs.generate(language, table, balance=True)
    widest = max(map(len, default.split("\n")))
    layouts = [default] + [
        esolangs.generate(language, table, width=width)
        for width in range(1, max(65, widest + 1))
    ]
    optimum = min(layouts, key=balance_score)
    assert balanced in layouts
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate(language, balanced, inputs=len(table).bit_length() - 1) == table


def test_native_width_generators_have_balance_rules():
    from esolangs.registry import LANGUAGES
    from esolangs.tools.wrap import takes_width

    assert not [
        name
        for name, language in LANGUAGES.items()
        if (generator := language.boolean) is not None
        and takes_width(generator)
        and language.balance is None
    ]
