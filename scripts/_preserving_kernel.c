#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* With 512 classes, 256 DFA rows, 16 loop types and values <= 10^10,
   every accumulated product is below 2^128. The Python checker remains
   responsible for the resulting supersolution, independently of this code. */
typedef unsigned __int128 wide;

static int image(const int *rows, const int *edges, const int *types,
                 const int *starts, const int *positions, int n, int s,
                 int k, int h, uint64_t a, uint64_t b, uint64_t scale,
                 const uint64_t *value, uint64_t *result, wide *sum,
                 uint64_t *loops) {
    size_t count = (size_t)s * h * n;
    memset(sum, 0, count * sizeof(*sum));
    memset(loops, 0, (size_t)k * h * n * sizeof(*loops));
    for (int c = 0; c < s; ++c) {
        if (types[c] < 0) continue;
        for (int i = 0; i < h; ++i) {
            for (int j = 0; j < n; ++j) {
                int end = rows[8*j+7];
                if (end >= 0)
                    loops[((size_t)types[c]*h+i)*n+end] +=
                        value[((size_t)c*h+i)*n+j];
            }
        }
    }
    wide literal = (wide)a*b*scale;
    uint64_t loop_weight = b*b;
    for (int c = 0; c < s; ++c) {
        for (int i = 0; i < h; ++i) {
            /* At most 256 weights <= 10^10: the grouped sum fits uint64_t. */
            uint64_t grouped[16] = {0};
            for (int j = 0; j < n; ++j) {
                uint64_t left = value[((size_t)c*h+i)*n+j];
                if (!left) continue;
                for (int column = 0; column < 6; ++column) {
                    int target = edges[c*(6+k)+column];
                    int end = rows[8*j+column];
                    if (target >= 0 && end >= 0)
                        sum[((size_t)target*h+i)*n+end] += literal*left;
                }
                int middle = rows[8*j+6];
                if (middle < 0) continue;
                grouped[positions[middle]] += left;
            }
            for (int position = 0; position < h; ++position) {
                uint64_t left = grouped[position];
                if (!left) continue;
                for (int column = 0; column < k; ++column) {
                    int target = edges[c*(6+k)+6+column];
                    if (target < 0) continue;
                    size_t output = ((size_t)target*h+i)*n;
                    size_t input = ((size_t)column*h+position)*n;
                    wide weight = (wide)loop_weight*left;
                    for (int end = 0; end < n; ++end) {
                        uint64_t right = loops[input+end];
                        if (right) sum[output+end] += weight*right;
                    }
                }
            }
        }
    }
    memset(sum, 0, (size_t)h*n*sizeof(*sum));
    for (int i = 0; i < h; ++i)
        sum[(size_t)i*n+starts[i]] = (wide)a*a*scale*scale;
    wide divisor = (wide)a*a*scale;
    for (size_t i = 0; i < count; ++i) {
        wide entry = (sum[i]+divisor-1)/divisor;
        if (entry > 100*scale) return -2;
        result[i] = (uint64_t)entry;
    }
    return 0;
}

int construct(const int *rows, const int *edges, const int *types,
              const int *starts, const int *positions, int n, int s,
              int k, int h, uint64_t a, uint64_t b, uint64_t scale,
              uint64_t *output) {
    if (n < 1 || n > 256 || s < 1 || s > 512 || k < 1 || k > 16 ||
        h < 1 || h > 16 || a < 1 || a > 2048 || b < 1 || b > 512 ||
        scale != 100000000) return -1;
    size_t count = (size_t)s*h*n;
    uint64_t *value = calloc(count, sizeof(*value));
    uint64_t *next = calloc(count, sizeof(*next));
    uint64_t *candidate = calloc(count, sizeof(*candidate));
    uint64_t *tested = calloc(count, sizeof(*tested));
    uint64_t *loops = calloc((size_t)k*h*n, sizeof(*loops));
    wide *sum = calloc(count, sizeof(*sum));
    int status = -4;
    if (!value || !next || !candidate || !tested || !loops || !sum) goto done;
    for (int i = 0; i < h; ++i) value[(size_t)i*n+starts[i]] = scale;
    struct timespec began, now;
    timespec_get(&began, TIME_UTC);
    for (int iteration = 0; iteration < 1500; ++iteration) {
        status = image(rows, edges, types, starts, positions, n, s, k, h,
                       a, b, scale, value, next, sum, loops);
        if (status) goto done;
        if (!memcmp(value, next, count*sizeof(*value))) {
            memcpy(output, next, count*sizeof(*output));
            status = iteration+1;
            goto done;
        }
        if (iteration % 20 == 19) {
            int within_budget = 1;
            for (size_t i = 0; i < count; ++i) {
                candidate[i] = (next[i]*10001+9999)/10000;
                if (candidate[i] > 100*scale) within_budget = 0;
            }
            if (!within_budget) goto advance;
            status = image(rows, edges, types, starts, positions, n, s, k, h,
                           a, b, scale, candidate, tested, sum, loops);
            if (status) goto done;
            int dominated = 1;
            for (size_t i = 0; i < count; ++i)
                if (tested[i] > candidate[i]) { dominated = 0; break; }
            if (dominated) {
                memcpy(output, candidate, count*sizeof(*output));
                status = iteration+1;
                goto done;
            }
        }
advance:;
        uint64_t *swap = value; value = next; next = swap;
        timespec_get(&now, TIME_UTC);
        if (now.tv_sec-began.tv_sec >= 40) { status = -3; goto done; }
    }
    status = -5;
done:
    free(value); free(next); free(candidate); free(tested); free(loops); free(sum);
    return status;
}
