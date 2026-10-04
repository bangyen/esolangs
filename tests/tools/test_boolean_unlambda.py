"""unlambda generator tests."""

from esolangs import tools as boolean
from tests.tools.boolean_runners import five_input_sample


def test_unlambda_binds_repeated_subtrees_and_skips_equal_halves() -> None:
    """Share-taking nodes cut both totals and lengthen no table.

    A node returns ``s`` over its selected promises, so a repeated subtree
    bound once as ```` `N`dX ```` is ``i`` wherever it recurs below, and a
    node whose halves agree reads and runs the half.  41,074 characters over
    the 256 three-input tables fall to 32,522 (20.8%), and 144,722 over the
    seeded five-input sample to 100,963 (30.2%).
    """
    from tests.tools.plain_oracles import unlambda_plain as _plain

    three = [format(value, "08b") for value in range(256)]
    assert boolean.unlambda("01101001") == (
        "``@`d`k``s``?0i`d`@`d`k``s``?0ii``?1i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "``?1i`d`@`d`k``s``?1ii``?0i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "`d`@`d`k``s``?0i`d`.0v``?1i`d`.1v"
    )
    for tables, before, after in (
        (three, 41074, 32522),
        (five_input_sample(), 144722, 100963),
    ):
        plain = [len(_plain(table)) for table in tables]
        shared = [len(boolean.unlambda(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
