from __future__ import annotations

import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    tomllib: Any = import_module("tomli")


ROOT = Path(__file__).parents[1]


def test_release_versions_and_source_install_manifest_stay_in_sync():
    import hybrid_contextual_routing as plugin

    project_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = project_data["project"]["version"]
    root_manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    package_manifest = yaml.safe_load(
        (ROOT / "hybrid_contextual_routing" / "plugin.yaml").read_text(encoding="utf-8")
    )
    skill_text = (ROOT / "hybrid_contextual_routing" / "skill" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    skill_version = re.search(r"^version:\s*(\S+)$", skill_text, re.MULTILINE)

    assert root_manifest["name"] == package_manifest["name"]
    assert (
        project_data["project"]["entry-points"]["hermes_agent.plugins"][
            "hybrid-contextual-routing"
        ]
        == "hybrid_contextual_routing"
    )
    assert skill_version is not None
    assert {
        project_version,
        str(root_manifest["version"]),
        str(package_manifest["version"]),
        skill_version.group(1),
    } == {project_version}
    assert (ROOT / "__init__.py").exists()
    assert {
        project_data["project"]["description"],
        root_manifest["description"].strip(),
        package_manifest["description"].strip(),
        plugin.__description__,
    } == {project_data["project"]["description"]}


def test_entrypoint_metadata_constants_match_source_manifest():
    import hybrid_contextual_routing as plugin

    manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))

    assert plugin.__version__ == str(manifest["version"])
    assert plugin.__description__ == manifest["description"].strip()
    assert plugin.__author__ == manifest["author"]


def test_every_package_data_pattern_matches_a_real_resource():
    project_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_dir = ROOT / "hybrid_contextual_routing"
    patterns = project_data["tool"]["setuptools"]["package-data"][
        "hybrid_contextual_routing"
    ]

    assert patterns
    for pattern in patterns:
        assert list(package_dir.glob(pattern)), (
            f"package-data pattern is stale: {pattern}"
        )


def test_sdist_manifest_keeps_source_plugin_and_trust_model_complete():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert "include __init__.py" in manifest
    assert "include plugin.yaml" in manifest
    assert "include ANNOUNCE-POST.md CHANGELOG.md" in manifest
    assert "recursive-include docs *.md" in manifest


def test_packaged_default_config_declares_egress_schema_version():
    config = yaml.safe_load(
        (ROOT / "hybrid_contextual_routing" / "data" / "routing_config.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert config["egress_schema_version"] == 1
    assert config["model_egress"] == {}


def test_readme_uses_distribution_safe_trust_link_and_scoped_sensitivity_claims():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert (
        "https://github.com/smfworks/hermes-plugin-hybrid-routing/"
        "blob/v1.1.0/docs/EGRESS-TRUST-MODEL.md"
    ) in readme
    assert "](docs/EGRESS-TRUST-MODEL.md)" not in readme
    assert "secrets, PII, and confidentiality markers" not in readme
    assert "Bundled secret and PII patterns" not in readme
    assert (
        "secret assignments, bearer credentials, private-key headers, "
        "SSN/card-number formats, and confidentiality markers" in readme
    )


def test_announcement_uses_canonical_absolute_article_url():
    announcement = (ROOT / "ANNOUNCE-POST.md").read_text(encoding="utf-8")

    assert (
        "https://www.smfclearinghouse.com/blog/"
        "2026-07-28-hybrid-contextual-model-routing-hermes"
    ) in announcement
    assert "](/blog/" not in announcement


def test_trust_model_uses_runtime_operator_attestation_wording():
    trust_model = (ROOT / "docs" / "EGRESS-TRUST-MODEL.md").read_text(encoding="utf-8")

    assert "local, operator-declared; transport not verified; ready" in trust_model
    assert "shows `local, ready`" not in trust_model


def test_readme_scopes_role_cue_inflections_to_reviewed_words():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Only shipped and reviewed cue words receive regular inflections" in readme
