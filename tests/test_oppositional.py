from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

import hybrid_contextual_routing as plugin
from hybrid_contextual_routing.router import HybridRouter, redacted_input_preview

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


def _cloud_only(config) -> None:
    for tier in config["tiers"].values():
        tier["model"] = "provider/cloud"
    config["model_egress"] = {"provider/cloud": "external"}
    config["sensitivity"]["local_only_model"] = ""


@pytest.mark.parametrize(
    "text",
    [
        "password=SYNTHETIC_VALUE",
        "ｐａｓｓｗｏｒｄ＝SYNTHETIC_VALUE",
        "password＝SYNTHETIC_VALUE",
        "pass\u200bword=SYNTHETIC_VALUE",
        "p\u200cassword=SYNTHETIC_VALUE",
        "password\u200d=SYNTHETIC_VALUE",
        "password\ufeff=SYNTHETIC_VALUE",
        "PASSWORD\u0301=SYNTHETIC_VALUE",
        "раssword=SYNTHETIC_VALUE",
        "passwor\u0501=SYNTHETIC_VALUE",
    ],
)
def test_obfuscated_secret_assignments_do_not_route_to_cloud(tmp_path, text):
    decision = configured_router(tmp_path, _cloud_only).classify(text)

    assert decision.sensitivity == "sensitive"
    assert decision.disposition == "block"
    assert decision.model == ""
    assert decision.candidates == []


@pytest.mark.parametrize(
    "text",
    [
        "AWS_ACCESS_KEY_ID=AKIATESTKEYIDEXAMPLE",
        "OPENAI_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz",
        "sk-proj-abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "xoxb-123456789012-123456789012-abcdefghij",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sig",
        "mongodb://user:SYNTHETIC_VALUE@localhost:27017",
        "postgres://user:SYNTHETIC_VALUE@localhost/db",
        "private_key=SYNTHETIC_VALUE",
        "passwd=SYNTHETIC_VALUE",
        "DB_PASS=SYNTHETIC_VALUE",
        "ENCRYPTION_KEY=SYNTHETIC_VALUE",
        "Authorization: Token ghp_abcdefghijklmnopqrstuvwxyz",
        "Authorization: Basic dXNlcjpwYXNzd29yZA==",
    ],
)
def test_high_signal_credential_shapes_fail_closed(tmp_path, text):
    decision = configured_router(tmp_path, _cloud_only).classify(text)

    assert decision.sensitivity == "sensitive"
    assert decision.disposition == "block"
    assert decision.model == ""


def test_explain_does_not_echo_classify_payload(tmp_path):
    secret = "password=SYNTHETIC_SUPER_SECRET_VALUE"
    preview = configured_router(tmp_path, _cloud_only).explain(secret)

    assert preview["input_preview"] == redacted_input_preview(secret)
    assert "SYNTHETIC_SUPER_SECRET_VALUE" not in json.dumps(preview)


def test_yaml_aliases_are_rejected(tmp_path):
    config_path = tmp_path / "routing_config.yaml"
    config_path.write_text(
        DEFAULT_CONFIG.read_text(encoding="utf-8")
        + "\nextra: &anchor value\ncopy: *anchor\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="YAML aliases are not supported"):
        HybridRouter(config_path=str(config_path)).get_status()


def test_copied_config_without_schema_v1_cannot_authorize_local(tmp_path):
    def configure(config):
        config.pop("egress_schema_version", None)
        config.pop("model_egress", None)
        config["sensitivity"]["local_only_model"] = "custom:local/private"
        config["tiers"]["balanced"]["model"] = "provider/cloud"

    router = configured_router(tmp_path, configure)
    decision = router.classify("password=SYNTHETIC_VALUE")

    assert router.get_status()["egress_metadata"]["schema_version"] == 0
    assert decision.disposition == "block"
    assert decision.model == ""


def test_local_looking_names_are_not_inferred_without_attestation(tmp_path):
    def configure(config):
        config["sensitivity"]["local_only_model"] = "custom:local/private-model"
        config["model_egress"] = {}
        config["tiers"]["balanced"]["model"] = "provider/cloud"

    router = configured_router(tmp_path, configure)
    decision = router.classify("password=SYNTHETIC_VALUE")

    assert decision.disposition == "block"
    assert decision.model == ""
    assert decision.egress == ""


def test_cli_blocks_sensitive_text_without_echoing_it(tmp_path, monkeypatch, capsys):
    router = configured_router(tmp_path, _cloud_only)
    monkeypatch.setattr(plugin, "_get_router", lambda: router)
    secret = "password=SYNTHETIC_SUPER_SECRET_VALUE"

    exit_code = plugin.handle_cli_route([secret])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Disposition: block" in output
    assert secret not in output
    assert "SYNTHETIC_SUPER_SECRET_VALUE" not in output
    assert redacted_input_preview(secret) in output
