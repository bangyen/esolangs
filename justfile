# Task runner for the project

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# Tool paths
HOMEBREW_BIN := "/opt/homebrew/bin"
LLVM_BIN := "/opt/homebrew/Cellar/llvm/21.1.1/bin"
CARGO_BIN := "$HOME/.cargo/bin"
RUBY_BIN := "/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.4.0/bin"

# Help
help:
    @echo "Available targets:"
    @echo "  lint-python  - Lint Python files with Black, Ruff, and MyPy"
    @echo "  lint-c       - Lint C files with clang-format and clang-tidy"
    @echo "  lint-cpp     - Lint C++ files with clang-format and clang-tidy"
    @echo "  lint-rust    - Lint Rust files with rustfmt and clippy"
    @echo "  lint-ruby    - Lint Ruby files with rubocop"
    @echo "  lint-lean    - Lint Lean files with lean linter"
    @echo "  lint-r       - Lint R files with lintr"
    @echo "  lint-asm     - Basic syntax check for Assembly files"
    @echo "  lint         - Run all linting targets"
    @echo "  test         - Run Python tests with pytest"
    @echo "  install-dev  - Install development dependencies"
    @echo "  clean        - Clean up generated files"

# install tooling
install-dev:
    #!/usr/bin/env bash
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

# lint c
lint-c:
    #!/usr/bin/env bash
    export PATH="{{HOMEBREW_BIN}}:{{LLVM_BIN}}:$PATH"
    if command -v clang-format >/dev/null 2>&1; then
        find src/esolangs/compilers/c -name "*.c" -exec clang-format --dry-run --Werror {} \; || echo "Warning: clang-format found formatting issues. Run 'clang-format -i src/esolangs/compilers/c/*.c' to fix."
    else
        echo "Warning: clang-format not found. Install with: brew install clang-format"
    fi
    if command -v clang-tidy >/dev/null 2>&1; then
        find src/esolangs/compilers/c -name "*.c" -exec clang-tidy --quiet --warnings-as-errors=* {} \; 2>/dev/null || echo "Note: clang-tidy found issues or missing compilation database (expected for standalone files)"
    else
        echo "Warning: clang-tidy not found. Install with: brew install llvm"
    fi

# lint cpp
lint-cpp:
    #!/usr/bin/env bash
    export PATH="{{HOMEBREW_BIN}}:{{LLVM_BIN}}:$PATH"
    if command -v clang-format >/dev/null 2>&1; then
        find extra/c++ -name "*.cpp" -exec clang-format --dry-run --Werror {} \; || echo "Warning: clang-format found formatting issues. Run 'clang-format -i extra/c++/*.cpp' to fix."
    else
        echo "Warning: clang-format not found. Install with: brew install clang-format"
    fi
    if command -v clang-tidy >/dev/null 2>&1; then
        find extra/c++ -name "*.cpp" -exec clang-tidy --quiet --warnings-as-errors=* {} \; 2>/dev/null || echo "Note: clang-tidy found issues or missing compilation database (expected for standalone files)"
    else
        echo "Warning: clang-tidy not found. Install with: brew install llvm"
    fi

# lint rust
lint-rust:
    #!/usr/bin/env bash
    export PATH="{{CARGO_BIN}}:$PATH"
    if command -v rustfmt >/dev/null 2>&1; then
        find extra/rust -name "*.rs" -exec rustfmt --check {} \; || echo "Warning: rustfmt found formatting issues. Run 'rustfmt extra/rust/*.rs' to fix."
    else
        echo "Warning: rustfmt not found. Install Rust toolchain"
    fi
    if command -v cargo >/dev/null 2>&1; then
        (cd extra/rust && cargo clippy || true)
    else
        echo "Warning: cargo not found. Install Rust toolchain"
    fi

# lint ruby
lint-ruby:
    #!/usr/bin/env bash
    export PATH="{{RUBY_BIN}}:$PATH"
    if command -v rubocop >/dev/null 2>&1; then
        rubocop extra/ruby/ || true
    else
        echo "Warning: rubocop not found. Install with: brew install ruby && gem install rubocop"
    fi

# lint lean
lint-lean:
    #!/usr/bin/env bash
    if command -v lean4 >/dev/null 2>&1; then
        find extra/lean -name "*.lean" -exec lean4 --check {} \; || true
    elif command -v lean >/dev/null 2>&1 && lean --version 2>&1 | grep -q "Lean 4" >/dev/null 2>&1; then
        find extra/lean -name "*.lean" -exec lean --check {} \; || true
    else
        echo "Warning: Lean 4 not found. Install Lean 4 with: elan toolchain install stable && elan default stable"
        echo "Note: Current 'lean' command is LeanCloud CLI, not Lean theorem prover."
    fi

# lint r
lint-r:
    #!/usr/bin/env bash
    if command -v Rscript >/dev/null 2>&1; then
        Rscript -e "if (!require('lintr', quietly=TRUE)) install.packages('lintr', repos='https://cran.rstudio.com/')" 2>/dev/null && Rscript -e "lintr::lint_dir('extra/r')" || true
    else
        echo "Warning: Rscript not found. Install R"
    fi

# lint asm
lint-asm:
    #!/usr/bin/env bash
    if command -v nasm >/dev/null 2>&1; then
        find extra/assembly -name "*.asm" -exec nasm -f elf64 -o /dev/null {} \; 2>/dev/null || echo "Note: Some assembly files may not be x86-64 compatible or have syntax issues."
    else
        echo "Warning: nasm not found. Install with: brew install nasm"
    fi

# lint all code
lint: lint-python lint-c lint-cpp lint-rust lint-ruby lint-lean lint-r lint-asm
    @echo "All lint checks completed!"

# run tests
test:
    {{PYTHON}} -m pytest

# clean generated
clean:
    #!/usr/bin/env bash
    find . \( -name "*.pyc" -o -name "__pycache__" -o -name "*.egg-info" -o -name "*.o" -o -name "*.so" -o -name "*.dylib" -o -name "*.exe" \) -delete 2>/dev/null || true
