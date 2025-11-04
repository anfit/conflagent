# Conflagent Agent Guidelines

## Scope
These instructions apply to the entire repository unless a nested `AGENTS.md` overrides them.

## Engineering Workflow
- Prefer small, reviewable changes with clear commit messages.
- Keep feature branches rebased on `main` to align with the trunk-based flow described in `README.md`.
- Every code change must be covered by automated tests; add or update unit tests in `tests/` alongside feature work or bug fixes.

## Testing
- Run `pytest` from the repository root before submitting a change. All tests must pass.
- When adding new behaviours, extend existing tests or create new ones under `tests/` that exercise success and failure paths.
- Use `unittest.mock` (see existing tests) to isolate external Confluence HTTP calls instead of hitting real services.

## Python Style
- Target Python 3.10+ and follow PEP 8 conventions used in the project.
- Keep Flask route handlers thin: delegate logic to helper functions in `conflagent.py` where possible.
- When interacting with Confluence, reuse helpers like `build_headers`, `get_page_by_title`, and `abort` on non-200 responses to keep error handling consistent.
- Avoid introducing new dependencies unless absolutely necessary; prefer the standard library or packages already listed in `requirements.txt`.

## OpenAPI & Configuration
- If modifying the API contract, update the OpenAPI decorators and ensure tests cover the schema expectations.
- Configuration files such as `conflagent.<endpoint>.properties` are treated as secrets; never commit real credentials.

## Documentation & Miscellaneous
- Document externally visible behavioural changes in `README.md` or other relevant markdown files.
- Do not introduce print-based debugging in committed code; rely on logging or tests instead.
- Format commit messages with a standard prefix (`feat:`, `fix:`, `chore:`, `refactor:`, or `tests:`) followed by a capitalised, imperative-style summary.
