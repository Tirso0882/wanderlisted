# Contributing to Wanderlisted

Thank you for your interest in contributing to Wanderlisted! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Contributing to Wanderlisted](#contributing-to-wanderlisted)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [Getting Started](#getting-started)
  - [Development Setup](#development-setup)
    - [Prerequisites](#prerequisites)
    - [Backend Setup](#backend-setup)
    - [Frontend Setup](#frontend-setup)
    - [Running Tests](#running-tests)
  - [How to Contribute](#how-to-contribute)
    - [Reporting Bugs](#reporting-bugs)
    - [Suggesting Features](#suggesting-features)
    - [Code Contributions](#code-contributions)
  - [Pull Request Process](#pull-request-process)
  - [Coding Standards](#coding-standards)
    - [Python](#python)
    - [Frontend (TypeScript)](#frontend-typescript)
    - [Linting \& Formatting](#linting--formatting)
  - [Testing](#testing)
  - [Commit Messages](#commit-messages)
    - [Types](#types)
    - [Scopes](#scopes)
    - [Examples](#examples)
  - [Questions?](#questions)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch from `main`
4. Make your changes
5. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend)
- pnpm (for frontend package management)

### Backend Setup

```bash
make install        # Create venv and install dependencies
cp .env.example .env  # Configure environment variables
make dev            # Start FastAPI server on :8000
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev            # Start Next.js dev server on :3000
```

### Running Tests

```bash
make test           # Run all tests
make test-unit      # Run unit tests only
make coverage       # Run with coverage report
```

## How to Contribute

### Reporting Bugs

- Use [GitHub Issues](../../issues) with the **Bug Report** template
- Include steps to reproduce, expected behavior, and actual behavior
- Include Python/Node version and OS information

### Suggesting Features

- Use [GitHub Issues](../../issues) with the **Feature Request** template
- Describe the use case and expected behavior
- Explain why this would benefit the project

### Code Contributions

1. Check existing issues for something to work on, or create a new one
2. Comment on the issue to indicate you're working on it
3. Create a branch following the naming convention: `<type>/<short-description>`
   - Examples: `feat/add-currency-tool`, `fix/hotel-search-timeout`

## Pull Request Process

1. Ensure your code passes all tests and linting (`make lint && make test`)
2. Update documentation if you're changing public APIs or behavior
3. Add tests for new functionality (target 80% coverage)
4. Fill out the pull request template completely
5. Request review from a maintainer
6. Address review feedback promptly

## Coding Standards

### Python

- Python 3.12+ type annotations: `list[str]`, `dict[str, Any]`, `X | None`
- Imports: stdlib → third-party → local, separated by blank lines
- Use `custom_logging.AppLogger` for logging (never `print()`)
- All tools use `@tool` decorator from `langchain_core.tools`
- All agents extend `SpecializedAgent` from `src/agent/agents/base.py`
- Access `TravelAgentState` fields with `.get("field", default)` — never attribute access
- Use `get_llm(tier=...)` — never hardcode model names

### Frontend (TypeScript)

- Next.js App Router conventions
- Zustand for global state, React Query for server data
- Tailwind CSS 4 + shadcn/ui components
- `react-hook-form` + `zod` for form validation

### Linting & Formatting

```bash
make lint    # Ruff linting
make fmt     # Ruff formatting
```

## Testing

- Use **pytest** with async tests (`async def test_...`)
- Mock HTTP with **`respx`** (not `unittest.mock` or `responses`)
- Mock payloads as module-level `_MOCK_*` constants
- Use `monkeypatch.setenv()` for API keys
- One test file per module: `test_{module}.py`
- Integration tests use `@pytest.mark.integration`

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code refactoring |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |
| `style` | Code style (formatting) |
| `perf` | Performance improvement |

### Scopes

`agent`, `tools`, `rag`, `graph`, `prompts`, `api`, `frontend`, `k8s`

### Examples

```
feat(tools): add geolocation search to hotel tool
fix(agent): handle empty response from budget agent
docs(readme): update architecture diagram
test(tools): add coverage for currency conversion edge cases
```

## Questions?

If you have questions about contributing, please open a [Discussion](../../discussions) or reach out through issues.
