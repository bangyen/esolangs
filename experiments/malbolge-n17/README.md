# Malbolge 17-input experiments

## Exact truth table

`fixture-a.mb` reads 17 ASCII bits, most significant first, prints the
corresponding digit from `fixture-a.bits` and halts. All 131,072 inputs
matched the reference table from reset. Row `r` is bit `7 - r % 8` of
byte `r // 8`. For example, rows 0 and 1 print `1` and `0`.

```sh
printf 00000000000000000 | uv run esolangs run Malbolge experiments/malbolge-n17/fixture-a.mb
```

## Marker prototype

`marker.mb` reads 17 ASCII bits, most significant first. An input ending
in `10` selects the adjacent marker. The other three endings select the
original marker. The program reads that marker at instruction 38,575 and
halts at 38,576 with empty output.

This is fixture A of the marker experiment. All 131,072 inputs selected
the expected address from reset. The 184-instruction pointer walk would
need to fit into 74 instructions to use it in the full decoder.

Run this trace from the repository root to see the two addresses for
inputs that share their first 15 bits.

```sh
uv run python - <<'PY'
from pathlib import Path

from esolangs.languages.malbolge.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

source = Path("experiments/malbolge-n17/marker.mb").read_text(encoding="ascii")
for row, expected in [(61472, 51031), (61474, 51032)]:
    io = ScriptedIO(f"{row:017b}")
    machine = _Machine(source, io)
    while machine.ip != 38575 and not machine.halted:
        machine.step()
    assert machine.ip == 38575 and machine.state[2] == expected
    print(row, machine.state[2])
    machine.step()
    assert machine.ip == 38576
    machine.step()
    assert machine.halted and io.reads == 17 and not io.past_end
    assert io.getvalue() == ""
PY
```
