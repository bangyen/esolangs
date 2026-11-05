"""A three-instruction ceiling for Codesick's short node labels."""

from esolangs.languages.codesick.proof_formulas import node_count


def _chars(n: int, _: str) -> int:
    """At most three instructions per node, ten label occurrences per three."""
    count = node_count(n)
    # Base88 names (skipping three keywords) fit digits10(C+1).
    # A node and two forwarders cost <=(64+10w), with two final prints.
    return (68 + 10 * len(str(count + 1))) * count + 43
