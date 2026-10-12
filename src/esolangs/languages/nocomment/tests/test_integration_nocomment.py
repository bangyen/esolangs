"""NoComment through the shared API, CLI and machinery."""

import esolangs


def test_nocomment_builds_at_the_arity_that_escaped() -> None:
    """The escape's subject is gone: n=12 is a template, not a refusal."""
    n = 12
    table = "".join(str(bin(r).count("1") % 2) for r in range(2**n))
    template = esolangs.generate("NoComment", table)
    assert template.inputs == 12
