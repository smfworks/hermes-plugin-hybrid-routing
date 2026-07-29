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
