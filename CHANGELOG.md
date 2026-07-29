# Changelog

All notable changes to this project are documented here.

## 1.1.0 — 2026-07-29

### Fixed

- Make GitHub repository installs discoverable and enableable by Hermes through a root manifest and registration proxy.
- Correct source-template and override paths for profile-scoped `HERMES_HOME` installations.
- Pass a `Path` to Hermes skill registration so plugin loading completes instead of failing after partial registration.
- Replace the unsupported internal setuptools backend with `setuptools.build_meta`.
- Fail closed for sensitive classifications when no local-only model is configured.
- Reject missing or empty sensitivity-pattern sets so a partial override cannot silently disable secret/PII detection.
- Remove cloud models from every sensitive fallback chain.
- Remove the hard-coded `ollama-cloud/glm-5.2` fallback; only configured models can be selected.
- Choose tier fallbacks by capability distance instead of a fixed fast-first order.
- Preserve classification metadata and the built-in 9-case classifier smoke suite when model fields are blank.
- Match simple difficulty cues case-insensitively.
- Re-read profile configuration on each command or tool invocation.
- Validate malformed YAML sections, regexes, model refs, and thresholds with actionable errors.
- Reject terminal-control, whitespace, overlong, and structurally incomplete model references.
- Base inline execution on the effective selected model rather than only the requested difficulty tier.
- Match custom sensitivity patterns case-insensitively.
- Preserve bundled secret/PII detectors as a non-removable baseline when custom patterns are configured.
- Resolve profile configuration through Hermes' authoritative active-home API.
- Remove a stale package-data declaration and provide an executable package-template copy command.
- Validate delegation model refs before status output and reject Unicode surrogate refs.
- Report the unique active sensitivity-rule count and advertise slash-command arguments to native gateways.
- Clarify gateway transport privacy and correct announcement verification/reference claims.
- Validate the local-only model during every command's common configuration pass.
- Keep static checks portable across typed and untyped Hermes/TOML environments.
- Validate output-exposed role/tier identifiers and descriptions before rendering.
- Cover the root source-install wrapper in repository-wide Mypy gates.
- Validate delegation skip tiers against the canonical tier set.
- Code-wrap dynamic slash-command values to neutralize Markdown and mentions.
- Use variable-length CommonMark code fences for arbitrary slash-command paths and errors.
- Escape control-bearing paths, inputs, errors, and other dynamic CLI output.
- Bound role cues, reject empty values, and match literal cues at token boundaries with regular inflections.
- Correct regular inflections such as `refactored` and `refactoring` without generating doubled consonants.
- Prefer the most specific matching role cue so exact phrases do not lose to generic sub-cues, and recognize `roadmapped`/`roadmapping` for the shipped `roadmap` cue.
- Require exactly the canonical fast, balanced, and strong tier mappings.
- Validate tier input-token limits and return only validated, JSON-safe fields from status.
- Render blank models consistently as an em dash in human-facing slash and CLI output.
- Backfill version, description, and author metadata for wheel entry-point installs.
- Correct the documented tested Hermes runtime version.
- Return `candidates` in routing JSON while retaining `fallback_chain` for compatibility.
- Handle malformed tool arguments without raising out of the plugin boundary.
- Require an exact `model_egress: local` attestation before a sensitive model becomes actionable; missing or external metadata now fails closed.
- Require `egress_schema_version: 1` for the 1.1 copied-config contract; legacy copies remain usable for ordinary routing but cannot authorize sensitive routing.
- Add an authoritative `disposition` field so blocked sensitive routes cannot be mistaken for inline permission when `should_delegate` is false.
- Reject duplicate YAML mapping keys and merge keys before policy compilation.
- Surface effective egress classes in decisions, candidate routes, status JSON, slash output, and CLI output while retaining the 1.0 string-list fields.
- Validate the central egress registry and surface unlisted normal models as `unknown` rather than conflating missing metadata with an external declaration.
- Always recommend separate execution for sensitive decisions instead of trusting configured primary-model string equality as runtime identity.

### Clarified

- The plugin provides advisory recommendations; it does not automatically switch or execute a model.
- Standard Hermes delegation does not support per-call model selection.
- Sensitive routing is fail-closed but is not a data-loss-prevention boundary for cloud-primary sessions.
- Corrected installation template paths and removed the unpublished PyPI installation claim.
- Documented the egress trust model, migration path, and the distinction between operator-attested metadata and verified physical transport.

### Quality

- Added regression coverage, Ruff formatting/lint configuration, mypy configuration, and development dependencies.
