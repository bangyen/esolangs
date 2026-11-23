"""Execute the owned construction witnesses and check that each table is used."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from esolangs.exceptions import GeneratorCapError
from esolangs.operations import generation
from esolangs.registry import LANGUAGES

if TYPE_CHECKING:
    from docs import evidence
else:
    # Owned tests import through scripts, so patch that module instance.
    from scripts.docs import evidence


type _WitnessKey = tuple[str, str, evidence.TableWitness]


class _WitnessRun:
    def __init__(self) -> None:
        self.declared: dict[_WitnessKey, evidence.ConstructionBoundary] = {
            (language, label, witness): record
            for language in LANGUAGES
            for label, record in evidence.construction_records(language).items()
            if record.test is not None
            for witness in record.witnesses
        }
        self._retained: dict[int, _WitnessKey] = {}
        self._tables: dict[int, tuple[str, set[_WitnessKey]]] = {}
        self._active = ""
        self._observed: set[_WitnessKey] = set()
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

    def materialized(self, witness: evidence.TableWitness, table: str) -> None:
        key = self._retained.get(id(witness))
        if key is None or key not in self.declared:
            return
        node = self.declared[key].test
        assert node is not None
        if self._active == node or self._active.startswith(node + "["):
            self._tables.setdefault(id(table), (table, set()))[1].add(key)

    def observe(
        self, language: str, table: str, *, width: int | None, balance: bool
    ) -> None:
        retained = self._tables.get(id(table))
        if retained is None:
            return
        for key in retained[1]:
            record = self.declared[key]
            layout = record.generation_options()
            if key[0] == language and (
                not layout or (width, balance) == (record.width, record.balance)
            ):
                self._observed.add(key)

    @contextmanager
    def exercise(
        self, language: str, table: str, *, width: int | None, balance: bool
    ) -> Iterator[None]:
        try:
            yield
        except GeneratorCapError:
            self.observe(language, table, width=width, balance=balance)
            raise
        else:
            self.observe(language, table, width=width, balance=balance)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Generator[None, object, object]:
        self._observed.clear()
        self._tables.clear()
        self._active = item.nodeid
        try:
            return (yield)
        finally:
            self._tables.clear()
            self._active = ""

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
            self.seen.update(self._observed)


def main() -> int:
    """Run each declared pytest node once in a serial process."""
    run = _WitnessRun()
    if not run.declared:
        raise ValueError("no owned construction witnesses were declared")
    original_table = evidence.TableWitness.table
    original_generate = generation._generate_checked  # noqa: SLF001
    original_construct = evidence.construct_witness

    def observed_table(witness: evidence.TableWitness) -> str:
        table = original_table(witness)
        run.materialized(witness, table)
        return table

    def observed_generate(language: str, table: str, *args: Any, **kwargs: Any) -> Any:
        with run.exercise(
            language, table, width=kwargs["width"], balance=kwargs["balance"]
        ):
            return original_generate(language, table, *args, **kwargs)

    def observed_construct[T](
        language: str, table: str, constructor: Callable[[str], T]
    ) -> T:
        with run.exercise(language, table, width=None, balance=False):
            return original_construct(language, table, constructor)

    with (
        patch.object(evidence, "construction_boundaries", run.read),
        patch.object(evidence.TableWitness, "table", observed_table),
        patch.object(generation, "_generate_checked", observed_generate),
        patch.object(evidence, "construct_witness", observed_construct),
    ):
        status = pytest.main(
            [
                "-q",
                "-n",
                "0",
                "-o",
                "addopts=--timeout-method=thread",
                *sorted(
                    {record.test for record in run.declared.values() if record.test}
                ),
            ],
            plugins=[run],
        )
    if status != 0:
        return int(status)
    missed = run.declared.keys() - run.seen
    for language, label, witness in sorted(missed, key=str):
        print(
            f"{language}/{label}: n={witness.arity} {witness.name} "
            "did not reach the declared generator layout"
        )
    if missed:
        return 1
    print(f"{len(run.seen)} declared construction witnesses exercised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
