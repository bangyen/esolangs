"""Shared assertions for seeded native-machine factories."""

import pytest

from esolangs.runtime.randomness import Seeded


def rng_factory(prepare, source):
    rng = Seeded(7)
    before = rng._random.getstate()
    options = {"rng": rng}
    factory = prepare(source, options)
    return rng, before, options, factory


def reject_rng_options(prepare, invalid, message, valid):
    with pytest.raises(TypeError, match=message):
        prepare(invalid, {})
    with pytest.raises(TypeError, match="only the rng"):
        prepare(valid, {"unknown": True})
