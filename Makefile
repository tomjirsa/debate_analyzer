.PHONY: help reset_venv test deploy clean format lint typecheck all

# Default target
help:
	@echo "Available targets:"
	@echo "  make reset_venv  - Remove and recreate virtual environment"
	@echo "  make test        - Run tests with coverage"
	@echo "  make deploy      - Build and deploy package"
	@echo "  make clean       - Remove build artifacts and caches"
	@echo "  make format      - Format code with black"
	@echo "  make lint        - Run ruff linter"
	@echo "  make typecheck   - Run mypy type checker"
	@echo "  make all         - Run format, lint, typecheck, and test"

# Reset virtual environment
reset_venv:
	@echo "Removing existing virtual environment..."
	@poetry env remove --all || true
	@echo "Installing dependencies..."
	@poetry install --extras transcribe --extras webapp
	@echo "Virtual environment reset complete!"

# Run tests with coverage
test:
	@echo "Running tests with coverage..."
	@poetry run pytest

# Build and deploy
deploy: test
	@echo "Building package..."
	@poetry build
	@echo "Publishing package..."
	@poetry publish
	@echo "Deployment complete!"

# Clean build artifacts and caches
clean:
	@echo "Cleaning build artifacts and caches..."
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -rf .ruff_cache/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete!"

# Format code
format:
	@echo "Formatting code with black..."
	@poetry run black src/ tests/
	@echo "Formatting complete!"

# Run linter
lint:
	@echo "Running ruff linter..."
	@poetry run ruff check src/ tests/
	@echo "Linting complete!"

# Run type checker
typecheck:
	@echo "Running mypy type checker..."
	@poetry run mypy src/
	@echo "Type checking complete!"

# Run all checks
all: format lint typecheck test
	@echo "All checks passed!"
