# Generate, run, and debug XOR

XOR's two-input truth table is `0110`: rows `00`, `01`, `10`, `11` produce
`0`, `1`, `1`, `0`. The same table shows three different language interfaces.

## A stdin-driven program

```python
import esolangs

table = "0110"
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin)
assert esolangs.read_answer("brainfuck", output) == "1"
assert esolangs.verify("brainfuck", table)
```

`encode_inputs` matters: input alphabets and line shapes differ by language.
`verify` executes all four rows, rather than trusting the generated text.

## An input-embedding template

Some languages put inputs into their source. `generate` then returns a template
and `instantiate` fills one row:

```python
template = esolangs.generate("Minifuck", table)
program = esolangs.instantiate("Minifuck", template, [1, 0])
output = esolangs.run("Minifuck", program)
assert esolangs.read_answer("Minifuck", output) == "1"
```

`esolangs.describe(name)["parameterized"]` identifies this interface.

## A raster program

Piet source is an image rather than text:

```python
raster = esolangs.generate("Piet", table)
assert isinstance(raster, esolangs.Raster)
raster.to_png()  # bytes suitable for writing to a .png file
assert esolangs.verify("Piet", table)
```

## Inspect execution

The VM exposes a common step interface while retaining language-shaped state:

```python
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
vm = esolangs.make_vm("brainfuck", program, stdin)
for _ in range(20):
    if vm.halted:
        break
    vm.step()
print(vm.ip, vm.memory, vm.output)
```

For an interactive view, save the source and run:

```console
$ printf '0\n1\n' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
```

Use `just benchmark brainfuck 0110 --row 1` when changing a generator. Its
JSON reports source units, best and median generation time, and deterministic
command count. Treat time as diagnostic; size and command counts are stable
regression evidence.
