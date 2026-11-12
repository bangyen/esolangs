"""Independent old wiki/literal trajectories partitioned over existing MEDIUM owners."""

from esolangs.languages.thisthat import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.workspace_oracle import WorkspaceOracle

from . import full_oracle, workspace_views


def check_accounting_thisthat(bucket):
    """Run the fixed bucket without replacing any prior owner body or bound."""
    context = workspace_views.Context(
        native,
        ScriptedIO,
        WorkspaceVariant,
        WorkspaceSnapshot,
        WorkspaceModel,
        WrittenState,
        WorkspaceOracle,
    )
    records = full_oracle.cases()
    assert len(records) == 67
    assert 0 <= bucket < 9
    for index, case in enumerate(records):
        selected = 1 if index == 65 else index % 9
        if selected == bucket:
            workspace_views.trace(case, context, history="final", wire=False)
