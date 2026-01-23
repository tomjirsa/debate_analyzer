# Project Setup Guide

## Agent Task Description: Set Up Python Poetry Project with Best Practices

Create a professional Python project called `debate-analyzer` using Poetry with a production-ready structure following modern Python best practices.

### Project Structure Required:

```
debate_analyzer/
├── src/
│   └── debate_analyzer/
│       └── __init__.py (with __version__ = "0.1.0")
├── tests/
│   ├── __init__.py
│   └── test_example.py (with example tests)
├── doc/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   ├── API.md
│   └── HOWTO.md
├── pyproject.toml (Poetry config with all dependencies)
├── Makefile (with targets: reset_venv, test, deploy, clean, format, lint, typecheck, all)
├── README.md (quick setup guide)
├── .gitignore (standard Python gitignore)
└── .cursorrules (project-specific AI agent rules)
```

### System Requirements:

- **Python 3.9+**
- **ffmpeg** - Required for video processing (yt-dlp uses it for merging video/audio streams)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Key Requirements:

1. **pyproject.toml Configuration**:
   - Python 3.9+
   - Dev dependencies: pytest, pytest-cov, black, ruff, mypy
   - Configure black (line-length=88)
   - Configure ruff (select E, F, I, N, W, B, Q)
   - Configure pytest with coverage for src/debate_analyzer
   - Configure mypy (disallow_untyped_defs=true)

2. **Makefile** with these targets:
   - `reset_venv`: Remove and recreate virtual environment
   - `test`: Run tests with coverage
   - `deploy`: Build and publish (runs tests first)
   - `clean`: Remove build artifacts and caches
   - `format`: Format code with black
   - `lint`: Run ruff linter
   - `typecheck`: Run mypy type checker
   - `all`: Run format, lint, typecheck, test

3. **Documentation Files**:
   - `README.md`: Quick setup instructions only (installation, basic usage, project structure)
   - `doc/ARCHITECTURE.md`: Architecture overview, design principles, technology stack
   - `doc/DEVELOPMENT.md`: Development workflow, code quality standards, testing guidelines
   - `doc/API.md`: API documentation placeholder
   - `doc/HOWTO.md`: How-to guides placeholder

4. **Test Setup**:
   - Example test file with proper type hints
   - Test for __version__
   - Example test class and methods
   - All following pytest conventions

5. **Code Standards**:
   - All code must have type hints
   - Use Google-style docstrings
   - Follow src-layout pattern (code in src/, tests in root tests/)

6. **.gitignore**: Standard Python gitignore including poetry.lock, virtual environments, build artifacts, IDE files

### Project Conventions:

- **Source code**: ALL application code in `/src/debate_analyzer/`
- **Tests**: ALL tests in root-level `/tests/` (standard Python convention)
- **Documentation**: ALL detailed docs in `/doc/` (README is for quick setup only)
- **Type safety**: Strict mypy configuration, all functions need type hints
- **Testing**: High coverage expectations (>80%), use pytest
- **Code quality**: black formatting, ruff linting, mypy type checking

### Implementation Steps for Agent:

1. Initialize Poetry project with proper metadata
2. Configure pyproject.toml with all tools and dependencies
3. Create src-layout structure with src/debate_analyzer/
4. Create tests/ directory at root level
5. Create doc/ directory with all documentation files
6. Create Makefile with all required targets
7. Create comprehensive README.md for quick setup
8. Create .gitignore with Python-specific ignores
9. Write example test file demonstrating best practices
10. Initialize __init__.py with version string

### Quality Checklist:

- [ ] Poetry project initializes without errors
- [ ] All dependencies install correctly
- [ ] `make test` runs successfully
- [ ] `make format` formats code
- [ ] `make lint` checks code quality
- [ ] `make typecheck` validates types
- [ ] `make all` passes all checks
- [ ] All documentation files are populated
- [ ] Project structure matches src-layout convention
- [ ] Example tests pass and demonstrate patterns
