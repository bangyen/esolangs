import time
import sys
sys.path.insert(0, "src")
import full_gen2

t0 = time.time()
prog, how = full_gen2.build("0001")
dt = time.time() - t0
label = f"OK len={len(prog)} via {how}" if prog else "no program"
print(f"RESULT AND(0001): {label}  {dt:.1f}s")
