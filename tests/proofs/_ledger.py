"""Read structured proof rows and audit the surrounding proof prose."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from scripts.docs.proof_status import ProofRow
from scripts.docs.resource_description import SCALING_CLASSES as SCALING_CLASSES
from scripts.docs.resource_description import SCALING_EVIDENCE as SCALING_EVIDENCE

#: Resolved from this file, not the working directory: the suite is run from
#: the repo root, from `just`, and from a worktree, and only ``__file__`` is
#: stable across all three.
DOC = Path(__file__).resolve().parents[2] / "docs" / "proofs" / "index.md"

#: The scheme definitions carry prose headings; the ledger's Proof column
#: carries short labels.  The mapping is explicit because the two genuinely
#: differ ("Decision tree." defines the ``tree`` label), so deriving one from
#: the other by lowercasing would silently accept a renamed heading.
SCHEME_LABELS = {
    "Decision tree": "tree",
    "Minterms": "minterms",
    "Finite lookup": "finite lookup",
    "Parameterized tree": "parameterized tree",
    "Parameterized lookup": "parameterized lookup",
    "Parameterized construction": "parameterized construction",
    "Linear lookup": "linear lookup",
    "Reduction": "reduction",
}

#: Defined in the "Proof schemes" section but deliberately not a Proof label:
#: it describes how the lookup rows relate to their tree route rather than
#: naming a proof.  Listed so a test can tell "not a label" from "undefined".
NOT_A_LABEL = frozenset({"Size dispatch"})

#: Qualifiers that may appear alongside a scheme in the Proof column.  Both
#: are defined in prose rather than as a ``**Heading.**``: ``cap`` in the
#: ledger preamble, ``exception`` in the Exceptions section.
QUALIFIERS = frozenset({"cap", "exception"})

_WORD_NUMBERS = {"no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

#: The scaling evidence whose rows the audit table must carry as open on
#: generation time or output size, and vice versa.
UNSETTLED_SCALING = frozenset({"measured", "lower bound"})

#: A ``linear`` clause names its argument; longer than this it is prose.
LINEAR_CLAUSE_WORDS = 12

#: A measured cell that opens ``worst`` or ``at most`` states a formula,
#: whose spaced operators count as words.
FORMULA_CLAUSE_WORDS = 20


class Row(ProofRow):
    """One structured generator ledger row with scheme and growth views."""

    @property
    def schemes(self) -> tuple[str, ...]:
        """Return the labels naming proof schemes rather than qualifiers."""
        return tuple(x for x in self.labels if x not in QUALIFIERS)

    @property
    def scaling_clause(self) -> str:
        """Return the declared scaling argument."""
        return self.resources.scaling.clause

    @property
    def execution_class(self) -> str:
        """Return the declared execution growth class."""
        return self.resources.execution.growth

    @property
    def execution_clause(self) -> str:
        """Return the declared execution bound."""
        return self.resources.execution.clause

    @property
    def workspace_class(self) -> str:
        """Return the declared workspace growth class."""
        return self.resources.workspace.growth

    @property
    def workspace_clause(self) -> str:
        """Return the declared workspace bound."""
        return self.resources.workspace.clause


@dataclass(frozen=True)
class Ledger:
    """Everything ``proofs/index.md`` claims that can be checked against the code."""

    rows: tuple[Row, ...]
    defined_schemes: frozenset[str]
    cap_section: str
    cap_bullets: int
    exception_section: str
    exception_bullets: int
    claimed_arguments: int
    claimed_exceptions: int
    no_tree_route: frozenset[str]

    def by_name(self) -> dict[str, Row]:
        """Rows keyed by the generator's registry display name."""
        return {row.generator: row for row in self.rows}

    def labelled(self, label: str) -> tuple[Row, ...]:
        """Every row carrying ``label`` in its Proof column."""
        return tuple(row for row in self.rows if label in row.labels)


def _section(text: str, heading: str) -> str:
    """Return the body under ``heading``, up to the next heading of any depth."""
    match = re.search(rf"^#+ {re.escape(heading)}$", text, re.MULTILINE)
    assert match, f"{DOC} has no {heading!r} heading"
    rest = text[match.end() :]
    following = re.search(r"^#+ ", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


def _bullets(section: str) -> int:
    """Count top-level ``- `` bullets, ignoring wrapped continuation lines."""
    return sum(1 for line in section.splitlines() if line.startswith("- "))


def load(path: Path | None = None) -> Ledger:
    """Read and parse the ledger."""
    text = (path or DOC).read_text(encoding="utf-8")

    from scripts.docs.proof_status import load as load_status

    proofs, _ = load_status()
    rows = [
        Row(
            row.generator,
            row.labels,
            row.qualification,
            row.resources,
            row.evidence,
            row.definitions,
        )
        for row in proofs
    ]

    schemes = _section(text, "Proof schemes")
    defined = {
        match.group(1)
        for match in re.finditer(r"^\*\*(.+?)\.\*\*", schemes, re.MULTILINE)
    }

    # ``scripts/docs/proof_status.py`` renders this sentence; reading it back
    # catches a committed copy left behind by an edit to the ledger rows.
    count = re.search(
        r"records (\d+) theoretical totality arguments and (\w+) exceptions?",
        " ".join(text.split()),
    )
    assert count, f"{DOC} no longer states its own totals"

    # Each exemption owns a bullet so language removal can cut it whole.
    heading = (
        "These generators keep no unconstrained tree route and have no subtree to fold:"
    )
    assert heading in schemes, "Size dispatch no longer names its exemption list"
    exemptions = schemes.split(heading, 1)[1]
    names = frozenset(re.findall(r"^- ([^:\n]+):", exemptions, re.MULTILINE))
    assert names, "Size dispatch no longer names which rows lack a tree route"

    cap = _section(text, "Resource-ceiling audit")
    exceptions = _section(text, "Exceptions and walls")
    return Ledger(
        no_tree_route=names,
        rows=tuple(rows),
        defined_schemes=frozenset(defined),
        cap_section=cap,
        cap_bullets=_bullets(cap),
        exception_section=exceptions,
        exception_bullets=_bullets(exceptions),
        claimed_arguments=int(count.group(1)),
        claimed_exceptions=(
            int(word)
            if (word := count.group(2).lower()).isdigit()
            else _WORD_NUMBERS[word]
        ),
    )
