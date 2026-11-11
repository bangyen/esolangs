"""Execute the owned construction witnesses and check that each table is used."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from esolangs.registry import LANGUAGES

if TYPE_CHECKING:
    from docs import evidence
else:
    # Owned tests import through scripts, so patch that module instance.
    from scripts.docs import evidence


type _WitnessKey = tuple[str, str, evidence.TableWitness]


class _WitnessRun:
    def __init__(self) -> None:
        self.declared: dict[_WitnessKey, str] = {
            (language, label, witness): node
            for language in LANGUAGES
            for label, record in evidence.construction_records(language).items()
            if (node := record.test) is not None
            for witness in record.witnesses
        }
        self._retained: dict[int, _WitnessKey] = {}
        self._active = ""
        self.seen: set[_WitnessKey] = set()
        self._read = evidence.construction_boundaries

    def read(
        self, language: str, *, benchmark_only: bool = False
    ) -> dict[str, tuple[evidence.TableWitness, ...]]:
        records = self._read(language, benchmark_only=benchmark_only)
        for label, witnesses in records.items():
            for witness in witnesses:
                self._retained[id(witness)] = language, label, witness
        return records

    def observe(self, witness: evidence.TableWitness) -> None:
        key = self._retained.get(id(witness))
        if key is not None and key in self.declared:
            node = self.declared[key]
            if self._active == node or self._active.startswith(node + "["):
                self.seen.add(key)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Generator[None, object, object]:
        self._active = item.nodeid
        try:
            return (yield)
        finally:
            self._active = ""


def main() -> int:
    """Run each declared pytest node once in a serial process."""
    run = _WitnessRun()
    if not run.declared:
        raise ValueError("no owned construction witnesses were declared")
    original_table = evidence.TableWitness.table

    def observed_table(witness: evidence.TableWitness) -> str:
        run.observe(witness)
        return original_table(witness)

    with (
        patch.object(evidence, "construction_boundaries", run.read),
        patch.object(evidence.TableWitness, "table", observed_table),
    ):
        status = pytest.main(
            [
                "-q",
                "-n",
                "0",
                "-o",
                "addopts=--timeout-method=thread",
                *sorted(set(run.declared.values())),
            ],
            plugins=[run],
        )
    if status != 0:
        return int(status)
    missed = run.declared.keys() - run.seen
    for language, label, witness in sorted(missed, key=str):
        print(f"{language}/{label}: n={witness.arity} {witness.name} was unused")
    if missed:
        return 1
    print(f"{len(run.seen)} declared construction witnesses exercised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
