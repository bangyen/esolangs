"""Independent one-row Streetcode walker and sparse tape, capped at 48 cells.

The author's command table: https://esolangs.org/wiki/Streetcode (78016).
Wall-free row, byte-independent integer cells, IO, stop and dead-end reversal;
lane geometry and junctions remain in raw tests. Movement follows Decisions.
"""

from esolangs.languages.streetcode.interpreter import _Machine
from tests.interpreters.oracle_support import observed, reject_faults

from .full_oracle import Case
from .workspace_checks import check_case


def _check(factory):
    check_case(Case("C^O;", "unused"), factory)


def check_raw_streetcode():
    _check(_Machine)
    for code in ([], [""], ["abc"], ["CC"]):
        assert observed(_Machine, code, "", lambda machine: machine.snapshot()) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongCell(_Machine):
        def step(self):
            super().step()
            self.cells = {**self.cells, self.cp: self.cells.get(self.cp, 0) + 1}

    reject_faults(_check, _Machine, WrongCell)
