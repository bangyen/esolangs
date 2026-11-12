"""Complete independent microstates for the original bounded IO family."""

from esolangs.languages.object_disoriented import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.workspace_oracle import WorkspaceOracle

from . import full_oracle, workspace_views


def check_accounting_object_disoriented(table):
    """Partition all376 old records once over the unchanged23 MEDIUM table owners."""
    labels = full_oracle.table_labels()
    assert len(labels) == len(set(labels)) == 23
    assert table in labels
    bucket = labels.index(table)
    context = workspace_views.Context(
        native,
        ScriptedIO,
        WorkspaceVariant,
        WorkspaceSnapshot,
        WorkspaceModel,
        WrittenState,
        WorkspaceOracle,
    )
    for index, case in enumerate(full_oracle.cases()):
        if index % 23 == bucket:
            workspace_views.trace(case, context)
