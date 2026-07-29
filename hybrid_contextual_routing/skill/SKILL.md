---
name: hybrid-contextual-routing
description: "Pick the right model by role, difficulty, and sensitivity."
version: 1.0.0
author: SMF Works
license: MIT
---

# Hybrid Contextual Model Routing

Route tasks to the right model based on what the task actually is — not a one-size-fits-all default.

## When to Use

- A task might benefit from a different model than the session default
- You want to check whether this task should be delegated
- The user asks "which model should handle this?" or "/route"
- You're setting up a cron job and need to pick the right model
- You're doing sensitive work that should stay local

## The Core Principle

**The primary session model stays fixed** (preserves prompt caching). Specialized tasks are **delegated to subagents** running the appropriate model. This is contextual switching without cache-breaking.

## How It Works

### Step 1: Classify the Task

Use the `route_classify` tool:
```
route_classify(text="Analyze the strategic trade-offs of our roadmap")
```

Or use the `/route` slash command:
```
/route Analyze the strategic trade-offs of our roadmap
```

Or from the terminal:
```bash
hermes route "Analyze the strategic trade-offs of our roadmap"
```

### Step 2: Interpret the Decision

The router returns a routing decision with:

| Field | Values | Meaning |
|-------|--------|---------|
| `model` | `provider/model-id` | Which model to use |
| `tier` | `fast` / `balanced` / `strong` | Cost/capability tier |
| `role` | `coding` / `research` / `creative` / `strategy` / `vision` / `general` | Task category |
| `difficulty` | `simple` / `standard` / `hard` | How complex the task is |
| `sensitivity` | `normal` / `sensitive` | Whether content has PII/secrets |
| `should_delegate` | `True` / `False` | Whether to delegate to a subagent |
| `reason` | string | Why this decision was made |

### Step 3: Act on the Decision

- **`should_delegate == False`** → Handle inline. The task matches the primary model or is simple enough.
- **`should_delegate == True`** → Delegate to a subagent running the selected model.
- **`sensitivity == sensitive`** → Content routes to a local-only model. Never send sensitive content to a cloud provider.

## Routing Rules

```
Sensitivity first:
  Sensitive → local-only model (never cloud)
  Normal → continue

Role second:
  coding → coding model
  creative → creative model
  strategy → strong reasoning model
  research → research model
  general → tier check

Difficulty tier last:
  simple → fast tier (handle inline)
  standard → balanced tier (usually inline)
  hard → strong tier (usually delegate)

Delegation:
  Skip if: fast tier, or selected model == session default
  Delegate if: different model needed, or sensitive content needs isolation
```

## Configuration

The config lives at:
- **Default (shipped):** `~/.hermes/plugins/hybrid-contextual-routing/data/routing_config.yaml`
- **User override:** `~/.hermes/profiles/<profile>/hybrid_routing/routing_config.yaml`

The router uses the user override if it exists, otherwise the shipped default.

## Useful Commands

```
/route                  — show current routing config
/route test             — run the 9-case test suite
/route <text>           — classify text and show routing decision
hermes route             — CLI: show config
hermes route test        — CLI: run tests
hermes route "text"      — CLI: classify text
```