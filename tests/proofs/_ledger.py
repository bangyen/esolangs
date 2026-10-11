"""Read structured proof rows and audit the surrounding proof prose."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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

#: The Scaling column's classes, the text before the cell's first colon.
#: ``linear`` is proved O(T) size and time; ``linear, time n log`` keeps one
#: stated log factor in generation time; ``measured`` has no bound at all;
#: ``open`` and ``lower bound`` are the roadmap audit's open rows.
SCALING_CLASSES = frozenset(
    {"linear", "linear, time n log", "measured", "open", "lower bound"}
)

#: The classes whose rows the roadmap's audit table must carry as open on
#: generation time or output size, and vice versa.
UNSETTLED_SCALING = frozenset({"measured", "open", "lower bound"})

#: A ``linear`` clause names its argument; longer than this it is prose.
LINEAR_CLAUSE_WORDS = 12

#: A measured cell that opens ``worst`` or ``at most`` states a formula,
#: whose spaced operators count as words.
FORMULA_CLAUSE_WORDS = 20

#: The Execution column's classes: commands to halt, held to their growth by
#: ``tests/proofs/deep/execution.py``.  ``unmeasured`` says why.
EXECUTION_CLASSES = frozenset({"poly n", "linear", "unmeasured"})

#: The Workspace column's classes: peak written state in bits, held to its
#: growth by ``tests/proofs/deep/workspace.py``.  ``T log T`` is T cells of
#: ``log T``-bit values.
WORKSPACE_CLASSES = EXECUTION_CLASSES | {"T log T"}


@dataclass(frozen=True)
class Row:
    """One generator ledger row."""

    generator: str
    labels: tuple[str, ...]
    qualification: str
    scaling: str
    execution: str
    workspace: str

    @property
    def schemes(self) -> tuple[str, ...]:
        """The labels that name a proof scheme rather than a qualifier."""
        return tuple(x for x in self.labels if x not in QUALIFIERS)

    @property
    def scaling_class(self) -> str:
        """The Scaling cell's class: the text before its first colon."""
        return self.scaling.split(":", 1)[0].strip()

    @property
    def scaling_clause(self) -> str:
        """The Scaling cell's argument or term: the text after its class."""
        return self.scaling.split(":", 1)[1].strip() if ":" in self.scaling else ""

    @property
    def execution_class(self) -> str:
        """The Execution cell's class: the text before its first colon."""
        return self.execution.split(":", 1)[0].strip()

    @property
    def execution_clause(self) -> str:
        """The Execution cell's reason: the text after its class."""
        return self.execution.split(":", 1)[1].strip() if ":" in self.execution else ""

    @property
    def workspace_class(self) -> str:
        """The Workspace cell's class: the text before its first colon."""
        return self.workspace.split(":", 1)[0].strip()

    @property
    def workspace_clause(self) -> str:
        """The Workspace cell's store: the text after its class."""
        return self.workspace.split(":", 1)[1].strip() if ":" in self.workspace else ""


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
            row.scaling,
            row.execution,
            row.workspace,
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

    # "A Painter Ant, Alight, BIO, ... keep no tree route at all" -- the
    # Size dispatch paragraph's exemption list, read rather than duplicated
    # here so naming another generator in the prose also arms the test.
    # Matched against whitespace-collapsed prose: the sentence is wrapped to
    # 80 columns, so the names and the verb routinely straddle a line break.
    exempt = re.search(
        r"([\w,\-~/ ()]+?) keeps? no tree route at all",
        " ".join(schemes.split()),
    )
    assert exempt, "Size dispatch no longer names which rows lack a tree route"
    names = frozenset(
        part.strip() for part in re.split(r",| and ", exempt.group(1)) if part.strip()
    )

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
