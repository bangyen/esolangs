"""Run an Alight source file through the shared interpreter entry point."""

from esolangs.languages.alight.interpreter import run
from esolangs.runtime._entry import script_main

if __name__ == "__main__":
    script_main(run, shape="strip")
