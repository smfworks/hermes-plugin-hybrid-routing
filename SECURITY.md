# Security Policy

## Reporting a vulnerability

Email **michael@smfworks.com**. Do not open a public issue that includes secret values or private routing configs.

## Trust model

This plugin is an **advisory** router. It does not switch the Hermes session model and does not call an LLM.

- Sensitivity classification is a local heuristic baseline, not a DLP product.
- `model_egress` values are **operator attestations**. The plugin does not probe the network to prove a destination is local.
- Names such as `ollama` or `ollama-cloud` never imply locality. An `ollama-cloud/*` ref must be marked `external` unless the operator has independently verified a local endpoint and attested that exact ref as `local`.
- Sensitive routes fail closed unless `sensitivity.local_only_model` exactly matches a `model_egress: local` entry.

## Secrets

- Do not commit filled `routing_config.yaml` copies that contain real model credentials.
- Ship blank model fields in the packaged default config.
- CI runs tests, ruff, mypy, and bandit on pull requests.

## Production expectations

- `hermes plugins install smfworks/hermes-plugin-hybrid-routing` then copy the packaged template to `$HERMES_HOME/hybrid_routing/routing_config.yaml`.
- Verify with `hermes route test` after configuration.
