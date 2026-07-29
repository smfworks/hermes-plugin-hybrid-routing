# Hybrid Contextual Model Routing — Hermes Plugin

Classify tasks by sensitivity, role, and difficulty, then recommend the best configured model without changing the primary session model.

## What It Does

Every Hermes session has a default model. This plugin adds a deterministic, local classifier that returns a routing recommendation. It does **not** silently switch the active model or make an LLM call itself.

### Three Signals

1. **Sensitivity** — secrets, PII, and confidentiality markers require a configured local-only model
2. **Role** — coding, research, creative, strategy, vision, or general
3. **Difficulty** — simple (fast tier), standard (balanced tier), hard (strong tier)

Sensitive classifications fail closed: if no local-only model is configured, the router returns no model and no cloud fallback.

## Installation

### Option A: Hermes CLI

```bash
# Default profile
hermes plugins install smfworks/hermes-plugin-hybrid-routing
hermes plugins enable hybrid-contextual-routing

# Named profile
hermes -p <name> plugins install smfworks/hermes-plugin-hybrid-routing
hermes -p <name> plugins enable hybrid-contextual-routing
```

### Option B: Manual install

```bash
PROFILE_HOME="${HERMES_HOME:-$HOME/.hermes}"  # use ~/.hermes/profiles/<name> if needed
git clone https://github.com/smfworks/hermes-plugin-hybrid-routing.git \
  "$PROFILE_HOME/plugins/hybrid-contextual-routing"
env HERMES_HOME="$PROFILE_HOME" hermes plugins enable hybrid-contextual-routing
```

You can also enable it in `$HERMES_HOME/config.yaml` (or the selected profile home's `config.yaml`):

```yaml
plugins:
  enabled:
    - hybrid-contextual-routing
```

## Configuration

The plugin ships with **blank model fields**. You must explicitly configure your models after installation. Blank defaults prevent silent routing to an unavailable provider.

### Step 1: Copy the default config

For a repository or Hermes CLI installation, use the same profile-scoped Hermes home that owns the plugin. `HERMES_HOME` is `~/.hermes` for the default profile and `~/.hermes/profiles/<name>` for a named profile.

```bash
PROFILE_HOME="${HERMES_HOME:-$HOME/.hermes}"  # replace for a named profile if needed
mkdir -p "$PROFILE_HOME/hybrid_routing"
cp "$PROFILE_HOME/plugins/hybrid-contextual-routing/hybrid_contextual_routing/data/routing_config.yaml" \
   "$PROFILE_HOME/hybrid_routing/routing_config.yaml"
```

For a Python package installation, copy the packaged template without overwriting an existing configuration:

```bash
PROFILE_HOME="${HERMES_HOME:-$HOME/.hermes}" python - <<'PY'
import importlib.resources as resources
import os
from pathlib import Path

target = Path(os.environ["PROFILE_HOME"]).expanduser() / "hybrid_routing" / "routing_config.yaml"
if target.exists():
    raise SystemExit(f"Refusing to overwrite existing config: {target}")
target.parent.mkdir(parents=True, exist_ok=True)
template = resources.files("hybrid_contextual_routing").joinpath("data/routing_config.yaml")
target.write_bytes(template.read_bytes())
print(f"Copied routing config to {target}")
PY
```

### Step 2: Fill in your models

Run `hermes auth list` to see which providers you have configured, then edit the copied config:

```yaml
tiers:
  fast:
    model: ollama-cloud/glm-5.2
  balanced:
    model: openai-codex/gpt-5.6-sol
  strong:
    model: xai-oauth/grok-4.5

sensitivity:
  # This must identify a genuinely local provider/model.
  local_only_model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4

delegation:
  # Match the provider/model ref used by the primary session.
  primary_model: openai-codex/gpt-5.6-sol
```

Leave any tier or role blank if you do not have a model for it. The router skips blank entries and chooses the nearest configured capability fallback. It never invents an unconfigured model.

Bundled secret and PII patterns are always enforced. Patterns in the copied configuration add detectors; they cannot replace the safety baseline.

### Step 3: Verify

```bash
hermes route                         # show configuration
hermes route test                    # pass the 9 classification cases
hermes route "Debug this function"   # show a routing decision
```

Configuration is re-read on every tool or command invocation, so edits require no restart.

## Usage

### Slash command

```text
/route                              — show routing config
/route test                         — run the 9-case classifier test suite
/route Analyze this architecture    — classify text and show a decision
```

### CLI subcommand

```bash
hermes route
hermes route test
hermes route "Debug this function"
```

### Tools available to the LLM

```text
route_classify(text="...")    — classify a task
route_status()                — show routing config
route_test()                  — run the classifier test suite
```

## Interpreting a Decision

The result includes the selected `model`, ordered `candidates`, classification metadata, a `reason`, and `should_delegate`.

Configured model references must use `provider/model-id`, be 512 characters or fewer, and contain no whitespace or terminal-control characters. The router rejects malformed references before returning or displaying them.

`should_delegate` is an **orchestration recommendation**, not an execution guarantee. Hermes' standard `delegate_task` tool does not accept a per-call model; subagents inherit the configured delegation model. To execute a recommendation, the caller must use an orchestration path that can select that provider/model, or configure `delegation.provider` and `delegation.model` for the workload before delegating.

## Privacy Boundary

The classifier code runs locally after input reaches Hermes and does not call an LLM. For sensitive text, the router returns only the configured local-only model and never includes cloud fallbacks. If that model is blank, routing fails closed. A missing or empty `sensitivity.patterns` list is rejected so a partial override cannot silently disable detection.

This plugin is **not a data-loss-prevention boundary**. A messaging gateway such as Telegram, Discord, or Slack transports the text before Hermes can classify it. A cloud-hosted primary model may likewise receive session text before it calls `route_classify`. For strict confidentiality, classify through the local CLI or another trusted transport before submitting the task to an LLM, or start with a trusted local primary model. Verify that `local_only_model` actually resolves to local infrastructure.

## Adding a New Role

Edit the profile routing config:

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

The router picks up the change on the next invocation. No code changes are required. Each role may define up to 64 nonempty literal cues of at most 128 characters. Cue matching is case-insensitive, token-boundary-aware, and recognizes regular inflections such as `test`, `tests`, `tested`, and `testing`; cues are not regular expressions.

## Cloud/Local Hybrid Example

```yaml
tiers:
  fast:
    model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4
  balanced:
    model: openai-codex/gpt-5.6-sol
  strong:
    model: xai-oauth/grok-4.5

sensitivity:
  local_only_model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4
```

This configuration recommends a local model for fast work and detected sensitive content, while balanced and strong work can use configured cloud models. Sensitive decisions contain no cloud candidates.

## How It Works

1. A user or agent invokes `/route`, `hermes route`, or `route_classify`.
2. The local rules classify sensitivity, role, and difficulty.
3. The router validates model refs, filters blank fields, and builds an ordered candidate list.
4. Sensitive classifications either select the local-only model or fail closed.
5. The caller decides how to execute the recommendation.

The primary session remains fixed, which preserves prompt caching. Actual model execution remains the orchestrator's responsibility.

## Repository Structure

```text
hermes-plugin-hybrid-routing/
├── plugin.yaml                         # source-install manifest
├── __init__.py                         # source-install registration proxy
├── hybrid_contextual_routing/
│   ├── plugin.yaml                     # packaged manifest
│   ├── __init__.py                     # tools, commands, and skill registration
│   ├── router.py                       # deterministic classification engine
│   ├── data/routing_config.yaml        # blank-model configuration template
│   └── skill/SKILL.md                  # bundled agent guidance
├── tests/
├── pyproject.toml
└── README.md
```

## Requirements

- A current Hermes Agent installation (tested with v0.19.0)
- Python 3.10 or later
- At least one configured model for actionable recommendations

PyYAML is installed automatically as a package dependency.

## License

MIT

## Author

SMF Works — built by Aiona Edge, CIO and Chief AI Research Scientist
