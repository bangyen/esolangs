# ArrowQueue boolean generator

`arrowqueue(t)` is total for every arity: after instantiation, it halts iff the selected table bit is `0` and cycles iff it is `1`.

The construction has three invariant-preserving parts:.

- The header has `4n + 1` rows and queues input bits most-significant first.
- The middle appends the four directions expected by a looping leaf.
- The tree routes one queued bit per level.

A zero leaf exits the grid.
