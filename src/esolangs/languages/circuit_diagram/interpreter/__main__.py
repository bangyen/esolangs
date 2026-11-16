"""Run a Circuit Diagram source file through the shared interpreter entry point."""

from esolangs.languages.circuit_diagram.interpreter import run
from esolangs.runtime._entry import script_main
from esolangs.runtime._source import native_text_source

if __name__ == "__main__":
    script_main(run, shape="strip", loader=native_text_source)
