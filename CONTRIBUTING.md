# Contributing

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check .
mypy hybrid_contextual_routing __init__.py
```

## Pull requests

- Keep changes reviewable. Do not mix routing-policy changes with packaging-only edits unless the tests require both.
- Sensitive-routing behavior is fail-closed. Do not add provider-name inference for locality.
- CI (`.github/workflows/ci.yml`) must be green.

## Release notes

Update `CHANGELOG.md` and the version in `plugin.yaml` / `pyproject.toml` / package constants together.
