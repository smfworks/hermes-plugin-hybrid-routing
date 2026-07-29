# Hybrid Contextual Model Routing — Hermes Plugin

Route tasks to the right model based on sensitivity, role, and difficulty. The right tool for the right job — without breaking prompt caching.

## What It Does

Every AI agent has a default model. This plugin adds contextual routing: it classifies incoming tasks by three signals and recommends the best model for each one. Specialized tasks get delegated to subagents running the appropriate model, while the primary session model stays fixed to preserve prompt caching.

### Three Signals

1. **Sensitivity** — secrets, PII, and confidentiality markers route to a local-only model
2. **Role** — coding, research, creative, strategy, vision, or general
3. **Difficulty** — simple (fast tier), standard (balanced tier), hard (strong tier)

## Installation

### Option A: Manual install

```bash
# Clone or copy the plugin directory into ~/.hermes/plugins/
git clone https://github.com/smfworks/hermes-plugin-hybrid-routing.git ~/.hermes/plugins/hybrid-contextual-routing
```

### Option B: From Hermes CLI (when published)

```bash
hermes plugins install smfworks/hermes-plugin-hybrid-routing
```

### Enable the plugin

```bash
hermes plugins enable hybrid-contextual-routing
```

Or add to `~/.hermes/config.yaml`:
```yaml
plugins:
  enabled:
    - hybrid-contextual-routing
```

## Configuration

The plugin ships with **blank model fields** — you must explicitly configure your models on install. This prevents silent routing to a provider you don't have.

### Step 1: Copy the default config

```bash
mkdir -p ~/.hermes/profiles/<your-profile>/hybrid_routing/
cp ~/.hermes/plugins/hybrid-contextual-routing/data/routing_config.yaml \
   ~/.hermes/profiles/<your-profile>/hybrid_routing/routing_config.yaml
```

### Step 2: Fill in your models

Run `hermes auth list` to see which providers you have configured, then edit the config:

```yaml
tiers:
  fast:
    model: ollama-cloud/glm-5.2          # your fast/cheap model
  balanced:
    model: openai-codex/gpt-5.6-sol      # your balanced workhorse
  strong:
    model: xai-oauth/grok-4.5            # your strongest reasoning model

sensitivity:
  local_only_model: ollama-cloud/qwen3.5:397b  # sensitive content stays separate

delegation:
  primary_model: openai-codex/gpt-5.6-sol      # must match your session default
```

Leave any tier or role blank if you don't have a model for it — the router skips blank entries and falls through to the next available one.

### Step 3: Verify

```bash
hermes route          # should show your models
hermes route test     # should pass 9/9
hermes route "test"   # should classify and show a routing decision
```

The router hot-loads the config on first use — no restart needed.

## Usage

### Slash command (CLI and gateway)
```
/route                              — show routing config
/route test                         — run the 9-case test suite
/route Analyze this architecture    — classify text and show routing decision
```

### CLI subcommand
```bash
hermes route                        — show config
hermes route test                   — run tests
hermes route "Debug this function"  — classify text
```

### Tools (available to the LLM)
```
route_classify(text="...")    — classify a task
route_status()                — show routing config
route_test()                  — run test suite
```

## Adding a New Role

Edit your routing config:
```yaml
roles:
  legal:
    model: anthropic/claude-opus-4-7
    description: "Legal document review and analysis"
    cues:
      - "contract"
      - "legal"
      - "compliance"
      - "regulation"
```

The router picks up the change on next load. No code changes.

## Cloud/Local Hybrid Inference

The plugin supports hybrid stacks with local and cloud providers:

```yaml
tiers:
  fast:
    model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4   # local, unlimited
  balanced:
    model: openai-codex/gpt-5.6-sol                           # cloud
  strong:
    model: xai-oauth/grok-4.5                                 # cloud

sensitivity:
  local_only_model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4  # sensitive stays local
```

This gives you:
- **Fast tasks** → local model, zero marginal cost
- **Balanced work** → cloud model, per-token
- **Deep reasoning** → cloud frontier model, per-token
- **Sensitive content** → local model, data never leaves your hardware

## How It Works

The plugin uses Hermes' delegation-based routing pattern:

1. User sends a task
2. The agent calls `route_classify` to classify it
3. The router returns which model fits, whether to delegate, and why
4. If the selected model matches the primary → handle inline (no cache break)
5. If the selected model differs → delegate to a subagent running that model
6. Sensitive content always routes to local-only and delegates to isolate the data

This achieves contextual model switching **per-task** without breaking the prompt caching that makes long conversations affordable.

## Plugin Structure

```
~/.hermes/plugins/hybrid-contextual-routing/
├── plugin.yaml              # manifest
├── __init__.py              # registration — tools, commands, skill
├── router.py                # classification engine
├── data/
│   └── routing_config.yaml  # default config (shipped)
├── skill/
│   └── SKILL.md             # bundled skill (agent guidance)
└── README.md                # this file
```

## Requirements

- Hermes Agent v2026.7 or later
- PyYAML (`pip install pyyaml`) — for config parsing
- At least one configured LLM provider

## License

MIT

## Author

SMF Works — built by Aiona Edge, CIO and Chief AI Research Scientist