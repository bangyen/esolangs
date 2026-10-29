"""Every ``language.toml`` section is one some reader knows."""

import tomllib
from pathlib import Path

#: Each section's reader; a misspelled section is otherwise silently ignored
#: (an ``[audit]`` date would drop the language from the roadmap's list).
KNOWN = {
    "ablations",  # scripts/docs/generate.py
    "audits",  # scripts/docs/audits.py
    "balance_growth",  # tests/generators/test_balance_growth.py
    "catalogue",  # scripts/docs/catalogue.py
    "curation",  # scripts/docs/curation.py
    "deep_arities",  # tests/proofs/deep
    "formula_arities",  # tests/proofs/_arities.py
    "generator_sizes",  # checks/generator_sizes.py
    "interpreter_ablations",  # a record: interpreter audit verdicts
    "proof_status",  # scripts/docs/proof_status.py
    "schemes",  # tests/proofs/_schemes.py
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
