"""Tests for the emitted-size and step-count baseline gate.

The gate's own failure path is what matters here: a check that cannot report
a difference passes for the wrong reason, and this one exists precisely
because nothing was measuring these numbers.  ``differences`` is exercised
directly rather than through a sweep, which keeps the suite off the ~3s the
full 192 measurements take -- the gate step in ``just test`` pays that.
"""

import json
from typing import Any

from scripts.check_generator_sizes import (
    BASELINE,
    SCHEMA,
    TABLES,
    baseline,
    differences,
)

RECORD = {
    "language": "brainfuck",
    "truth_table": TABLES[0],
    "source_units": 205,
    "commands": 179,
    "generation_ns_best": 1234,
    "generation_ns_median": 5678,
}


def _measured() -> dict[str, Any]:
    return baseline([dict(RECORD)])


class TestProjection:
    """A sweep is reduced to exactly the fields that repeat run to run."""

    def test_timings_are_dropped(self) -> None:
        rows = _measured()["records"]["brainfuck"][TABLES[0]]
        assert rows == {"source_units": 205, "commands": 179}

    def test_the_header_carries_the_corpus(self) -> None:
        measured = _measured()
        assert measured["schema"] == SCHEMA
        assert measured["tables"] == list(TABLES)


class TestDifferences:
    """Every way the measurement can disagree with the baseline is reported."""

    def test_an_identical_baseline_is_silent(self) -> None:
        assert differences(_measured(), _measured()) == []

    def test_a_size_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "source_units": 206}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] source_units: 205 -> 206"
        ]

    def test_a_step_count_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "commands": 180}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] commands: 179 -> 180"
        ]

    def test_a_win_fails_too(self) -> None:
        """A smaller program is still a diff the baseline has to record."""
        smaller = baseline([{**RECORD, "source_units": 12}])
        assert differences(_measured(), smaller) != []

    def test_a_new_language_is_reported(self) -> None:
        added = baseline([dict(RECORD), {**RECORD, "language": "Fargo"}])
        assert differences(_measured(), added) == [
            "Fargo: not in the baseline (new language?)"
        ]

    def test_a_dropped_language_is_reported(self) -> None:
        empty = baseline([])
        assert differences(_measured(), empty) == [
            "brainfuck: in the baseline but not in the registry"
        ]

    def test_a_stale_schema_short_circuits(self) -> None:
        stale = {**_measured(), "schema": SCHEMA - 1}
        assert differences(stale, _measured()) == [
            f"baseline schema {SCHEMA - 1!r}, expected {SCHEMA}"
        ]

    def test_a_changed_corpus_short_circuits(self) -> None:
        """Comparing across corpora would read as a whole-registry change."""
        stale = {**_measured(), "tables": ["0110"]}
        lines = differences(stale, _measured())
        assert len(lines) == 1
        assert lines[0].startswith("baseline tables")


class TestCommittedBaseline:
    """The file in the tree is the corpus this gate claims to cover."""

    def test_it_covers_every_language_and_table(self) -> None:
        recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert recorded["schema"] == SCHEMA
        assert recorded["tables"] == list(TABLES)
        assert recorded["records"]
        for name, rows in recorded["records"].items():
            assert sorted(rows) == sorted(TABLES), name
            for table, fields in rows.items():
                assert fields["source_units"] > 0, (name, table)
