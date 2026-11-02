"""Exact flat lookup length and command count."""


def commands(n: int, _: str) -> int:
    """Return D+8n+19, with the actual digits of the maximal chosen literal."""
    from esolangs.languages.super_snusp.generator import _decimal

    return len(_decimal(1 << ((1 << n) - 1))) + 8 * n + 19
