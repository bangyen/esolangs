# Makefile for esolangs project
# Provides linting targets for all languages used in the project

.PHONY: help lint lint-python lint-c lint-cpp lint-rust lint-ruby lint-lean lint-r lint-asm lint-all clean test install-dev

# Default target
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
	@echo "  lint-all     - Alias for lint"
	@echo "  test         - Run Python tests with pytest"
	@echo "  install-dev  - Install development dependencies"
	@echo "  clean        - Clean up generated files"

# Python linting (already configured in pyproject.toml)
lint-python:
	@echo "Running Python linting..."
	@echo "Formatting with Black..."
	black --check .
	@echo "Linting with Ruff..."
	ruff check .
	@echo "Type checking with MyPy..."
	mypy .

# C linting
lint-c:
	@echo "Running C linting..."
	@if command -v clang-format >/dev/null 2>&1; then \
		echo "Checking C formatting with clang-format..."; \
		find compilers/c -name "*.c" -exec clang-format --dry-run --Werror {} \; || \
		echo "Warning: clang-format found formatting issues. Run 'clang-format -i compilers/c/*.c' to fix."; \
	else \
		echo "Warning: clang-format not found. Install with: brew install clang-format"; \
	fi
	@if command -v clang-tidy >/dev/null 2>&1; then \
		echo "Running clang-tidy on C files..."; \
		find compilers/c -name "*.c" -exec clang-tidy {} \; || true; \
	else \
		echo "Warning: clang-tidy not found. Install with: brew install llvm"; \
	fi

# C++ linting
lint-cpp:
	@echo "Running C++ linting..."
	@if command -v clang-format >/dev/null 2>&1; then \
		echo "Checking C++ formatting with clang-format..."; \
		find extra/c++ -name "*.cpp" -exec clang-format --dry-run --Werror {} \; || \
		echo "Warning: clang-format found formatting issues. Run 'clang-format -i extra/c++/*.cpp' to fix."; \
	else \
		echo "Warning: clang-format not found. Install with: brew install clang-format"; \
	fi
	@if command -v clang-tidy >/dev/null 2>&1; then \
		echo "Running clang-tidy on C++ files..."; \
		find extra/c++ -name "*.cpp" -exec clang-tidy {} \; || true; \
	else \
		echo "Warning: clang-tidy not found. Install with: brew install llvm"; \
	fi

# Rust linting
lint-rust:
	@echo "Running Rust linting..."
	@if command -v rustfmt >/dev/null 2>&1; then \
		echo "Checking Rust formatting with rustfmt..."; \
		find extra/rust -name "*.rs" -exec rustfmt --check {} \; || \
		echo "Warning: rustfmt found formatting issues. Run 'rustfmt extra/rust/*.rs' to fix."; \
	else \
		echo "Warning: rustfmt not found. Install Rust toolchain."; \
	fi
	@if command -v cargo >/dev/null 2>&1; then \
		echo "Running clippy on Rust files..."; \
		cd extra/rust && cargo clippy || true; \
	else \
		echo "Warning: cargo not found. Install Rust toolchain."; \
	fi

# Ruby linting
lint-ruby:
	@echo "Running Ruby linting..."
	@if command -v ruby >/dev/null 2>&1 && command -v rubocop >/dev/null 2>&1; then \
		echo "Running rubocop on Ruby files..."; \
		rubocop extra/ruby/ || true; \
	else \
		echo "Warning: Ruby or rubocop not found. Install with: brew install ruby && gem install rubocop"; \
	fi

# Lean linting
lint-lean:
	@echo "Running Lean linting..."
	@if command -v lean >/dev/null 2>&1; then \
		echo "Checking Lean files..."; \
		if lean --version >/dev/null 2>&1; then \
			find extra/lean -name "*.lean" -exec lean --check {} \; || true; \
		else \
			echo "Warning: Lean 3 not available on ARM64. Files are Lean 3 syntax and require x86_64 or Lean 4 conversion."; \
		fi; \
	else \
		echo "Warning: lean not found. Install Lean 4 with: elan toolchain install stable && elan default stable"; \
	fi

# R linting
lint-r:
	@echo "Running R linting..."
	@if command -v Rscript >/dev/null 2>&1; then \
		if Rscript -e "if (!require('lintr', quietly=TRUE)) install.packages('lintr', repos='https://cran.rstudio.com/')" 2>/dev/null; then \
			echo "Running lintr on R files..."; \
			Rscript -e "lintr::lint_dir('extra/r')" || true; \
		else \
			echo "Warning: Could not install or load lintr package."; \
		fi; \
	else \
		echo "Warning: R not found. Install R."; \
	fi

# Assembly basic syntax checking
lint-asm:
	@echo "Running Assembly syntax checking..."
	@if command -v nasm >/dev/null 2>&1; then \
		echo "Checking Assembly syntax with nasm..."; \
		find extra/assembly -name "*.asm" -exec nasm -f elf64 -o /dev/null {} \; 2>/dev/null || \
		echo "Note: Some assembly files may not be x86-64 compatible or have syntax issues."; \
	else \
		echo "Warning: nasm not found. Install with: brew install nasm"; \
	fi

# Run all linting targets
lint: lint-python lint-c lint-cpp lint-rust lint-ruby lint-lean lint-r lint-asm

# Alias for lint
lint-all: lint

# Python testing
test:
	@echo "Running Python tests..."
	pytest

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install -e ".[dev]"

# Clean up generated files
clean:
	@echo "Cleaning up generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.o" -delete
	find . -type f -name "*.so" -delete
	find . -type f -name "*.dylib" -delete
	find . -type f -name "*.exe" -delete
