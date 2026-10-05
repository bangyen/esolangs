"""Public proof metadata preserves explicit verdicts in the packaged manifest."""

import json
from pathlib import Path

import esolangs


def test_packaged_status_reaches_describe() -> None:
    package = Path(esolangs.__file__).parent
    data = json.loads((package / "proof_status.json").read_text())
    for row in data["audit"]:
        public = esolangs.describe(row["generator"])["proof_status"]
        assert public is not None
        assert public["audit"] == {
            key: value for key, value in row.items() if key != "generator"
        }
    for row in data["ledger"]:
        public = esolangs.describe(row["generator"])["proof_status"]
        assert public is not None
        assert {key: value for key, value in public.items() if key != "audit"} == {
            key: value for key, value in row.items() if key != "generator"
        }


def test_no_audit_does_not_invent_a_guarantee() -> None:
    public = esolangs.describe("brainfuck")["proof_status"]
    assert public is not None
    assert all(value is None for value in public["audit"].values())
    assert esolangs.describe("HQ9+")["proof_status"] is None


def test_caller_mutation_cannot_change_later_descriptions() -> None:
    public = esolangs.describe("Malbolge")["proof_status"]
    assert public is not None
    public["labels"].append("fake proof")
    public["audit"]["generation_time"] = "Linear"
    fresh = esolangs.Language("Malbolge").describe()["proof_status"]
    assert fresh is not None
    assert "fake proof" not in fresh["labels"]
    assert fresh["audit"]["generation_time"] == "Open"
