"""Every generator the deep-proof tuning fixture names still exists."""

import tomllib

from esolangs.registry import BY_BOOLEAN
from tests.proofs.deep import _TUNING


def test_tuning_names_only_real_generators() -> None:
    tuning = tomllib.loads(_TUNING.read_text(encoding="utf-8"))
    for section, keys in tuning.items():
        assert set(keys) <= set(BY_BOOLEAN), (section, set(keys) - set(BY_BOOLEAN))
