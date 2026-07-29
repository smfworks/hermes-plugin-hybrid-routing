# Hybrid Contextual Model Routing — Hermes Plugin

Classify tasks by sensitivity, role, and difficulty, then recommend the best configured model without changing the primary session model.

## What It Does

Every Hermes session has a default model. This plugin adds a deterministic, local classifier that returns a routing recommendation. It does **not** silently switch the active model or make an LLM call itself.

### Three Signals

1. **Sensitivity** — common secret assignments and credential forms (including bearer tokens and private-key headers), SSN/card-number formats, and confidentiality markers are classified as sensitive and require an explicitly local-attested model
2. **Role** — coding, research, creative, strategy, vision, or general
3. **Difficulty** — simple (fast tier), standard (balanced tier), hard (strong tier)

Sensitive classifications fail closed: the router returns no model and no fallback unless `local_only_model` exactly matches a ref explicitly marked `local` in `model_egress`.

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

# Exact refs omitted here remain visibly unknown.
# "local" is an operator attestation; verify the provider's real endpoint.
egress_schema_version: 1
model_egress:
  custom:local-laguna/poolside/Laguna-S-2.1-NVFP4: local
  ollama-cloud/glm-5.2: external
  openai-codex/gpt-5.6-sol: external
  xai-oauth/grok-4.5: external

sensitivity:
  local_only_model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4

delegation:
  # Match the provider/model ref used by the primary session.
  primary_model: openai-codex/gpt-5.6-sol
```

Leave any tier or role blank if you do not have a model for it. The router skips blank entries and chooses the nearest configured capability fallback. It never invents an unconfigured model. Normal models omitted from `model_egress` still route but are reported as `unknown`. A sensitive model must have an exact `local` entry or the decision fails closed.

Bundled secret assignments, bearer credentials, private-key headers, SSN/card-number formats, and confidentiality markers are always enforced. Patterns in the copied configuration add detectors; they cannot replace the safety baseline. This heuristic list is not a complete PII, secret-scanning, or DLP detector.

### Step 3: Verify

```bash
hermes route                         # show configuration
hermes route test                    # pass the 9 classification cases
hermes route classify test           # classify the reserved task text "test"
hermes route "Debug this function"   # show a routing decision
```

Configuration is re-read on every tool or command invocation, so edits require no restart.

## Usage

### Slash command

```text
/route                              — show routing config
/route test                         — run the 9-case classifier test suite
/route classify test                — classify the reserved task text "test"
/route Analyze this architecture    — classify text and show a decision
```

### CLI subcommand

```bash
hermes route
hermes route test
hermes route classify status
hermes route "Debug this function"
```

Use the explicit `classify` form when the task text itself is exactly `status` or `test`; those bare words remain command names.

### Tools available to the LLM

```text
route_classify(text="...")    — classify a task
route_status()                — show routing config
route_test()                  — run the classifier test suite
```

## Interpreting a Decision

The result includes the selected `model`, effective `egress`, ordered `candidates`, structured `candidate_routes`, classification metadata, a `reason`, a machine-readable `disposition`, and the compatibility Boolean `should_delegate`. `candidates` and `fallback_chain` remain string lists for compatibility; `candidate_routes` pairs each model with its effective egress class and declaration provenance.

`disposition` is authoritative for orchestration:

- `inline` — the selected route can be handled in the declared primary context.
- `separate` — use a separate execution path that can select the returned model.
- `block` — a sensitive route failed closed; do **not** process the text inline.
- `unavailable` — no actionable model route exists.

Configured model references must use `provider/model-id`, be 512 characters or fewer, and contain no whitespace or terminal-control characters. The router rejects malformed references before returning or displaying them.

`should_delegate` remains for 1.0 compatibility and is true only for `separate`. It is false for both `inline` and fail-closed `block`, so consumers must use `disposition` rather than interpreting false as permission to continue. Sensitive actionable decisions always use `separate`; equality with the copied `delegation.primary_model` setting is not treated as authoritative runtime identity. Hermes' standard `delegate_task` tool does not accept a per-call model; subagents inherit the configured delegation model. To execute a recommendation, the caller must use an orchestration path that can select that provider/model, or configure `delegation.provider` and `delegation.model` for the workload before delegating.

## Privacy Boundary

The classifier code runs locally after input reaches Hermes and does not call an LLM. For sensitive text, the router returns only `sensitivity.local_only_model` when the exact ref is explicitly classified `local` in `model_egress`. A blank model, absent or mismatched metadata, or an explicit `external` class produces no candidate and no fallback. A missing or empty `sensitivity.patterns` list is rejected so a partial override cannot silently disable detection.

`local` is operator-attested metadata, not network attestation. The plugin does not infer trust from a provider prefix and cannot verify every provider's effective `base_url`, proxy, tunnel, DNS resolution, or transport. Verify the real destination before declaring a ref local and re-check it whenever provider configuration changes. See [Egress Trust Model](https://github.com/smfworks/hermes-plugin-hybrid-routing/blob/v1.1.0/docs/EGRESS-TRUST-MODEL.md).

This plugin is **not a data-loss-prevention boundary**. A messaging gateway such as Telegram, Discord, or Slack transports the text before Hermes can classify it. A cloud-hosted primary model may likewise receive session text before it calls `route_classify`. For strict confidentiality, classify through the local CLI or another trusted transport before submitting the task to an LLM, or start with a trusted local primary model.

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

The router picks up the change on the next invocation. No code changes are required. Each role may define up to 64 nonempty literal cues of at most 128 characters. Cue matching is case-insensitive and token-boundary-aware; cues are not regular expressions. Only shipped and reviewed cue words receive regular inflections such as `test`, `tests`, `tested`, and `testing`. Custom cues otherwise match their exact literal words and phrases.

## Cloud/Local Hybrid Example

```yaml
tiers:
  fast:
    model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4
  balanced:
    model: openai-codex/gpt-5.6-sol
  strong:
    model: xai-oauth/grok-4.5

egress_schema_version: 1
model_egress:
  custom:local-laguna/poolside/Laguna-S-2.1-NVFP4: local
  openai-codex/gpt-5.6-sol: external
  xai-oauth/grok-4.5: external

sensitivity:
  local_only_model: custom:local-laguna/poolside/Laguna-S-2.1-NVFP4
```

This configuration recommends a local-classified model for fast work and detected sensitive content, while balanced and strong work can use configured external models. Sensitive decisions contain only the exact local-classified model.

## How It Works

1. A user or agent invokes `/route`, `hermes route`, or `route_classify`.
2. The local rules classify sensitivity, role, and difficulty.
3. The router validates model refs and the central exact-reference egress registry.
4. Sensitive classifications select only an explicitly local-classified model or fail closed.
5. Normal classifications build an ordered candidate list with effective egress metadata; unlisted refs remain `unknown`.
6. The caller decides how to execute the recommendation.

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
├── docs/EGRESS-TRUST-MODEL.md        # egress schema, invariants, and limits
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
