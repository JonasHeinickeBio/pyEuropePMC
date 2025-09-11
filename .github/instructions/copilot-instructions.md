# Copilot Instructions for PyEuropePMC

## Project Overview
PyEuropePMC is a Python toolkit for automated search, extraction, entity annotation, and knowledge graph integration of scientific literature from Europe PMC. The codebase is designed to be modular, extensible, and user-friendly for bioinformatics and data science applications.

---

## Coding Standards

- Use modern Python (3.9+) and follow [PEP8](https://peps.python.org/pep-0008/) guidelines.
- Use type hints for all functions and method signatures.
- Write concise, informative docstrings for all public functions, classes, and modules.
- Prefer clear, descriptive variable and function names (e.g., `search_articles`, `annotate_entities`).
- Structure code into logical modules: API client, parsers, annotators, KG integration, utils.
- Code should adhere to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) for consistency.
- Use `logging` for debug and info messages; avoid print statements in production code.
- Use `f-strings` for string formatting (Python 3.6+).
- The code should pass all linting checks using `ruff` for formatting.
- The code should pass the pre-commit hooks defined in `.pre-commit-config.yaml` and the cdci checks.

## Error Handling
- Use try/catch blocks with specific exceptions.
- Avoid catching generic exceptions unless absolutely necessary.
- Raise custom exceptions for specific error cases (e.g., `EuropePMCError`, `APIError`).
- Use `logging` to capture errors with context, including function names and parameters.
- Ensure that all exceptions are documented in the function docstrings.

---

## Workflow Guidelines

- **API Access:**
  - Use the official Europe PMC REST API for all data retrieval.
  - Support flexible query parameters and output formats (JSON, XML, DC).
  - Handle API errors gracefully and provide informative error messages.

- **Testing:**
  - Write unit tests for all major functions using `pytest`.
  - Include example queries and expected outputs in the `examples/` directory.
  - Test names should be descriptive and adhere to the format `test_<functionality>_<expected_behavior>`.
  - Use fixtures for common test setups (e.g., mock API responses).
  - Test files should be located in the `tests/` directory, organized by module and under unit or functional tests and they should follow the naming convention `<module_name>_test.py`.

- **Documentation:**
  - Update `README.md` and API docs as features are added.
  - Add usage examples and code snippets for common tasks.

---

## Prompt and Agentic Workflow Tips

- For complex tasks, ask Copilot to plan the steps before generating code.
- Use modular functions: each function should do one thing well and be testable in isolation.
- Store reusable prompts for LLM-based annotation or extraction in `.github/prompts/`.
- When integrating with other tools (e.g., KG frameworks), provide clear interface definitions and usage examples.

---

## General Best Practices

- Handle exceptions and edge cases; log errors with context.
- Use `requirements.txt` for dependencies and keep it up to date.
- Do not include API keys or sensitive data in the codebase.
- Use GitHub Issues for bugs, feature requests, and discussion.
- Reference issues and PRs in commit messages for traceability.

---

*These instructions help Copilot and contributors generate consistent, high-quality code and documentation for PyEuropePMC. Please update as the project evolves.*
