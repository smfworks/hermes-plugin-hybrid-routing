from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
import yaml

from hybrid_contextual_routing.router import HybridRouter

DEFAULT_CONFIG = (
    Path(__file__).parents[1]
    / "hybrid_contextual_routing"
    / "data"
    / "routing_config.yaml"
)


def configured_router(tmp_path, mutate) -> HybridRouter:
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config = deepcopy(config)
    mutate(config)
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return HybridRouter(config_path=str(config_path))


def test_sensitive_content_without_local_model_fails_closed(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "openai-codex/gpt-5.6-sol"
        config["delegation"]["primary_model"] = "openai-codex/gpt-5.6-sol"

    decision = configured_router(tmp_path, configure).classify("password=private-value")

    assert decision.sensitivity == "sensitive"
    assert decision.model == ""
    assert decision.candidates == []
    assert decision.should_delegate is False
    assert decision.disposition == "block"
    assert decision.to_dict()["disposition"] == "block"
    assert "operator-declared local model is not configured" in decision.reason


@pytest.mark.parametrize(
    "text",
    [
        "my password is synthetic-value",
        "the API key is synthetic-value",
        "this token value is synthetic-value",
        "OPENAI_API_KEY=synthetic-value",
        "DB_PASSWORD=synthetic-value",
        "dbPassword=synthetic-value",
        "SECRET_KEY=synthetic-value",
        "clientSecret=synthetic-value",
        "access_token: synthetic-value",
        "the API   key is SYNTHETIC_VALUE",
        "API_KEY_STAGING=SYNTHETIC_QUALIFIED_MARKER",
        "PASSWORD_PROD=SYNTHETIC_QUALIFIED_MARKER",
        "API key for staging is SYNTHETIC_NATURAL_MARKER",
        "password's value is SYNTHETIC_POSSESSIVE_MARKER",
        "my password definitely really is SYNTHETIC_VALUE",
        "my password normally is SYNTHETIC_ADVERB_MARKER",
        "the API key generally is SYNTHETIC_ADVERB_MARKER",
        "the token temporarily is SYNTHETIC_ADVERB_MARKER",
        "API key for staging environment is SYNTHETIC_SCOPED_MARKER",
        "Bearer token SYNTHETIC_BEARER_MARKER",
        "Authorization: Bearer SYNTHETIC_BEARER_MARKER",
        "AWS_SECRET_ACCESS_KEY=SYNTHETIC_AWS_MARKER",
        "-----BEGIN PRIVATE KEY-----\nSYNTHETIC_PRIVATE_KEY_MARKER",
        "MIP: material",
        "MIP:",
        "MIP:material",
        "API_KEY_STAGING is SYNTHETIC_SECRET",
        "my API-key is SYNTHETIC_SECRET",
        "my password's current value is SYNTHETIC_SECRET",
        "Bearer SYNTHETIC_VALUE",
        "API key for the staging environment is SYNTHETIC_VALUE",
        "password for the production database is SYNTHETIC_VALUE",
        "password equals SYNTHETIC_VALUE",
        "-----BEGIN ENCRYPTED PRIVATE KEY-----",
        "-----BEGIN DSA PRIVATE KEY-----",
        "-----BEGIN PGP PRIVATE KEY BLOCK-----",
        "SECRET_KEY_BASE=SYNTHETIC_VALUE",
        "API_KEY_STRIPE=SYNTHETIC_VALUE",
        "CLIENTSECRET_GITHUB=SYNTHETIC_VALUE",
        "PASSWORD_HASH=SYNTHETIC_VALUE",
        "API key: SYNTHETIC_VALUE",
        "API key = SYNTHETIC_VALUE",
        '{"password": "SYNTHETIC_VALUE"}',
        '{"api_key":"SYNTHETIC_VALUE"}',
        "{'access_token': 'SYNTHETIC_VALUE'}",
        "API_KEY_STG=SYNTHETIC_VALUE",
        "API_KEY_PRD=SYNTHETIC_VALUE",
        "TOKEN_DEV2=SYNTHETIC_VALUE",
        "PASSWORD=none.marker",
        "TOKEN=null-marker",
        "API_KEY=not-configured-marker",
        "API key equals none.marker",
        "my password value is not-a-placeholder",
        "my password value is nevermore",
        "my password value is no-marker",
        "my password value is none-marker",
        "my password value is unset-marker",
        "my password value is missing-marker",
        "my password value is absent-marker",
        "my password value for staging is SYNTHETIC_VALUE",
        "my password definitely for staging is SYNTHETIC_VALUE",
        "my password actually is SYNTHETIC_VALUE",
        "my password securely is SYNTHETIC_VALUE",
        "Bearer policy-marker.SYNTHETIC_VALUE",
        "Bearer token status-marker.SYNTHETIC_VALUE",
        "Bearer token is-marker.SYNTHETIC_VALUE",
        "Authorization: Bearer documentation-marker.SYNTHETIC_VALUE",
        "Bearer token-marker.SYNTHETIC_VALUE",
        "Bearer authentication-marker.SYNTHETIC_VALUE",
        "Bearer authorization-marker.SYNTHETIC_VALUE",
        "Bearer credentials-marker.SYNTHETIC_VALUE",
        "Bearer scheme-marker.SYNTHETIC_VALUE",
        "Bearer header-marker.SYNTHETIC_VALUE",
        "Bearer budget-marker.SYNTHETIC_VALUE",
        "Bearer rotation-marker.SYNTHETIC_VALUE",
        "Bearer ttl-marker.SYNTHETIC_VALUE",
        "Bearer expiry-marker.SYNTHETIC_VALUE",
        "Bearer expiration-marker.SYNTHETIC_VALUE",
        "Bearer format-marker.SYNTHETIC_VALUE",
        "Bearer is-marker.SYNTHETIC_VALUE",
        "Bearer are-marker.SYNTHETIC_VALUE",
        "Bearer was-marker.SYNTHETIC_VALUE",
        "Bearer were-marker.SYNTHETIC_VALUE",
        "Bearer should-marker.SYNTHETIC_VALUE",
        "Bearer must-marker.SYNTHETIC_VALUE",
        "Bearer can-marker.SYNTHETIC_VALUE",
        "Bearer means-marker.SYNTHETIC_VALUE",
        "Bearer represents-marker.SYNTHETIC_VALUE",
        "Bearer uses-marker.SYNTHETIC_VALUE",
    ],
)
def test_natural_language_secret_assignments_fail_closed(tmp_path, text):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "provider/cloud"
        config["model_egress"] = {"provider/cloud": "external"}

    decision = configured_router(tmp_path, configure).classify(text)

    assert decision.sensitivity == "sensitive"
    assert decision.disposition == "block"
    assert decision.model == ""
    assert decision.candidates == []


@pytest.mark.parametrize(
    "text",
    [
        "API key rotation is scheduled",
        "token budget is 1000",
        "passwordless authentication is enabled",
        "my password policy is strict",
        "the token policy is documented",
        "TOKEN_BUDGET=1000",
        "PASSWORD_POLICY=strict",
        "TOKEN_ROTATION=scheduled",
        "PASSWORD_EXPIRY=tomorrow",
        "TOKEN_STATUS=active",
        "PASSWORD_FILE=/run/secrets/service-password",
        "ACCESS_TOKEN_PATH=/run/secrets/service-token",
        "SECRET_SANTA=gift-exchange",
        "Bearer token policy is documented",
        "Bearer authentication is documented",
        "Bearer tokens are credentials",
        "Bearer authorization is documented",
        "Bearer token status is documented",
        "Bearer token supply is documented",
        "Bearer token assembly is complete",
        "Bearer token family is documented",
        "Authorization: Bearer token policy is documented",
        "Authorization: Bearer *** policy is documented",
        "API_KEY_STAGING is not stored",
        "PASSWORD_PROD equals no stored value",
        "the password for staging is not stored",
        "the API key for production is never logged",
        "the token for service is currently not stored",
        "the password currently is not stored",
        "the API key for the staging environment is not stored",
        "A token supply is constrained",
        "A token assembly is constrained",
        "API_KEY_ROTATION_DAYS=30",
        "TOKEN_POLICY=strict",
        "PASSWORD_TTL=3600",
        "ACCESS_TOKEN_EXPIRATION=tomorrow",
        "PASSWORD=none",
        "TOKEN=null",
        "API_KEY=not-configured",
        "SECRET_KEY=unset",
        '{"password": null}',
        '{"api_key":"none"}',
        "my password is not configured",
        "my password is not currently stored",
        "my password is never securely logged",
        "my password is never stored",
        "my password is no value",
        "my password is none",
        "my password is unset",
        "my password is missing",
        "my password is absent",
        "my password is null",
        "API key equals none.",
    ],
)
def test_benign_security_and_token_budget_prose_stays_normal(tmp_path, text):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "provider/cloud"
        config["model_egress"] = {"provider/cloud": "external"}

    decision = configured_router(tmp_path, configure).classify(text)

    assert decision.sensitivity == "normal"
    assert decision.model == "provider/cloud"
    assert decision.egress == "external"


def test_sensitive_model_without_explicit_local_egress_fails_closed(tmp_path):
    def configure(config):
        config["sensitivity"]["local_only_model"] = "custom:local/private-model"

    router = configured_router(tmp_path, configure)
    decision = router.classify("password=private-value")
    status = router.get_status()

    assert decision.sensitivity == "sensitive"
    assert decision.model == ""
    assert decision.candidates == []
    assert decision.should_delegate is False
    assert "not explicitly classified as local" in decision.reason
    assert "local-only model" not in decision.reason
    assert "configured sensitive-model reference" in decision.reason
    assert "physical transport is not verified" in decision.reason
    assert status["sensitivity"]["local_only_egress"] == "unknown"
    assert status["egress_metadata"]["sensitive_migration_required"] is True


def test_sensitive_content_has_no_cloud_fallbacks_and_requests_separate_execution(
    tmp_path,
):
    def configure(config):
        config["tiers"]["fast"]["model"] = "openai-codex/fast"
        config["tiers"]["balanced"]["model"] = "openai-codex/balanced"
        config["tiers"]["strong"]["model"] = "xai-oauth/strong"
        config["sensitivity"]["local_only_model"] = "custom:local/private-model"
        config["model_egress"] = {
            "custom:local/private-model": "local",
            "openai-codex/fast": "external",
            "openai-codex/balanced": "external",
            "xai-oauth/strong": "external",
        }
        config["delegation"]["primary_model"] = "openai-codex/primary"

    decision = configured_router(tmp_path, configure).classify("api_key=private-value")

    assert decision.model == "custom:local/private-model"
    assert decision.egress == "local"
    assert decision.egress_declaration == "operator"
    assert decision.candidates == ["custom:local/private-model"]
    assert decision.candidate_routes == [
        {
            "model": "custom:local/private-model",
            "egress": "local",
            "egress_declaration": "operator",
        }
    ]
    assert decision.to_dict()["candidates"] == decision.candidates
    assert decision.to_dict()["candidate_routes"] == decision.candidate_routes
    assert decision.should_delegate is True
    assert decision.disposition == "separate"
    assert "delegated" not in decision.reason
    assert "operator-declared local model" in decision.reason
    assert "local-only model" not in decision.reason
    assert "physical transport not verified" in decision.reason
    assert "separate execution" in decision.reason


def test_blank_config_still_classifies_task_metadata():
    decision = HybridRouter().classify(
        "Debug this Python function that has a bug in the import logic"
    )

    assert decision.model == ""
    assert decision.tier == "strong"
    assert decision.role == "coding"
    assert decision.difficulty == "hard"
    assert decision.sensitivity == "normal"
    assert decision.should_delegate is False
    assert decision.disposition == "unavailable"


def test_builtin_self_test_validates_classifier_with_blank_models():
    results = HybridRouter().run_tests()

    assert results["passed"] == results["total"] == 9
    assert all(result["passed"] for result in results["results"])


def test_partial_config_never_invents_an_unconfigured_model(tmp_path):
    def configure(config):
        config["tiers"]["fast"]["model"] = "custom:local/only-configured-model"

    decision = configured_router(tmp_path, configure).classify(
        "Summarize the quarterly report for leadership"
    )

    assert decision.model == "custom:local/only-configured-model"
    assert decision.candidates == ["custom:local/only-configured-model"]
    assert "glm-5.2" not in decision.reason


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello there", ["provider/fast", "provider/balanced", "provider/strong"]),
        (
            "Summarize the quarterly report for leadership",
            ["provider/balanced", "provider/strong", "provider/fast"],
        ),
        (
            "Analyze the strategic trade-offs in this architecture",
            ["provider/strong", "provider/balanced", "provider/fast"],
        ),
    ],
)
def test_tier_fallbacks_degrade_by_capability_distance(tmp_path, text, expected):
    def configure(config):
        config["tiers"]["fast"]["model"] = "provider/fast"
        config["tiers"]["balanced"]["model"] = "provider/balanced"
        config["tiers"]["strong"]["model"] = "provider/strong"

    decision = configured_router(tmp_path, configure).classify(text)

    assert decision.candidates == expected


def test_missing_tier_uses_nearest_capability_fallback(tmp_path):
    def configure(config):
        config["tiers"]["fast"]["model"] = "provider/fast"
        config["tiers"]["strong"]["model"] = "provider/strong"

    decision = configured_router(tmp_path, configure).classify(
        "Summarize the quarterly report for leadership"
    )

    assert decision.tier == "balanced"
    assert decision.model == "provider/strong"
    assert decision.candidates == ["provider/strong", "provider/fast"]


def test_simple_cues_are_case_insensitive():
    router = HybridRouter()

    assert (
        router.classify_difficulty("Good morning everyone joining the call today")
        == "simple"
    )


def test_role_cues_match_tokens_and_regular_inflections_not_embedded_words():
    router = HybridRouter()

    assert router.classify_role("This contest celebrates design") == "general"
    assert router.classify_role("The team is refactoring the release") == "coding"
    assert router.classify_role("We need a unit test for this module") == "coding"
    assert router.classify_role("The attestation is complete") == "general"


@pytest.mark.parametrize(
    "text",
    [
        "We papered the wall yesterday",
        "I feel contented with the result",
        "The antique was classed as fragile",
    ],
)
def test_noun_and_adjective_cues_do_not_gain_verb_inflections(text):
    assert HybridRouter().classify_role(text) == "general"


@pytest.mark.parametrize(
    "text",
    [
        "I found my keys",
        "These goods were imported yesterday",
        "The patient tested positive today",
        "The company imports fruit",
        "The patient is testing positive today",
    ],
)
def test_ambiguous_role_cues_do_not_gain_generated_inflections(text):
    assert HybridRouter().classify_role(text) == "general"


@pytest.mark.parametrize(
    ("text", "role"),
    [("find x", "research"), ("import x", "coding"), ("test x", "coding")],
)
def test_ambiguous_role_cues_still_match_exact_literals(text, role):
    assert HybridRouter().classify_role(text) == role


@pytest.mark.parametrize(
    "text",
    [
        "Please improve this sentence",
        "The budget was approved",
        "Improvements are welcome",
    ],
)
def test_prove_difficulty_cue_does_not_match_embedded_words(text):
    assert HybridRouter().classify_difficulty(text) != "hard"


@pytest.mark.parametrize("text", ["prove it", "proves it", "proved it", "proving it"])
def test_prove_difficulty_cue_matches_reviewed_word_forms(text):
    assert HybridRouter().classify_difficulty(text) == "hard"


@pytest.mark.parametrize("text", ["refactor", "refactors", "refactored", "refactoring"])
def test_shipped_refactor_cue_matches_regular_inflections(text):
    assert HybridRouter().classify_role(text) == "coding"


@pytest.mark.parametrize(
    ("text", "role"),
    [
        ("writing a blog", "creative"),
        ("drafting an article", "creative"),
        ("searching for sources", "research"),
    ],
)
def test_multiword_role_cues_inflect_the_semantic_verb(text, role):
    assert HybridRouter().classify_role(text) == role


def test_longest_matched_role_cue_has_precedence_over_multiple_shorter_cues(tmp_path):
    def configure(config):
        for role_config in config["roles"].values():
            role_config["cues"] = []
        config["roles"]["research"]["cues"] = ["very competitive", "analysis"]
        config["roles"]["strategy"]["cues"] = ["competitive analysis"]

    router = configured_router(tmp_path, configure)

    assert router.classify_role("very competitive analysis") == "strategy"


def test_every_shipped_exact_role_cue_routes_to_its_owning_role():
    router = HybridRouter()

    for role, role_config in router.config["roles"].items():
        for cue in role_config.get("cues", []):
            assert router.classify_role(cue) == role, (role, cue)


@pytest.mark.parametrize("text", ["roadmapped", "roadmapping"])
def test_shipped_roadmap_cue_matches_doubled_consonant_inflections(text):
    assert HybridRouter().classify_role(text) == "strategy"


@pytest.mark.parametrize("cue", ["", "   "])
def test_role_cues_reject_empty_or_whitespace_values(tmp_path, cue):
    def configure(config):
        config["roles"]["coding"]["cues"] = [cue]

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"roles\.coding\.cues\[0\]"):
        router.classify("hello")


@pytest.mark.parametrize(
    "cues",
    [
        ["x" * 129],
        [f"cue-{index}" for index in range(65)],
    ],
)
def test_role_cues_are_bounded(tmp_path, cues):
    def configure(config):
        config["roles"]["coding"]["cues"] = cues

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"roles\.coding\.cues"):
        router.classify("hello")


@pytest.mark.parametrize("mutation", ["extra", "missing"])
def test_tiers_require_exactly_the_canonical_keys(tmp_path, mutation):
    def configure(config):
        if mutation == "extra":
            config["tiers"]["fas"] = {"model": "provider/typo"}
        else:
            del config["tiers"]["fast"]

    router = configured_router(tmp_path, configure)

    with pytest.raises(
        ValueError, match="tiers must contain exactly: fast, balanced, strong"
    ):
        router.get_status()


def test_canonical_tier_values_must_be_mappings(tmp_path):
    def configure(config):
        config["tiers"]["fast"] = None

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"tiers\.fast must be a YAML mapping"):
        router.get_status()


@pytest.mark.parametrize("invalid_value", [date(2026, 7, 29), -1, True, "128000"])
def test_tier_max_input_tokens_must_be_a_nonnegative_integer(tmp_path, invalid_value):
    def configure(config):
        config["tiers"]["fast"]["max_input_tokens"] = invalid_value

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"tiers\.fast\.max_input_tokens"):
        router.classify("hello")


def test_status_returns_only_validated_supported_config_fields(tmp_path):
    def configure(config):
        unsupported = date(2026, 7, 29)
        config["tiers"]["fast"]["unsupported"] = unsupported
        config["roles"]["coding"]["unsupported"] = unsupported
        config["difficulty"]["unsupported"] = unsupported
        config["delegation"]["unsupported"] = unsupported

    status = configured_router(tmp_path, configure).get_status()

    json.dumps(status)
    assert "unsupported" not in status["tiers"]["fast"]
    assert "unsupported" not in status["roles"]["coding"]
    assert "unsupported" not in status["difficulty"]
    assert "unsupported" not in status["delegation"]


def test_non_mapping_yaml_is_rejected_with_clear_error(tmp_path):
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        HybridRouter(config_path=str(config_path)).classify("hello")


def test_invalid_regex_reports_the_config_field(tmp_path):
    def configure(config):
        config["sensitivity"]["patterns"] = ["[unterminated"]

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"sensitivity\.patterns\[0\]"):
        router.classify("hello")


def test_non_string_model_ref_reports_the_config_field(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = 42

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"tiers\.balanced\.model must be a string"):
        router.classify("Summarize the report for leadership")


def test_non_mapping_config_section_reports_the_section(tmp_path):
    def configure(config):
        config["roles"] = ["coding"]

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="roles must be a YAML mapping"):
        router.classify("hello")


def test_non_mapping_delegation_section_reports_the_section(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "provider/balanced"
        config["delegation"] = ["fast"]

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="delegation must be a YAML mapping"):
        router.classify("Summarize the report for leadership")


def test_invalid_unused_role_model_is_not_silently_ignored(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "provider/balanced"
        config["roles"]["coding"]["model"] = 42

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"roles\.coding\.model must be a string"):
        router.classify("Summarize the report for leadership")


def test_invalid_difficulty_threshold_reports_the_config_field(tmp_path):
    def configure(config):
        config["difficulty"]["hard_if_many_words"] = "many"

    router = configured_router(tmp_path, configure)

    with pytest.raises(
        ValueError,
        match=r"difficulty\.hard_if_many_words must be a non-negative integer",
    ):
        router.classify("Review quarterly financial results for senior leadership")


@pytest.mark.parametrize("patterns", [None, []])
def test_sensitive_patterns_cannot_be_omitted_or_disabled(tmp_path, patterns):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "cloud/standard-model"
        config["sensitivity"]["local_only_model"] = "local/private-model"
        if patterns is None:
            config["sensitivity"].pop("patterns")
        else:
            config["sensitivity"]["patterns"] = patterns

    router = configured_router(tmp_path, configure)

    with pytest.raises(
        ValueError,
        match=r"sensitivity\.patterns must contain at least one pattern",
    ):
        router.classify("password=private-value")


def test_custom_sensitivity_patterns_are_case_insensitive(tmp_path):
    def configure(config):
        config["sensitivity"]["patterns"] = [r"custom-secret=\S+"]
        config["sensitivity"]["local_only_model"] = "local/private"
        config["model_egress"] = {"local/private": "local"}
        config["tiers"]["balanced"]["model"] = "cloud/standard"

    decision = configured_router(tmp_path, configure).classify(
        "CUSTOM-SECRET=private-value"
    )

    assert decision.sensitivity == "sensitive"
    assert decision.model == "local/private"
    assert decision.candidates == ["local/private"]


def test_custom_patterns_cannot_replace_bundled_secret_detectors(tmp_path):
    def configure(config):
        config["sensitivity"]["patterns"] = [r"^CUSTOM_ONLY$"]
        config["sensitivity"]["local_only_model"] = "local/private"
        config["model_egress"] = {"local/private": "local"}
        config["tiers"]["balanced"]["model"] = "cloud/standard"

    router = configured_router(tmp_path, configure)

    bundled_match = router.classify("password=private-value")
    custom_match = router.classify("custom_only")

    assert bundled_match.sensitivity == "sensitive"
    assert bundled_match.model == "local/private"
    assert bundled_match.candidates == ["local/private"]
    assert custom_match.sensitivity == "sensitive"


def test_status_validates_the_security_configuration(tmp_path):
    def configure(config):
        config["sensitivity"]["patterns"] = []

    router = configured_router(tmp_path, configure)

    with pytest.raises(
        ValueError,
        match=r"sensitivity\.patterns must contain at least one pattern",
    ):
        router.get_status()


def test_status_rejects_invalid_primary_model_before_rendering(tmp_path):
    def configure(config):
        config["delegation"]["primary_model"] = "provider/ok\x1b]52;c;payload\x07model"

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"delegation\.primary_model"):
        router.get_status()


def test_normal_route_rejects_invalid_local_only_model_during_common_validation(
    tmp_path,
):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "cloud/valid"
        config["sensitivity"]["local_only_model"] = "local/\ud800"

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"sensitivity\.local_only_model"):
        router.classify("Summarize the report for leadership")


def test_custom_role_identifier_rejects_surrogates_before_routing(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "cloud/valid"
        config["roles"]["custom\ud800role"] = {
            "model": "cloud/custom",
            "cues": ["match-custom-role"],
        }

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="roles key"):
        router.classify("match-custom-role")


@pytest.mark.parametrize(
    ("section", "bad_name", "error_field"),
    [
        ("roles", "bad`role", "roles key"),
        ("tiers", "bad\x1btier", "tiers key"),
    ],
)
def test_output_exposed_config_identifiers_are_safe(
    tmp_path, section, bad_name, error_field
):
    def configure(config):
        config[section][bad_name] = {"model": "cloud/valid", "cues": ["match"]}

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=error_field):
        router.get_status()


def test_output_exposed_descriptions_reject_terminal_controls(tmp_path):
    def configure(config):
        config["roles"]["coding"]["description"] = "safe\x1b]52;c;payload\x07"

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"roles\.coding\.description"):
        router.get_status()


@pytest.mark.parametrize("invalid_tier", ["fas", "fast`@everyone", "fast\x1b"])
def test_delegation_skip_tiers_require_safe_canonical_identifiers(
    tmp_path, invalid_tier
):
    def configure(config):
        config["delegation"]["skip_for_tier"] = [invalid_tier]

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"delegation\.skip_for_tier\[0\]"):
        router.get_status()


def test_status_reports_unique_active_sensitivity_pattern_count(tmp_path):
    def configure(config):
        config["sensitivity"]["patterns"] = [r"custom-secret=\S+"]

    router = configured_router(tmp_path, configure)
    status = router.get_status()

    active_patterns = {pattern.pattern for pattern in router._compiled_sensitive}
    baseline_router = HybridRouter()
    baseline_router.get_status()
    baseline_patterns = {
        pattern.pattern for pattern in baseline_router._compiled_sensitive
    }
    assert status["sensitivity"]["pattern_count"] == len(active_patterns)
    assert active_patterns == baseline_patterns | {r"custom-secret=\S+"}
    assert len(router._compiled_sensitive) == len(baseline_patterns) + 1


def test_status_reports_effective_model_egress_and_sensitive_readiness(tmp_path):
    def configure(config):
        local_model = "custom:local/private-model"
        config["tiers"]["fast"]["model"] = local_model
        config["tiers"]["balanced"]["model"] = "cloud/balanced"
        config["sensitivity"]["local_only_model"] = local_model
        config["model_egress"] = {local_model: "local"}
        config["delegation"]["primary_model"] = "cloud/balanced"

    status = configured_router(tmp_path, configure).get_status()

    assert status["model_egress"] == {"custom:local/private-model": "local"}
    assert status["tiers"]["fast"]["egress"] == "local"
    assert status["tiers"]["fast"]["egress_declaration"] == "operator"
    assert status["tiers"]["balanced"]["egress"] == "unknown"
    assert status["tiers"]["balanced"]["egress_declaration"] == "none"
    assert status["roles"]["coding"]["egress"] == ""
    assert status["sensitivity"]["local_only_egress"] == "local"
    assert status["sensitivity"]["local_route_ready"] is True
    assert status["delegation"]["primary_egress"] == "unknown"
    assert status["egress_metadata"] == {
        "schema_version": 1,
        "supported_schema_version": 1,
        "metadata_complete": False,
        "unknown_count": 1,
        "unknown_models": ["cloud/balanced"],
        "orphan_count": 0,
        "orphan_models": [],
        "sensitive_migration_required": False,
    }


def test_sensitive_route_always_requests_separate_execution(tmp_path):
    def configure(config):
        config["sensitivity"]["local_only_model"] = "local/private"
        config["model_egress"] = {"local/private": "local"}
        config["delegation"]["primary_model"] = "local/private"
        config["delegation"]["skip_if_same_as_primary"] = True

    decision = configured_router(tmp_path, configure).classify("password=private-value")

    assert decision.model == "local/private"
    assert decision.should_delegate is True
    assert "separate execution" in decision.reason
    assert "same as primary model" not in decision.reason


def test_fast_role_override_delegates_when_selected_model_differs_from_primary(
    tmp_path,
):
    def configure(config):
        config["tiers"]["fast"]["model"] = "provider/primary"
        config["roles"]["creative"]["model"] = "cloud/creative-model"
        config["delegation"]["primary_model"] = "provider/primary"
        config["delegation"]["skip_for_tier"] = ["fast"]

    decision = configured_router(tmp_path, configure).classify("write a blog")

    assert decision.tier == "fast"
    assert decision.model == "cloud/creative-model"
    assert decision.should_delegate is True
    assert "handled inline" not in decision.reason


def test_missing_fast_tier_delegates_to_different_fallback_model(tmp_path):
    def configure(config):
        config["tiers"]["balanced"]["model"] = "cloud/balanced-model"
        config["delegation"]["primary_model"] = "local/primary"
        config["delegation"]["skip_for_tier"] = ["fast"]

    decision = configured_router(tmp_path, configure).classify("hello")

    assert decision.tier == "fast"
    assert decision.model == "cloud/balanced-model"
    assert decision.should_delegate is True
    assert "handled inline" not in decision.reason


@pytest.mark.parametrize(
    "model_ref",
    [
        "provider/",
        "/model",
        "not-a-provider-ref",
        " provider/model",
        "provider/model ",
        "provider/mo\n del",
        "provider/ok\x1b[2Jmodel",
        "provider/model\u2028suffix",
        "provider/model\u200esuffix",
        "provider/model`markdown",
        "provider/model*markup",
        "provider/\ud800",
        "provider/" + "x" * 513,
    ],
)
def test_malformed_or_terminal_unsafe_model_refs_are_rejected(tmp_path, model_ref):
    def configure(config):
        config["tiers"]["balanced"]["model"] = model_ref

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=r"tiers\.balanced\.model"):
        router.classify("Summarize the report for leadership")


@pytest.mark.parametrize(
    ("registry", "error"),
    [
        ([], r"model_egress must be a YAML mapping"),
        ({42: "local"}, r"model_egress\[0\]\.model must be a string"),
        ({"": "local"}, r"model_egress\[0\]\.model must not be empty"),
        ({"provider/model": True}, r"model_egress\[0\]\.egress must be a string"),
        (
            {"provider/model": "private"},
            r"model_egress\[0\]\.egress must be one of: external, local",
        ),
        (
            {"not-a-provider-ref": "local"},
            r"model_egress\[0\]\.model must use a non-empty provider/model reference",
        ),
    ],
)
def test_model_egress_registry_is_strictly_validated(tmp_path, registry, error):
    def configure(config):
        config["model_egress"] = registry

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match=error):
        router.get_status()


def test_sensitive_model_explicitly_marked_external_fails_closed(tmp_path):
    def configure(config):
        model = "custom:maybe-local/private-model"
        config["sensitivity"]["local_only_model"] = model
        config["model_egress"] = {model: "external"}

    decision = configured_router(tmp_path, configure).classify("token=private-value")

    assert decision.model == ""
    assert decision.egress == ""
    assert decision.candidates == []
    assert decision.candidate_routes == []
    assert "not explicitly classified as local" in decision.reason


def test_sensitive_local_attestation_requires_an_exact_model_ref(tmp_path):
    def configure(config):
        config["sensitivity"]["local_only_model"] = "custom:local/model-a"
        config["model_egress"] = {"custom:local/model-b": "local"}

    decision = configured_router(tmp_path, configure).classify("secret=private-value")

    assert decision.model == ""
    assert decision.candidates == []
    assert "not explicitly classified as local" in decision.reason


def test_status_reports_orphan_egress_declarations(tmp_path):
    def configure(config):
        config["model_egress"] = {"provider/unused": "external"}

    metadata = configured_router(tmp_path, configure).get_status()["egress_metadata"]

    assert metadata["metadata_complete"] is False
    assert metadata["unknown_count"] == 0
    assert metadata["orphan_count"] == 1
    assert metadata["orphan_models"] == ["provider/unused"]


def test_normal_same_primary_route_has_inline_disposition(tmp_path):
    def configure(config):
        config["tiers"]["fast"]["model"] = "provider/primary"
        config["delegation"]["primary_model"] = "provider/primary"

    decision = configured_router(tmp_path, configure).classify("hello")

    assert decision.model == "provider/primary"
    assert decision.disposition == "inline"
    assert decision.should_delegate is False


def test_legacy_egress_config_is_reported_and_sensitive_routing_blocks(tmp_path):
    def configure(config):
        config.pop("egress_schema_version", None)
        config.pop("model_egress", None)
        config["sensitivity"]["local_only_model"] = "custom:local/private"

    router = configured_router(tmp_path, configure)
    status = router.get_status()
    decision = router.classify("password=private-value")

    assert status["egress_metadata"]["schema_version"] == 0
    assert status["egress_metadata"]["supported_schema_version"] == 1
    assert status["egress_metadata"]["sensitive_migration_required"] is True
    assert decision.disposition == "block"
    assert decision.candidates == []


def test_nonempty_egress_registry_requires_schema_version(tmp_path):
    def configure(config):
        config.pop("egress_schema_version", None)
        config["model_egress"] = {"custom:local/private": "local"}

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="egress_schema_version must be 1"):
        router.get_status()


@pytest.mark.parametrize("schema_version", [True, "1", 2, -1])
def test_egress_schema_version_is_strictly_validated(tmp_path, schema_version):
    def configure(config):
        config["egress_schema_version"] = schema_version

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="egress_schema_version"):
        router.get_status()


def test_versioned_egress_registry_rejects_null_mapping(tmp_path):
    def configure(config):
        config["egress_schema_version"] = 1
        config["model_egress"] = None

    router = configured_router(tmp_path, configure)

    with pytest.raises(ValueError, match="model_egress must be a YAML mapping"):
        router.get_status()


def test_duplicate_yaml_keys_are_rejected(tmp_path):
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(
        "egress_schema_version: 1\nmodel_egress: {}\nmodel_egress: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate YAML mapping key"):
        HybridRouter(config_path=config_path).get_status()


def test_yaml_merge_keys_are_rejected(tmp_path):
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(
        "defaults: &defaults\n  provider/model: external\n"
        "egress_schema_version: 1\nmodel_egress:\n  <<: *defaults\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="YAML merge keys are not supported"):
        HybridRouter(config_path=config_path).get_status()
