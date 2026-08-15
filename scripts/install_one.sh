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
# The language name matches `esolangs list` (e.g. "brainfuck", "Nevermind",
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

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! curl -fsSL "$base/scripts/bundle_one.py" -o "$tmp/bundle_one.py"; then
    echo "install_one: could not fetch bundle_one.py from $base" >&2
    exit 1
fi

python3 "$tmp/bundle_one.py" --base "$base" "$lang"
