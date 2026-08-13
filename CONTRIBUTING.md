# Contributing

## Development setup

Python 3.10 or later.

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
ruff format --check .
mypy hybrid_contextual_routing tests
```

CI on GitHub Actions runs the same install plus `python -m build` and
`twine check` on Python 3.10–3.13.

## Pull requests

- Target `main`.
- Use conventional commits (`fix:`, `test:`, `docs:`, `ci:`, `chore:`).
- Do not add conversation hooks. Routing stays advisory so Hermes prompt
  caching is preserved.
- Update `CHANGELOG.md` and keep versions in sync across `pyproject.toml`,
  both `plugin.yaml` files, `hybrid_contextual_routing/__init__.py`, and
  `hybrid_contextual_routing/skill/SKILL.md`.
- Add or extend tests for any behavior change. Do not weaken fail-closed
  sensitive-routing tests.

## Security

See `SECURITY.md`. Do not include live credentials in fixtures. Use
synthetic markers such as `SYNTHETIC_VALUE`.
