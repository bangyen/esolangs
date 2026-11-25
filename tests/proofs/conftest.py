"""Share one witness build when both local resource checks are selected."""

from pathlib import Path

import pytest

_PROOFS = Path(__file__).parent
_CHECK_SIZE = pytest.StashKey[bool]()


def _local_cases(
    items: list[pytest.Item], filename: str, test: str
) -> dict[str, pytest.Item]:
    return {
        item.name.removeprefix(test): item
        for item in items
        if item.path == _PROOFS / filename
        and item.name.startswith(test + "[")
        and not any(item.get_closest_marker(band) for band in ("slow", "weekly"))
    }


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Join paired checks after selection, keeping standalone node IDs available."""
    if config.option.collectonly:
        return
    sizes = _local_cases(items, "test_scaling_formulas.py", "test_size_formulas_hold")
    workspace = _local_cases(
        items,
        "test_workspace_formulas.py",
        "test_execution_and_workspace_formulas_hold",
    )
    joined = []
    for case, item in sizes.items():
        if case in workspace:
            workspace[case].stash[_CHECK_SIZE] = True
            joined.append(item)
    if joined:
        merged = set(joined)
        items[:] = [item for item in items if item not in merged]
        config.hook.pytest_deselected(items=joined)


@pytest.fixture
def include_size_proof(request: pytest.FixtureRequest) -> bool:
    """Include the size assertion for a paired local case."""
    return request.node.stash.get(_CHECK_SIZE, False)
