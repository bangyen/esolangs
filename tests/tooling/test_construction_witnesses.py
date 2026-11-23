"""Construction evidence requires a matching exercise by the owned test."""

from types import SimpleNamespace

import pytest

import esolangs
from checks import check_construction_witnesses as check
from scripts.docs import evidence
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    ("exercise", "status"),
    [("read", 1), ("wrong width", 1), ("generate", 0), ("cap", 0)],
)
def test_materialization_does_not_cover_a_construction(monkeypatch, exercise, status):
    node = "test_owner.py::test_boundary"
    reference = evidence.TableWitness(2, "parity")
    boundary = evidence.ConstructionBoundary(
        (reference,), benchmark=False, test=node, width=None if exercise == "cap" else 8
    )
    monkeypatch.setattr(check, "LANGUAGES", {REFERENCE: object()})
    monkeypatch.setattr(evidence, "construction_records", lambda *_: {"case": boundary})

    def refuse(_table):
        raise esolangs.GeneratorCapError("test cap")

    def run(_args, *, plugins):
        (audit,) = plugins
        item = SimpleNamespace(nodeid=node)
        hook = audit.pytest_runtest_call(item)
        next(hook)
        table = evidence.construction_boundaries(REFERENCE)["case"][0].table()
        if exercise == "cap":
            with pytest.raises(esolangs.GeneratorCapError, match="test cap"):
                evidence.construct_witness(REFERENCE, table, refuse)
        elif exercise != "read":
            esolangs.generate(
                REFERENCE, table, width=8 if exercise == "generate" else 1
            )
        with pytest.raises(StopIteration):
            next(hook)
        audit.pytest_runtest_logreport(SimpleNamespace(when="call", passed=True))
        return 0

    monkeypatch.setattr(check.pytest, "main", run)
    assert check.main() == status
