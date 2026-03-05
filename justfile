serve:
    uv run uvicorn server:app --reload --app-dir src
format:
    uv run ruff format
test:
    uv run pytest --cov=src/ ; uv run coverage-badge -f -o docs/coverage.svg
