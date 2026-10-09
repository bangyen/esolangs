"""No file grows past the cap, and tests/ stays smaller than src/."""

import pathlib
import subprocess

#: The most lines a file may have before it has to be split.
MAX_LINES = 1200

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TREES = ("src", "tests", "scripts")


def _sizes() -> dict[str, int]:
    """Return every checked file's line count, keyed by repo-relative path."""
    return {
        path.relative_to(_ROOT).as_posix(): path.read_text().count("\n")
        for tree in _TREES
        for path in sorted((_ROOT / tree).rglob("*.py"))
    }


def test_no_file_is_over_the_cap() -> None:
    """A file over the cap must be split."""
    over = {name: lines for name, lines in _sizes().items() if lines > MAX_LINES}
    assert not over, f"over {MAX_LINES} lines: {over}. Split the file."


def _tracked_lines(tree: str) -> int:
    """Count the lines of ``tree/*.py`` files git sees, as ``wc -l`` does."""
    # Untracked files count too: a new language's tests are untracked until
    # committed, and a file only staged for deletion does not.
    listed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            f"{tree}/*.py",
        ],
        cwd=_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    names = [name.decode() for name in listed.split(b"\0") if name]
    paths = [_ROOT / name for name in names]
    return sum(path.read_bytes().count(b"\n") for path in paths if path.exists())


def test_tests_stay_smaller_than_src() -> None:
    """The test budget: tests/*.py lines stay under src/*.py lines."""
    tests, src = _tracked_lines("tests"), _tracked_lines("src")
    assert src > 0
    assert tests < src, f"tests/ has {tests} lines, src/ only {src}: trim tests"
