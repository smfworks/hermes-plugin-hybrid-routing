---
name: hybrid-contextual-routing
description: "Pick a configured model by role, difficulty, sensitivity."
version: 1.1.0
author: SMF Works
license: MIT
---

# Hybrid Contextual Model Routing

Use this skill to classify a task and recommend a configured model. The router is deterministic and advisory: it does not switch the active model or execute the recommendation.

## When to Use

- A task may benefit from a different model than the session default.
- The user asks which model should handle a task.
- A cron or workflow needs a model selected before it runs.
- You want a local classification before submitting possibly sensitive text to an LLM.

## Classify

Use one of these local entry points:

```text
route_classify(text="Analyze the strategic trade-offs of our roadmap")
/route Analyze the strategic trade-offs of our roadmap
hermes route "Analyze the strategic trade-offs of our roadmap"
```

The decision contains:

| Field | Meaning |
|---|---|
| `model` | Selected configured `provider/model-id`, or empty when routing fails closed |
| `egress` | Effective `local`, `external`, or derived `unknown` class |
| `egress_declaration` | `operator` for an exact registry entry, otherwise `none` |
| `candidates` | Ordered configured model refs retained for compatibility |
| `candidate_routes` | Ordered refs paired atomically with egress and declaration provenance |
| `tier` | `fast`, `balanced`, or `strong` |
| `role` | Detected task category |
| `difficulty` | `simple`, `standard`, or `hard` |
| `sensitivity` | `normal` or `sensitive` |
| `disposition` | Authoritative action: `inline`, `separate`, `block`, or `unavailable` |
| `should_delegate` | Compatibility Boolean; true only when disposition is `separate` |
| `reason` | Explanation of the decision |

Model references must contain a non-empty provider and model ID, be no more than 512 characters, and contain no whitespace or terminal-control characters.

## Act on the Decision

- If `disposition` is `block`, do not process the sensitive text inline or invent a fallback.
- If `disposition` is `unavailable`, report the configuration problem.
- If `disposition` is `inline`, handle the task in the declared primary context when appropriate.
- If `disposition` is `separate`, use an execution path that can actually select the returned provider/model.
- Do not infer permission from `should_delegate: false`; that value also accompanies `block`.
- Do **not** assume standard `delegate_task` can honor the selected model. Hermes subagents inherit the configured delegation model; the tool has no per-call model argument.
- For recurring or session-scoped work, configure Hermes `delegation.provider` and `delegation.model` before delegating.

## Privacy Rules

1. Sensitive classification has priority over role and difficulty.
2. A sensitive decision contains only `sensitivity.local_only_model` when its exact ref is marked `local` in `model_egress`.
3. A blank model, missing/mismatched metadata, or an `external` class fails closed with no candidate.
4. Never infer locality from a provider or model name. Unlisted refs remain visibly `unknown`.
5. Treat `local` as operator-attested metadata, not network proof. Verify the provider's effective endpoint or `base_url`, proxies, tunnels, and trust boundary.
6. Sensitive decisions always recommend separate execution; configured primary-model string equality is not verified runtime identity.

> This plugin is not a DLP boundary. Classification is local only after input reaches Hermes; a messaging gateway still transports the text, and a cloud primary may receive it before `route_classify` runs. For strict confidentiality, use the local CLI or another trusted transport before sending the task to an LLM, or use a trusted local primary model.

## Routing Order

```text
Sensitivity:
  sensitive -> exact local-classified model, otherwise fail closed
  normal    -> continue

Role:
  configured specialized role model -> first candidate
  otherwise                           -> difficulty tier

Difficulty:
  simple   -> fast, then balanced, then strong
  standard -> balanced, then strong, then fast
  hard     -> strong, then balanced, then fast
```

Blank model refs are skipped. The router never inserts an unconfigured built-in model. Missing or empty `sensitivity.patterns` is rejected rather than disabling sensitive-data detection. Bundled sensitivity patterns remain enforced; configured patterns are additive.

Configure egress centrally by exact ref:

```yaml
egress_schema_version: 1
model_egress:
  custom:local-myserver/my-model: local
  openai-codex/gpt-5.6-sol: external

sensitivity:
  local_only_model: custom:local-myserver/my-model
```

Refs omitted from `model_egress` remain usable for normal routing but carry the effective class `unknown`.

## Configuration

- Repository/CLI install template: `$HERMES_HOME/plugins/hybrid-contextual-routing/hybrid_contextual_routing/data/routing_config.yaml`
- Active override: `$HERMES_HOME/hybrid_routing/routing_config.yaml`
- Default-profile fallback when `HERMES_HOME` is unset: `~/.hermes`

For a named profile, `HERMES_HOME` is normally `~/.hermes/profiles/<profile>`.

The profile override is re-read on each command or tool call.

## Useful Commands

```text
/route                  — show current routing config
/route test             — run the 9-case classifier test suite
/route <text>           — classify text
hermes route            — show config
hermes route test       — run tests
hermes route "text"     — classify text
```
