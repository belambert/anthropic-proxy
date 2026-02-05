# Agent Instructions

This is a Python project using `uv` for dependency management.

## Project Structure

```
src/anthropic_proxy/  # main package source code
tests/                # test files (pytest)
pyproject.toml        # project config and dependencies
.python-version       # python version (3.13+)
.github/workflows/    # CI/CD workflows
```

## Common Commands

Install dependencies:

    uv sync

Add a dependency:

    uv add <package-name>

Run tests:

    uv run pytest

Check formatting:

    uv run black --check .
    uv run isort --check-only .

Auto-format code:

    uv run black .
    uv run isort .

## Code Style

### Formatting
- adhere to "black" style
- write concise code
- chain expressions when intermediate results aren't used (unless it
  hurts readability)
- use blank lines strategically within functions to group related code
- shorten names to fit code on fewer lines
- organize code in "newspaper" order: most important/high-level content
  first, implementation details later

### Naming
- use short names, abbreviating when longer than ~10 chars
- common variable names:
  - `model` for models
  - `tokenizer` or `tok` for tokenizers
  - `ckpt` for checkpoints

### Type Hints
- use mypy type annotations when possible

### Documentation
- keep docstrings to one short line
- limit inline comments to roughly one per three lines of code
- for markdown shell commands, indent with 4 spaces instead of code
  blocks
- capitalize markdown headers
- inline comments (sentence fragments): no capital, no period
- prose (docstrings, markdown): full sentences with capitals and periods

### Imports
- organize imports to be compatible with isort

### Logging
- log sparingly

### Git
- separate unrelated changes into different commits
- avoid boilerplate in commit messages (no "Generated with" or
  "Co-Authored-By")

## CI/CD

Two GitHub Actions workflows run on pushes to `main` and on PRs:

**lint.yml** - checks code style:
- black formatting
- isort import ordering

**test.yml** - runs test suite:
- pytest
