"""Hybrid Contextual Routing — Hermes plugin registration.

Wires the classification engine into Hermes as three tools, a slash
command (/route), a CLI subcommand (hermes route), and a bundled skill.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

from .router import HybridRouter

logger = logging.getLogger(__name__)

__version__ = "1.0.1"
__description__ = (
    "Contextual model routing for Hermes agents. Classifies tasks by sensitivity, "
    "role, and difficulty, then recommends the right model for the job. Supports "
    "cloud/local hybrid inference stacks with per-tier, per-role, and fail-closed "
    "sensitivity recommendations while keeping the primary session model fixed for "
    "prompt caching."
)
__author__ = "SMF Works"


def _safe_output_text(value: object) -> str:
    """Render arbitrary values without terminal controls or Unicode controls."""
    rendered = []
    for char in str(value):
        category = unicodedata.category(char)
        if not (category.startswith("C") or category in {"Zl", "Zp"}):
            rendered.append(char)
            continue
        codepoint = ord(char)
        if char == "\n":
            rendered.append(r"\n")
        elif char == "\r":
            rendered.append(r"\r")
        elif char == "\t":
            rendered.append(r"\t")
        elif codepoint <= 0xFF:
            rendered.append(f"\\x{codepoint:02x}")
        elif codepoint <= 0xFFFF:
            rendered.append(f"\\u{codepoint:04x}")
        else:
            rendered.append(f"\\U{codepoint:08x}")
    return "".join(rendered)


def _markdown_code(value: object) -> str:
    """Put an arbitrary value in a CommonMark-safe inline code span."""
    text = _safe_output_text(value)
    longest_run = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest_run + 1)
    if not text:
        return f"{fence} {fence}"
    padding = " " if text.startswith(("`", " ")) or text.endswith(("`", " ")) else ""
    return f"{fence}{padding}{text}{padding}{fence}"


# ── Router factory ─────────────────────────────────────────────────────
# A router is cheap to construct. Creating one per command/tool call keeps
# profile resolution thread-safe and makes config edits visible immediately.


def _get_router() -> HybridRouter:
    """Create a router for the active profile's current configuration.

    Checks for a user override config at:
    $HERMES_HOME/hybrid_routing/routing_config.yaml

    Hermes' authoritative profile-home API is used when available. Standalone
    package use falls back to HERMES_HOME and then ~/.hermes.
    """
    import os
    from importlib import import_module

    try:
        get_hermes_home = import_module("hermes_constants").get_hermes_home
    except (ImportError, AttributeError):
        hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    else:
        hermes_home = Path(get_hermes_home())

    candidate = hermes_home / "hybrid_routing" / "routing_config.yaml"
    user_config = str(candidate) if candidate.exists() else None

    return HybridRouter(config_path=user_config)


# ── Tool schemas ───────────────────────────────────────────────────────

ROUTE_CLASSIFY_SCHEMA = {
    "name": "route_classify",
    "description": (
        "Classify a task and get a routing recommendation. "
        "Returns which model should handle the task, whether to delegate "
        "to a subagent, and why. Use this when deciding which model is "
        "best suited for a task — especially for strategy, creative, "
        "coding, research, or sensitive content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The task text to classify.",
            },
        },
        "required": ["text"],
    },
}

ROUTE_STATUS_SCHEMA = {
    "name": "route_status",
    "description": (
        "Show the current model routing configuration — which models are "
        "assigned to each tier (fast, balanced, strong) and role "
        "(coding, research, creative, strategy). Use this to understand "
        "the routing setup before classifying tasks."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

ROUTE_TEST_SCHEMA = {
    "name": "route_test",
    "description": (
        "Run the 9-case classifier smoke suite. Returns pass/fail for "
        "sensitivity, role, difficulty, and tier classification cases."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


# ── Tool handlers ──────────────────────────────────────────────────────


def handle_route_classify(args: dict, **kwargs) -> str:
    """Classify a task and return the routing decision as JSON."""
    del kwargs
    if not isinstance(args, dict):
        return json.dumps({"error": "Arguments must be a JSON object"})
    text = args.get("text", "")
    if not isinstance(text, str):
        return json.dumps({"error": "'text' must be a string"})
    if not text.strip():
        return json.dumps({"error": "No text provided to classify"})
    try:
        router = _get_router()
        decision = router.classify(text)
        return json.dumps(decision.to_dict(), indent=2)
    except Exception as e:
        logger.error("route_classify failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Classification failed: {e}"})


def handle_route_status(args: dict, **kwargs) -> str:
    """Return the current routing configuration as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        status = router.get_status()
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error("route_status failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Status failed: {e}"})


def handle_route_test(args: dict, **kwargs) -> str:
    """Run the classifier smoke suite and return results as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        results = router.run_tests()
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.error("route_test failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Test failed: {e}"})


# ── Slash command handler ──────────────────────────────────────────────


def handle_route_command(args: str, **kwargs) -> str:
    """Handle /route slash command.

    Usage:
      /route                  — show routing config
      /route test             — run test suite
      /route <text>           — classify the text
    """
    del kwargs
    arg = (args or "").strip()
    try:
        router = _get_router()
        if not arg or arg == "status":
            status = router.get_status()
            lines = ["**Hybrid Contextual Routing — Configuration**", ""]
            lines.append("**Tiers:**")
            for tier_name, tier_cfg in status.get("tiers", {}).items():
                lines.append(
                    f"  • {_markdown_code(tier_name)} → "
                    f"{_markdown_code(tier_cfg.get('model') or '—')}"
                )
            lines.append("")
            lines.append("**Roles:**")
            for role_name, role_cfg in status.get("roles", {}).items():
                lines.append(
                    f"  • {_markdown_code(role_name)} → "
                    f"{_markdown_code(role_cfg.get('model') or '—')}"
                )
            lines.append("")
            local_only = status.get("sensitivity", {}).get("local_only_model") or "—"
            lines.append(f"**Sensitive local-only:** {_markdown_code(local_only)}")
            lines.append(
                f"**Config:** {_markdown_code(status.get('config_path', '—'))}"
            )
            return "\n".join(lines)
        elif arg == "test":
            results = router.run_tests()
            passed = results["passed"]
            total = results["total"]
            status_emoji = "✅" if passed == total else "❌"
            lines = [
                f"**Classifier Smoke Suite — {passed}/{total} passed** {status_emoji}",
                "",
            ]
            for r in results["results"]:
                emoji = "✅" if r["passed"] else "❌"
                lines.append(
                    f"{emoji} Test {r['test']}: {_markdown_code(r['input'][:50])}"
                )
                lines.append(f"   → {_markdown_code(r['actual']['model'] or '—')}")
            return "\n".join(lines)
        else:
            decision = router.classify(arg)
            execution = "RECOMMENDED" if decision.should_delegate else "NOT REQUIRED"
            lines = [
                "**Routing Decision**",
                "",
                f"• **Model:** {_markdown_code(decision.model or '—')}",
                f"• **Tier:** {_markdown_code(decision.tier)}",
                f"• **Role:** {_markdown_code(decision.role)}",
                f"• **Difficulty:** {_markdown_code(decision.difficulty)}",
                f"• **Sensitivity:** {_markdown_code(decision.sensitivity)}",
                f"• **Separate execution:** {execution}",
                "",
                f"**Reason:** {_markdown_code(decision.reason)}",
                "",
                "**Fallback chain:**",
            ]
            for i, m in enumerate(decision.candidates):
                label = "primary" if i == 0 else f"fallback {i}"
                lines.append(f"  {_markdown_code(label)} → {_markdown_code(m)}")
            return "\n".join(lines)
    except Exception as e:
        logger.error("route command failed: %s", _safe_output_text(e))
        return f"Route command failed: {_markdown_code(e)}"


# ── CLI command handler ────────────────────────────────────────────────


def handle_cli_route(args) -> int:
    """Handle `hermes route` CLI subcommand."""
    arg = " ".join(args) if args else ""
    try:
        router = _get_router()
        if not arg or arg == "status":
            status = router.get_status()
            print("=" * 60)
            print("  HYBRID CONTEXTUAL ROUTING — Configuration")
            print("=" * 60)
            print()
            print("TIERS:")
            for tier_name, tier_cfg in status.get("tiers", {}).items():
                model = tier_cfg.get("model") or "—"
                desc = tier_cfg.get("description", "")
                print(
                    f"  {_safe_output_text(tier_name):12s} → {_safe_output_text(model)}"
                )
                if desc:
                    print(f"  {' ':12s}   {_safe_output_text(desc)}")
            print()
            print("ROLES:")
            for role_name, role_cfg in status.get("roles", {}).items():
                model = role_cfg.get("model") or "—"
                desc = role_cfg.get("description", "")
                auxiliary = role_cfg.get("auxiliary", False)
                marker = " (auxiliary)" if auxiliary else ""
                print(
                    f"  {_safe_output_text(role_name):12s} → "
                    f"{_safe_output_text(model)}{marker}"
                )
                if desc:
                    print(f"  {' ':12s}   {_safe_output_text(desc)}")
            print()
            sens = status.get("sensitivity", {})
            print("SENSITIVITY:")
            local_only_model = sens.get("local_only_model") or "—"
            print(f"  local_only  → {_safe_output_text(local_only_model)}")
            print(f"  patterns    → {sens.get('pattern_count', 0)} regex rules")
            print()
            deleg = status.get("delegation", {})
            print("DELEGATION:")
            primary_model = deleg.get("primary_model") or "—"
            print(f"  primary model    → {_safe_output_text(primary_model)}")
            print(f"  skip for tiers   → {deleg.get('skip_for_tier', [])}")
            print(f"  skip if same     → {deleg.get('skip_if_same_as_primary', True)}")
            print()
            print(f"CONFIG: {_safe_output_text(status.get('config_path', '—'))}")
            print("=" * 60)
        elif arg == "test":
            results = router.run_tests()
            passed = results["passed"]
            total = results["total"]
            print()
            print("=" * 60)
            print(f"  CLASSIFIER SMOKE SUITE — {total} cases")
            print("=" * 60)
            print()
            for r in results["results"]:
                emoji = "✅" if r["passed"] else "❌"
                print(f"  Test {r['test']}: {emoji}")
                print(f"    Input:    {_safe_output_text(r['input'])}")
                print(f"    Model:    {_safe_output_text(r['actual']['model'] or '—')}")
                print(f"    Tier:     {_safe_output_text(r['actual']['tier'])}")
                print(f"    Role:     {_safe_output_text(r['actual']['role'])}")
                print(f"    Delegate: {r['actual']['delegate']}")
                print()
            print(f"  Result: {passed}/{total} passed")
            if passed == total:
                print("  ALL CLASSIFIER CHECKS PASSED ✅")
            else:
                print(f"  {total - passed} FAILED ❌")
            print("=" * 60)
        else:
            decision = router.classify(arg)
            print()
            print("┌─────────────────────────────────────────────────┐")
            print("│  ROUTING DECISION                               │")
            print("└─────────────────────────────────────────────────┘")
            print()
            print(
                f"  Input:      {_safe_output_text(arg[:80])}"
                f"{'...' if len(arg) > 80 else ''}"
            )
            print()
            print(f"  Model:      {decision.model or '—'}")
            print(f"  Provider:   {decision.provider or '—'}")
            print(f"  Tier:       {decision.tier}")
            print(f"  Role:       {decision.role}")
            print(f"  Difficulty: {decision.difficulty}")
            print(f"  Sensitivity: {decision.sensitivity}")
            print()
            execution = "RECOMMENDED" if decision.should_delegate else "NOT REQUIRED"
            print(f"  Separate execution: {execution}")
            print()
            print(f"  Reason:     {_safe_output_text(decision.reason)}")
            print()
            print("  Fallback chain:")
            for i, m in enumerate(decision.candidates):
                marker = "primary" if i == 0 else f"fallback {i}"
                print(f"    {marker:12s} → {m}")
            print()
        return 0
    except Exception as e:
        print(f"Error: {_safe_output_text(e)}")
        return 1


# ── Registration ───────────────────────────────────────────────────────


def register(ctx):
    """Register all plugin components with Hermes."""

    # Current Hermes builds create entry-point manifests from the entry-point name
    # alone. Backfill public metadata without overriding source-manifest values.
    manifest = getattr(ctx, "manifest", None)
    if manifest is not None:
        for field_name, value in (
            ("version", __version__),
            ("description", __description__),
            ("author", __author__),
        ):
            if not getattr(manifest, field_name, ""):
                setattr(manifest, field_name, value)

    # ── Tools ──────────────────────────────────────────────────────
    ctx.register_tool(
        name="route_classify",
        toolset="routing",
        schema=ROUTE_CLASSIFY_SCHEMA,
        handler=handle_route_classify,
        description="Classify a task and get a model routing recommendation.",
    )

    ctx.register_tool(
        name="route_status",
        toolset="routing",
        schema=ROUTE_STATUS_SCHEMA,
        handler=handle_route_status,
        description="Show the current model routing configuration.",
    )

    ctx.register_tool(
        name="route_test",
        toolset="routing",
        schema=ROUTE_TEST_SCHEMA,
        handler=handle_route_test,
        description="Run the routing test suite.",
    )

    # ── Slash command ──────────────────────────────────────────────
    ctx.register_command(
        name="route",
        handler=handle_route_command,
        description="Model routing: /route [status|test|<text to classify>]",
        args_hint="[status|test|text]",
    )

    # ── CLI subcommand ─────────────────────────────────────────────
    ctx.register_cli_command(
        name="route",
        help="Hybrid contextual model routing — classify tasks, show config, run tests",
        setup_fn=lambda subparser: subparser.add_argument(
            "args", nargs="*", help="status | test | <text to classify>"
        ),
        handler_fn=lambda args: handle_cli_route(
            args.args if hasattr(args, "args") else []
        ),
    )

    # ── Bundled skill ──────────────────────────────────────────────
    skill_path = Path(__file__).parent / "skill" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            name="hybrid-contextual-routing",
            path=skill_path,
        )

    logger.info("hybrid-contextual-routing plugin registered")
