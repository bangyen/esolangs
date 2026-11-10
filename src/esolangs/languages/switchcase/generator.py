"""SwitchCase Boolean generator: buffer inputs, then share equal residuals.

Each input is read in stream order. Decision cases branch on the buffered
character; equal subtables share a case, equal children skip their test,
and constant residuals go straight to one of two printing leaves.

Size:
    O(T) text and construction: O(T/log T) residuals, O(log T) address digits.
    n=4 parity: 188 chars, n=10 random 1847: 4,139 chars.
    Constants: n+15+2b chars, n+6+b commands, 25+bl(n+1)+bl(n) written bits;
    b is the answer.

Decisions:
    Full splitting replaces decimal minority keys, which cost Theta(T log T)
    characters. Fresh-buffer reads define the next buffer, keeping the header
    narrow. Sharing is canonical; see [ablations.split_switch_on_top_bit].
"""

from esolangs.generation.decision import reduced_diagram
from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def switchcase(truth_table: str) -> str:
    """Build a SwitchCase program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        # Read into _, leaving the fresh answer a at zero until the last case.
        return (
            "$_\n0?=a"
            + "," * n
            + "\n$a\n0?"
            + ("+1" if truth_table[0] == "1" else "")
            + "@\n"
        )
    essential = essential_inputs(truth_table, n)
    return _diagram(n, essential, read_at(truth_table, essential, n))


def _diagram(n: int, essential: list[int], table: str) -> str:
    """Read every input, then dispatch shared residuals to two answer leaves."""
    diagram, root = reduced_diagram(table, len(essential))
    placed = {0: 0, 1: 1}
    nodes: list[tuple[int, int, int]] = []

    def place(reference: int) -> int:
        found = placed.get(reference)
        if found is not None:
            return found
        depth, zero, one = diagram[reference]
        zero, one = place(zero), place(one)
        placed[reference] = result = len(nodes) + 2
        nodes.append((depth, zero, one))
        return result

    # Case addresses depend on zero-first postorder, not analysis node ids.
    place(root)
    ranks = {physical: rank for rank, physical in enumerate(essential)}
    names = {physical: f"x{rank}" for physical, rank in ranks.items()}
    cases = ["$_\n0?=a=x0"]
    for i in range(n):
        if i in names:
            rank = ranks[i]
            define = f"=x{rank + 1}" if rank + 1 < len(essential) else ""
            # A buffer is fresh zero: its read also defines the next buffer.
            cases.append(f"${names[i]}\n0?,{define}")
        else:
            cases.append("$_\n0?,\n!,")
    count = len(nodes)

    def address(node: int) -> int:
        # Reverse post-order puts the root immediately after the last read.
        return n + count + 2 + node if node < 2 else n + count + 3 - node

    for depth, zero, one in reversed(nodes):
        cases.append(
            f"$x{depth}\n48?'" + str(address(zero)) + "\n!'" + str(address(one))
        )
    end = n + count + 4
    cases += [f"$a\n0?@'{end}", "$a\n0?+1@", "$_\n-1?+0"]
    return "\n".join(cases) + "\n"


def switchcase_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return switchcase(request.table)
