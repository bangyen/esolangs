# Vandevelo's bounded sparse cubes prevent linear text

The current generator does not have worst-case linear output size in
characters. Its fixed sparse candidate limit gives an explicit family with
output length Ω(2ⁿ log n). Consequently, generation time measured in
character operations cannot be O(2ⁿ). This concerns the shipped generator,
not every possible Vandevelo construction.

## The family

Put T = 2ⁿ and, for n ≥ 100, let m be the largest odd integer at most
⌊T/n⌋. Define fₙ(x) = 1 exactly when the unsigned binary value of x is
less than m. This specifies the family without a search or a stored table.
Since T/n ≥ 4, we have T/(2n) ≤ m ≤ T/n. Both m and T − m are odd and
greater than one. Neither is a power of two.

An affine subspace of dimension d over the binary field, and every coset
of it, has 2ᵈ points. Thus neither the one-set nor the zero-set is an
affine coset. In fact, `_affine_coset` immediately rejects both because
their sizes are not powers of two. The generator therefore uses `_Peel`.
Its sparse threshold is ⌊T/max(48,n)⌋ = ⌊T/n⌋. The initial one-set
already lies below that threshold, so `run` immediately calls `sparse`.
The constructor's scoring does not remove points or change this decision.

## Cube and guard bounds

Each iteration of `sparse` starts with at most 24 retained directions,
adds nearest differences only up to a total of 48, and fills any remaining
slots only while the total is below 48. `_grow` chooses directions from
that list and deletes chosen directions; it never adds a candidate.
Hence every emitted cube has dimension d ≤ 48 and at most 2⁴⁸ points.

The directions are independent: after an extension, `_grow` removes every
candidate whose translate of the pivot is already in the cube. Extending
by a remaining candidate therefore doubles the cube. Every extension is
checked against the remaining one-set. The emitted cubes are disjoint,
because their points are deleted from that set; the pivot is removed on
every iteration, so the process covers all m points. If C is the number
of cubes, then

    C ≥ m / 2⁴⁸ ≥ T / (2n · 2⁴⁸).

For a cube of dimension d, `_constraints` returns a basis of its
annihilator, with exactly c = n − d independent equations. To see the
basis property, associate each input coordinate with its column across
the d directions. A short relation expresses a non-core column as a sum
of earlier core columns. Its mask has that non-core coordinate as its
unique leading coordinate, so the short relations are independent.
Reduced elimination supplies a basis of the full annihilator. Appending
only rows independent of the accumulated relations completes their span
to that annihilator, whose dimension is n − d. The right-hand sides are
the masks' parities at the cube's base, so these equations define exactly
the cube.

Every guard thus starts with c ≥ n − 48 ≥ n/2 independent equations.
`_pruned` initially has no implied tests. It adds an implied test only
after a guard has been reduced to one test. Inductively, every guard
retains all its equations: with an empty implication set its at least
two equations remain, and the implication set stays empty.

Each guard references at least c distinct identifiers. A weight-one
equation references its input name; independence prevents two such
equations from using the same input. Every wider equation references a
register. The generator's `used` set prevents reuse of that register
within the guard, both when looking for an exact match and when choosing
a register to morph or respell. New register names are allocated after
the n input names in the injective `short_name` enumeration. Register
names and input names are therefore disjoint. Input negation and register
polarity affect tests but do not remove these references.

## Character lower bound

All these names use the fixed alphabet of letters, digits, underscore,
ampersand, asterisk and dollar sign, containing at most q = 66 characters.
For any c distinct nonempty names, put h = ⌊log₆₆(c/2)⌋. There are fewer
than 66ʰ ≤ c/2 names shorter than h, because

    ∑_{j=1}^{h−1} 66ʲ < 66ʰ.

At least c/2 of the names therefore have length at least h. Their total
length is at least (c/2)h. Applying c ≥ n/2 independently to every guard
gives at least

    (n/4) ⌊log₆₆(n/4)⌋

identifier characters per guard. Reusing the same names on different
lines does not eliminate the characters written on those lines. Thus
the emitted source length Lₙ satisfies

    Lₙ ≥ [T / (2n · 2⁴⁸)] · (n/4) ⌊log₆₆(n/4)⌋
       = (T / 2⁵¹) ⌊log₆₆(n/4)⌋.

In particular Lₙ/T is unbounded. This proves Ω(T log n) characters and
disproves O(T) characters. The bound applies to both default and compact
spelling, since both retain the same identifier references. Writing the
returned string requires Ω(Lₙ) character work, so character-level
generation time is also superlinear. This does not give a superlinear
lower bound in a model treating arbitrary strings as unit-cost objects,
or contradict a linear bound on executed VM commands.

The candidate cap is decisive. Any fixed cap K yields the same argument
with 2ᴷ in place of 2⁴⁸. Raising it to another fixed constant cannot prove
asymptotic linearity. A construction with a growing cap would need a new
analysis; this proof does not settle its size or generation time.

## Execution check

The asymptotic claim follows from the code structure, not an extrapolation
of small measurements. As a finite control, the same odd-prefix family
with m the largest odd integer at most ⌊T/max(48,n)⌋ was generated at
n = 8 and 9. Both affine shortcuts rejected it, the sparse cubes covered
all ones, and pruning left their equations intact. Every input row was
executed through the interpreter with halting or an exact repeated-state
cycle determining the answer; all answers matched and all n inputs were
read. The n = 8 table had five ones, cube dimensions 2 and 0, and 204
source characters; n = 9 had nine ones, dimensions 3 and 0, and 221
characters. Together these checks executed 768 rows. These small cases
check the route and execution, not the asymptotic lower bound.

## Replacement status

The math-proof siege attempt did not establish a universal O(T)-character,
O(T)-generation replacement or disprove the existence of one. Its conditional
affine-cover compilers and special-case constructions are research leads,
not implemented or execution-verified replacements. The unresolved route
requires both a universally small cover and a deterministic discovery rule
whose coefficient, identifier and data-routing costs are charged.

Restrictions on read-first affine guards, fixed direction libraries, local
merges or specific routing models do not prove a lower bound for every legal
Vandevelo program. Conditional input consumption remains a separate route.
The interpreter and generator were left unchanged. The lower bound above
is the established result for the shipped construction; universal linearity
remains open.
