# Architecture

## Overview

This document describes the architecture and design decisions for the Debate Analyzer project.

## Project Structure

### Source Code (`/src`)
All application source code resides in the `/src` folder. This follows Python packaging best practices and keeps the project organized.

```
src/
└── debate_analyzer/
    ├── __init__.py
    ├── core/          # Core business logic
    ├── models/        # Data models
    ├── utils/         # Utility functions
    └── api/           # API interfaces
```

### Tests (`/tests`)
Tests are located in the root-level `/tests` folder. This is the standard Python convention and allows for:
- Clear separation between source and test code
- Easy test discovery by pytest
- Simpler import paths in test files

```
tests/
├── __init__.py
├── unit/          # Unit tests
├── integration/   # Integration tests
└── fixtures/      # Test fixtures and data
```

### Documentation (`/doc`)
All documentation except the main README is stored in the `/doc` folder:
- Architecture documentation
- Development guides
- API documentation
- How-to guides
- Design decisions

## Design Principles

1. **Separation of Concerns**: Keep business logic, data models, and utilities separate
2. **Type Safety**: Use type hints throughout the codebase
3. **Testability**: Write testable code with clear dependencies
4. **Documentation**: Document public APIs and complex logic

## Technology Stack

- **Python**: 3.9+
- **Package Manager**: Poetry
- **Testing**: pytest, pytest-cov
- **Code Quality**: black, ruff, mypy
- **Build System**: Poetry + Make

## Module Organization

[Add your module organization details here as the project grows]

## Data Flow

[Add your data flow diagrams and descriptions here]

## External Dependencies

[Document key external dependencies and why they were chosen]
