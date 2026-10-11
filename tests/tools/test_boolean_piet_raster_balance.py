"""Piet's raster balancing is measured on rendered, executable images."""

import pytest

from esolangs.raster import Raster
from esolangs.tools.piet.balance import _bounded_operations, _emit, _plan
from tests.support.witness_tables import witnesses

pytestmark = pytest.mark.medium

TABLES = list(dict.fromkeys(witnesses(1) + witnesses(2)))


def score(image: Raster) -> tuple[int, int, int]:
    width, height = len(image.rows[0]), len(image.rows)
    return abs(width - height), width * height, width


def test_piet_invalid_plans_abort() -> None:
    operations = _bounded_operations("01101001")
    with pytest.raises(AssertionError, match="no room"):
        _plan(operations, 5, 6)
    plan = _plan(operations, 13, 14)
    with pytest.raises(AssertionError, match="exceeds"):
        _emit(operations, plan._replace(width=1))
    overlapping = plan._replace(rows=[plan.rows[0]._replace(x=0), *plan.rows[1:]])
    with pytest.raises(AssertionError, match="overwrites"):
        _emit(operations, overlapping)
    shifted = plan._replace(
        rows=[plan.rows[0], plan.rows[1]._replace(x=plan.rows[1].x + 1), *plan.rows[2:]]
    )
    with pytest.raises(AssertionError, match="turn model"):
        _emit(operations, shifted)
