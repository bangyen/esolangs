#!/bin/sh
# Download one esolang interpreter as a single self-contained file.
#
#   curl -fsSL https://raw.githubusercontent.com/bangyen/esolangs/main/scripts/install_one.sh | sh -s <language>
#
# Fetches the interpreter and the shared esolangs.exceptions /
# esolangs.interpreters.io modules from the repository and inlines them into
# one file, esolangs_<language>.py, in the current directory:
#
#   python esolangs_brainfuck.py program.txt
#
# The language name matches `esolangs list` (e.g. "brainfuck", "Modulous",
# "Forþ").  Override the repository base with $ESOLANGS_BASE to install from
# a fork or a tag.
set -eu

lang="${1:-}"
base="${ESOLANGS_BASE:-https://raw.githubusercontent.com/bangyen/esolangs/main}"

if [ -z "$lang" ]; then
    echo "usage: install_one.sh <language>" >&2
    echo "  curl -fsSL $base/scripts/install_one.sh | sh -s <language>" >&2
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "install_one: python3 is required" >&2
    exit 1
fi

# And a python3 new enough to run what this installs.  The interpreters use
# PEP 695 type aliases, so an older one gets a SyntaxError out of a file it
# just downloaded, pointing at a line it did not write.  Checked here, where
# the message can name the version, rather than left to the bundle.
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    have="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    echo "install_one: python3 3.12 or newer is required, found $have" >&2
    echo "  the interpreters use syntax $have cannot parse" >&2
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! curl -fsSL "$base/scripts/bundle_one.py" -o "$tmp/bundle_one.py"; then
    echo "install_one: could not fetch bundle_one.py from $base" >&2
    exit 1
fi

python3 "$tmp/bundle_one.py" --base "$base" "$lang"
