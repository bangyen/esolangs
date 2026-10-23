# Boolfuck's gate route fits the tree's workspace

The ledger bounds Boolfuck's workspace with the term
$\max(12, \mathrm{bl}(2n-3)+11)$ (the tree prints from cell $2n-3$: 38 > 37
bits at $n=4$ under the old $\mathrm{bl}(2n-2)+10$). This shows the AND/XOR
gate route (`normal_gates`) stays within the tighter
$\mathrm{bl}(L-1) + \max(12, \mathrm{bl}(2n-2)+10) + n + \sum_{i<n}\mathrm{bl}(i)
+ \mathrm{bl}(2n) + \mathrm{bl}(n)$ bits for $n \ge 4$; it is admitted from $n=6$.

Workspace is the peak bits of three snapshot parts: the control state, the
set of 1-cells on the tape, and input progress. A cell $c$ costs
$w(c)=\mathrm{bl}(|c|)$, at least 1, plus 1 if negative, so $w(-1)=2$.

## Tape

Input $i$ is read onto cell $2i$, its flag is cell $2i+1$, the result $R$ is
cell $2n$, scratch is cell $-1$. Since $w(2i)=\mathrm{bl}(i)+1$ for $i \ge 1$
and $w(0)=1$, the ledger's tape terms are
$B = \sum_{i<n} w(2i) + w(2n)$: every input cell and $R$ set at once.

- **Header.** Reads set only input cells and scratch: at most
  $\sum_{i<n} w(2i) + 2 \le B$, since $w(2n) \ge 2$.
- **Prefix**, levels $i < n-2$. A fork sets flag $2i+1$, then `[+` on the
  bit clears it; the one-arm clears the flag on entry and the zero-arm's
  `[+` clears it too. An equal-halves level clears its bit. At level $i$,
  then, bits and flags below $i$ are 0, $R$ is 0, and the only cell beyond
  the input cells is flag $2i+1$: $w(2i+1) \le w(2n)$, so the total is
  within $B$.
- **Gate phase.** Below depth $n-2$ every tested bit and flag is 0. A gate
  leaf touches only $x=2n-4$, $y=2n-2$, $R$ and one pending flag
  $f \in \{2n-3, 2n-1\}$; its tail clears $f$, then $x$ and $y$, before the
  printer toggles the carrier $2n-3$. The peak is at most
  $w(2n-4)+w(2n-2)+w(2n)+w(2n-1)$, within $B$ exactly when
  $w(2n-1) \le \sum_{j \le n-3} w(2j)$: false at $n=3$ ($3 > 1$), true at
  $n=4$ ($3 \le 3$) and after, since the right side gains at least
  $\mathrm{bl}(2n-4)+1$ per input while the left gains at most 1.
- **Constant exits** clear $x$ and $y$ before setting $R$.

## State and input progress

The pointer stays in $[-1, 2n]$, the tree route's range. Reads happen only
in the header; prints only from $R$ or the carrier after every byte is
drained, as at the tree's leaves. The program counter's
$\mathrm{bl}(L-1)$ uses the emitted length. So these parts take the
configurations the tree route takes.

## Measurement

Every row of every gate-route program over 16 tables an arity, $n=4..9$,
runs to the right answer; the gate-phase peak equals
$w(2n-4)+w(2n-2)+w(2n)+w(2n-1)$ at every $n$, and the tape peak stays within
$B$ (13 of 13 at $n=4$, 27 of 30 at $n=8$).
`tests/proofs/test_workspace_formulas.py` checks the full bound at
$n=3, 6, 7, 8$.
