# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## Planned

### Classify the remaining cross-checks' exit codes
The cross-check exit-code convention (0 = success, 2 = malformed, 3 =
invalid runtime op, 1 = unclassified) is documented in the README and was
applied to basicfuck, the Ruby/R extras, NoComment, and EXCON.  Most C++
references (kak, trash, painfuck, forþ, 2dFish, %^2^-1) still use a generic
`EXIT_FAILURE` (1) for every error.  That is conformant today — 1 is the
reserved unclassified code — but these cross-checks have not been *classified*
into the 2/3 split the convention describes, so a harness consuming the
convention (e.g. the differential fuzzer) cannot distinguish their malformed
from their runtime failures.  Classifying them is mechanical but touches
every C++ reference; decide whether the consistency is worth it.
