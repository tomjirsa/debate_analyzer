.PHONY: help reset_venv test deploy clean format lint typecheck all stats-local webapp-stop webapp-api webapp-frontend webapp-start

# Default target
help:
	@echo "Available targets:"
	@echo "  make reset_venv   - Remove and recreate virtual environment"
	@echo "  make test        - Run tests with coverage"
	@echo "  make deploy      - Build and deploy package"
	@echo "  make clean       - Remove build artifacts and caches"
	@echo "  make format      - Format code with black"
	@echo "  make lint        - Run ruff linter"
	@echo "  make typecheck   - Run mypy type checker"
	@echo "  make all         - Run format, lint, typecheck, and test"
	@echo "  make stats-local   - Run stats job locally (use PREFIX=./data/transcripts)"
	@echo "  make webapp-stop   - Stop local webapp (API on 8000, frontend on 5173)"
	@echo "  make webapp-api    - Start API in foreground (terminal 1)"
	@echo "  make webapp-frontend - Start frontend dev server in foreground (terminal 2)"
	@echo "  make webapp-start  - Print instructions to run webapp in two terminals"

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

# Run stats job against local transcript directory (no AWS)
# Usage: make stats-local PREFIX=./data/transcripts
stats-local:
	@if [ -z "$(PREFIX)" ]; then echo "Usage: make stats-local PREFIX=<path to dir with *_transcription.json>"; exit 1; fi
	TRANSCRIPTS_PREFIX="$(PREFIX)" poetry run python -m debate_analyzer.batch.stats_job

# Stop local webapp (processes on port 8000 and 5173)
webapp-stop:
	@lsof -i :8000 -i :5173 -t 2>/dev/null | xargs kill 2>/dev/null || true
	@echo "Webapp stopped (ports 8000 and 5173)."

# Start API in foreground (run in terminal 1)
webapp-api:
	poetry run python -m debate_analyzer.api

# Start frontend dev server in foreground (run in terminal 2)
webapp-frontend:
	cd frontend && npm run dev

# Print instructions for two-terminal workflow
webapp-start:
	@echo "Run the webapp in two terminals from repo root:"
	@echo "  Terminal 1: make webapp-api"
	@echo "  Terminal 2: make webapp-frontend"
	@echo "Then open http://localhost:5173 (frontend proxies /api to the API on :8000)."
