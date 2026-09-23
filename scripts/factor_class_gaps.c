// Class gaps of primes mod 11, for docs/proofs/factor.tex (Lemma "Computed
// class gaps").  For each residue a, prints the largest (p' - p)/ln^2 max(p, 37)
// over consecutive primes p < p' <= X of class a with p >= P0, and the largest
// raw gap.  Segmented Eratosthenes; X = 1e11 took 14 minutes on one core.
//
//   cc -O2 -o gaps scripts/factor_class_gaps.c -lm && ./gaps 100000000000 2
//
// The gaps from 0 to each class's first prime (P0 = 2 skips them) are covered
// by tests/proofs/deep/factor_constants.py, which re-sieves a prefix.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  uint64_t X = strtoull(argv[1], 0, 10), P0 = strtoull(argv[2], 0, 10);
  uint64_t R = (uint64_t)sqrtl((long double)X) + 2;
  char *s = calloc(R + 1, 1);
  uint32_t *bp = malloc(sizeof(uint32_t) * R);
  size_t nb = 0;
  for (uint64_t i = 2; i <= R; i++)
    if (!s[i]) {
      bp[nb++] = i;
      for (uint64_t j = i * i; j <= R; j += i) s[j] = 1;
    }
  uint64_t last[11] = {0}, bestp[11] = {0}, bestq[11] = {0}, maxg[11] = {0};
  double best[11] = {0};
  const uint64_t S = 1 << 24;
  char *seg = malloc(S);
  for (uint64_t lo = 2; lo <= X; lo += S) {
    uint64_t hi = lo + S - 1;
    if (hi > X) hi = X;
    memset(seg, 0, hi - lo + 1);
    for (size_t k = 0; k < nb; k++) {
      uint64_t p = bp[k];
      if (p * p > hi) break;
      uint64_t st = ((lo + p - 1) / p) * p;
      if (st < p * p) st = p * p;
      for (uint64_t j = st; j <= hi; j += p) seg[j - lo] = 1;
    }
    for (uint64_t x = lo; x <= hi; x++)
      if (!seg[x - lo]) {
        int a = x % 11;
        if (last[a] >= P0) {
          uint64_t g = x - last[a];
          double l = log((double)(last[a] > 37 ? last[a] : 37));
          double r = g / (l * l);
          if (r > best[a]) best[a] = r, bestp[a] = last[a], bestq[a] = x;
          if (g > maxg[a]) maxg[a] = g;
        }
        last[a] = x;
      }
  }
  for (int a = 1; a <= 10; a++)
    printf("%d ratio %.6f at %llu->%llu maxgap %llu\n", a, best[a],
           (unsigned long long)bestp[a], (unsigned long long)bestq[a],
           (unsigned long long)maxg[a]);
  return 0;
}
