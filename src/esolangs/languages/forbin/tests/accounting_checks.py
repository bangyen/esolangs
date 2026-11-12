"""Independent bounded Forbin graph/history checks for the existing owner."""

from esolangs.exceptions import InputExhaustedError
from esolangs.languages.forbin import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.workspace_oracle import WorkspaceOracle

from . import accounting_core as core
from .accounting_traces import cases, trace


def check_accounting_forbin():
    """Check all343 finite/error records without replacing any old owner body."""
    context = core.Context(
        native,
        ScriptedIO,
        WorkspaceVariant,
        WorkspaceSnapshot,
        WorkspaceModel,
        InputExhaustedError,
        WrittenState,
        WorkspaceOracle,
    )
    records = cases()
    assert len(records) == 343
    for record in records:
        trace(record, context)
