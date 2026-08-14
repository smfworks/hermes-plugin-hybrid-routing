# Security Policy

## Reporting a Vulnerability

Email **aionaedge@agentmail.to** with a description, reproduction steps, and
impact. Do **not** open a public GitHub issue for security reports.

We aim to acknowledge reports within 5 business days.

## Scope

This plugin classifies task text and recommends a configured model route. It
does not execute the task, call an LLM, or switch the primary Hermes session.

Treat operator configuration as untrusted input. Invalid model references,
malformed YAML, oversized configs, and oversized classify text must fail
closed rather than invent a route.

See [docs/EGRESS-TRUST-MODEL.md](docs/EGRESS-TRUST-MODEL.md) for the egress
attestation contract.

## Security invariants

- Sensitive classifications never recommend a model unless
  `sensitivity.local_only_model` exactly matches a `model_egress: local`
  entry on schema version 1.
- Locality is operator-attested metadata, not network proof. The plugin does
  not inspect `base_url`, DNS, proxies, or tunnels.
- Bundled sensitivity detectors cannot be replaced by a copied config; extra
  patterns are additive.
- Public slash/CLI output escapes control characters. Tool JSON errors are
  sanitized the same way. The CLI does not echo classify payloads and exits
  `2` when a sensitive route is blocked.
- Classifier input is bounded (`MAX_CLASSIFY_CHARS`). Config files are
  bounded (`MAX_CONFIG_BYTES`). YAML aliases and merge keys are rejected.
- Sensitivity matching folds fullwidth, zero-width, combining-mark, and a
  reviewed lookalike set before detectors run. This is not a complete
  Unicode-confusable or DLP boundary.
- The plugin is **not** a DLP or gateway privacy boundary. Messaging
  transports and a cloud primary model may see text before classification.

## Out of scope

- Verifying that a declared-local provider actually stays on-box
- Completeness of secret/PII detection
- Hermes core, provider SDKs, or third-party model endpoints
