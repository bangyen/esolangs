"""The local gate may skip work, but only work CI is known to redo.

``scripts/verify.py`` deselects the ``slow`` marker from a default run in both
test suites -- pytest's and ``extra/line``'s -- on the standing argument that
CI runs those tests on every push, so skipping them locally costs no coverage.
That argument only holds while the skip is exactly as narrow as it claims, so
the two halves are pinned here: the filter must reach the line step *and* it
must step aside for a caller who asked for something else, since a silently
discarded ``-m`` would turn someone's explicit selection into a different run
than the one they asked for.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify.py"


def load_script() -> object:
    """Import the verifier as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("verify", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLineAddopts:
    """``PYTEST_ADDOPTS`` for the line step composes, never clobbers."""

    def test_an_empty_environment_gets_the_filter(self) -> None:
        """The default case: nothing set, so the step deselects slow tests."""
        verify = load_script()
        assert verify._line_addopts({}) == "-m 'not slow'"  # noqa: SLF001

    def test_an_unrelated_flag_is_kept(self) -> None:
        """A caller's own option survives having the filter added to it."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-x"})  # noqa: SLF001
        assert got == "-x -m 'not slow'"

    def test_a_callers_own_marker_expression_wins(self) -> None:
        """``-m slow`` asks for the opposite set, and must not be overridden.

        Appending a second ``-m`` would leave the last one winning, so a run
        asking *for* the slow tests would silently execute none of them --
        the failure this guard exists to prevent.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m slow"})  # noqa: SLF001
        assert got == "-m slow"

    def test_the_filter_is_not_applied_twice(self) -> None:
        """Re-applying to an already-filtered environment is a no-op."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m 'not slow'"})  # noqa: SLF001
        assert got == "-m 'not slow'"

    def test_the_attached_marker_spelling_also_counts(self) -> None:
        """pytest reads ``-mslow`` too, so it is just as much a choice.

        Only the separated form shows up as a bare ``-m`` token, so a plain
        membership test would miss this and append a competing expression.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-mslow"})  # noqa: SLF001
        assert got == "-mslow"

    def test_a_long_option_is_not_mistaken_for_a_marker(self) -> None:
        """``--maxfail`` starts with neither ``-m`` nor a marker expression.

        The guard matches on the short-option prefix, and ``-m`` is pytest's
        only short option beginning that way, so a double-dashed option must
        still receive the filter.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "--maxfail=1"})  # noqa: SLF001
        assert got == "--maxfail=1 -m 'not slow'"


class TestLineStepIsNamedOnce:
    """The step name is a key in three places; a typo would go unnoticed."""

    def test_the_constant_matches_the_step_table_and_its_scope(self) -> None:
        """``LINE_STEP`` is the name the table and the scope map both use.

        Each lookup is by string, so a name that drifted in one place would
        not raise -- the step would simply stop being scoped, or stop being
        filtered, with nothing to say so.
        """
        verify = load_script()
        names = [name for name, _ in verify.STEPS]
        assert verify.LINE_STEP in names
        assert verify.LINE_STEP in verify.STEP_SCOPE
