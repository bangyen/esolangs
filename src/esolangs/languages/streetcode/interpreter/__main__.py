"""Run a Streetcode program file."""

from esolangs.languages.streetcode.interpreter import run
from esolangs.runtime._entry import script_main

if __name__ == "__main__":
    script_main(run, shape="strip")
