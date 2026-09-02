"""Check .pre-commit-config.yaml's hook revs against pyproject.toml's pins.

Dependabot watches pyproject.toml's dev extra but has no pre-commit
ecosystem, so a bump there leaves the matching hook ``rev`` behind and the
two run different versions of the same tool.  That is not cosmetic: a
ruff-format hook a minor behind the project's ruff reformats files the
project's ruff considers formatted, so ``just test-quick`` never converges.

This enforces the rule .github/dependabot.yml states in prose.  It is
deliberately literal -- it maps a hook repo to the distribution it ships and
compares the two strings -- so a new tool must be added here to be checked.
"""

import re
import sys
from pathlib import Path

# hook repo (as it appears in .pre-commit-config.yaml) -> pyproject dist name
HOOKS = {
    "https://github.com/charliermarsh/ruff-pre-commit": "ruff",
    "https://github.com/pre-commit/mirrors-mypy": "mypy",
}

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_pins(text: str) -> dict[str, str]:
    """Map distribution name to its exact pin, for ``name==version`` only."""
    return {m[1]: m[2] for m in re.finditer(r'"([A-Za-z0-9_.-]+)==([^"]+)"', text)}


def _hook_revs(text: str) -> dict[str, str]:
    """Map hook repo URL to its ``rev``, leading ``v`` stripped."""
    pairs = re.findall(r"-\s+repo:\s*(\S+)\s*\n\s*rev:\s*(\S+)", text)
    return {repo: rev.lstrip("v") for repo, rev in pairs}


def main() -> int:
    """Report any hook rev that disagrees with its pyproject pin."""
    pins = _pyproject_pins((ROOT / "pyproject.toml").read_text())
    revs = _hook_revs((ROOT / ".pre-commit-config.yaml").read_text())

    bad = []
    for repo, dist in HOOKS.items():
        pin, rev = pins.get(dist), revs.get(repo)
        if pin is None or rev is None:
            bad.append(f"  {dist}: not found (pyproject={pin!r} hook={rev!r})")
        elif pin != rev:
            bad.append(f"  {dist}: pyproject pins {pin}, hook rev is v{rev}")

    if bad:
        print("hook revs out of step with pyproject.toml's pins:")
        print("\n".join(bad))
        print("\nFix: edit the rev in .pre-commit-config.yaml to match, then")
        print("run the formatter -- a version bump often reformats files.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
