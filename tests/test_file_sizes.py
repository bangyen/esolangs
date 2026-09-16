"""No file grows past the cap, and the ones already over it only shrink.

The cap is on raw lines, which is what ``wc -l`` and a reviewer's scrollbar
see.  1500 sits just above the repo's 90th percentile, so it flags outliers
rather than taxing the commenting style: 38% of the tree is comments and
docstrings, and a tighter cap would price those out rather than the code.

``_RATCHET`` pins every file already over the cap at the size it had when
this test landed, so nothing had to be split up front.  Three rules keep it
converging: a new file over the cap fails, a pinned file that grows fails,
and a pinned file that has fallen under the cap must be removed from the
table -- otherwise a split would quietly leave its old budget behind for the
next file to spend.
"""

import pathlib

import pytest

#: The most lines a file may have before it has to be split.
MAX_LINES = 1500

#: Files already over :data:`MAX_LINES`, at the size they had when the cap
#: landed.  Each may only shrink, and must be deleted from this table once it
#: is under the cap.  Nothing may be added: a new entry means a file grew past
#: the cap instead of being split.
_RATCHET = {
    "src/esolangs/__init__.py": 1598,
    "src/esolangs/interpreters/grid_based/streetcode.py": 1855,
    "tests/interpreters/test_forbin.py": 1721,
    "tests/interpreters/test_streetcode.py": 2249,
    "tests/test_answer_plumbing.py": 1977,
    "tests/test_cli_conventions.py": 3403,
    "tests/test_vm.py": 2671,
    "tests/tools/test_boolean_grid.py": 2305,
    "tests/tools/test_boolean_minifuck.py": 3192,
    "tests/tools/test_boolean_other.py": 2633,
    "tests/tools/test_boolean_parameterized.py": 3563,
    "tests/tools/test_boolean_pct.py": 2443,
    "tests/tools/test_boolean_tape.py": 2070,
}

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TREES = ("src", "tests", "scripts")


def _sizes() -> dict[str, int]:
    """Return every checked file's line count, keyed by repo-relative path."""
    return {
        path.relative_to(_ROOT).as_posix(): path.read_text().count("\n")
        for tree in _TREES
        for path in sorted((_ROOT / tree).rglob("*.py"))
    }


def test_no_unratcheted_file_is_over_the_cap() -> None:
    """A file over the cap must be split, not added to the ratchet."""
    over = {
        name: lines
        for name, lines in _sizes().items()
        if lines > MAX_LINES and name not in _RATCHET
    }
    assert not over, (
        f"over {MAX_LINES} lines and not in the ratchet: {over}. Split the"
        " file -- the ratchet is for what was already over when the cap"
        " landed, not a place to park new growth."
    )


@pytest.mark.parametrize(("name", "ceiling"), sorted(_RATCHET.items()))
def test_a_ratcheted_file_only_shrinks(name: str, ceiling: int) -> None:
    """A file already over the cap may not grow any further."""
    lines = _sizes().get(name)
    assert lines is not None, (
        f"{name} is in the ratchet but does not exist; drop its entry"
    )
    assert lines <= ceiling, (
        f"{name} grew from {ceiling} to {lines} lines. It is already over the"
        f" {MAX_LINES}-line cap, so it may only shrink."
    )


def test_the_ratchet_holds_nothing_under_the_cap() -> None:
    """A file that has come under the cap leaves the ratchet.

    Otherwise the entry survives its own split and the budget it was granted
    is left lying around for the next file to grow into.
    """
    sizes = _sizes()
    retired = {
        name: sizes[name]
        for name in _RATCHET
        if name in sizes and sizes[name] <= MAX_LINES
    }
    assert not retired, (
        f"under the {MAX_LINES}-line cap now, so remove from the ratchet: {retired}"
    )
