"""FALSE's stack, variables, frames and input progress by construction."""

import re


def workspace_terms(_: int, program: str) -> dict[str, int]:
    """Identify the lookup or lambda route and count its non-input stores."""
    compact = "".join(program.split())
    direct = compact.endswith("*0\\>1&.")
    packed = not direct and compact.endswith("1&.")
    cached = not (direct or packed) and "[" in compact
    stores = compact.count(":")
    if packed:
        stores -= len(re.findall(r"\^1&[a-z]:", compact))
    return {"A": int(direct), "B": int(packed), "C": int(cached), "S": stores}
