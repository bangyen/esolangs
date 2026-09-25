"""The numbered citations of the coefficient-mass papers name the right results.

``polynomial.tex`` imports its coefficient-mass bound from a companion paper
by number -- ``\\cite[Corollary~3.4]{coefficient-mass}`` -- and the Markdown
companion and the ledger cite it and its siblings the same way.  A number is
not a link: reordering or inserting a result renumbers everything after it,
leaving a citation pointing at the wrong statement -- or at no statement --
silently and while still compiling.

The papers live in `bangyen/coefficient-mass`_ and are cited at a tag, so the
numbering those citations rely on is pinned here as :data:`PINNED`, generated
by that repo's ``just pin``.  This test holds every numbered citation to a
pinned result and the label it is supposed to name, and holds every citation
to the pinned tag.  Moving to a newer tag means regenerating :data:`PINNED`
and changing :data:`TAG` together; the labels are the part that must not move.

.. _bangyen/coefficient-mass: https://github.com/bangyen/coefficient-mass
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: Resolved from this file, not the working directory, for the same reason
#: :mod:`tests.proofs._ledger` does it: `just`, the repo root and a worktree
#: are all valid places to run from.
PROOFS = Path(__file__).resolve().parents[2] / "docs" / "proofs"

#: The coefficient-mass release every citation points at.
TAG = "v1"
REPO = "https://github.com/bangyen/coefficient-mass/blob/"

#: ``(paper, number) -> (word, label, title)`` at :data:`TAG`, from
#: ``just pin`` in bangyen/coefficient-mass.
PINNED = {
    ("coefficient-mass", "3.4"): ("Corollary", "cor:mass", "Logarithmic mass"),
    ("coefficient-mass-attainment", "2.1"): (
        "Proposition",
        "prop:confluent",
        "Confluent analogue",
    ),
    ("coefficient-mass-complex", "2.1"): ("Lemma", "lem:multisection", "Multisection"),
    ("coefficient-mass-complex", "2.3"): (
        "Corollary",
        "cor:imag",
        "Purely imaginary pairs",
    ),
    ("coefficient-mass-complex", "4.2"): (
        "Theorem",
        "thm:bothsigns",
        "Rows at real roots of both signs",
    ),
}

#: The companion papers, as the keys citations use.
PAPERS = frozenset(paper for paper, _ in PINNED)

#: Every numbered citation of a companion, as
#: ``(citing file, cited paper, number) -> (word, label)``.  The test also
#: checks the reverse: that every such citation in a citing file is listed.
CITATIONS = {
    ("index.md", "coefficient-mass", "3.4"): ("Corollary", "cor:mass"),
    ("polynomial.md", "coefficient-mass-attainment", "2.1"): (
        "Proposition",
        "prop:confluent",
    ),
    ("polynomial.md", "coefficient-mass-complex", "2.3"): ("Corollary", "cor:imag"),
    ("polynomial.tex", "coefficient-mass", "3.4"): ("Corollary", "cor:mass"),
    ("polynomial.tex", "coefficient-mass-complex", "2.1"): (
        "Lemma",
        "lem:multisection",
    ),
    ("polynomial.tex", "coefficient-mass-complex", "4.2"): (
        "Theorem",
        "thm:bothsigns",
    ),
}

#: The files whose citations the table above has to cover.
CITING = ("index.md", "polynomial.md", "polynomial.tex")

#: A numbered reference in running text or in a ``\cite`` option.
_REFERENCE = re.compile(
    r"(Theorem|Lemma|Corollary|Proposition)[~ ]+(\d+\.\d+)",
)

#: The paper a line cites: the key of its ``\cite``, or -- in Markdown, which
#: has no ``\cite`` -- the file name its link targets.
_CITE_KEY = re.compile(r"\\cite\[[^]]*\]\{([^}]*)\}")
_LINK_KEY = re.compile(r"\]\([^)]*?([\w-]+)\.tex\)")

#: Any link into the companion repo, and the version it names.
_COMPANION_LINK = re.compile(re.escape(REPO) + r"([^/]+)/")


def _cited(name: str) -> set[tuple[str, str, str]]:
    """The ``(word, paper, number)`` references to a companion ``name`` makes.

    The paper is the key the line's own ``\\cite`` names, or the ``.tex`` link
    target in Markdown.  A numbered reference on a line that names neither is
    the file's reference to itself; one whose key is not a companion is
    somebody else's.
    """
    found: set[tuple[str, str, str]] = set()
    for line in (PROOFS / name).read_text().splitlines():
        cite = _CITE_KEY.search(line) or _LINK_KEY.search(line)
        if cite is None or cite.group(1) not in PAPERS:
            continue
        for match in _REFERENCE.finditer(line):
            found.add((match.group(1), cite.group(1), match.group(2)))
    return found


@pytest.mark.parametrize(("citation", "expected"), sorted(CITATIONS.items()))
def test_citation_resolves(
    citation: tuple[str, str, str], expected: tuple[str, str]
) -> None:
    """Each cited number is the pinned, labelled result of the paper it names."""
    _, paper, number = citation
    assert (paper, number) in PINNED, f"{paper} {number} is not pinned"
    word, label, _ = PINNED[paper, number]
    assert (word, label) == expected


def test_every_citation_is_covered() -> None:
    """No file cites a companion by a number this table does not list."""
    for name in CITING:
        listed = {
            (word, paper, number)
            for (file, paper, number), (word, _) in CITATIONS.items()
            if file == name
        }
        assert _cited(name) == listed, name


def test_every_link_is_at_the_pinned_tag() -> None:
    """A link to another version of the papers may name other numbers."""
    for name in CITING:
        text = (PROOFS / name).read_text()
        assert set(_COMPANION_LINK.findall(text)) <= {TAG}, name


def test_the_cited_title_is_the_one_the_paper_names() -> None:
    """The bibliography entry's parenthetical names Corollary 3.4's title."""
    assert PINNED["coefficient-mass", "3.4"][2] == "Logarithmic mass"
    # Compared with whitespace collapsed: the entry is prose, and rewrapping
    # it to fit the margin (``1ab35a6d``) moved the parenthetical onto the
    # line above without changing what it names.
    bibliography = " ".join((PROOFS / "polynomial.tex").read_text().split())
    assert "Corollary~3.4 (Logarithmic mass)" in bibliography
