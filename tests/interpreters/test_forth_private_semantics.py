"""Independently execute Forþ's alternate constructions."""

import itertools

import pytest

from esolangs.tools.forth import _forth_ordered, _forth_stack_programs
from tests.interpreters.forth_observer import check
from tests.interpreters.forth_reference import Reference


@pytest.mark.parametrize("n", range(1, 7))
def test_read_and_rotate_arrangements(n):
    for expected, source in _forth_stack_programs(n).items():
        text = "\n".join(str(i) for i in range(n)) + "\n"
        ref = Reference(text)
        assert ref.execute(source)
        assert tuple(ref.stack) == expected
        assert check(source, text)["reads"] == n


@pytest.mark.medium
@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_ordered_shared_and_unshared(n, shard):
    for value in range(shard, 2 ** (2**n), 16 if n == 3 else 1):
        table = format(value, f"0{2**n}b")
        for perm in itertools.permutations(range(n)):
            ordered = [""] * (2**n)
            for row, answer in enumerate(table):
                bits = format(row, f"0{n}b")
                ordered[int("".join(bits[i] for i in perm), 2)] = answer
            for share in (False, True):
                source = _forth_ordered("".join(ordered), perm, share=share)
                assert source
                for row, answer in enumerate(table):
                    result = check(source, "\n".join(format(row, f"0{n}b")) + "\n")
                    assert result["output"] == answer
                    assert result["reads"] == n
