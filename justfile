# Task runner for the project

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# Tool paths
HOMEBREW_BIN := "/opt/homebrew/bin"
LLVM_BIN := `command -v brew >/dev/null 2>&1 && echo "$(brew --prefix llvm)/bin" || echo ""`
CARGO_BIN := "$HOME/.cargo/bin"

# Help
help:
    @echo "Available targets:"
    @echo "  lint-python  - Lint Python files with Black, Ruff, and MyPy"
    @echo "  lint-rust    - Lint Rust files with rustfmt and clippy"
    @echo "  lint-lean    - Lint Lean files with lean linter"
    @echo "  lint         - Run all linting targets"
    @echo "  test         - Run the full local check (lint, pytest, bandit, cargo)"
    @echo "  install-dev  - Install development dependencies"
    @echo "  clean        - Clean up generated files"

# install tooling
install-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv >/dev/null 2>&1; then
        echo "Using uv..."
        uv pip install -e ".[dev]"
    else
        echo "Using pip..."
        python -m pip install -U pip
        pip install -e ".[dev]"
    fi

# lint python
lint-python:
    {{PYTHON}} -m black --check .
    {{PYTHON}} -m ruff check .
    {{PYTHON}} -m mypy src

# Lint helpers.  Each target fails loudly when its tool is present and the
# code is unclean, and skips cleanly (exit 0) when the tool is missing, so a
# local `just lint` degrades gracefully without silently swallowing failures.

# lint rust
lint-rust:
    #!/usr/bin/env bash
    set -euo pipefail
    export PATH="{{CARGO_BIN}}:$PATH"
    if command -v rustfmt >/dev/null 2>&1; then
        fail=0
        while IFS= read -r f; do
            rustfmt --check "$f" || fail=1
        done < <(find extra/rust -name "*.rs")
        exit $fail
    fi
    if command -v cargo >/dev/null 2>&1; then
        (cd extra/rust && cargo clippy)
    else
        echo "skip: cargo not found"
    fi

# lint lean
lint-lean:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v lake >/dev/null 2>&1; then
        (cd extra/lean/esolangs && lake build)
    else
        echo "skip: lake (Lean 4) not found"
    fi

# lint all code
lint: lint-python lint-rust lint-lean
    @echo "All lint checks completed!"

# test (full local check: lint, pytest, bandit, cargo, verify scripts)
test:
    sh scripts/check_all.sh

# clean generated
clean:
    #!/usr/bin/env bash
    find . \( -name "*.pyc" -o -name "__pycache__" -o -name "*.egg-info" -o -name "*.o" -o -name "*.so" -o -name "*.dylib" -o -name "*.exe" \) -delete 2>/dev/null || true
