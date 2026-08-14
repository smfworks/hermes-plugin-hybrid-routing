# Changelog

## Unreleased

### Added

- Regression test: `ollama-cloud/*` is never inferred as a local sensitive destination.

All notable changes to this project are documented here.

## 1.1.2 — 2026-08-13

### Fixed

- Normalize classifier text for sensitivity matching so fullwidth, zero-width,
  combining-mark, and reviewed lookalike spoofs cannot send secrets to a cloud
  model.
- Add bundled detectors for well-known token prefixes, AWS access-key IDs,
  `Authorization: Token/Basic`, `private_key`/`passwd` assignments, and
  database URIs with an embedded password.
- Reject YAML aliases so a small config cannot expand into a graph bomb.
- Return CLI exit code `2` when classify is blocked for sensitivity, instead of
  treating a blocked secret route as a successful `0`.
- Stop echoing classify input on the CLI and in `explain()` previews.

## 1.1.1 — 2026-08-13

### Fixed

- Return a non-zero CLI exit code when `hermes route test` fails the smoke suite.
- Reject non-string and oversized classify input before running sensitivity regexes.
- Reject routing configs larger than 1 MiB before YAML parse.
- Sanitize tool JSON error payloads the same way slash and CLI output is sanitized.
- Require `egress_schema_version: 1` for `local_route_ready` and for an actionable sensitive route.
- Include `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md` in the source distribution.
- Point the README trust-model link at `main` so packaged copies do not depend on a tag.

### Quality

- Add GitHub Actions CI (`pip install -e ".[dev]"`, Ruff, Mypy, pytest, build/twine) on Python 3.10–3.13.
- Add Dependabot for GitHub Actions and pip.
- Add SECURITY.md and CONTRIBUTING.md; document the editable install path in the README.
- Log payload-free classification outcomes; warn if the bundled skill file is missing.
- Mark the package Production/Stable and ship a `py.typed` marker.

## 1.1.0 — 2026-07-29

### Fixed

- Make GitHub repository installs discoverable and enableable by Hermes through a root manifest and registration proxy.
- Correct source-template and override paths for profile-scoped `HERMES_HOME` installations.
- Pass a `Path` to Hermes skill registration so plugin loading completes instead of failing after partial registration.
- Replace the unsupported internal setuptools backend with `setuptools.build_meta`.
- Fail closed for sensitive classifications when `sensitivity.local_only_model` is blank.
- Reject missing or empty sensitivity-pattern sets so a partial override cannot silently disable bundled sensitivity detection.
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
- Preserve bundled sensitivity detectors as a non-removable baseline when custom patterns are configured.
- Detect natural-language, spaced-label, quoted-object-key, colon, and equal-sign secret assignments such as `password is ...`, `API key: ...`, and `{"password": "..."}`.
- Detect bounded non-metadata-qualified credential variables and generic deployment qualifiers; scoped, possessive, current-value, and reviewed adverbial assignments with `is` or `equals`; bare and token-labeled bearer credentials; AWS secret-access assignments; standard encrypted/DSA/PGP private-key headers; and normal `MIP:` markers. Keep complete bearer-policy and bearer-lifecycle prose, policy, budget, rotation, status, passwordless, file/path-pointer, exact non-value sentinels, and explicit terminal negated state prose normal without exempting credential values that merely begin with those words.
- Give the longest matched role cue precedence over multiple shorter matches.
- Keep the project, source-directory, installed-entry-point, and module plugin descriptions identical.
- Use the canonical absolute Clearinghouse URL for the linked routing article in the announcement.
- Inflect only reviewed verb heads and noun plurals in role cues, including `writing a blog`, `drafting an article`, and `searching for sources`, without treating nouns such as `paper`, `content`, or `class` as arbitrary verbs; keep ambiguous cues such as `find`, `import`, and `test` literal-only.
- Qualify every human-facing declared-local route and status label as operator-declared with transport not verified; label undeclared blocked references as not declared.
- Resolve profile configuration through Hermes' authoritative active-home API.
- Remove a stale package-data declaration and provide an executable package-template copy command.
- Validate delegation model refs before status output and reject Unicode surrogate refs.
- Report the unique active sensitivity-rule count and advertise slash-command arguments to native gateways.
- Clarify gateway transport privacy and correct announcement verification/reference claims.
- Validate the configured sensitive model during every command's common configuration pass.
- Keep static checks portable across typed and untyped Hermes/TOML environments.
- Validate output-exposed role/tier identifiers and descriptions before rendering.
- Cover the root source-install wrapper in repository-wide Mypy gates.
- Validate delegation skip tiers against the canonical tier set.
- Code-wrap dynamic slash-command values to neutralize Markdown and mentions.
- Add explicit slash/CLI `classify <text>` forms so reserved task text such as `test` and `status` remains classifiable.
- Use a distribution-safe canonical `main` trust-model URL and scope sensitivity claims to the bundled detector classes.
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
