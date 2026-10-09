"""CV(N)(C) through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs


class TestNameResolutionIsTrulyCaseInsensitive:
    """The usage text promises it for every name, including the odd ones."""

    @pytest.mark.parametrize(
        "spelling", ["CV(N)(C)", "cv(n)(c)", "CV(n)(c)", "cvnc", "CVNC"]
    )
    def test_the_overridden_name_folds_too(self, spelling: str) -> None:
        """Its id came from an exact-key override, so only one case matched."""
        assert esolangs.describe(spelling)["name"] == "CV(N)(C)"


class TestPathAndTextTrailingNewline:
    """Path input strips one trailing newline; string input preserves it."""

    def test_lf_ignored_by_cvnc_makes_path_and_text_agree(self, tmp_path: Path) -> None:
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110", width=3) + "\n")
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], truth_table="0110")
        assert esolangs.run("CV(N)(C)", path, stdin=stdin, timeout=5) == "0"
        assert esolangs.run("CV(N)(C)", path.read_text(), stdin=stdin, timeout=5) == "0"

    def test_they_agree_without_one(self, tmp_path: Path) -> None:
        """The difference is the newline and nothing else."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110"))
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], truth_table="0110")
        assert esolangs.run("CV(N)(C)", path, stdin=stdin, timeout=5) == esolangs.run(
            "CV(N)(C)", path.read_text(), stdin=stdin, timeout=5
        )
