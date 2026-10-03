"""Independent spectral-certificate rejection controls."""

import pytest

from scripts.perron_certificate import check_certificate


@pytest.mark.parametrize(
    ("rows", "vector", "bound", "alphabet"),
    [
        ([[1]], [1], (1, 1), "a"),
        ([[0]], [0], (1, 1), "a"),
        ([[0, 0]], [1], (1, 1), "ab"),
        ([[0]], [1], (0, 1), "a"),
        ([[0]], [True], (1, 1), "a"),
        ([[0]], [1], (1, 0), "a"),
        ([[0]], [1, 1], (1, 1), "a"),
        ([[0, 0]], [1], (2, 1), "aa"),
    ],
)
def test_corrupted_certificates(rows, vector, bound, alphabet) -> None:
    with pytest.raises(ValueError, match=r"invalid|spectral"):
        check_certificate(rows, vector, bound, alphabet)


def test_repeated_edges_are_counted() -> None:
    check_certificate([[0, 0]], [3], (2, 1), "ab")
    with pytest.raises(ValueError, match="spectral"):
        check_certificate([[0, 0]], [3], (1999, 1000), "ab")


def test_dead_edges_contribute_nothing() -> None:
    check_certificate([[-1, 0]], [3], (1, 1), "ab")


@pytest.mark.medium
def test_cli_checks_grammar_and_rejects_a_spectrally_valid_mismatch(tmp_path) -> None:
    import json
    import subprocess
    import sys
    from pathlib import Path

    certificate = tmp_path / "certificate.json"
    data = {
        "alphabet": "ab",
        "rows": [[1, 0], [1, -1]],
        "vector": [1, 1],
        "bound": [2, 1],
        "factors": ["ab"],
        "regexes": [],
    }
    script = Path(__file__).resolve().parents[2] / "scripts/perron_certificate.py"
    command = [sys.executable, str(script), str(certificate), "--check-grammar"]
    certificate.write_text(json.dumps(data))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "forbidden-factor grammar verified" in result.stdout
    data["rows"][1][1] = 0
    certificate.write_text(json.dumps(data))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "grammar mismatch on 'ab'" in result.stderr
