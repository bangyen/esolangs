"""CV(N)(C) through the shared API, CLI and machinery."""

from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs import run, serialization


class TestNameResolutionIsTrulyCaseInsensitive:
    """The usage text promises it for every name, including the odd ones."""

    @pytest.mark.parametrize(
        "spelling", ["CV(N)(C)", "cv(n)(c)", "CV(n)(c)", "cvnc", "CVNC"]
    )
    def test_the_overridden_name_folds_too(self, spelling: str) -> None:
        """Its id came from an exact-key override, so only one case matched."""
        assert esolangs.describe(spelling).name == "CV(N)(C)"


class TestPathAndTextTrailingNewline:
    """Path and string input preserve the same source newlines."""

    def test_lf_ignored_by_cvnc_makes_path_and_text_agree(self, tmp_path: Path) -> None:
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110", width=3).source + "\n")
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], truth_table="0110")
        assert (
            run(
                "CV(N)(C)",
                path,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
            .unwrap()
            .output
            == "0"
        )
        assert (
            run(
                "CV(N)(C)",
                path.read_text(),
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
            .unwrap()
            .output
            == "0"
        )

    def test_they_agree_without_one(self, tmp_path: Path) -> None:
        """The difference is the newline and nothing else."""
        path = tmp_path / "c.txt"
        path.write_text(esolangs.generate("CV(N)(C)", "0110").source)
        stdin = esolangs.encode_inputs("CV(N)(C)", [0, 0], truth_table="0110")
        assert (
            run(
                "CV(N)(C)",
                path,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
            .unwrap()
            .output
            == run(
                "CV(N)(C)",
                path.read_text(),
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=5),
            )
            .unwrap()
            .output
        )


@pytest.mark.parametrize("name", ["CV(N)(C)"])
def test_the_override_name_specifically(name: str) -> None:
    """Named, so a future override cannot quietly reintroduce the gap."""
    assert esolangs.describe(f" {name} ").name == name
    api = esolangs.Language(name)
    artifact = api.generate("01")
    expected = artifact.evaluate([1])
    assert expected.answer == expected.observation.output == "1"
    for settings in (None, api.settings()):
        tagged = replace(artifact, language=" cv(n)(c) ", settings=settings)
        assert tagged.evaluate([1]) == api.prepare(tagged).evaluate([1]) == expected
        restored = serialization.from_json("cv_n_c", api.to_json(tagged))
        assert restored.language == api.name
        assert restored.evaluate([1]) == expected
    for slug in ("cvnc", "cv_n_c"):
        with pytest.raises(esolangs.ProgramError, match="generated for"):
            api.run(replace(artifact, language=slug)).unwrap()
