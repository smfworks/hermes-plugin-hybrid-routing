from __future__ import annotations

import json
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

import hybrid_contextual_routing as plugin
from hybrid_contextual_routing import handle_route_classify


def test_route_classify_handler_never_raises_for_malformed_arguments():
    result = json.loads(handle_route_classify(cast(Any, None)))

    assert result == {"error": "Arguments must be a JSON object"}


@pytest.mark.parametrize("patterns", [None, []])
def test_public_handler_rejects_disabled_sensitivity_patterns(
    tmp_path, monkeypatch, patterns
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["tiers"]["balanced"]["model"] = "cloud/standard"
    config["sensitivity"]["local_only_model"] = "local/private"
    if patterns is None:
        config["sensitivity"].pop("patterns")
    else:
        config["sensitivity"]["patterns"] = patterns
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    router = plugin.HybridRouter(config_path=str(config_path))
    monkeypatch.setattr(plugin, "_get_router", lambda: router)

    result = json.loads(handle_route_classify({"text": "password=private-value"}))

    assert "sensitivity.patterns must contain at least one pattern" in result["error"]


def test_blocked_sensitive_route_is_unambiguous_at_every_public_boundary(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["sensitivity"]["local_only_model"] = "local/private"
    config["tiers"]["balanced"]["model"] = "provider/cloud"
    config["model_egress"] = {"provider/cloud": "external"}
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    tool_result = json.loads(
        plugin.handle_route_classify({"text": "password=private-value"})
    )
    natural_language_result = json.loads(
        plugin.handle_route_classify({"text": "my password is private-value"})
    )
    slash_status = plugin.handle_route_command("")
    slash_result = plugin.handle_route_command("password=private-value")
    exit_code = plugin.handle_cli_route(["password=private-value"])
    output = capsys.readouterr().out

    assert tool_result["disposition"] == "block"
    assert tool_result["should_delegate"] is False
    assert natural_language_result["sensitivity"] == "sensitive"
    assert natural_language_result["disposition"] == "block"
    assert natural_language_result["model"] == ""
    assert natural_language_result["candidates"] == []
    assert "**Migration action:**" in slash_status
    assert "exact sensitive model ref" in slash_status
    assert "after verifying its endpoint" in slash_status
    assert "• **Disposition:** `block`" in slash_result
    assert (
        "• **Separate execution:** **BLOCKED — do not process inline**" in slash_result
    )
    assert exit_code == 2
    assert "Sensitivity: sensitive" in output
    assert "Disposition: block" in output
    assert "Separate:   BLOCKED — do not process inline" in output
    assert "password=private-value" not in output


@pytest.mark.parametrize(
    "text",
    [
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
def test_high_value_credential_forms_block_across_public_boundaries(
    tmp_path, monkeypatch, capsys, text
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["tiers"]["balanced"]["model"] = "provider/cloud"
    config["model_egress"] = {"provider/cloud": "external"}
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert tool_result["sensitivity"] == "sensitive"
    assert tool_result["disposition"] == "block"
    assert tool_result["model"] == ""
    assert tool_result["candidates"] == []
    assert "• **Disposition:** `block`" in slash_result
    assert exit_code == 2
    assert "Sensitivity: sensitive" in cli_output
    assert "Disposition: block" in cli_output
    assert text not in cli_output


@pytest.mark.parametrize(
    "text",
    [
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
def test_noncredential_security_forms_stay_normal_across_public_boundaries(
    tmp_path, monkeypatch, capsys, text
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    for tier in config["tiers"].values():
        tier["model"] = "provider/cloud"
    config["model_egress"] = {"provider/cloud": "external"}
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert tool_result["sensitivity"] == "normal"
    assert tool_result["disposition"] in {"inline", "separate"}
    assert tool_result["model"] == "provider/cloud"
    assert "• **Sensitivity:** `normal`" in slash_result
    assert exit_code == 0
    assert "Sensitivity: normal" in cli_output


def test_cli_status_renders_blank_models_with_em_dash(monkeypatch, capsys):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    exit_code = plugin.handle_cli_route([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "fast         → —" in output
    assert "coding       → —" in output
    assert "model       → —" in output
    assert "primary model    → —" in output
    assert "→ None" not in output


@pytest.mark.parametrize(("text", "role"), [("test", "coding"), ("status", "general")])
def test_reserved_task_text_has_explicit_classify_form_across_public_surfaces(
    monkeypatch, capsys, text, role
):
    router = plugin.HybridRouter()
    seen = []
    classify = router.classify

    def record_classify(value):
        seen.append(value)
        return classify(value)

    monkeypatch.setattr(router, "classify", record_classify)
    monkeypatch.setattr(plugin, "_get_router", lambda: router)

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(f"classify {text}")
    exit_code = plugin.handle_cli_route(["classify", text])
    cli_output = capsys.readouterr().out

    assert tool_result["role"] == role
    assert f"• **Role:** `{role}`" in slash_result
    assert "Classifier Smoke Suite" not in slash_result
    assert "Routing — Configuration" not in slash_result
    assert exit_code == 0
    assert "Input:      [redacted" in cli_output
    assert f"Input:      {text}" not in cli_output
    assert f"Role:       {role}" in cli_output
    assert seen == [text, text, text]


def test_specific_role_phrase_wins_across_tool_slash_and_cli(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["roles"]["research"]["model"] = "provider/research"
    config["roles"]["strategy"]["model"] = "provider/strategy"
    config["delegation"]["primary_model"] = "provider/research"
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    tool_result = json.loads(
        plugin.handle_route_classify({"text": "competitive analysis"})
    )
    slash_result = plugin.handle_route_command("competitive analysis")
    exit_code = plugin.handle_cli_route(["competitive analysis"])
    cli_output = capsys.readouterr().out

    assert tool_result["role"] == "strategy"
    assert tool_result["model"] == "provider/strategy"
    assert tool_result["disposition"] == "separate"
    assert "• **Role:** `strategy`" in slash_result
    assert "• **Model:** `provider/strategy`" in slash_result
    assert exit_code == 0
    assert "Role:       strategy" in cli_output
    assert "Model:      provider/strategy" in cli_output


@pytest.mark.parametrize(
    ("text", "role"),
    [
        ("writing a blog", "creative"),
        ("drafting an article", "creative"),
        ("searching for sources", "research"),
    ],
)
def test_multiword_cue_inflections_match_across_tool_slash_and_cli(
    monkeypatch, capsys, text, role
):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert tool_result["role"] == role
    assert f"• **Role:** `{role}`" in slash_result
    assert exit_code == 0
    assert f"Role:       {role}" in cli_output


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
def test_ambiguous_role_inflections_stay_general_across_public_boundaries(
    monkeypatch, capsys, text
):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert tool_result["role"] == "general"
    assert "• **Role:** `general`" in slash_result
    assert exit_code == 0
    assert "Role:       general" in cli_output


@pytest.mark.parametrize(
    "text",
    [
        "Please improve this sentence",
        "The budget was approved",
        "Improvements are welcome",
    ],
)
def test_prove_cue_embedded_words_stay_nonhard_across_public_boundaries(
    monkeypatch, capsys, text
):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    tool_result = json.loads(plugin.handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert tool_result["difficulty"] != "hard"
    assert "• **Difficulty:** `hard`" not in slash_result
    assert exit_code == 0
    assert "Difficulty: hard" not in cli_output


def test_slash_and_cli_surface_effective_egress(tmp_path, monkeypatch, capsys):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    local_model = "custom:local/private"
    external_model = "provider/balanced"
    config["tiers"]["balanced"]["model"] = external_model
    config["sensitivity"]["local_only_model"] = local_model
    config["model_egress"] = {local_model: "local"}
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    slash_status = plugin.handle_route_command("")
    slash_decision = plugin.handle_route_command(
        "Summarize the quarterly report for leadership"
    )
    status_json = json.loads(plugin.handle_route_status({}))

    assert f"`{external_model}` (`unknown`)" in slash_status
    assert (
        f"`{local_model}` (`local`, operator-declared; transport not verified; ready)"
        in slash_status
    )
    assert "**Sensitive model:**" in slash_status
    assert "Sensitive local-only" not in slash_status
    assert "**Egress metadata:** incomplete (`1` unknown, `0` orphan)" in slash_status
    assert "**Egress schema:** `1` (supported `1`)" in slash_status
    assert "**Sensitive migration required:** no" in slash_status
    assert "• **Egress:** `unknown`" in slash_decision
    assert "• **Egress declaration:** `none`" in slash_decision
    assert f"`{external_model}` (`unknown`)" in slash_decision
    assert status_json["sensitivity"]["local_route_ready"] is True

    assert plugin.handle_cli_route([]) == 0
    cli_status = capsys.readouterr().out
    assert f"{external_model} [unknown]" in cli_status
    assert (
        f"{local_model} [local, operator-declared; transport not verified; ready]"
        in cli_status
    )
    assert "metadata       → incomplete (1 unknown, 0 orphan)" in cli_status
    assert "schema         → 1 (supported 1)" in cli_status
    assert "migration      → not required" in cli_status

    assert (
        plugin.handle_cli_route(
            ["Summarize", "the", "quarterly", "report", "for", "leadership"]
        )
        == 0
    )
    cli_decision = capsys.readouterr().out
    assert "Egress:    unknown" in cli_decision
    assert "Egress declaration: none" in cli_decision
    assert f"{external_model} [unknown]" in cli_decision


def test_local_egress_is_always_qualified_in_human_outputs(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    local_model = "cloud-looking/local-alias"
    config["tiers"]["balanced"]["model"] = local_model
    config["roles"]["creative"]["model"] = local_model
    config["delegation"]["primary_model"] = local_model
    config["model_egress"] = {local_model: "local"}
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    task = "write a blog post about routing"
    slash_status = plugin.handle_route_command("")
    slash_decision = plugin.handle_route_command(task)

    markdown_provenance = "`local`, operator-declared; transport not verified"
    assert slash_status.count(f"`{local_model}` ({markdown_provenance})") == 2
    assert f"• **Egress:** {markdown_provenance}" in slash_decision
    assert f"`{local_model}` ({markdown_provenance})" in slash_decision

    assert plugin.handle_cli_route([]) == 0
    cli_status = capsys.readouterr().out
    plain_provenance = "local, operator-declared; transport not verified"
    assert cli_status.count(f"{local_model} [{plain_provenance}]") == 3

    assert plugin.handle_cli_route(task.split()) == 0
    cli_decision = capsys.readouterr().out
    assert f"Egress:    {plain_provenance}" in cli_decision
    assert f"{local_model} [{plain_provenance}]" in cli_decision


def test_status_surfaces_do_not_call_unknown_egress_operator_declared(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    local_model = "custom:local/private"
    config["sensitivity"]["local_only_model"] = local_model
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    slash_status = plugin.handle_route_command("")
    assert (
        f"`{local_model}` (`unknown`, not declared; transport not verified; blocked)"
        in slash_status
    )
    assert "`unknown`, operator-declared" not in slash_status

    assert plugin.handle_cli_route([]) == 0
    cli_status = capsys.readouterr().out
    assert (
        f"{local_model} [unknown, not declared; transport not verified; blocked]"
        in cli_status
    )
    assert "unknown, operator-declared" not in cli_status


def test_status_tool_rejects_noninteger_max_input_tokens(tmp_path, monkeypatch):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["tiers"]["fast"]["max_input_tokens"] = date(2026, 7, 29)
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    result = json.loads(plugin.handle_route_status({}))

    assert "tiers.fast.max_input_tokens" in result["error"]
    assert "not JSON serializable" not in result["error"]


def test_cli_status_rejects_control_bearing_primary_model(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    control_ref = "provider/ok\x1b]52;c;payload\x07model"
    config["delegation"]["primary_model"] = control_ref
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    exit_code = plugin.handle_cli_route([])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "delegation.primary_model" in output
    assert "\x1b" not in output


def test_slash_command_rejects_surrogate_model_without_echoing_it(
    tmp_path, monkeypatch
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    surrogate_ref = "provider/\ud800"
    config["tiers"]["balanced"]["model"] = surrogate_ref
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    output = plugin.handle_route_command("Summarize the report for leadership")

    assert output.startswith("Route command failed:")
    assert "tiers.balanced.model" in output
    assert surrogate_ref not in output


def test_invalid_local_only_model_is_blocked_at_tool_slash_and_cli_boundaries(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    surrogate_ref = "local/\ud800"
    config["tiers"]["balanced"]["model"] = "cloud/valid"
    config["sensitivity"]["local_only_model"] = surrogate_ref
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )
    text = "Summarize the report for leadership"

    tool_result = json.loads(handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert "sensitivity.local_only_model" in tool_result["error"]
    assert slash_result.startswith("Route command failed:")
    assert "sensitivity.local_only_model" in slash_result
    assert exit_code == 1
    assert "sensitivity.local_only_model" in cli_output
    assert surrogate_ref not in json.dumps(tool_result)
    assert surrogate_ref not in slash_result
    assert surrogate_ref not in cli_output


def test_invalid_role_identifier_is_blocked_at_tool_slash_and_cli_boundaries(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    surrogate_role = "custom\ud800role"
    config["roles"][surrogate_role] = {
        "model": "cloud/custom",
        "cues": ["match-custom-role"],
    }
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )
    text = "match-custom-role"

    tool_result = json.loads(handle_route_classify({"text": text}))
    slash_result = plugin.handle_route_command(text)
    exit_code = plugin.handle_cli_route([text])
    cli_output = capsys.readouterr().out

    assert "roles key" in tool_result["error"]
    assert slash_result.startswith("Route command failed:")
    assert "roles key" in slash_result
    assert exit_code == 1
    assert "roles key" in cli_output
    assert surrogate_role not in json.dumps(tool_result)
    assert surrogate_role not in slash_result
    assert surrogate_role not in cli_output


def test_invalid_skip_tier_is_blocked_at_tool_slash_and_cli_boundaries(
    tmp_path, monkeypatch, capsys
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["delegation"]["skip_for_tier"] = ["fas"]
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    tool_result = json.loads(plugin.handle_route_status({}))
    slash_result = plugin.handle_route_command("")
    exit_code = plugin.handle_cli_route([])
    cli_output = capsys.readouterr().out

    assert "delegation.skip_for_tier[0]" in tool_result["error"]
    assert slash_result.startswith("Route command failed:")
    assert "delegation.skip_for_tier[0]" in slash_result
    assert exit_code == 1
    assert "delegation.skip_for_tier[0]" in cli_output


def test_slash_decision_code_wraps_markdown_active_dynamic_values(
    tmp_path, monkeypatch
):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["roles"]["__ZXQROLE__"] = {
        "model": "provider/x/~~ZXQMODEL~~/@everyone",
        "cues": ["match-zxq-role"],
    }
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    output = plugin.handle_route_command("match-zxq-role")

    assert "• **Role:** `__ZXQROLE__`" in output
    assert "• **Model:** `provider/x/~~ZXQMODEL~~/@everyone`" in output
    assert "**Reason:** `" in output
    assert "@everyone`" in output


def test_slash_test_code_wraps_configured_models(tmp_path, monkeypatch):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    model = "provider/x/~~ZXQ_MODEL~~/@everyone"
    for tier in config["tiers"].values():
        tier["model"] = model
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    output = plugin.handle_route_command("test")

    assert f"   → `{model}`" in output
    assert f"   → {model}" not in output


def test_slash_test_renders_blank_models_with_em_dash(monkeypatch):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    output = plugin.handle_route_command("test")

    assert "   → `—`" in output
    assert "   → ``" not in output


def test_slash_errors_code_wrap_markdown_active_field_names(tmp_path, monkeypatch):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["roles"]["__ZXQROLE__"] = {
        "model": "provider/model",
        "description": "unsafe\x1bdescription",
    }
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(config_path)),
    )

    output = plugin.handle_route_command("")

    assert output.startswith("Route command failed: `")
    assert "roles.__ZXQROLE__.description" in output
    assert "\x1b" not in output


def test_status_paths_are_safe_for_markdown_and_terminal_output(
    tmp_path, monkeypatch, capsys
):
    markdown_dir = tmp_path / "profile`@everyone"
    markdown_dir.mkdir()
    markdown_config = markdown_dir / "routing_config.yaml"
    markdown_config.write_text(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(markdown_config)),
    )

    slash_output = plugin.handle_route_command("")

    assert f"**Config:** ``{markdown_config}``" in slash_output
    assert f"**Config:** `{markdown_config}`" not in slash_output

    terminal_dir = tmp_path / "profile\x1b]8;;example.invalid\x07name"
    terminal_dir.mkdir()
    terminal_config = terminal_dir / "routing_config.yaml"
    terminal_config.write_text(
        markdown_config.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(
        plugin,
        "_get_router",
        lambda: plugin.HybridRouter(config_path=str(terminal_config)),
    )

    assert plugin.handle_cli_route([]) == 0
    cli_output = capsys.readouterr().out
    assert "\x1b" not in cli_output
    assert "\x07" not in cli_output
    assert "\\x1b" in cli_output
    assert "\\x07" in cli_output


def test_router_factory_observes_config_edits_without_restart(tmp_path, monkeypatch):
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["tiers"]["balanced"]["model"] = "provider/old-model"
    config_dir = tmp_path / "hybrid_routing"
    config_dir.mkdir()
    config_path = config_dir / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)

    first = plugin._get_router().classify("Summarize the report for leadership")
    config["tiers"]["balanced"]["model"] = "provider/new-model"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    second = plugin._get_router().classify("Summarize the report for leadership")

    assert first.model == "provider/old-model"
    assert second.model == "provider/new-model"


def test_router_factory_uses_authoritative_hermes_home(tmp_path, monkeypatch):
    authoritative_home = tmp_path / "authoritative"
    process_home = tmp_path / "process"
    config = yaml.safe_load(
        (
            Path(__file__).parents[1]
            / "hybrid_contextual_routing"
            / "data"
            / "routing_config.yaml"
        ).read_text(encoding="utf-8")
    )
    config["tiers"]["balanced"]["model"] = "provider/authoritative"
    config_dir = authoritative_home / "hybrid_routing"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "routing_config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(process_home))
    monkeypatch.setitem(
        sys.modules,
        "hermes_constants",
        types.SimpleNamespace(get_hermes_home=lambda: authoritative_home),
    )

    decision = plugin._get_router().classify("Summarize the report for leadership")

    assert decision.model == "provider/authoritative"
    assert Path(plugin._get_router().config_path) == config_path


def test_register_uses_current_hermes_plugin_context_api():
    class Logger:
        def info(self, *args, **kwargs):
            del args, kwargs

    class Context:
        def __init__(self):
            self.logger = Logger()
            self.tools = []
            self.commands = []
            self.cli_commands = []
            self.skills = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs)

        def register_command(self, **kwargs):
            self.commands.append(kwargs)

        def register_cli_command(self, **kwargs):
            self.cli_commands.append(kwargs)

        def register_skill(self, **kwargs):
            assert isinstance(kwargs["path"], Path)
            self.skills.append(kwargs)

    context = Context()
    plugin.register(context)

    assert [item["name"] for item in context.tools] == [
        "route_classify",
        "route_status",
        "route_test",
    ]
    assert [item["name"] for item in context.commands] == ["route"]
    assert context.commands[0]["args_hint"] == "[status|test|classify <text>|text]"
    assert [item["name"] for item in context.cli_commands] == ["route"]
    assert [item["name"] for item in context.skills] == ["hybrid-contextual-routing"]
    assert context.skills[0]["path"].as_posix().endswith("skill/SKILL.md")


def test_entrypoint_registration_backfills_manifest_metadata():
    class Manifest:
        version = ""
        description = ""
        author = ""

    class Context:
        manifest = Manifest()
        logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()

        def register_tool(self, **kwargs):
            pass

        def register_command(self, **kwargs):
            pass

        def register_cli_command(self, **kwargs):
            pass

        def register_skill(self, **kwargs):
            pass

    context = Context()
    plugin.register(context)

    assert context.manifest.version == plugin.__version__
    assert context.manifest.description == plugin.__description__
    assert context.manifest.author == plugin.__author__


def test_cli_test_returns_nonzero_when_smoke_suite_fails(monkeypatch, capsys):
    class FakeRouter:
        def run_tests(self):
            return {
                "passed": 8,
                "total": 9,
                "results": [
                    {
                        "test": 1,
                        "input": "hi",
                        "passed": False,
                        "actual": {
                            "model": "",
                            "tier": "fast",
                            "role": "general",
                            "delegate": False,
                        },
                    }
                ],
            }

    monkeypatch.setattr(plugin, "_get_router", lambda: FakeRouter())

    assert plugin.handle_cli_route(["test"]) == 1
    output = capsys.readouterr().out
    assert "8/9 passed" in output
    assert "FAILED" in output


def test_cli_test_returns_zero_when_smoke_suite_passes(monkeypatch, capsys):
    class FakeRouter:
        def run_tests(self):
            return {"passed": 9, "total": 9, "results": []}

    monkeypatch.setattr(plugin, "_get_router", lambda: FakeRouter())

    assert plugin.handle_cli_route(["test"]) == 0
    assert "ALL CLASSIFIER CHECKS PASSED" in capsys.readouterr().out


def test_tool_errors_sanitize_control_characters(monkeypatch):
    def boom():
        raise ValueError("bad\x1b]52;c;payload\x07 config")

    monkeypatch.setattr(plugin, "_get_router", boom)

    result = json.loads(plugin.handle_route_classify({"text": "hello"}))

    assert result["error"].startswith("Classification failed:")
    assert "\x1b" not in result["error"]
    assert "\\x1b" in result["error"]


def test_route_classify_rejects_oversized_text_without_constructing_router(
    monkeypatch,
):
    called = {"value": False}

    def boom():
        called["value"] = True
        raise AssertionError("router should not be constructed")

    monkeypatch.setattr(plugin, "_get_router", boom)

    result = json.loads(
        plugin.handle_route_classify({"text": "x" * (plugin.MAX_CLASSIFY_CHARS + 1)})
    )

    assert called["value"] is False
    assert result == {
        "error": f"text must be at most {plugin.MAX_CLASSIFY_CHARS} characters"
    }


def test_register_warns_when_bundled_skill_is_missing(monkeypatch, caplog):
    import logging

    class Context:
        def register_tool(self, **kwargs):
            pass

        def register_command(self, **kwargs):
            pass

        def register_cli_command(self, **kwargs):
            pass

        def register_skill(self, **kwargs):
            raise AssertionError("skill should not register")

    monkeypatch.setattr(Path, "exists", lambda self: False)
    caplog.set_level(logging.WARNING, logger="hybrid_contextual_routing")

    plugin.register(Context())

    assert "bundled skill missing" in caplog.text
