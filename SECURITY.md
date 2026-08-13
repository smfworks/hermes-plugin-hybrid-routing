# Security Policy

## Reporting

Email **aionaedge@agentmail.to** for vulnerabilities in this advisory router.
Do not open public GitHub issues for security reports.

## Scope

This plugin classifies task text and recommends a model route. It does not
execute the task. Configuration is untrusted input: invalid model references
must fail closed.

See `docs/EGRESS-TRUST-MODEL.md` for the egress attestation contract.
