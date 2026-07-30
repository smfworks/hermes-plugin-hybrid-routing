# Egress Trust Model

This document defines how the hybrid router represents model egress and what the representation can—and cannot—guarantee.

## Goal

A sensitive routing decision must never treat a model as local merely because its provider or model name looks local. The router must fail closed unless the exact configured model reference has explicit local egress metadata.

## Configuration Schema

`model_egress` is a top-level mapping from an exact validated `provider/model-id` reference to one of two classes:

```yaml
egress_schema_version: 1
model_egress:
  custom:local-laguna/poolside/Laguna-S-2.1-NVFP4: local
  openai-codex/gpt-5.6-sol: external
```

The classes are:

- `local` — the operator attests that the model resolves to trusted local or operator-controlled infrastructure that satisfies the intended sensitive-data policy.
- `external` — the model may send task data beyond that local trust boundary.

A model omitted from `model_egress` has the derived class `unknown`. `unknown` cannot be configured as an attestation: it means the operator supplied no declaration. Explicit `external` entries distinguish a deliberate external declaration from missing metadata.

## Enforced Invariants

1. The router never derives egress from a provider name, model-id, URI scheme, or comment.
2. One central exact-reference mapping supplies the class everywhere that model appears, preventing per-tier or per-role contradictions.
3. `model_egress` must be a YAML mapping; every key must be a valid model reference and every value must be exactly `local` or `external`.
4. A sensitive route is actionable only when `sensitivity.local_only_model` is nonblank and its exact reference resolves to `local`.
5. Missing metadata, an explicit `external` class, or a mismatched reference produces no sensitive candidate and no cloud fallback.
6. Normal tier and role routing remains available. Unlisted normal models carry the effective class `unknown`.
7. Decisions expose the selected `egress`, declaration provenance, and a `candidate_routes` list containing each candidate's model and effective class. Existing `candidates` and `fallback_chain` string lists remain for compatibility.
8. Decisions expose an authoritative `disposition`: `inline`, `separate`, `block`, or `unavailable`. The compatibility Boolean `should_delegate` is false for both `inline` and `block` and must not be used as an allow signal.
9. Status output exposes effective classes, declaration provenance, unknown/orphan counts, metadata completeness, migration state, and a `local_route_ready` boolean.
10. Sensitive decisions always recommend separate execution. A copied `delegation.primary_model` string is not authoritative runtime identity and cannot suppress that recommendation.
11. Versioned 1.1+ copied configurations declare `egress_schema_version: 1`. A missing marker is legacy and cannot authorize sensitive routing.
12. Duplicate YAML mapping keys and merge keys are rejected before policy compilation.

## Decision Algorithm

For sensitive input:

```text
local_only_model is blank
    -> no route

local_only_model effective egress is not local
    -> no route

local_only_model effective egress is local
    -> that exact model is the only candidate; recommend separate execution
```

The fail-closed branches return `disposition: block`, no model, and no candidates. Ordinary no-route branches return `unavailable`.

For normal input, role and tier selection proceeds as before. Each selected candidate receives its effective egress class from the central registry; absence means `unknown`.

## Migration from 1.0.x

Existing tier and role model references continue to route. They are reported as `unknown` until classified explicitly.

Versioned 1.1+ copies must retain `egress_schema_version: 1`. A copied 1.0 configuration without that marker is reported as schema `0`; ordinary routing remains advisory, but sensitive routing stays blocked until the copy is migrated.

An existing `sensitivity.local_only_model` no longer becomes actionable by name alone. Add an exact registry entry after checking the provider's real destination:

```yaml
egress_schema_version: 1
model_egress:
  custom:local-myserver/my-model: local

sensitivity:
  local_only_model: custom:local-myserver/my-model
```

Run `hermes route` and confirm that the sensitive route shows `local, operator-declared; transport not verified; ready`. An undeclared ref shows `unknown, not declared; transport not verified; blocked`; an explicitly external ref shows `external, operator-declared; transport not verified; blocked`. Both states fail closed for sensitive classifications.

## Trust Boundary and Non-Goals

`local` is operator-attested metadata, not network attestation. The plugin does not introspect every provider's `base_url`, DNS resolution, proxy, tunnel, transport, or runtime configuration. A dishonest or stale `local` entry can therefore misdescribe the actual destination.

The metadata strengthens the router's configuration semantics: locality is explicit, centralized, visible, and required for sensitive recommendations. It does **not** prove that bytes stayed on one machine or network.

The plugin is also not a DLP boundary. A gateway or cloud primary model may receive text before the local classifier runs. Strictly confidential workflows must use a trusted input path and primary model in addition to this routing policy.

## Operator Checklist

Before marking a model `local`:

1. Resolve the model reference through the actual Hermes provider configuration.
2. Inspect the effective endpoint or `base_url`; do not trust the model-reference prefix.
3. Confirm proxy, tunnel, and DNS behavior.
4. Confirm the infrastructure is inside the intended trust boundary.
5. Re-check the entry whenever provider configuration changes.
