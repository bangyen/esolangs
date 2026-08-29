"""Verify the length-7 selector against the shipped interpreter."""

from lib import run

TEMPLATE = "113{X0}1213"
SETTER = {0: "1", 1: "2"}


def main():
    """Instantiate both bits and report output, length and halt status."""
    lengths = set()
    for bit in (0, 1):
        code = TEMPLATE.replace("{X0}", SETTER[bit])
        out, status = run(code, "", limit=50000)
        lengths.add(len(code))
        print(
            f"  bit={bit} code={code!r} -> output={out!r} "
            f"(byte {ord(out) if len(out) == 1 else '-'}) status={status}"
        )
    print(f"  same instantiation length: {len(lengths) == 1} {lengths}")


if __name__ == "__main__":
    main()
