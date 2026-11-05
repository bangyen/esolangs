"""Workspace formula definitions shared by proof tests and scaffolding."""

from collections.abc import Callable

from esolangs.registry import LANGUAGES
from tests.proofs._arities import formula_arities
from tests.proofs._formula import ledger_formulas

#: Formulas the ledger notation cannot state: a case split, a definition,
#: a count taken from the program.  Each lives on its language's
#: ``proof_workspace`` (``proof_formulas.py`` in its package); this table
#: holds only entries that cannot relocate, with the reason.
_HAND: dict[str, tuple[Callable[[int, str], int], bool, tuple[int, ...]]] = {}

#: Arities where the default (see ``ledger_formulas``) is too slow or too
#: shallow for the construction, aggregated from each package's
#: ``[formula_arities]`` section.
_ARITIES = formula_arities("workspace")
#: Generator -> (formula, exact?, arities): the ledger's own clause where
#: it parses (``tests/proofs/_formula.py``), else ``_HAND``.
_HAND.update(
    (name, lang.certification.proof_workspace)
    for name, lang in LANGUAGES.items()
    if lang.certification.proof_workspace is not None
)
FORMULAS = ledger_formulas(
    lambda row: row.workspace_clause if " bits" in row.workspace_clause else "",
    _HAND,
    _ARITIES,
    column="workspace",
)
