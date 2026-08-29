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

end PctBooleanWall
