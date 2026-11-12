"""Independent full scalar-family Packlang accounting on the old corpus."""

from esolangs.languages.packlang import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.workspace_oracle import WorkspaceOracle

from . import full_oracle, workspace_views


def check_accounting_packlang():
    """Preserve all1132 old cases and compare their full declared workspace."""
    context = workspace_views.Context(
        native,
        ScriptedIO,
        WorkspaceVariant,
        WorkspaceSnapshot,
        WorkspaceModel,
        WrittenState,
        WorkspaceOracle,
    )
    for case in full_oracle.cases():
        workspace_views.trace(case, context)

    workspace_views.retained_controls(context)
    workspace_views.prepared_siblings(context)
