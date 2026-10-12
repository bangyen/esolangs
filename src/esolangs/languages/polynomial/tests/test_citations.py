"""Summary citations retain their numbered references and release tag."""

from __future__ import annotations

import re
from pathlib import Path

SUMMARY = Path(__file__).resolve().parents[5] / "docs" / "proofs" / "index.md"
TAG = "v1"
REPO = "https://github.com/bangyen/coefficient-mass/blob/"
CITATIONS = {
    ("coefficient-mass", "3.4"): ("Corollary", "cor:mass"),
    ("coefficient-mass-attainment", "2.1"): ("Proposition", "prop:confluent"),
    ("coefficient-mass-complex", "2.1"): ("Lemma", "lem:multisection"),
    ("coefficient-mass-complex", "2.3"): ("Corollary", "cor:imag"),
    ("coefficient-mass-complex", "4.2"): ("Theorem", "thm:bothsigns"),
}
PAPERS = frozenset(paper for paper, _ in CITATIONS)
_REFERENCE = re.compile(r"(Theorem|Lemma|Corollary|Proposition) +(\d+\.\d+)")
_LINK_KEY = re.compile(r"\]\([^)]*?([\w-]+)\.tex\)")
_COMPANION_LINK = re.compile(re.escape(REPO) + r"([^/]+)/")


def test_every_citation_is_covered() -> None:
    found = set()
    for line in SUMMARY.read_text().splitlines():
        cite = _LINK_KEY.search(line)
        if cite is None or cite.group(1) not in PAPERS:
            continue
        for match in _REFERENCE.finditer(line):
            found.add((match.group(1), cite.group(1), match.group(2)))
    expected = {
        (word, paper, number) for (paper, number), (word, _) in CITATIONS.items()
    }
    assert found == expected


def test_every_link_is_at_the_pinned_tag() -> None:
    assert set(_COMPANION_LINK.findall(SUMMARY.read_text())) == {TAG}


def test_summary_retains_the_recorded_title() -> None:
    assert "Corollary 3.4 (Logarithmic mass)" in " ".join(SUMMARY.read_text().split())
