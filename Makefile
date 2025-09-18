# Makefile for esolangs project

# Configuration
PYTHON = venv/bin/python
PIP = venv/bin/pip
BLACK = venv/bin/black
RUFF = venv/bin/ruff
MYPY = venv/bin/mypy
PYTEST = venv/bin/pytest

# Tool paths
HOMEBREW_BIN = /opt/homebrew/bin
LLVM_BIN = /opt/homebrew/Cellar/llvm/21.1.1/bin
CARGO_BIN = $(HOME)/.cargo/bin
RUBY_BIN = /opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.4.0/bin

# Common functions
define setup_path
	@export PATH="$(1):$$PATH"
endef

define run_tool
	if command -v $(1) >/dev/null 2>&1; then \
		$(2); \
	else \
		echo "Warning: $(1) not found. $(3)"; \
	fi
endef

define lint_c_cpp
	$(call setup_path,$(HOMEBREW_BIN):$(LLVM_BIN)) && \
	$(call run_tool,clang-format, \
		find $(1) -name "$(2)" \
			-exec clang-format --dry-run --Werror {} \; || \
		echo "Warning: clang-format found formatting issues. \
			Run 'clang-format -i $(3)' to fix.", \
		Install with: brew install clang-format) && \
	$(call run_tool,clang-tidy, \
		find $(1) -name "$(2)" \
			-exec clang-tidy --quiet --warnings-as-errors=* {} \; \
			2>/dev/null || \
		echo "Note: clang-tidy found issues or missing compilation database \
			(expected for standalone files)", \
		Install with: brew install llvm)
endef

.PHONY: help lint lint-python lint-c lint-cpp lint-rust lint-ruby lint-lean lint-r lint-asm clean test install-dev

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

lint-python:
	$(BLACK) --check .
	$(RUFF) check .
	$(MYPY) .

lint-c:
	$(call lint_c_cpp,src/esolangs/compilers/c,*.c,src/esolangs/compilers/c/*.c)

lint-cpp:
	$(call lint_c_cpp,extra/c++,*.cpp,extra/c++/*.cpp)

lint-rust:
	$(call setup_path,$(CARGO_BIN)) && \
	$(call run_tool,rustfmt, \
		find extra/rust -name "*.rs" \
			-exec rustfmt --check {} \; || \
		echo "Warning: rustfmt found formatting issues. \
			Run 'rustfmt extra/rust/*.rs' to fix.", \
		Install Rust toolchain) && \
	$(call run_tool,cargo, \
		cd extra/rust && cargo clippy || true, \
		Install Rust toolchain)

lint-ruby:
	$(call setup_path,$(RUBY_BIN)) && \
	$(call run_tool,rubocop, \
		rubocop extra/ruby/ || true, \
		Install with: brew install ruby && gem install rubocop)

lint-lean:
	@if command -v lean4 >/dev/null 2>&1; then \
		find extra/lean -name "*.lean" \
			-exec lean4 --check {} \; || true; \
	elif command -v lean >/dev/null 2>&1 && \
		lean --version 2>&1 | grep -q "Lean 4" >/dev/null 2>&1; then \
		find extra/lean -name "*.lean" \
			-exec lean --check {} \; || true; \
	else \
		echo "Warning: Lean 4 not found. \
			Install Lean 4 with: elan toolchain install stable && \
			elan default stable"; \
		echo "Note: Current 'lean' command is LeanCloud CLI, \
			not Lean theorem prover."; \
	fi

lint-r:
	$(call run_tool,Rscript, \
		Rscript -e "if (!require('lintr', quietly=TRUE)) \
			install.packages('lintr', repos='https://cran.rstudio.com/')" \
			2>/dev/null && \
		Rscript -e "lintr::lint_dir('extra/r')" || true, \
		Install R)

lint-asm:
	$(call run_tool,nasm, \
		find extra/assembly -name "*.asm" \
			-exec nasm -f elf64 -o /dev/null {} \; 2>/dev/null || \
		echo "Note: Some assembly files may not be x86-64 compatible \
			or have syntax issues.", \
		Install with: brew install nasm)

lint: lint-python lint-c lint-cpp lint-rust lint-ruby lint-lean lint-r lint-asm

test:
	$(PYTEST)

install-dev:
	$(PIP) install -e ".[dev]"

clean:
	find . \( \
		-name "*.pyc" \
		-o -name "__pycache__" \
		-o -name "*.egg-info" \
		-o -name "*.o" \
		-o -name "*.so" \
		-o -name "*.dylib" \
		-o -name "*.exe" \
	\) -delete 2>/dev/null || true
