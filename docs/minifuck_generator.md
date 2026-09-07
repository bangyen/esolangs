# Minifuck boolean generator

Minifuck has no usable termination convention: a program that halts cannot
make the required input-dependent silent choice. The generator instead emits
output directly.

The constructed route is total through four inputs. Five-input coverage is
partial; flat pools and the tested composition schemes do not close the gap.
Refusals are explicit rather than search timeouts. The generator's source and
tests are authoritative for the pool, pointer, and emitter invariants.

Do not treat a broader search as evidence of a language wall. The documented
negative result applies to the tested flat and composition families only.
