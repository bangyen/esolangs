import Mathlib

/-! Correctness of the Factor encoder

Factor is brainfuck re-encoded as the prime factorization of a single
integer: each distinct prime factor's residue mod 11 selects a brainfuck
instruction and its exponent is the run length
(``src/esolangs/interpreters/tape_based/factor.py``,
``src/esolangs/tools/generators/tape.py::_factor_encode``).

This file proves the two halves of the round-trip ``decode (encode code) =
code``:

1. **totality**: the encoder's search for a prime with a given residue mod 11
   always terminates, because each residue 1..8 is coprime to 11 and
   Dirichlet's theorem (``Nat.forall_exists_prime_gt_and_modEq``) gives a
   prime in every reduced residue class above any bound;
2. **the round-trip**: decoding the prime factorization of the encoded
   number recovers the run-length encoding, hence the original program.

The interpreter is modeled as a run-length encoding: a program is a list of
``(Cmd, exponent)`` runs of identical instructions, the encoder hands each
run the next prime congruent to the command's residue mod 11 and multiplies
by ``prime ^ runLength``, and the decoder reads the distinct prime factors
ascending (their residues identify the commands, their exponents the run
lengths).
-/

namespace FactorCorrect

/-! ## 1. Commands and their residues -/

/-- The eight brainfuck instructions (``]`` only as a marker; the interpreter
runs them through the brainfuck semantics). -/
inductive Cmd where
  | gt | lt | plus | minus | dot | comma | lbrack | rbrack
deriving DecidableEq, Repr

/-- The residue mod 11 assigned to each command. -/
def res : Cmd → ℕ
  | Cmd.gt => 1
  | Cmd.lt => 2
  | Cmd.plus => 3
  | Cmd.minus => 4
  | Cmd.dot => 5
  | Cmd.comma => 6
  | Cmd.lbrack => 7
  | Cmd.rbrack => 8

/-- Residues are valid (nonzero and below 11). -/
lemma res_pos (c : Cmd) : 0 < res c := by
  cases c <;> simp [res]

lemma res_lt_11 (c : Cmd) : res c < 11 := by
  cases c <;> simp [res]

/-- Every residue is coprime to 11 (11 is prime and the residue is in 1..8). -/
lemma res_coprime_11 (c : Cmd) : (res c).Coprime 11 := by
  rw [Nat.coprime_comm]
  have hpr : Nat.Prime 11 := by norm_num
  rw [Nat.Prime.coprime_iff_not_dvd hpr]
  intro hdiv
  have hle : 11 ≤ res c := Nat.le_of_dvd (res_pos c) hdiv
  have hlt : res c < 11 := res_lt_11 c
  omega

/-- The residue map is injective: distinct commands have distinct residues. -/
lemma res_injective : Function.Injective res := by
  intro a b h
  cases a <;> cases b <;> simp [res] at h ⊢

/-- A valid residue: an integer in 1..8. -/
def ValidResidue (r : ℕ) : Prop := 1 ≤ r ∧ r ≤ 8

/-- The command whose residue is ``r`` (defaults to ``gt`` outside 1..8). -/
noncomputable def cmdOfRes (r : ℕ) : Cmd :=
  if r = 1 then Cmd.gt
  else if r = 2 then Cmd.lt
  else if r = 3 then Cmd.plus
  else if r = 4 then Cmd.minus
  else if r = 5 then Cmd.dot
  else if r = 6 then Cmd.comma
  else if r = 7 then Cmd.lbrack
  else Cmd.rbrack

/-- ``cmdOfRes`` inverts ``res`` on valid residues. -/
lemma res_cmdOfRes (r : ℕ) (hr : ValidResidue r) : res (cmdOfRes r) = r := by
  unfold cmdOfRes
  rcases hr with ⟨h1, h8⟩
  interval_cases r <;> simp [res]

/-- ``cmdOfRes`` is the inverse of ``res`` (which is injective). -/
lemma cmdOfRes_res (c : Cmd) : cmdOfRes (res c) = c := by
  cases c <;> simp [cmdOfRes, res]

/-! ## 2. Run-length encoding -/

/-- Count the leading run of ``c`` in ``cs``: returns ``(length, rest)`` where
``replicate length c ++ rest = cs`` and ``rest`` does not start with ``c``. -/
def splitRun : Cmd → List Cmd → ℕ × List Cmd
  | _, [] => (0, [])
  | c, x :: xs =>
      if x = c then
        let (n, rest) := splitRun c xs
        (n + 1, rest)
      else
        (0, x :: xs)

/-- ``splitRun`` splits off a run of the head command: the leading copies
recombined with the rest recover the original list. -/
lemma splitRun_spec (c : Cmd) (cs : List Cmd) :
    List.replicate (splitRun c cs).1 c ++ (splitRun c cs).2 = cs := by
  induction cs with
  | nil => simp [splitRun]
  | cons x xs ih =>
      by_cases hx : x = c
      · subst x
        simp [splitRun]
        rw [List.replicate_succ]
        rw [List.cons_append]
        exact congrArg (fun t => c :: t) ih
      · simp [splitRun, hx]

/-- ``splitRun`` shrinks the list: the remainder is no longer than the input. -/
lemma splitRun_rest_length (c : Cmd) (cs : List Cmd) :
    (splitRun c cs).2.length ≤ cs.length := by
  induction cs with
  | nil => simp [splitRun]
  | cons x xs ih =>
      by_cases hx : x = c
      · subst x
        simp [splitRun]
        omega
      · simp [splitRun, hx]

def runGroup : List Cmd → List (Cmd × ℕ)
  | [] => []
  | c :: cs =>
      (c, (splitRun c cs).1 + 1) :: runGroup (splitRun c cs).2
termination_by cs => cs.length
decreasing_by
  simp_wf
  have hle := splitRun_rest_length c cs
  omega

/-- Expand a run list back into a flat program. -/
def expand : List (Cmd × ℕ) → List Cmd
  | [] => []
  | (c, n) :: rs => List.replicate n c ++ expand rs

/-- Expanding the run decomposition recovers the original program. -/
lemma expand_runGroup : ∀ cs : List Cmd, expand (runGroup cs) = cs := by
  have hwf : WellFounded fun a b : List Cmd => a.length < b.length := by
    exact InvImage.wf (fun l : List Cmd => l.length) Nat.lt_wfRel.wf
  refine (WellFounded.fix hwf (fun cs ih => ?_))
  cases cs with
  | nil => simp [runGroup, expand]
  | cons c cs' =>
      simp [runGroup, expand]
      have hsplit := splitRun_spec c cs'
      have hrest_len : (splitRun c cs').2.length < (c :: cs').length := by
        rw [List.length_cons]
        have hle := splitRun_rest_length c cs'
        omega
      have hrest : expand (runGroup (splitRun c cs').2) = (splitRun c cs').2 :=
        ih (splitRun c cs').2 hrest_len
      have hgoal :
          List.replicate ((splitRun c cs').1 + 1) c ++ expand (runGroup (splitRun c cs').2)
            = c :: cs' := by
        rw [hrest]
        rw [List.replicate_succ]
        rw [List.cons_append]
        exact congrArg (fun t => c :: t) hsplit
      exact hgoal

/-! ## 3. The encoder and its totality -/

/-- Every command's residue is a valid residue. -/
lemma validResidue_res (c : Cmd) : ValidResidue (res c) := by
  constructor <;> (cases c <;> simp [res])

/-- **Totality**: for every valid residue and every bound, there is a prime
above the bound congruent to the residue mod 11.  This is Dirichlet's
theorem on primes in arithmetic progressions. -/
lemma exists_prime_ge_with_res (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) :
    ∃ p ≥ candidate, p.Prime ∧ p % 11 = r := by
  rcases hr with ⟨h1, h8⟩
  have hcop : r.Coprime 11 := by
    have hpr : Nat.Prime 11 := by norm_num
    rw [Nat.coprime_comm, Nat.Prime.coprime_iff_not_dvd hpr]
    intro hdiv
    have hle : 11 ≤ r := Nat.le_of_dvd (by omega) hdiv
    omega
  obtain ⟨p, hp_gt, hpp, hmod⟩ :=
    Nat.forall_exists_prime_gt_and_modEq candidate (q := 11) (a := r) (by norm_num) hcop
  refine ⟨p, hp_gt.le, hpp, ?_⟩
  have hr11 : r < 11 := by omega
  change p % 11 = r % 11 at hmod
  simpa [Nat.mod_eq_of_lt hr11] using hmod

/-- The least prime at or above ``candidate`` congruent to ``r`` mod 11. -/
noncomputable def nextPrimeWithRes (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) : ℕ :=
  Nat.find (exists_prime_ge_with_res candidate r hr)

/-- ``nextPrimeWithRes`` returns a prime at or above the candidate with the
given residue. -/
lemma nextPrimeWithRes_spec (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) :
    candidate ≤ nextPrimeWithRes candidate r hr
      ∧ (nextPrimeWithRes candidate r hr).Prime
      ∧ nextPrimeWithRes candidate r hr % 11 = r := by
  unfold nextPrimeWithRes
  exact Nat.find_spec (exists_prime_ge_with_res candidate r hr)

/-- ``nextPrimeWithRes`` is at or above the candidate. -/
lemma nextPrimeWithRes_ge (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) :
    candidate ≤ nextPrimeWithRes candidate r hr :=
  (nextPrimeWithRes_spec candidate r hr).1

/-- ``nextPrimeWithRes`` is prime. -/
lemma nextPrimeWithRes_prime (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) :
    (nextPrimeWithRes candidate r hr).Prime :=
  (nextPrimeWithRes_spec candidate r hr).2.1

/-- ``nextPrimeWithRes`` has the requested residue. -/
lemma nextPrimeWithRes_mod (candidate : ℕ) (r : ℕ) (hr : ValidResidue r) :
    nextPrimeWithRes candidate r hr % 11 = r :=
  (nextPrimeWithRes_spec candidate r hr).2.2

/-- The pairs ``(prime, exponent)`` the encoder chooses for each run. -/
noncomputable def encodePairs : List (Cmd × ℕ) → ℕ → List (ℕ × ℕ)
  | [], _candidate => []
  | (c, e) :: rs, candidate =>
      let p := nextPrimeWithRes candidate (res c) (validResidue_res c)
      (p, e) :: encodePairs rs (p + 1)

/-- The encoder: ``num * ∏ p^e`` over the chosen pairs. -/
noncomputable def encodeRuns (runs : List (Cmd × ℕ)) (num candidate : ℕ) : ℕ :=
  num * (List.map (fun pe : ℕ × ℕ => pe.1 ^ pe.2) (encodePairs runs candidate)).prod

/-- Encode a program as the Factor integer for it. -/
noncomputable def encode (code : List Cmd) : ℕ :=
  encodeRuns (runGroup code) 1 2

/-! ## 4. The decoder and the round-trip -/

/-- The distinct prime factors of ``n``, ascending (via the range). -/
def primeFactors (n : ℕ) : List ℕ :=
  List.filter (fun p => 0 < n.factorization p) (List.range (n + 1))

/-- The exponent ``q`` receives across the chosen ``(prime, exponent)``
pairs. -/
noncomputable def chosenExp (runs : List (Cmd × ℕ)) (candidate : ℕ) (q : ℕ) : ℕ :=
  (encodePairs runs candidate).foldl (fun acc pe => acc + pe.2 * (if pe.1 = q then 1 else 0)) 0

/-- The factorization of a prime at an arbitrary point. -/
lemma prime_factorization_at {p q : ℕ} (hp : p.Prime) :
    p.factorization q = if p = q then 1 else 0 := by
  by_cases h : p = q
  · subst p
    simp [Nat.Prime.factorization_self hp]
  · have h0 : p.factorization q = 0 := by
      rw [Nat.factorization_eq_zero_iff]
      by_cases hq : q.Prime
      · right; left
        intro hdiv
        have : p = q := (Nat.Prime.dvd_iff_eq hp (Nat.Prime.ne_one hq)).mp hdiv
        exact h this
      · left
        exact hq
    simp [h, h0]

/-- A ``foldl`` over an additive accumulation distributes the initial value. -/
lemma foldl_add_const (g : ℕ × ℕ → ℕ) (l : List (ℕ × ℕ)) (a : ℕ) :
    l.foldl (fun acc pe => acc + g pe) a = a + l.foldl (fun acc pe => acc + g pe) 0 := by
  induction l generalizing a with
  | nil => simp
  | cons pe l ih =>
      simp only [List.foldl_cons]
      have h1 := ih (a + g pe)
      have h2 := ih (0 + g pe)
      rw [h1, h2]
      omega

/-- The head run's chosen pair. -/
lemma encodePairs_cons (c : Cmd) (e : ℕ) (rs : List (Cmd × ℕ)) (candidate : ℕ) :
    encodePairs ((c, e) :: rs) candidate
      = (nextPrimeWithRes candidate (res c) (validResidue_res c), e)
        :: encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) := by
  rfl

/-- The chosen exponent at the head run. -/
lemma chosenExp_cons (c : Cmd) (e : ℕ) (rs : List (Cmd × ℕ)) (candidate q : ℕ) :
    chosenExp ((c, e) :: rs) candidate q
      = e * (if nextPrimeWithRes candidate (res c) (validResidue_res c) = q then 1 else 0)
        + chosenExp rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) q := by
  unfold chosenExp
  rw [encodePairs_cons, List.foldl_cons]
  simp only [zero_add]
  rw [foldl_add_const]

/-- Every prime chosen for the tail runs is at least ``candidate``. -/
lemma encodePairs_primes_ge (runs : List (Cmd × ℕ)) (candidate : ℕ) :
    ∀ p ∈ (encodePairs runs candidate).map Prod.fst, candidate ≤ p := by
  induction runs generalizing candidate with
  | nil => simp [encodePairs]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      simp [encodePairs]
      constructor
      · exact nextPrimeWithRes_ge candidate (res c) (validResidue_res c)
      · intro a x hm
        have hm' : a
            ∈ (encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst := by
          exact List.mem_map.mpr ⟨(a, x), hm, rfl⟩
        have hge := ih (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) a hm'
        have hle : candidate ≤ nextPrimeWithRes candidate (res c) (validResidue_res c) :=
          nextPrimeWithRes_ge candidate (res c) (validResidue_res c)
        omega

/-- The primes chosen by the encoder are pairwise distinct: each next prime is
greater than the previous. -/
lemma encodePairs_primes_nodup (runs : List (Cmd × ℕ)) (candidate : ℕ) :
    ((encodePairs runs candidate).map Prod.fst).Nodup := by
  induction runs generalizing candidate with
  | nil => simp [encodePairs]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      simp [encodePairs, List.nodup_cons]
      constructor
      · intro x hx
        have hx' : nextPrimeWithRes candidate (res c) (validResidue_res c)
            ∈ (encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst := by
          exact List.mem_map.mpr
            ⟨(nextPrimeWithRes candidate (res c) (validResidue_res c), x), hx, rfl⟩
        have hge :=
          encodePairs_primes_ge rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
            (nextPrimeWithRes candidate (res c) (validResidue_res c)) hx'
        omega
      · exact ih (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)

/-- The factorization of the encoded number at ``q`` is ``num``'s plus the
sum of the chosen exponents at ``q``. -/
lemma encodeRuns_factorization_at (runs : List (Cmd × ℕ)) (candidate num : ℕ)
    (hnz : num ≠ 0) (q : ℕ) :
    (encodeRuns runs num candidate).factorization q
      = num.factorization q + chosenExp runs candidate q := by
  induction runs generalizing num candidate with
  | nil => simp [encodeRuns, encodePairs, chosenExp]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      let p := nextPrimeWithRes candidate (res c) (validResidue_res c)
      have hp : p.Prime := by simpa [p] using nextPrimeWithRes_prime candidate (res c) (validResidue_res c)
      have hp0 : p ≠ 0 := Nat.Prime.ne_zero hp
      have hpe0 : p ^ e ≠ 0 := pow_ne_zero e hp0
      have hnm : num * p ^ e ≠ 0 := mul_ne_zero hnz hpe0
      have hstep : encodeRuns ((c, e) :: rs) num candidate = encodeRuns rs (num * p ^ e) (p + 1) := by
        simp [encodeRuns, encodePairs, p, Nat.mul_assoc]
      rw [hstep]
      have hih := ih (p + 1) (num * p ^ e) hnm
      rw [hih]
      have hfac_q : (num * p ^ e).factorization q = num.factorization q + e * (p.factorization q) := by
        rw [Nat.factorization_mul hnz hpe0]
        rw [Nat.factorization_pow]
        rw [Finsupp.add_apply, Finsupp.smul_apply]
        rfl
      rw [hfac_q]
      rw [chosenExp_cons c e rs candidate q]
      have hpf : p.factorization q = if p = q then 1 else 0 := prime_factorization_at hp
      rw [hpf]
      ac_rfl

/-- The factorization of the encoded number at ``q`` is exactly the chosen
exponent at ``q`` (with ``num = 1``). -/
lemma encodeRuns_factorization_one (runs : List (Cmd × ℕ)) (candidate q : ℕ) :
    (encodeRuns runs 1 candidate).factorization q = chosenExp runs candidate q := by
  rw [encodeRuns_factorization_at runs candidate 1 (by norm_num) q]
  simp

/-- The runs a number's factorization decodes to: each distinct prime's
residue identifies the command and its exponent the run length. -/
noncomputable def decodeRuns (n : ℕ) : List (Cmd × ℕ) :=
  (primeFactors n).map (fun p => (cmdOfRes (p % 11), n.factorization p))

/-- Decode a Factor integer into its brainfuck instruction string. -/
noncomputable def decode (n : ℕ) : List Cmd := expand (decodeRuns n)

/-- ``chosenExp`` is positive exactly at the chosen primes. -/
lemma chosenExp_pos_iff (runs : List (Cmd × ℕ)) (candidate q : ℕ)
    (hpos : ∀ r ∈ runs, 0 < r.2) :
    0 < chosenExp runs candidate q ↔ q ∈ (encodePairs runs candidate).map Prod.fst := by
  induction runs generalizing candidate with
  | nil => simp [chosenExp, encodePairs]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      have he : 0 < e := hpos (c, e) (by simp)
      rw [chosenExp_cons, encodePairs_cons]
      by_cases h : q = nextPrimeWithRes candidate (res c) (validResidue_res c)
      · subst q
        simp [he]
      · have hpq : ¬nextPrimeWithRes candidate (res c) (validResidue_res c) = q := by
          intro hp
          exact h hp.symm
        simp [h, hpq]
        simpa [List.mem_map] using ih (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
          (fun r hr => hpos r (by simp [hr]))

/-- The chosen primes appear in strictly increasing order. -/
lemma encodePairs_pairwise_lt_fst (runs : List (Cmd × ℕ)) (candidate : ℕ) :
    (encodePairs runs candidate).Pairwise (fun pe1 pe2 : ℕ × ℕ => pe1.1 < pe2.1) := by
  induction runs generalizing candidate with
  | nil => simp [encodePairs]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      rw [encodePairs_cons]
      apply List.Pairwise.cons
      · intro pe' hpe'
        have hm : pe'.1
            ∈ (encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst := by
          exact List.mem_map.mpr ⟨pe', hpe', rfl⟩
        have hge :=
          encodePairs_primes_ge rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) pe'.1 hm
        omega
      · exact ih (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)

/-- The distinct prime factors of the encoded number are exactly the chosen
primes, ascending. -/
lemma primeFactors_encodeRuns (runs : List (Cmd × ℕ)) (candidate : ℕ)
    (hpos : ∀ r ∈ runs, 0 < r.2) :
    primeFactors (encodeRuns runs 1 candidate)
      = (encodePairs runs candidate).map Prod.fst := by
  unfold primeFactors
  apply List.SortedLT.eq_of_mem_iff
  · exact (List.Pairwise.filter
      (fun q => decide (0 < (encodeRuns runs 1 candidate).factorization q))
      (List.sortedLT_range (encodeRuns runs 1 candidate + 1)).pairwise).sortedLT
  · exact (List.Pairwise.map (f := Prod.fst)
      (R := fun pe1 pe2 : ℕ × ℕ => pe1.1 < pe2.1) (S := fun a b : ℕ => a < b)
      (H := fun pe1 pe2 h => h)
      (encodePairs_pairwise_lt_fst runs candidate)).sortedLT
  · intro q
    rw [List.mem_filter, List.mem_range, List.mem_map,
      encodeRuns_factorization_one runs candidate q]
    constructor
    · intro h
      rcases h with ⟨hle, hposq⟩
      have hposq' : 0 < chosenExp runs candidate q := by simpa using hposq
      simpa [List.mem_map] using (chosenExp_pos_iff runs candidate q hpos).1 hposq'
    · intro h
      have hposq : 0 < chosenExp runs candidate q :=
        (chosenExp_pos_iff runs candidate q hpos).2 (by simpa [List.mem_map] using h)
      have hfac : 0 < (encodeRuns runs 1 candidate).factorization q := by
        rw [encodeRuns_factorization_one runs candidate q]
        exact hposq
      have hne0 : (encodeRuns runs 1 candidate).factorization q ≠ 0 := by omega
      have hfull : q.Prime ∧ q ∣ encodeRuns runs 1 candidate
          ∧ encodeRuns runs 1 candidate ≠ 0 := by
        have hnot : ¬(¬ q.Prime ∨ ¬ q ∣ encodeRuns runs 1 candidate
            ∨ encodeRuns runs 1 candidate = 0) :=
          (Nat.factorization_eq_zero_iff (encodeRuns runs 1 candidate) q).not.mp hne0
        tauto
      have hle : q ≤ encodeRuns runs 1 candidate :=
        Nat.le_of_dvd (by omega : 0 < encodeRuns runs 1 candidate) hfull.2.1
      exact ⟨by omega, by simpa using hposq⟩

/-- The head run's prime contributes nothing to the factorization at any other
point: at ``q ≠ p`` the encoded number's factorization agrees with the tail's. -/
lemma encodeRuns_head_neq (c : Cmd) (e : ℕ) (rs : List (Cmd × ℕ)) (candidate q : ℕ)
    (hq : q ≠ nextPrimeWithRes candidate (res c) (validResidue_res c)) :
    (encodeRuns ((c, e) :: rs) 1 candidate).factorization q
      = (encodeRuns rs 1 (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).factorization q := by
  rw [encodeRuns_factorization_one ((c, e) :: rs) candidate q]
  rw [encodeRuns_factorization_one rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) q]
  rw [chosenExp_cons c e rs candidate q]
  have hpq : ¬nextPrimeWithRes candidate (res c) (validResidue_res c) = q := by
    intro hp
    exact hq hp.symm
  rw [if_neg hpq]
  simp

/-- The runs recovered by the decoder are the runs the encoder folded in. -/
lemma decodeRuns_encodeRuns (runs : List (Cmd × ℕ)) (candidate : ℕ)
    (hpos : ∀ r ∈ runs, 0 < r.2) :
    decodeRuns (encodeRuns runs 1 candidate) = runs := by
  induction runs generalizing candidate with
  | nil => simp [decodeRuns, primeFactors, encodeRuns, encodePairs, Nat.factorization_one]
  | cons pe rs ih =>
      rcases pe with ⟨c, e⟩
      have hpos_rs : ∀ r ∈ rs, 0 < r.2 := fun r hr => hpos r (by simp [hr])
      have hhead : (cmdOfRes (nextPrimeWithRes candidate (res c) (validResidue_res c) % 11),
          (encodeRuns ((c, e) :: rs) 1 candidate).factorization
            (nextPrimeWithRes candidate (res c) (validResidue_res c)))
          = (c, e) := by
        have hcmd : cmdOfRes (nextPrimeWithRes candidate (res c) (validResidue_res c) % 11) = c := by
          rw [nextPrimeWithRes_mod candidate (res c) (validResidue_res c), cmdOfRes_res c]
        have hfac : (encodeRuns ((c, e) :: rs) 1 candidate).factorization
            (nextPrimeWithRes candidate (res c) (validResidue_res c)) = e := by
          rw [encodeRuns_factorization_one ((c, e) :: rs) candidate
            (nextPrimeWithRes candidate (res c) (validResidue_res c))]
          rw [chosenExp_cons c e rs candidate (nextPrimeWithRes candidate (res c) (validResidue_res c))]
          have hnot : nextPrimeWithRes candidate (res c) (validResidue_res c)
              ∉ (encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst := by
            intro hm
            have hge := encodePairs_primes_ge rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
              (nextPrimeWithRes candidate (res c) (validResidue_res c)) hm
            omega
          have hz : chosenExp rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
              (nextPrimeWithRes candidate (res c) (validResidue_res c)) = 0 := by
            have hiff := chosenExp_pos_iff rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
              (nextPrimeWithRes candidate (res c) (validResidue_res c)) hpos_rs
            have hnot_pos : ¬0 < chosenExp rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)
                (nextPrimeWithRes candidate (res c) (validResidue_res c)) := by
              exact fun hp0 => hnot (hiff.1 hp0)
            omega
          rw [if_pos rfl, hz]
          simp
        exact Prod.ext hcmd hfac
      unfold decodeRuns
      rw [primeFactors_encodeRuns ((c, e) :: rs) candidate (fun r hr => hpos r (by simp [hr]))]
      rw [encodePairs_cons, List.map_cons, List.map_cons]
      rw [hhead]
      have hmap : List.map (fun q : ℕ =>
            (cmdOfRes (q % 11), (encodeRuns ((c, e) :: rs) 1 candidate).factorization q))
            ((encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst)
          = List.map (fun q : ℕ =>
            (cmdOfRes (q % 11), (encodeRuns rs 1 (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).factorization q))
            ((encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst) := by
        apply List.map_congr_left
        intro q hq
        apply Prod.ext
        · rfl
        · exact encodeRuns_head_neq c e rs candidate q (by
            intro hqp
            have hge := encodePairs_primes_ge rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) q hq
            rw [← hqp] at hge
            omega)
      rw [hmap]
      have hrest : List.map (fun q : ℕ =>
            (cmdOfRes (q % 11), (encodeRuns rs 1 (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).factorization q))
            ((encodePairs rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)).map Prod.fst)
          = rs := by
        have hpf := primeFactors_encodeRuns rs (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) hpos_rs
        rw [← hpf]
        change decodeRuns (encodeRuns rs 1 (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1)) = rs
        exact ih (nextPrimeWithRes candidate (res c) (validResidue_res c) + 1) hpos_rs
      rw [hrest]

/-- Every run produced by ``runGroup`` has positive length. -/
lemma runGroup_pos : ∀ code : List Cmd, ∀ r ∈ runGroup code, 0 < r.2 := by
  have hwf : WellFounded fun a b : List Cmd => a.length < b.length := by
    exact InvImage.wf (fun l : List Cmd => l.length) Nat.lt_wfRel.wf
  refine (WellFounded.fix hwf (fun cs ih => ?_))
  intro r hr
  cases cs with
  | nil => simp [runGroup] at hr
  | cons c cs' =>
      have h : r = (c, (splitRun c cs').1 + 1) ∨ r ∈ runGroup (splitRun c cs').2 := by
        simpa [runGroup] using hr
      rcases h with h | hm
      · subst r
        simp
      · have hlen : (splitRun c cs').2.length < (c :: cs').length := by
          rw [List.length_cons]
          have hle := splitRun_rest_length c cs'
          omega
        exact ih (splitRun c cs').2 hlen r hm

/-- **The round-trip**: decoding the encoded integer recovers the program. -/
theorem decode_encode (code : List Cmd) : decode (encode code) = code := by
  unfold decode encode
  rw [decodeRuns_encodeRuns (runGroup code) 2 (runGroup_pos code)]
  exact expand_runGroup code

end FactorCorrect
