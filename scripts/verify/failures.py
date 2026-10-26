"""Read a pytest log's failures: the sections, their ids, the overrun mark.

Two tools classify the same shape.  The gate decides whether a step's
failures are all duration-band overruns it may rerun alone; the mutant
sweep decides whether a baseline or a mutant died only of duration
flips.  The FAILURES-section grammar and the overrun signature live
here so the two cannot drift into disagreeing about the same log.
"""

from __future__ import annotations

import re

# The shape the root conftest gives a duration-band failure (manufactured in
# tests/support/duration_policy.py): how long the test took, then the band it
# blew.  The message is the failure's whole body in its FAILURES section, so
# a match there is a reliable claim that the failure is a wall-clock overrun
# and nothing else.
DURATION_FAILURE = re.compile(r"\d+\.\d{2}s exceeds the (?:fast|medium) band limit")

# A FAILURES section header: the test's dotted name between underscore rules.
SECTION_HEADER = re.compile(r"^_+ (.+?) _+$")


def failure_sections(text: str) -> list[tuple[str, str]] | None:
    """Return a pytest log's FAILURES sections as (title, body) pairs.

    None when the log carries no FAILURES banner -- the sections were cut
    off, or the run died before printing them -- because then no failure in
    it can be classified at all.
    """
    lines = text.splitlines()
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("=") and " FAILURES " in line
        ),
        None,
    )
    if start is None:
        return None
    sections: list[tuple[str, list[str]]] = []
    for line in lines[start + 1 :]:
        if line.startswith("=") and "short test summary info" in line:
            break
        header = SECTION_HEADER.match(line)
        if header:
            sections.append((header.group(1), []))
        elif sections:
            sections[-1][1].append(line)
    return [(title, "\n".join(body)) for title, body in sections]


def section_matches(title: str, nodeid: str) -> bool:
    """Whether a FAILURES header *title* names the summarized *nodeid*.

    The header drops the file path and dots the separator the node id
    colons: ``tests/x.py::TestA::test_b`` is headed ``TestA.test_b``.
    """
    return nodeid.endswith(("::" + title, "::" + title.replace(".", "::")))


def failed_ids(lines: list[str]) -> list[str]:
    """Node ids of pytest's ``FAILED <id> - <reason>`` summary lines."""
    return [
        line[len("FAILED ") :].partition(" - ")[0].strip()
        for line in lines
        if line.startswith("FAILED ")
    ]
