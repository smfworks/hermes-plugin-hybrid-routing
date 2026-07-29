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
    assert exit_code == 0
    assert "Sensitivity: sensitive" in output
    assert "Disposition: block" in output
    assert "Separate:   BLOCKED — do not process inline" in output


def test_cli_status_renders_blank_models_with_em_dash(monkeypatch, capsys):
    monkeypatch.setattr(plugin, "_get_router", plugin.HybridRouter)

    exit_code = plugin.handle_cli_route([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "fast         → —" in output
    assert "coding       → —" in output
    assert "local_only  → —" in output
    assert "primary model    → —" in output
    assert "→ None" not in output


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
    assert f"`{local_model}` (`local`, ready)" in slash_status
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
    assert f"{local_model} [local, ready]" in cli_status
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
    assert context.commands[0]["args_hint"] == "[status|test|text]"
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
    assert context.manifest.description.startswith("Contextual model routing")
    assert context.manifest.author == "SMF Works"
