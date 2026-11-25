"""Every ``language.toml`` section is one some reader knows."""

import os
import tomllib
from pathlib import Path

from scripts.docs.fragments import aggregate, section

#: Each section's reader; a misspelled section is otherwise silently ignored
#: (an ``[audit]`` date would be ignored by the audit reader).
KNOWN = {
    "ablations",  # scripts/docs/ablations.py
    "audits",  # scripts/docs/audits.py
    "balance_growth",  # tests/generators/test_balance_growth.py
    "catalogue",  # scripts/docs/catalogue.py
    "construction_boundaries",  # scripts/docs/evidence.py
    "curation",  # scripts/docs/curation.py
    "deep_arities",  # tests/proofs/deep
    "evidence",  # scripts/docs/evidence.py
    "generator_sizes",  # checks/generator_sizes.py
    "interpreter_ablations",  # scripts/docs/ablations.py
    "resource_evidence",  # scripts/docs/resource_evidence.py
    "proof_status",  # scripts/docs/proof_status.py
    "schemes",  # tests/proofs/_schemes.py
    "semantic_evidence",  # scripts/docs/semantic.py
}

PACKAGES = Path(__file__).resolve().parents[2] / "src/esolangs/languages"


def test_every_section_is_a_known_one() -> None:
    stray = {
        f"{path.parent.name}: [{section}]"
        for path in PACKAGES.glob("*/language.toml")
        for section in tomllib.loads(path.read_text(encoding="utf-8"))
        if section not in KNOWN
    }
    assert stray == set()


def test_aggregate_reloads_a_replaced_fragment_with_the_same_mtime_and_size(tmp_path):
    package = tmp_path / "fixture"
    package.mkdir()
    fragment = package / "language.toml"
    fragment.write_text("[proof]\nsize = 1\n", encoding="utf-8")
    cache = {}
    builds = []

    def build(_packages, _languages):
        builds.append(section(fragment, "proof"))
        return builds[-1]

    assert aggregate(cache, tmp_path, (), build) == {"size": 1}
    original = fragment.stat()
    replacement = package / "replacement.toml"
    replacement.write_text("[proof]\nsize = 2\n", encoding="utf-8")
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
    replacement.replace(fragment)
    assert fragment.stat().st_mtime_ns == original.st_mtime_ns
    assert fragment.stat().st_size == original.st_size

    assert aggregate(cache, tmp_path, (), build) == {"size": 2}
    assert aggregate(cache, tmp_path, (), build) == {"size": 2}
    assert builds == [{"size": 1}, {"size": 2}]
