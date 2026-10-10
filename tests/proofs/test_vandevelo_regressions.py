"""Vandevelo stays measured and open, held to both regressions."""

from tests.proofs._ledger import load as load_ledger
from tests.proofs._roadmap import load
from tests.proofs.deep.execution import exempt_generators as execution_exempt
from tests.proofs.deep.linearity import exempt_generators


def test_vandevelo_remains_held_to_both_regressions() -> None:
    row = load().by_name()["Vandevelo"]
    assert row.output_size == "Measured"
    assert load_ledger().by_name()["Vandevelo"].execution_class == "linear"
    assert not row.size_is_settled
    assert row.is_open
    assert "Vandevelo" not in exempt_generators()
    assert "Vandevelo" not in execution_exempt()
