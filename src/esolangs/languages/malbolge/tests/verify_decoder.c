/* Executable certificate for the packed Malbolge decoder. The Python driver
 * supplies the VM tables, assembled layouts and source operand domains. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define WORDS 59049
typedef uint16_t Word;
typedef struct {
  int a, c, d, reads, outputs, out, returned, temporary;
} State;
static unsigned char decode[94], encrypt[94], crazy_digits[81],
    layout_changes[WORDS], opcodes[94][127];
static Word initial[WORDS], memory[WORDS], operand_values[WORDS][9],
    primary_words[32768], spill_words[32768];
static unsigned char slots[32768];
static int crazy(int a, int d) {
  int v = 0;
  for (int p = 1; p < WORDS; p *= 9) {
    v += p * crazy_digits[d % 9 * 9 + a % 9];
    a /= 9;
    d /= 9;
  }
  return v;
}
static int rotate_word(int a) { return a / 3 + a % 3 * 19683; }
static int opcode(int v, int c) {
  return v >= 33 && v <= 126 ? opcodes[c % 94][v] : 0;
}
static int glyph(char o, int c) {
  for (int v = 33; v <= 126; v++)
    if (decode[(v - 33 + c) % 94] == o)
      return v;
  abort();
}
static int first_crazy_a[WORDS];
static unsigned int trit_mask[WORDS];
static int prefix, early_layout_reads, live_stamp[WORDS], write_stamp[WORDS],
    recording, epoch, live_count, live[WORDS];
static void record_read(int k) {
  if (write_stamp[k] != epoch && live_stamp[k] != epoch) {
    live_stamp[k] = epoch;
    live[live_count++] = k;
    first_crazy_a[k] = -1;
  }
}
static void record_write(int k) { write_stamp[k] = epoch; }
static unsigned char column_marker[WORDS];
static int seen_at[WORDS], generation;
static unsigned char fallthrough[WORDS], jump_edges[96][WORDS];
static int jump_id[WORDS], jump_count;
static long navigation_checks, shadow_checks, conditioned_checks;
/* Between the two payload reads, D crosses arbitrary source operands. Apply
 * every allowed value until all paths rejoin. The two correlated words
 * need two cases only when their independent domains fail to converge. */
static int abstract_walk(State *s, Word *m, int limit, int target, int mode) {
  int current[2048], next[2048], size = 1, reference_d = s->d;
  current[0] = reference_d;
  for (int c = s->c; c < limit; c++) {
    int op = opcode(m[c], c);
    if (op != 'j' && op != 'o')
      return 0;
    int count = 0;
    generation++;
    for (int i = 0; i < size; i++) {
      int k = current[i];
      int alternatives = op == 'j' ? operand_values[k][0] : 0;
      if (op == 'j' && (column_marker[k] || layout_changes[k])) {
        fprintf(stderr, "variable navigation target %d at %d\n", k, c);
        exit(6);
      }
      for (int j = 0; j < (alternatives > 1 ? alternatives : 1); j++) {
        int v = k;
        if (op == 'j') {
          if (alternatives > 1) {
            v = operand_values[k][j + 1];
            if (k == 29524 && !s->returned)
              v = glyph("ji*p</vo"[j], k);
            if (mode == 1 && k == 39391 && v != glyph('<', k))
              continue;
            if (mode == 2 &&
                ((k == 39391 && v == glyph('<', k)) ||
                 (k == 39394 && (v == glyph('j', k) || v == glyph('v', k)))))
              continue;
            if (s->temporary == k + 1)
              v = crazy(59048, v);
          } else
            v = m[k];
          if (k >= s->c && k < c && v >= 33 && v <= 126)
            v = encrypt[v - 33];
        }
        int d = (v + 1) % WORDS;
        if (seen_at[d] != generation) {
          seen_at[d] = generation;
          assert(count < 2048);
          next[count++] = d;
        }
      }
    }
    if (op == 'j') {
      int v = m[reference_d];
      if (reference_d >= s->c && reference_d < c && v >= 33 && v <= 126)
        v = encrypt[v - 33];
      reference_d = v;
    }
    reference_d = (reference_d + 1) % WORDS;
    size = count;
    memcpy(current, next, sizeof(*next) * count);
    if (target < 0 && size == 1 && current[0] == reference_d)
      return 1;
  }
  return size == 1 && current[0] == target;
}
static void check_access(State *s, Word *m, int row, int op) {
  int c = s->c, d = s->d;
  if (!op || op == 'v')
    return;
  if (op == 'i') {
    if (!jump_id[c]) {
      assert(jump_count < 95);
      jump_id[c] = ++jump_count;
    }
    jump_edges[jump_id[c]][(m[d] + 1) % WORDS] = 1;
  } else
    fallthrough[c] = 1;
  if (!prefix)
    return;
  if (c == 29525)
    s->returned = 1;
  if (operand_values[c][0] > 1 || column_marker[c]) {
    fprintf(stderr, "variable PC %d row %d\n", c, row);
    exit(7);
  }
  if (op == 'i' && (operand_values[m[d]][0] > 1 || column_marker[m[d]]) &&
      m[d] != 29524) {
    fprintf(stderr, "unknown encrypted jump target %d row %d\n", m[d], row);
    exit(7);
  }
  if (c == 6220)
    s->temporary = d + 1;
  if (c == 6286)
    s->temporary = 0;
  if (strchr("ji*p", op) && column_marker[d] && c != 38469) {
    fprintf(stderr, "other marker read %d row %d k%d\n", c, row, d);
    exit(7);
  }
  int end = 0, goal = -1;
  if (c == 6223) {
    end = 6260;
    goal = 128;
  } else if (c == 6289) {
    end = 6317;
    goal = 35;
  } else if (operand_values[d][0] > 1 && strchr("ji*p", op) && c != 6220 &&
             c != 6286 && !(6223 <= c && c < 6260) &&
             !(6289 <= c && c < 6317)) {
    if (op != 'j') {
      fprintf(stderr, "other variable operand %d row %d k%d\n", c, row, d);
      exit(7);
    }
    end = c + 64;
  }
  if (!end)
    return;
  navigation_checks++;
  if (goal >= 0)
    shadow_checks++;
  if (!abstract_walk(s, m, end, goal, 0)) {
    conditioned_checks++;
    if (!abstract_walk(s, m, end, goal, 1) ||
        !abstract_walk(s, m, end, goal, 2)) {
      fprintf(stderr, "unjoined C%d D%d row%d\n", c, d, row);
      exit(7);
    }
  }
}
static unsigned char native_lookup_domains[335][2];
static long guard_checks, guard_glyphs;
static int checked_key, checked_tap;
static int guard_finish(const Word *m, int start, int stop, int raw) {
  int d = raw + 1;
  for (int c = start + 1; c < stop; c++) {
    int op = opcode(m[c], c);
    assert(op == 'o' || op == 'j');
    if (op == 'j') {
      if (d >= 5213 && d < 5548 && d % 3 != 1) {
        fprintf(stderr, "universal guard at %d reads mutable output %d at %d\n",
                start, d, c);
        exit(11);
      }
      record_read(d);
      int value = m[d];
      if (d >= start && d < c && value >= 33 && value <= 126)
        value = encrypt[value - 33];
      d = value;
    }
    d = (d + 1) % WORDS;
  }
  return d;
}

static void check_guard(State *s, Word *m, int row) {
  int c = s->c, d = s->d;
  int stop = c == 5585 ? 5617 : c == 5657 ? 5687 : c == 5697 ? 5721 : 0;
  if (!stop)
    return;
  assert(d >= 5213 && d < 5548 && d % 3 == 2);
  int want = guard_finish(m, c, stop, m[d]);
  guard_checks++;
  for (int j = 0; j < 2; j++) {
    int alternate = native_lookup_domains[d - 5213][j];
    if (!alternate)
      continue;
    guard_glyphs++;
    int got = guard_finish(m, c, stop, alternate);
    if (got != want) {
      fprintf(stderr,
              "guard divergence row%d pc%d addr%d raw%d alt%d got%d want%d\n",
              row, c, d, m[d], alternate, got, want);
      exit(12);
    }
  }
}


/* Instruction fetch and jump-target encryption both read the old cell.
 * Record a suffix cell only on its first read before a write. */
static int step(State *s, Word *m, int row) {
  int a = s->a, c = s->c, d = s->d, op = opcode(m[c], c);
  check_access(s, m, row, op);
  if (recording) {
    check_guard(s, m, row);
    if (c >= 5213 && c < 5548 && c % 3 != 1 && layout_changes[c])
      abort();
    if (op && strchr("ji*p", op) && d >= 5213 && d < 5548 && d % 3 != 1 &&
        layout_changes[d] && c != 5585 && c != 5657 && c != 5697 &&
        !(c == checked_tap && d == checked_key)) {
      fprintf(stderr, "unexpected output-lane read at pc%d addr%d row%d\n", c,
              d, row);
      exit(13);
    }
    if (op == 'i' && m[d] >= 5213 && m[d] < 5548 && m[d] % 3 != 1 &&
        layout_changes[m[d]])
      abort();
    record_read(c);
    if (op == 'i' || op == 'j' || op == '*' || op == 'p') {
      int no = live_count;
      record_read(d);
      if (live_count > no && op == 'p')
        first_crazy_a[d] = a;
    }
    if (op == 'i')
      record_read(m[d]);
    if (op == '*' || op == 'p')
      record_write(d);
    record_write(op == 'i' ? m[d] : c);
  }
  if (prefix && (layout_changes[c] ||
                 ((op == 'i' || op == 'j' || op == '*' || op == 'p') &&
                  layout_changes[d]) ||
                 (op == 'i' && layout_changes[m[d]])))
    early_layout_reads++;
  if (!op || op == 'v')
    return 0;
  switch (op) {
  case 'j':
    d = m[d];
    break;
  case 'i':
    c = m[d];
    break;
  case '*':
    a = m[d] = rotate_word(m[d]);
    break;
  case 'p':
    a = m[d] = crazy(a, m[d]);
    break;
  case '/':
    if (s->reads == 17)
      return 0;
    a = 48 + ((row >> (16 - s->reads++)) & 1);
    break;
  case '<':
    s->outputs++;
    s->out = a & 255;
  }
  if (m[c] >= 33 && m[c] <= 126)
    m[c] = encrypt[m[c] - 33];
  s->a = a;
  s->c = (c + 1) % WORDS;
  s->d = (d + 1) % WORDS;
  return 1;
}
static int run_to(State *s, Word *m, int row, int stop, int budget) {
  for (int j = 0; j <= budget; j++) {
    if (s->c == stop)
      return j;
    if (!step(s, m, row))
      break;
  }
  return -1;
}
static void read_file(const char *path, void *out, size_t size) {
  FILE *f = fopen(path, "rb");
  assert(f && fread(out, 1, size, f) == size);
  fclose(f);
}
static void load_inputs(void) {
  FILE *f = fopen("isa", "rb");
  assert(f);
  assert(fread(decode, 1, 94, f) == 94 && fread(encrypt, 1, 94, f) == 94 &&
         fread(crazy_digits, 1, 81, f) == 81);
  fclose(f);
  for (int c = 0; c < 94; c++)
    for (int v = 33; v < 127; v++) {
      int o = decode[(c + v - 33) % 94];
      opcodes[c][v] = strchr("ji*p</v", o) ? o : 'o';
    }
  read_file("initial", initial, sizeof(initial));
  read_file("mutable", layout_changes, WORDS);
  read_file("domains", operand_values, sizeof(operand_values));
  read_file("primary", primary_words, sizeof(primary_words));
  read_file("spill", spill_words, sizeof(spill_words));
  read_file("slots", slots, sizeof(slots));
}

static Word before_marker[WORDS], before_payload[WORDS], marked_memory[WORDS];
static unsigned char checkpoint[94][128][3];
#define SETTINGS 8
typedef struct {
  unsigned char order[3], flip, code[585];
} Layout;
static Layout layouts[SETTINGS];
static int models, layout_offset[WORDS], variable_addresses[585],
    variable_count;
static Word hubs[127];
static const int printer_entry[] = {4513, 4663, 4585};
static const int lookup_tap[] = {139, 127, 130};
static unsigned char covered[SETTINGS];
static long suffix_runs, equivalent_layouts;
static int max_live;
static Word suffix_memory[WORDS];
typedef struct classes {
  int n;
  Word *cells;
  unsigned int *allowed_trits;
  struct classes *next;
} SuffixClass;
static int extra_classes;
static SuffixClass classes[94][128][3];
static void load_layouts(void) {
  for (int v = 0; v < WORDS; v++) {
    int y = v;
    for (int j = 0; j < 30; j += 3) {
      trit_mask[v] |= 1u << (j + y % 3);
      y /= 3;
    }
  }
  FILE *f = fopen("layouts", "rb");
  assert(f);
  models = fread(layouts, sizeof(Layout), SETTINGS, f);
  assert(fgetc(f) == EOF);
  fclose(f);
  assert(models == SETTINGS);
  for (int i = 0; i < 585; i++) {
    int k = i < 250 ? 4450 + i : 5213 + i - 250;
    layout_offset[k] = i + 1;
    if (layout_changes[k])
      variable_addresses[variable_count++] = k;
  }
  read_file("hubs", hubs, sizeof(hubs));
}

/* After the first read by crazy, both A and the cell hold the result. For
 * that first read it suffices to preserve the result at each trit. */
static unsigned int equivalent_trits(int a, int value) {
  if (a < 0)
    return trit_mask[value];
  unsigned int bits = 0;
  for (int shift = 0; shift < 30; shift += 3) {
    int x = value % 3, y = a % 3;
    for (int d = 0; d < 3; d++)
      if (crazy_digits[d * 9 + y] % 3 == crazy_digits[x * 9 + y] % 3)
        bits |= 1u << (shift + d);
    value /= 3;
    a /= 3;
  }
  return bits;
}
static void run_printer(State *start, int setting, int z, int key, int hub,
                        int row, int word, int raw, int marker,
                        int lookup_glyph, int glyph_override) {
  const Layout *layout = &layouts[setting];
  memcpy(suffix_memory, memory, sizeof suffix_memory);
  for (int i = 0; i < variable_count; i++) {
    int k = variable_addresses[i];
    suffix_memory[k] = layout->code[layout_offset[k] - 1];
  }
  suffix_memory[key] = glyph_override;
  ++epoch;
  recording = 1;
  live_count = 0;
  State state = *start;
  int count = 0,
      tap = printer_entry[z] + lookup_tap[layout->order[z]] - lookup_tap[z],
      hit = 0;
  checked_key = key;
  checked_tap = tap;
  while (count++ < 2000) {
    if (state.c == tap) {
      if (state.d != key) {
        fprintf(stderr, "bad tap row%d marker%d raw%d setting%d D%d expect%d\n",
                row, marker, raw, setting, state.d, key);
        exit(2);
      }
      hit++;
    }
    if (!step(&state, suffix_memory, row))
      break;
  }
  recording = 0;
  covered[setting] = 1;
  suffix_runs++;
  int want = (hub == 41551) ^ ((layout->flip >> z) & 1);
  if (count >= 2000 || opcode(suffix_memory[state.c], state.c) != 'v' ||
      state.reads != 17 || state.outputs != 1 || state.out != 48 + want ||
      hit != 1) {
    fprintf(stderr,
            "bad suffix row%d k%d raw%d cp%d marker%d z%d setting%d tap%d "
            "out%d want%d pc%d\n",
            row, word, raw, lookup_glyph, marker, z, setting, hit, state.out,
            want, state.c);
    exit(2);
  }
}

/* Reuse a suffix only when its initial registers, slot, marker and every
 * cell read before its first write give the same execution. Layout bytes
 * are checked separately from the prefix-dependent register and code cells. */
static void verify_suffix(State *start, int lookup_glyph, int marker, int z,
                          int row, int word, int raw) {
  SuffixClass *f = &classes[lookup_glyph - 33][marker][z];
  while (f->n) {
    int i = 0;
    while (i < f->n &&
           ((trit_mask[memory[f->cells[i]]] & f->allowed_trits[i]) ==
            trit_mask[memory[f->cells[i]]]))
      i++;
    if (i == f->n)
      return;
    if (!f->next) {
      f->next = calloc(1, sizeof(SuffixClass));
      assert(f->next);
      extra_classes++;
    }
    f = f->next;
  }
  unsigned int requirements[WORDS] = {0};
  int required_cells[WORDS], size = 0, done[SETTINGS] = {0};
  prefix = 0;
  for (int t = 0; t < models; t++) {
    if (done[t])
      continue;
    Layout *l = layouts + t;
    int key = 5113 + 3 * lookup_glyph + lookup_tap[l->order[z]] - marker;
    int byte =
        layout_offset[key] ? l->code[layout_offset[key] - 1] : initial[key];

    int glyph_choices[2] = {byte, 0};
    if (key >= 5213 && key < 5548 && key % 3 != 1 && layout_changes[key]) {
      glyph_choices[0] = native_lookup_domains[key - 5213][0];
      glyph_choices[1] = native_lookup_domains[key - 5213][1];
    }
    int layout_reads[585], read_count = 0, ran = 0;
    unsigned char read_layout[585] = {0};
    for (int choice = 0; choice < 2; choice++) {
      int alternate = glyph_choices[choice];
      if (!alternate)
        continue;
      int hub = hubs[alternate];
      if (hub != 41551 && hub != 45925 && !(l->order[z] && hub == 54673))
        continue;
      ran = 1;
      run_printer(start, t, z, key, hub, row, word, raw, marker, lookup_glyph,
                  alternate);
      for (int i = 0; i < live_count; i++) {
        int k = live[i];
        if (layout_changes[k]) {
          int offset = layout_offset[k] - 1;
          if (!read_layout[offset]) {
            read_layout[offset] = 1;
            layout_reads[read_count++] = offset;
          }
        } else {
          unsigned int val = equivalent_trits(first_crazy_a[k], memory[k]);
          if (!requirements[k]) {
            requirements[k] = val;
            required_cells[size++] = k;
          } else
            requirements[k] &= val;
        }
      }
    }
    if (!ran)
      continue;
    for (int u = t + 1; u < models; u++) {
      const Layout *q = layouts + u;
      if ((layout_offset[key] && q->code[layout_offset[key] - 1] != byte) ||
          done[u] || l->order[z] != q->order[z] ||
          ((l->flip ^ q->flip) >> z & 1))
        continue;
      int j = 0;
      while (j < read_count &&
             l->code[layout_reads[j]] == q->code[layout_reads[j]])
        j++;
      if (j == read_count) {
        done[u] = 1;
        covered[u] = 1;
        equivalent_layouts++;
      }
    }
  }
  prefix = 1;
  if (!size)
    return;
  f->n = size;
  f->cells = malloc(sizeof(*f->cells) * size);
  f->allowed_trits = malloc(sizeof(*f->allowed_trits) * size);
  assert(f->cells && f->allowed_trits);
  if (size > max_live)
    max_live = size;
  /* Register 146 distinguishes most unequal suffix states. */
  for (int j = 1; j < size; j++)
    if (required_cells[j] == 146) {
      required_cells[j] = required_cells[0];
      required_cells[0] = 146;
      break;
    }
  for (int i = 0; i < size; i++) {
    int k = required_cells[i];
    f->cells[i] = k;
    f->allowed_trits[i] = requirements[k];
    if (operand_values[k][0] > 1 ||
        (k >= 51031 && k <= 51759 && (k - 51031) % 3 == 0)) {
      fprintf(stderr,
              "suffix live data row%d k%d cp%d marker%d z%d mutable%d\n", row,
              word, lookup_glyph, marker, z, k);
      exit(3);
    }
  }
}

int main(void) {
  load_inputs();
  read_file("lookup-domains", native_lookup_domains,
            sizeof native_lookup_domains);
  for (int k = 0; k < WORDS; k++)
    if (operand_values[k][0])
      column_marker[51031 + 3 * ((k - 1) % 243)] = 1;
  load_layouts();
  int n = 131072, markers = 0, operand_cases = 0, marker_joins = 0, keys = 0,
      max_prefix_slice = 0;
  prefix = 1;
  for (int row = 0; row < n; row++) {
    memcpy(before_marker, initial, sizeof(initial));
    State state = {0};
    assert(run_to(&state, before_marker, row, 38469, 12000) >= 0);
    int k = row % 4 == 3 ? spill_words[row / 4] : primary_words[row / 4],
        z = row % 4 == 3 ? slots[row / 4] : row % 4,
        where = 51031 + 3 * ((k - 1) % 243),
        high = initial[(k - 1) / 243 * 243 + 79];
    assert(state.d == where && state.reads == 17 && !state.outputs);
    State payload = state;
    memcpy(before_payload, before_marker, sizeof(before_payload));
    assert(run_to(&payload, before_payload, row, 6220, 2000) >= 0);
    assert(payload.d == k && payload.a == 59048);
    /* Only the rotated marker and register 140 depend on the column choice. */
    for (int o = 0; o < 8; o++) {
      int marker = glyph("ji*p</vo"[o], where);
      if (marker < 83)
        continue;
      markers++;
      State alt = state;
      memcpy(marked_memory, before_marker, sizeof(before_marker));
      marked_memory[where] = marker;
      assert(run_to(&alt, marked_memory, row, 6220, 2000) >= 0);
      assert(!memcmp(&alt, &payload, sizeof(State)));
      Word saved_register = marked_memory[140],
           rotated_marker = marked_memory[where];
      marked_memory[140] = before_payload[140];
      marked_memory[where] = before_payload[where];
      assert(!memcmp(marked_memory, before_payload, sizeof(before_payload)));
      marked_memory[140] = saved_register;
      marked_memory[where] = rotated_marker;
      marker_joins++;
      /* At 5656 the accumulator, restored payload and lookup address have a
       * closed form, independent of the choice of printer. */
      for (int j = 1; j <= operand_values[k][0]; j++) {
        int raw = operand_values[k][j];
        State current = alt;
        memcpy(memory, marked_memory, sizeof(memory));
        memory[k] = raw;
        if (k == 39391 && raw != glyph('<', 39391) &&
            (memory[39394] == glyph('j', 39394) ||
             memory[39394] == glyph('v', 39394)))
          memory[39394] = glyph('o', 39394);
        if (k == 39394 &&
            (raw == glyph('j', 39394) || raw == glyph('v', 39394)))
          memory[39391] = glyph('<', 39391);
        int len = run_to(&current, memory, row, 5656, 3000);
        if (len < 0) {
          printf("stage miss row %d k %d raw %d marker %d pc %d\n", row, k, raw,
                 marker, current.c);
          return 1;
        }
        int lookup_glyph = glyph('p', 19745 + high - raw),
            expect = 5113 + 3 * lookup_glyph;
        if (current.d != expect || current.a != 29524 || current.reads != 17 ||
            current.outputs || memory[k] != raw) {
          printf("stage diff row %d k %d raw %d marker %d got D%d want %d A%d "
                 "restored %d\n",
                 row, k, raw, marker, current.d, expect, current.a, memory[k]);
          return 1;
        }
        verify_suffix(&current, lookup_glyph, marker, z, row, k, raw);
        operand_cases++;
        if (len > max_prefix_slice)
          max_prefix_slice = len;
        if (!checkpoint[lookup_glyph - 33][marker][z]) {
          checkpoint[lookup_glyph - 33][marker][z] = 1;
          keys++;
        }
      }
    }
  }
  for (int t = 0; t < models; t++)
    assert(covered[t]);
  FILE *flow = fopen("edges", "w");
  assert(flow);
  for (int k = 0; k < WORDS; k++) {
    if (fallthrough[k])
      fprintf(flow, "%d %d\n", k, (k + 1) % WORDS);
    if (jump_id[k])
      for (int q = 0; q < WORDS; q++)
        if (jump_edges[jump_id[k]][q])
          fprintf(flow, "%d %d\n", k, q);
  }
  fclose(flow);
  printf("ordinary and shadow navigation proofs %ld, shadows %ld, conditioned "
         "%ld\n",
         navigation_checks, shadow_checks, conditioned_checks);
  printf("suffix executions %ld, reused %ld, highest live set %d, all verified "
         "%d splits %d\n",
         suffix_runs, equivalent_layouts, max_live, models, extra_classes);
  printf("rows %d markers %d joined %d raw+marker %d canonical keys %d max "
         "slice %d reads of layout-dependent cells %d\n",
         n, markers, marker_joins, operand_cases, keys, max_prefix_slice,
         early_layout_reads);
  printf("Universal guard states %ld, glyph alternatives %ld\n", guard_checks,
         guard_glyphs);
  return early_layout_reads != 0;
}
