# ArrowQueue boolean generator

`arrowqueue(t)` is total for every arity: after instantiation, it halts iff
the selected table bit is `0` and cycles iff it is `1`. Each lemma below is
checked executably by `scripts/arrowqueue_lemmas.py`, which `just test` and
CI both run (0.8s).

The construction has three invariant-preserving parts:

- The header has `4n + 1` rows and queues input bits most-significant first.
- The middle appends the four directions expected by a looping leaf.
- The tree routes one queued bit per level. Its subtrees occupy disjoint rows;
  the corridor to the right of each subtree is blank.

A zero leaf exits the grid. A one leaf drains remaining input bits, then enters
a direction ring in its only valid rightward entry state, which repeats exactly.
The proof is structural, not a table sweep; exhaustive coverage currently ends
at four inputs because five would require (2**32) tables.
