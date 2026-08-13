# Contributing

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

- Target `main`
- Do not add conversation hooks (cache-safe advisory only)
- Update CHANGELOG.md
- CI runs pytest on Python 3.10–3.12
