import sys
sys.path.insert(0, "src")
from esolangs.tools.boolean import parameterized
from esolangs.interpreters.grid_based import cod  # noqa: F401

print("imports ok")
print("minifuck 0110:", len(parameterized.minifuck("0110")), "chars")
print("cod 0110:", len(parameterized.cod("0110")), "chars")
