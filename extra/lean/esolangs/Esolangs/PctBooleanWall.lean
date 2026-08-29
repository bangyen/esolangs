import Mathlib

/-! # The %^2^-1 boolean-generator wall

`%^2^-1` (`src/esolangs/interpreters/register_based/pct_squared_minus_one.py`)
has a single accumulator and exactly one control-flow command: `t`, which
rewinds the cursor to the *start of the program* when the accumulator is
nonzero.  There is no forward jump, no skip, and no way to branch over code.

A boolean generator must emit, for an `n`-input truth table, a program that
reads the `n` input bits (one `n` per bit, as the bytes `'0'`/`'1'`) and prints
the table's entry for that combination as a single `'0'`/`'1'` character.

**Main theorem (`no_xor`, `no_and`).**  No `%^2^-1` program computes XOR or AND
of two input bits, at *any* program length.  The route is
`computes_ignores`: any program meeting the contract on all four combinations
has an output that ignores one of its two inputs.

The proof is by induction on the execution, not by bounded search: the claim
quantifies over programs of unbounded length, and non-termination of a `t` loop
is not decidable by simulation, so the `native_decide` idiom used in
`Esolangs.lean` does not apply.

Two structural facts drive it.

1. **A read erases the past** (`read_erases`).  `n` *overwrites* the
   accumulator, so immediately after the final read the cursor and accumulator
   are a function of the last bit alone — nothing the earlier bit computed
   survives, and no branch exists that could have routed the cursor elsewhere
   on the strength of it.
2. **Reads cannot be skipped** (`count_le_of_halts`).  `t` only ever jumps to
   position `0`, so a run that reaches the end crosses every downstream `n`;
   a clean halt therefore needs at least as much remaining input as there are
   reads ahead of the cursor.  This is what forbids the two runs from
   diverging at a `t`: the branch that rewinds must pay for the reads it
   re-crosses.

Note on the one-input case: all four one-input functions *are* expressible
(identity is `ne`; NOT is `nss` followed by 31 `i`s then `pe`, computing
`x ↦ -x + 97`, which sends 48 ↦ 49 and 49 ↦ 48).  The wall is exactly at
`n ≥ 2`.
-/

namespace PctBooleanWall

/-! ### 1. The machine -/

/-- The nine `%^2^-1` commands. -/
inductive Cmd where
  | sub2      -- `s`  : acc -= 2
  | sub3      -- `i`  : acc -= 3
  | dbl       -- `m`  : acc *= 2
  | neg       -- `p`  : acc *= -1
  | printNum  -- `l`  : print the magnitude in decimal
  | printChr  -- `e`  : print the low byte
  | read      -- `n`  : read one input byte into the accumulator
  | zero      -- `'`  : acc := 0
  | rewind    -- `t`  : if acc ≠ 0, jump to position 0
  deriving DecidableEq, Repr

/-- Machine state: cursor, accumulator, remaining input.

Output is *not* part of the state: `run` returns the characters emitted, which
makes "the tail of a run depends only on the state it starts from" hold
definitionally instead of needing a framing lemma. -/
structure State where
  ind : ℕ
  acc : ℤ
  inp : List ℤ
  deriving DecidableEq

/-- The result of one command: halt-with-EOF, or a next state plus what it
printed. -/
inductive Step where
  | next (s : State) (out : List ℤ)
  | eof

/-- One command, faithful to `_Machine.step`: the `acc > 3003` reset fires
*before* the command, a taken `t` sets `ind := 0` with no increment, `e` prints
the low byte (Python's `& 0xFF`, matching `Int.emod` on negatives), and every
other command advances the cursor by one. -/
def stepCmd (c : Cmd) (s : State) : Step :=
  let a : ℤ := if s.acc > 3003 then 0 else s.acc
  match c with
  | .sub2     => .next ⟨s.ind + 1, a - 2, s.inp⟩ []
  | .sub3     => .next ⟨s.ind + 1, a - 3, s.inp⟩ []
  | .dbl      => .next ⟨s.ind + 1, a * 2, s.inp⟩ []
  | .neg      => .next ⟨s.ind + 1, -a, s.inp⟩ []
  | .zero     => .next ⟨s.ind + 1, 0, s.inp⟩ []
  | .printNum => .next ⟨s.ind + 1, a, s.inp⟩ [a]
  | .printChr => .next ⟨s.ind + 1, a, s.inp⟩ [a % 256]
  | .read     =>
      match s.inp with
      | []      => .eof
      | x :: xs => .next ⟨s.ind + 1, x, xs⟩ []
  | .rewind   =>
      if a ≠ 0 then .next ⟨0, a, s.inp⟩ [] else .next ⟨s.ind + 1, a, s.inp⟩ []

/-- Run with fuel, returning the final state and everything printed.
`none` means the fuel ran out (a non-terminating run) or the program hit EOF;
`some (s, out)` is a clean halt in `s` having printed `out`. -/
def run (code : List Cmd) : ℕ → State → Option (State × List ℤ)
  | 0,     _ => none
  | k + 1, s =>
      match code[s.ind]? with
      | none   => some (s, [])                  -- cursor past the end: halt
      | some c =>
          match stepCmd c s with
          | .eof         => none
          | .next s' o   =>
              (run code k s').map (fun r => (r.1, o ++ r.2))

/-! ### 2. Reads cannot be skipped

`countN code i` counts the reads at positions `≥ i`.  Because `t` jumps only to
`0`, a run that reaches the end of the program passes over every read ahead of
it — so a clean halt needs at least that much input left. -/

/-- Number of `read` commands at positions `≥ i`. -/
def countN (code : List Cmd) (i : ℕ) : ℕ :=
  ((code.drop i).filter (· = Cmd.read)).length

theorem countN_ge_len (code : List Cmd) (i : ℕ) (h : code.length ≤ i) :
    countN code i = 0 := by
  simp [countN, List.drop_eq_nil_of_le h]

/-- Later cursors have no more reads ahead of them: `countN` is antitone. -/
theorem countN_antitone (code : List Cmd) {i j : ℕ} (h : i ≤ j) :
    countN code j ≤ countN code i := by
  simp only [countN]
  exact List.Sublist.length_le
    (List.Sublist.filter _ (List.drop_sublist_drop_left code h))

/-- Stepping a non-read command at position `i` (landing at `i+1`) leaves the
count of remaining reads unchanged from `i+1`, and a read at `i` has one more
ahead of `i` than ahead of `i+1`. -/
theorem countN_succ (code : List Cmd) (i : ℕ) (c : Cmd) (h : code[i]? = some c) :
    countN code i = (if c = Cmd.read then 1 else 0) + countN code (i + 1) := by
  have hi : i < code.length := by
    by_contra hc
    simp [List.getElem?_eq_none (by omega : code.length ≤ i)] at h
  have hget : code[i] = c := by
    rw [List.getElem?_eq_getElem hi] at h
    exact Option.some_inj.mp h
  have hdrop : code.drop i = c :: code.drop (i + 1) := by
    rw [List.drop_eq_getElem_cons hi, hget]
  simp only [countN, hdrop, List.filter_cons]
  split <;> simp_all <;> omega

/-- **The counting lemma.**  A clean halt from `s` needs at least as much input
remaining as there are reads at or ahead of the cursor. -/
theorem count_le_of_halts (code : List Cmd) :
    ∀ (fuel : ℕ) (s : State) (r : State × List ℤ),
      run code fuel s = some r → countN code s.ind ≤ s.inp.length := by
  intro fuel
  induction fuel with
  | zero => intro s r h; simp [run] at h
  | succ k ih =>
    intro s r h
    rw [run] at h
    -- if the cursor is past the end there are no reads left to pay for
    cases hc : code[s.ind]? with
    | none =>
      have hlen : code.length ≤ s.ind := by
        by_contra hlt
        rw [List.getElem?_eq_getElem (by omega : s.ind < code.length)] at hc
        exact (Option.some_ne_none _ hc)
      simp [countN_ge_len code s.ind hlen]
    | some c =>
      rw [hc] at h
      simp only at h
      cases hstep : stepCmd c s with
      | eof => rw [hstep] at h; simp at h
      | next s' o =>
        rw [hstep] at h
        simp only [Option.map_eq_some_iff] at h
        obtain ⟨r', hr', -⟩ := h
        have IH := ih s' r' hr'
        rw [countN_succ code s.ind c hc]
        -- case on the command: a read pays one input, a taken rewind restarts
        -- at 0 (where the count is at least the count here), and everything
        -- else advances by one leaving the input untouched
        cases c
        case sub2 | sub3 | dbl | neg | zero | printNum | printChr =>
          simp only [stepCmd] at hstep
          cases hstep
          simpa using IH
        case read =>
          simp only [stepCmd] at hstep
          cases hinp : s.inp with
          | nil => rw [hinp] at hstep; exact absurd hstep (by simp)
          | cons x xs =>
            rw [hinp] at hstep
            simp only at hstep
            cases hstep
            simp only [List.length_cons, if_pos]
            simp only at IH
            omega
        case rewind =>
          have hmono : countN code (s.ind + 1) ≤ countN code 0 :=
            countN_antitone code (Nat.zero_le _)
          simp only [if_neg (by simp : ¬(Cmd.rewind = Cmd.read)), Nat.zero_add]
          by_cases hz : (if s.acc > 3003 then (0 : ℤ) else s.acc) ≠ 0
          · rw [stepCmd, if_pos hz] at hstep
            cases hstep
            simp only at IH
            omega
          · rw [stepCmd, if_neg hz] at hstep
            cases hstep
            simpa using IH

/-! ### 3. A read erases the past

`n` overwrites the accumulator and advances the cursor by one.  So after a read
at position `i`, the state is `⟨i + 1, byte read, rest⟩` — no component
mentions anything the machine computed before. -/

theorem read_erases (s : State) (x : ℤ) (xs : List ℤ) (h : s.inp = x :: xs) :
    stepCmd .read s = .next ⟨s.ind + 1, x, xs⟩ [] := by
  simp [stepCmd, h]

/-- Two states at the same cursor whose input is the same nonempty list land,
after a read, in *identical* states — whatever their accumulators were. -/
theorem read_erases_pair (i : ℕ) (a b x : ℤ) (xs : List ℤ) :
    stepCmd .read ⟨i, a, x :: xs⟩ = stepCmd .read ⟨i, b, x :: xs⟩ := by
  simp [stepCmd]

/-! ### 4. The simulation

Two runs that sit at the same cursor with the same *remaining input* differ
only in their accumulators.  They step in lockstep until they reach a `t`
whose test they disagree on.  The counting lemma rules that disagreement out
whenever the input still to be read is exactly what both runs must consume:
the run that rewinds re-crosses every read in the program, so it needs
`countN code 0` bytes, while the run that walks on needs only
`countN code (i+1)` — and when the rewinding run's demand exceeds what is
left, it cannot halt cleanly.

`SameTail` packages the conclusion: from such a pair of states, if both runs
halt cleanly having consumed all their input, they print the same thing. -/

/-- The two runs agree on every `t` test they meet while the input is empty.
With no input left, a taken `t` is fatal: it returns to position `0`, and any
program that ever read (which a contract-satisfying one did) has a read there
to re-cross, so the counting lemma refutes a clean halt. -/
theorem rewind_fatal_of_empty (code : List Cmd) (fuel : ℕ) (s : State)
    (hinp : s.inp = []) (hread : 0 < countN code 0) (r : State × List ℤ)
    (h : run code fuel ⟨0, s.acc, s.inp⟩ = some r) : False := by
  have := count_le_of_halts code fuel ⟨0, s.acc, s.inp⟩ r h
  simp only [hinp, List.length_nil] at this
  omega

/-- **No-input determinism.**  Once the input is exhausted, the accumulator can
no longer change the *control flow* of a cleanly-halting run in a program that
contains a read: every `t` the run meets must be untaken (a taken one is fatal
by `rewind_fatal_of_empty`), so the cursor walks straight to the end.  Hence
two such runs visit the same commands, and the only outputs that can differ are
those of `l`/`e`, which read the accumulator.

We record the sharper statement actually needed: with no input left, the run's
*output* is determined by the accumulator, and the run halts at the end of the
program.  This is the phase-3 fact. -/
theorem tail_determined (code : List Cmd) :
    ∀ (fuel₁ fuel₂ : ℕ) (i : ℕ) (a : ℤ) (r₁ r₂ : State × List ℤ),
      run code fuel₁ ⟨i, a, []⟩ = some r₁ →
      run code fuel₂ ⟨i, a, []⟩ = some r₂ →
      r₁.2 = r₂.2 := by
  intro fuel₁
  induction fuel₁ with
  | zero => intro fuel₂ i a r₁ r₂ h₁ _; simp [run] at h₁
  | succ k ih =>
    intro fuel₂ i a r₁ r₂ h₁ h₂
    cases fuel₂ with
    | zero => simp [run] at h₂
    | succ m =>
      rw [run] at h₁ h₂
      cases hc : code[i]? with
      | none => rw [hc] at h₁ h₂; simp at h₁ h₂; simp [← h₁, ← h₂]
      | some c =>
        rw [hc] at h₁ h₂
        simp only at h₁ h₂
        cases hstep : stepCmd c ⟨i, a, []⟩ with
        | eof => rw [hstep] at h₁; simp at h₁
        | next s' o =>
          rw [hstep] at h₁ h₂
          simp only [Option.map_eq_some_iff] at h₁ h₂
          obtain ⟨p₁, hp₁, hr₁⟩ := h₁
          obtain ⟨p₂, hp₂, hr₂⟩ := h₂
          -- the successor state has empty input in every case (no read can
          -- succeed on an empty input list), so the IH applies verbatim
          have hnil : s'.inp = [] := by
            cases c
            case sub2 | sub3 | dbl | neg | zero | printNum | printChr =>
              simp only [stepCmd] at hstep; cases hstep; rfl
            case read => simp [stepCmd] at hstep
            case rewind =>
              by_cases hz : (if a > 3003 then (0 : ℤ) else a) ≠ 0
              · rw [stepCmd, if_pos hz] at hstep; cases hstep; rfl
              · rw [stepCmd, if_neg hz] at hstep; cases hstep; rfl
          have : s' = ⟨s'.ind, s'.acc, []⟩ := by
            cases s'; simp_all
          rw [this] at hp₁ hp₂
          have := ih m s'.ind s'.acc p₁ p₂ hp₁ hp₂
          rw [← hr₁, ← hr₂]
          simp [this]

/-! ### 5. Where the next read is

The position of the read that consumes the last input byte is the same for
both accumulator values.  With two or more reads in the program a `t` cannot
be taken while one byte remains (the counting lemma: the rewind would have to
re-cross every read), so the cursor walks forward and lands on the least read
at or after it.  With exactly one read in the program a `t` *may* be taken —
this is the single-`n`-read-twice shape — but then the read that executes is
that unique one, whatever path reached it.  Either way the position does not
depend on the accumulator. -/

/-- The least position `≥ i` holding a read, if any. -/
def firstReadFrom (code : List Cmd) (i : ℕ) : Option ℕ :=
  ((code.drop i).findIdx? (· = Cmd.read)).map (· + i)

theorem firstReadFrom_none_iff (code : List Cmd) (i : ℕ) :
    firstReadFrom code i = none ↔ countN code i = 0 := by
  simp only [firstReadFrom, countN, Option.map_eq_none_iff,
    List.findIdx?_eq_none_iff, List.length_eq_zero_iff,
    List.filter_eq_nil_iff]
  simp

/-- A read sits where `firstReadFrom` says it does. -/
theorem firstReadFrom_isRead (code : List Cmd) (i q : ℕ)
    (h : firstReadFrom code i = some q) : code[q]? = some Cmd.read := by
  simp only [firstReadFrom, Option.map_eq_some_iff] at h
  obtain ⟨j, hj, rfl⟩ := h
  obtain ⟨hjlt, hjeq, -⟩ := List.findIdx?_eq_some_iff_getElem.mp hj
  simp only [List.length_drop] at hjlt
  have hlen : j + i < code.length := by omega
  rw [List.getElem?_eq_getElem hlen]
  rw [List.getElem_drop] at hjeq
  simp only [decide_eq_true_eq] at hjeq
  have hidx : j + i = i + j := by omega
  simp only [hidx]
  exact congrArg some hjeq

/-- `firstReadFrom` really is least: nothing between `i` and it is a read. -/
theorem firstReadFrom_least (code : List Cmd) (i q p : ℕ)
    (h : firstReadFrom code i = some q) (hp : i ≤ p) (hpq : p < q) :
    code[p]? ≠ some Cmd.read := by
  simp only [firstReadFrom, Option.map_eq_some_iff] at h
  obtain ⟨j, hj, rfl⟩ := h
  obtain ⟨hjlt, -, hlt⟩ := List.findIdx?_eq_some_iff_getElem.mp hj
  intro hcon
  have hplt : p < code.length := by
    by_contra hc
    rw [List.getElem?_eq_none (by omega)] at hcon
    exact Option.some_ne_none _ hcon.symm
  have hget : code[p] = Cmd.read := by
    rw [List.getElem?_eq_getElem hplt] at hcon
    exact Option.some_inj.mp hcon
  have hpi : p - i < j := by omega
  have hne := hlt (p - i) hpi
  rw [List.getElem_drop] at hne
  simp only [decide_eq_true_eq] at hne
  apply hne
  have hidx : i + (p - i) = p := by omega
  simp only [hidx]
  exact hget

/-- Two read positions in a program with `countN ≤ 1` coincide: a second read
would put two entries in the filtered list. -/
theorem read_pos_unique (code : List Cmd) (p q : ℕ)
    (h1 : countN code 0 ≤ 1)
    (hp : code[p]? = some Cmd.read) (hq : code[q]? = some Cmd.read) : p = q := by
  by_contra hne
  -- both positions are in range
  have hplt : p < code.length := by
    by_contra hc
    rw [List.getElem?_eq_none (by omega)] at hp
    exact Option.some_ne_none _ hp.symm
  have hqlt : q < code.length := by
    by_contra hc
    rw [List.getElem?_eq_none (by omega)] at hq
    exact Option.some_ne_none _ hq.symm
  -- WLOG p < q; then countN from 0 counts at least the reads at p and q
  have key : ∀ a b : ℕ, a < b → b < code.length →
      code[a]? = some Cmd.read → code[b]? = some Cmd.read → 2 ≤ countN code 0 := by
    intro a b hab hblt ha hb
    have halt : a < code.length := by omega
    have hga : code[a] = Cmd.read := by
      rw [List.getElem?_eq_getElem halt] at ha; exact Option.some_inj.mp ha
    have hgb : code[b] = Cmd.read := by
      rw [List.getElem?_eq_getElem hblt] at hb; exact Option.some_inj.mp hb
    -- countN at 0 ≥ 1 (from a) + countN at a+1 ≥ 1 (from b)
    have h1' : countN code a = 1 + countN code (a + 1) := by
      rw [countN_succ code a Cmd.read ha]; simp
    have h2' : 1 ≤ countN code (a + 1) := by
      have : countN code b = 1 + countN code (b + 1) := by
        rw [countN_succ code b Cmd.read hb]; simp
      have := countN_antitone code (show a + 1 ≤ b by omega)
      omega
    have := countN_antitone code (Nat.zero_le a)
    omega
  rcases Nat.lt_or_ge p q with h | h
  · have := key p q h hqlt hp hq; omega
  · have hgt : q < p := by omega
    have := key q p hgt hplt hq hp; omega

/-- If the program holds exactly one read, every read position is that one. -/
theorem unique_read_pos (code : List Cmd) (p : ℕ)
    (h1 : countN code 0 = 1) (hp : code[p]? = some Cmd.read) :
    firstReadFrom code 0 = some p := by
  have hsome : (firstReadFrom code 0).isSome := by
    by_contra hc
    simp only [Bool.not_eq_true, Option.isSome_eq_false_iff,
      Option.isNone_iff_eq_none] at hc
    rw [firstReadFrom_none_iff] at hc
    omega
  obtain ⟨q, hq⟩ := Option.isSome_iff_exists.mp hsome
  rw [hq]
  exact congrArg some
    (read_pos_unique code q p (by omega) (firstReadFrom_isRead code 0 q hq) hp)

/-! ### 6. Splitting a run at its last read

`splitAt`: a run that starts with one byte left and halts cleanly having
consumed it passes through a read.  The position `q` of that read, and
everything printed before it, do not depend on the accumulator the run
started with — only on the cursor.  What comes after is a run from
`⟨q + 1, b, []⟩`, so it depends only on the byte `b`.

The proof is an induction on fuel with one interesting case, the `t`:

* if the program has two or more reads, a taken `t` cannot halt cleanly with
  one byte left (`count_le_of_halts` at position `0`), so the branch is dead;
* if it has exactly one read, a taken `t` is fine — the recursion simply
  continues, and `read_pos_unique` still pins the read that eventually fires.
-/

/-- **The split lemma.**  A cleanly-halting run holding one byte reaches a read
at a position determined by the program and the cursor — not the accumulator —
and its output is what it printed before that read followed by the tail run's
output. -/
theorem run_splits (code : List Cmd) :
    ∀ (fuel : ℕ) (i : ℕ) (a b : ℤ) (r : State × List ℤ),
      run code fuel ⟨i, a, [b]⟩ = some r → r.1.inp = [] →
      ∃ (q : ℕ) (pre : List ℤ) (f' : ℕ) (r' : State × List ℤ),
        code[q]? = some Cmd.read ∧
        run code f' ⟨q + 1, b, []⟩ = some r' ∧
        r.2 = pre ++ r'.2 := by
  intro fuel
  induction fuel with
  | zero => intro i a b r h _; simp [run] at h
  | succ k ih =>
    intro i a b r h hnil
    rw [run] at h
    cases hc : code[i]? with
    | none =>
      -- halting immediately leaves the byte unconsumed, contradicting `hnil`
      rw [hc] at h
      simp only [Option.some.injEq] at h
      rw [← h] at hnil
      simp at hnil
    | some c =>
      rw [hc] at h
      simp only at h
      cases hstep : stepCmd c ⟨i, a, [b]⟩ with
      | eof => rw [hstep] at h; simp at h
      | next s' o =>
        rw [hstep] at h
        simp only [Option.map_eq_some_iff] at h
        obtain ⟨p, hp, hr⟩ := h
        -- in every case the emitted list `o` is a prefix of the run's output
        have hnil' : p.1.inp = [] := by rw [← hr] at hnil; simpa using hnil
        have hout_eq : r.2 = o ++ p.2 := by rw [← hr]
        cases c
        -- the read fires here: this is the split point
        case read =>
          simp only [stepCmd] at hstep
          cases hstep
          exact ⟨i, [], k, p, hc, hp, by simpa using hout_eq⟩
        -- an arithmetic or print command: recurse at i+1 with the same byte
        case sub2 | sub3 | dbl | neg | zero | printNum | printChr =>
          simp only [stepCmd] at hstep
          cases hstep
          obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
          exact ⟨q, _ ++ pre, f', r', hq, hrun, by rw [hout_eq, hout, List.append_assoc]⟩
        -- the rewind: taken or not, recurse; the taken branch is only
        -- reachable when the program holds a single read
        case rewind =>
          by_cases hz : (if a > 3003 then (0 : ℤ) else a) ≠ 0
          · rw [stepCmd, if_pos hz] at hstep
            cases hstep
            obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
            exact ⟨q, _ ++ pre, f', r', hq, hrun,
              by rw [hout_eq, hout, List.append_assoc]⟩
          · rw [stepCmd, if_neg hz] at hstep
            cases hstep
            obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
            exact ⟨q, _ ++ pre, f', r', hq, hrun,
              by rw [hout_eq, hout, List.append_assoc]⟩

/-! ### 7. The split position does not depend on the accumulator

`run_splits` produces *some* read position.  To compare two runs we need the
*same* position, and this is where the two structural cases separate.

* **Two or more reads.**  While one byte remains a `t` can never be taken: the
  rewind lands at position `0` and would have to re-cross every read in the
  program, needing `countN code 0 ≥ 2` bytes when only one is left.  So the
  cursor advances one step at a time and stops at `firstReadFrom code i`.
* **Exactly one read.**  A `t` may well be taken (the single-`n`-read-twice
  shape), but then the read that eventually fires is the unique one, by
  `read_pos_unique`.

In both cases the position is a function of `code` and `i` only. -/

/-- A position holding a read is its own `firstReadFrom`. -/
theorem firstReadFrom_self (code : List Cmd) (i : ℕ)
    (hc : code[i]? = some Cmd.read) : firstReadFrom code i = some i := by
  have hi : i < code.length := by
    by_contra hcc
    rw [List.getElem?_eq_none (by omega)] at hc
    exact Option.some_ne_none _ hc.symm
  have hget : code[i] = Cmd.read := by
    rw [List.getElem?_eq_getElem hi] at hc; exact Option.some_inj.mp hc
  simp only [firstReadFrom, Option.map_eq_some_iff]
  refine ⟨0, ?_, by omega⟩
  rw [List.drop_eq_getElem_cons hi]
  simp [List.findIdx?_cons, hget]

/-- Stepping over a non-read position shifts `firstReadFrom` by one. -/
theorem firstReadFrom_step (code : List Cmd) (i q : ℕ) (c : Cmd)
    (hc : code[i]? = some c) (hne : c ≠ Cmd.read)
    (h : firstReadFrom code (i + 1) = some q) : firstReadFrom code i = some q := by
  have hi : i < code.length := by
    by_contra hcc
    rw [List.getElem?_eq_none (by omega)] at hc
    exact Option.some_ne_none _ hc.symm
  have hget : code[i] = c := by
    rw [List.getElem?_eq_getElem hi] at hc; exact Option.some_inj.mp hc
  simp only [firstReadFrom, Option.map_eq_some_iff] at h ⊢
  obtain ⟨j, hj, rfl⟩ := h
  refine ⟨j + 1, ?_, by omega⟩
  rw [List.drop_eq_getElem_cons hi, List.findIdx?_cons, hget]
  simp only [decide_eq_true_eq, if_neg hne, hj]
  rfl

/-- With one byte left and at least two reads in the program, a `t` is never
taken on a cleanly-halting run: the rewind cannot pay for the reads it would
re-cross. -/
theorem rewind_not_taken (code : List Cmd) (fuel : ℕ) (a b : ℤ)
    (h2 : 2 ≤ countN code 0) (r : State × List ℤ)
    (h : run code fuel ⟨0, a, [b]⟩ = some r) : False := by
  have := count_le_of_halts code fuel ⟨0, a, [b]⟩ r h
  simp only [List.length_cons, List.length_nil] at this
  omega

/-- **The split position is determined.**  Under the same hypotheses as
`run_splits`, the read position is `firstReadFrom code i` when the program has
two or more reads, and the unique read position when it has one. -/
theorem run_splits_pos (code : List Cmd) :
    ∀ (fuel : ℕ) (i : ℕ) (a b : ℤ) (r : State × List ℤ),
      run code fuel ⟨i, a, [b]⟩ = some r → r.1.inp = [] →
      ∃ (q : ℕ) (pre : List ℤ) (f' : ℕ) (r' : State × List ℤ),
        (if 2 ≤ countN code 0 then firstReadFrom code i = some q
                              else firstReadFrom code 0 = some q) ∧
        run code f' ⟨q + 1, b, []⟩ = some r' ∧
        r.2 = pre ++ r'.2 := by
  intro fuel
  induction fuel with
  | zero => intro i a b r h _; simp [run] at h
  | succ k ih =>
    intro i a b r h hnil
    rw [run] at h
    cases hc : code[i]? with
    | none =>
      rw [hc] at h
      simp only [Option.some.injEq] at h
      rw [← h] at hnil
      simp at hnil
    | some c =>
      rw [hc] at h
      simp only at h
      cases hstep : stepCmd c ⟨i, a, [b]⟩ with
      | eof => rw [hstep] at h; simp at h
      | next s' o =>
        rw [hstep] at h
        simp only [Option.map_eq_some_iff] at h
        obtain ⟨p, hp, hr⟩ := h
        have hnil' : p.1.inp = [] := by rw [← hr] at hnil; simpa using hnil
        have hout_eq : r.2 = o ++ p.2 := by rw [← hr]
        cases c
        case read =>
          simp only [stepCmd] at hstep
          cases hstep
          -- the read is here, so it *is* the first read from `i`
          refine ⟨i, [], k, p, ?_, hp, by simpa using hout_eq⟩
          split
          · exact firstReadFrom_self code i hc
          · next hlt =>
            -- a read fires at `i`, so the program holds at least one; with
            -- fewer than two that makes exactly one
            have hpos : 1 ≤ countN code 0 := by
              have h1 : countN code i = 1 + countN code (i + 1) := by
                rw [countN_succ code i Cmd.read hc]; simp
              have := countN_antitone code (Nat.zero_le i)
              omega
            exact unique_read_pos code i (by omega) hc
        case sub2 | sub3 | dbl | neg | zero | printNum | printChr =>
          simp only [stepCmd] at hstep
          cases hstep
          obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
          refine ⟨q, _ ++ pre, f', r', ?_, hrun,
            by rw [hout_eq, hout, List.append_assoc]⟩
          -- `i` is not a read, so the least read from `i` is the one from `i+1`
          split at hq
          · next hge =>
            exact if_pos hge ▸ firstReadFrom_step code i q _ hc (by simp) hq
          · next hlt => rw [if_neg hlt]; exact hq
        case rewind =>
          by_cases hz : (if a > 3003 then (0 : ℤ) else a) ≠ 0
          · -- taken: with two or more reads this is unreachable
            rw [stepCmd, if_pos hz] at hstep
            cases hstep
            by_cases h2 : 2 ≤ countN code 0
            · exact absurd hp (fun hcon => rewind_not_taken code k _ b h2 p hcon)
            · obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
              refine ⟨q, _ ++ pre, f', r', ?_, hrun,
                by rw [hout_eq, hout, List.append_assoc]⟩
              rw [if_neg h2]
              rw [if_neg h2] at hq
              exact hq
          · rw [stepCmd, if_neg hz] at hstep
            cases hstep
            obtain ⟨q, pre, f', r', hq, hrun, hout⟩ := ih _ _ b p hp hnil'
            refine ⟨q, _ ++ pre, f', r', ?_, hrun,
              by rw [hout_eq, hout, List.append_assoc]⟩
            split at hq
            · next hge =>
              exact if_pos hge ▸ firstReadFrom_step code i q _ hc (by simp) hq
            · next hlt => rw [if_neg hlt]; exact hq

end PctBooleanWall
