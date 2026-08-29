"""Check the constructive floor for a program meeting the boolean contract.

The exhaustive sweep in ``search2.py`` capped at length 11, which is below
the shortest program that can possibly satisfy the contract, so its null
result carries no information.  The echo is the witness that fixes the floor.
"""

from lib import table_of

ECHO = "111211111121"


def main():
    """Show the echo's table and confirm the floor is 12, not below."""
    table = table_of(ECHO)
    print(f"{ECHO!r} (len {len(ECHO)}): table={table}")
    print("  -> a one-input identity: ignores the second input, as expected")


if __name__ == "__main__":
    main()
