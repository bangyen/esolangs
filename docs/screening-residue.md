# Screening residue: what three spent audits are still worth

Three scratch audits were mostly consumed by the work they prompted, and
were never tracked.  This keeps the part that outlived them and drops the
working material.  Each section names its source and its date, and records
what has shipped since, so nobody re-runs a screen whose candidates
already landed.

---

## Boolean generator novelty axes

*From `unimplemented-boolean-novelty.md`, 2026-09-01.  Its six-language
ranking is entirely spent -- every candidate was pursued.  Inject,
Algebraic Programming Language, Packlang and Interprogck8 shipped and are
still here.  DINAC and `function x(y)`, its two lowest-rated picks, also
shipped and were then deliberately **pruned** -- DINAC in `c967e6e4`
(2026-09-12) as one of four "ordinary languages in costume",
`function x(y)` in `07885839` (2026-09-13) as a shared-shim language.
Their absence from the registry is a curation verdict, not an unbuilt
candidate; the criterion is in `docs/limitations.md`'s Curation section.
The axes below are what survived.*

A candidate is *novel* only if it forces a point the existing set does not
occupy:

* **Construction shape** -- decision tree (the default: cvnc, six_five,
  dimensional, cod, slow_acv_mammalian, most of register/stack/tape),
  minterm sum (circuit_diagram), ANF/XOR-of-products (fargo, the only one),
  grid walk (laserfuck, wii2d, a_painter_ant, streetcode).
* **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement (123).
* **Answer convention** -- print 0/1, landing colour (a_painter_ant),
  position-encoded (minifuck), decimal accumulator (%^2^-1),
  termination/halt-vs-loop (123, ArrowQueue, Point Break).
* **Input interface** -- read-and-route, bit-addressable index (fargo),
  parameterized embed (parameterized.py family).

This is an *admission* criterion.  `docs/limitations.md`'s Curation section
records *removals*, by a different criterion (shared-shim generators with no
downstream consumer); the two do not substitute for each other.

---

## The 2D x Unimplemented wiki screen

*From `twod-unimplemented-audit.md`, 2026-09-02.  Its correction already
landed in `b09e6366`; the screening record did not.*

**The roadmap's claimed pass could not have happened.**
`Category:Two-dimensional` does not exist on the wiki --
`list=allcategories&acprefix=Two` returns exactly one category,
`Two-dimensional languages`.  A query against a non-existent category
returns no members, so the four-language result attributed to it came from
somewhere else.

The real intersection is `Category:Unimplemented` (1543 pages) x
`Category:Two-dimensional languages` (567), screened to **36 survivors** by:

1. Subtract languages already in `docs/languages.md`.
2. Subtract titles already carrying a verdict in `docs/limitations.md` /
   `docs/roadmap.md` / `docs/walls.md`.
3. Reject on co-category: No IO, Stubs, Works-in-Progress, Joke languages,
   Nondeterministic, Output only, Non-textual, Graphical Output,
   Uncomputable, Unusable for programming, Ideas, Implemented.
4. Reject on page text: missing input, output or branch vocabulary;
   explicit work-in-progress wording; or a page under 1500 characters.

Spec reads then tiered the 36: **Tier A strong (3)** -- Super SNUSP,
Alight, Pinyin.  **Tier B plausible, one named blocker each (7)** -- ASCII
Code, Train, Wirefunge, `(...) IS 2D!!`, B-tapemark, BackTurn, Egnufeb.
**Tier C needs a deeper read (9)**.  **Tier D rejected on a named ground
(17)**.

**Tier A is fully resolved, so the roadmap's empty candidate list is
correct.**  Super SNUSP and Alight shipped, and so did B-tapemark from
Tier B; all three have generators in `src/esolangs/tools/`.  Pinyin was
audited and **rejected** in `cf59038f` (2026-09-08): routing pinned and a
two-input program prices at 4 characters, but the page's own selection
rule reroutes 8 of 23 `Hello, world!` characters, and its truth machine
on input 1 is unreachable under all 384 readings.  The randomness caveat
recorded during this screen -- tone 0 picks a random direction, `en`
pushes a random 0/1 -- was not what sank it.

Rejections and prunings are recorded in `docs/roadmap.md` and its history,
not in `src/esolangs/tools/`, which holds only what survived.

ABCDirection is **not** a candidate -- it was implemented here and then
removed; the rationale is in git history, not on the wiki.

---

## Boolean generators that still simulate

*From `boolean-simulator-audit.md`.  The `_find_pool` half shipped
(`b2c3744d`); the wii2d negative survives as a source comment at
`wii2d.py:67,90`.  The framing and the work order did not.*

"Uses a simulator" means **the module drives an interpreter or an execution
model at generation time**.  That splits three ways, and the split is most
of the answer:

1. **Simulator + candidate search** -- the actual offenders (minifuck,
   wii2d).  A search at generation time is what a rule should replace.
2. **Simulation as tracked emission, not search** -- already fine; the
   model is bookkeeping for what is being emitted, not a search over it.
3. **Size contests, no simulator at all** -- not in scope.

Remaining order of work:

1. `_try_print` -- smallest answer space, same evidence base.
2. `_find_pool` at the canonical probe state -- the closure next door.
3. `_find_pool` in general -- the real wall.
4. wii2d -- may not close; report the key rather than force it.

Per the standing rule, a longer emitted program is an acceptable price for
a rule, and the replaced search stays in the tests as the oracle.
