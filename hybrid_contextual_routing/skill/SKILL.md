---
name: hybrid-contextual-routing
description: "Pick a configured model by role, difficulty, sensitivity."
version: 1.0.1
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
| `candidates` | Ordered configured fallbacks; sensitive decisions contain only the local model |
| `tier` | `fast`, `balanced`, or `strong` |
| `role` | Detected task category |
| `difficulty` | `simple`, `standard`, or `hard` |
| `sensitivity` | `normal` or `sensitive` |
| `should_delegate` | Recommendation that another execution context is appropriate |
| `reason` | Explanation of the decision |

Model references must contain a non-empty provider and model ID, be no more than 512 characters, and contain no whitespace or terminal-control characters.

## Act on the Decision

- If `model` is empty, do not invent a model. Report the configuration problem.
- If `should_delegate` is false, handle the task inline when appropriate.
- If `should_delegate` is true, use an execution path that can actually select the returned provider/model.
- Do **not** assume standard `delegate_task` can honor the selected model. Hermes subagents inherit the configured delegation model; the tool has no per-call model argument.
- For recurring or session-scoped work, configure Hermes `delegation.provider` and `delegation.model` before delegating.

## Privacy Rules

1. Sensitive classification has priority over role and difficulty.
2. A sensitive decision contains only `sensitivity.local_only_model`.
3. If that field is blank, routing fails closed with no candidate.
4. Verify that the configured ref resolves to genuinely local infrastructure.

> This plugin is not a DLP boundary. Classification is local only after input reaches Hermes; a messaging gateway still transports the text, and a cloud primary may receive it before `route_classify` runs. For strict confidentiality, use the local CLI or another trusted transport before sending the task to an LLM, or use a trusted local primary model.

## Routing Order

```text
Sensitivity:
  sensitive -> configured local-only model, otherwise fail closed
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
