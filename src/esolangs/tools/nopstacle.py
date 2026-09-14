"""Prototype Boolean-function generator for Nopstacle."""

from esolangs.exceptions import TruthTableError
from esolangs.tools.helpers import _validate_truth_table

__all__ = ["instantiate_nopstacle", "nopstacle"]

_PREFIX = "Nopstacle Boolean prototype\n"
_WIDTH = "width "


def nopstacle(truth_table: str, width: int | None = None) -> str:
    """Build a template specialized by :func:`instantiate_nopstacle`.

    Nopstacle has no input instruction, so the template carries the truth
    table and one ``{Xi}`` slot per input.  Instantiation evaluates that table
    row and emits a program whose termination is the answer: halt is ``0``;
    crossing program copies forever is ``1``.

    This prototype deliberately specializes the lookup in the host.  A future
    registered generator should route the embedded bits inside Nopstacle.
    """
    n = _validate_truth_table(truth_table)
    slots = "".join(f"{{X{i}}}" for i in range(n))
    template = f"{_PREFIX}{truth_table}\n{slots}"
    return template if width is None else f"{template}\n{_WIDTH}{width}"


def instantiate_nopstacle(template: str, bits: list[int]) -> str:
    """Specialize a Nopstacle prototype template for ``bits``.

    The live two-row gadget is followed by an inert record of the table and
    embedded input.  With a ``#`` at ``(0, 1)`` the IP is boxed at the origin
    and halts; with a space there it turns right and crosses copies forever.
    """
    lines = template.splitlines()
    if len(lines) not in (3, 4) or lines[0] != _PREFIX.rstrip("\n"):
        raise ValueError("not a Nopstacle Boolean prototype template")
    truth_table, slots = lines[1:3]
    constrained = len(lines) == 4 and lines[3].startswith(_WIDTH)
    if len(lines) == 4 and not constrained:
        raise ValueError("malformed Nopstacle width")
    n = _validate_truth_table(truth_table)
    expected_slots = "".join(f"{{X{i}}}" for i in range(n))
    if slots != expected_slots:
        raise ValueError("malformed Nopstacle input slots")
    if len(bits) != n or any(bit not in (0, 1) for bit in bits):
        raise TruthTableError(f"expected {n} Boolean input bits, got {bits!r}")

    row = sum(bit << (n - 1 - i) for i, bit in enumerate(bits))
    selector = "#" if truth_table[row] == "0" else " "
    if constrained:
        return f" {selector}\n##".rstrip()
    encoded_table = truth_table.replace("0", " ").replace("1", "#")
    encoded_bits = "".join("#" if bit else " " for bit in bits)
    width = max(2, len(encoded_table), len(encoded_bits))
    return "\n".join(
        line.rstrip()
        for line in (
            f" {selector}".ljust(width),
            "##".ljust(width),
            encoded_table.ljust(width),
            encoded_bits.ljust(width),
        )
    )
