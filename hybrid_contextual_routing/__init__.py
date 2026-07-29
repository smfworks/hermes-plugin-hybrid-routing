"""Hybrid Contextual Routing — Hermes plugin registration.

Wires the classification engine into Hermes as three tools, a slash
command (/route), a CLI subcommand (hermes route), and a bundled skill.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .router import HybridRouter

logger = logging.getLogger(__name__)

# ── Router instance ────────────────────────────────────────────────────
# Lazily initialized — the config path depends on the active profile,
# which we resolve on first use.

_router: HybridRouter | None = None


def _get_router() -> HybridRouter:
    """Get or create the router instance.

    Checks for a user override config at:
      ~/.hermes/profiles/<profile>/hybrid_routing/routing_config.yaml

    Falls back to the shipped default config.
    """
    global _router
    if _router is not None:
        return _router

    # Look for a user override config in the active profile directory
    import os
    hermes_home = os.environ.get("HERMES_HOME", "")
    if not hermes_home:
        hermes_home = str(Path.home() / ".hermes")

    # Try the active profile's override path
    profile = os.environ.get("HERMES_PROFILE", "")
    user_config = None
    if profile:
        candidate = Path(hermes_home) / "profiles" / profile / "hybrid_routing" / "routing_config.yaml"
        if candidate.exists():
            user_config = str(candidate)

    # Also check the default profile path
    if not user_config:
        candidate = Path(hermes_home) / "hybrid_routing" / "routing_config.yaml"
        if candidate.exists():
            user_config = str(candidate)

    _router = HybridRouter(config_path=user_config)
    return _router


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
        "Run the 9-case test suite to verify the routing classification "
        "engine is working correctly. Returns pass/fail for each test case."
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
    text = args.get("text", "")
    if not text.strip():
        return json.dumps({"error": "No text provided to classify"})
    try:
        router = _get_router()
        decision = router.classify(text)
        return json.dumps(decision.to_dict(), indent=2)
    except Exception as e:
        logger.exception("route_classify failed")
        return json.dumps({"error": f"Classification failed: {e}"})


def handle_route_status(args: dict, **kwargs) -> str:
    """Return the current routing configuration as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        status = router.get_status()
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.exception("route_status failed")
        return json.dumps({"error": f"Status failed: {e}"})


def handle_route_test(args: dict, **kwargs) -> str:
    """Run the test suite and return results as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        results = router.run_tests()
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.exception("route_test failed")
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
                lines.append(f"  • `{tier_name}` → `{tier_cfg.get('model', '—')}`")
            lines.append("")
            lines.append("**Roles:**")
            for role_name, role_cfg in status.get("roles", {}).items():
                lines.append(f"  • `{role_name}` → `{role_cfg.get('model', '—')}`")
            lines.append("")
            lines.append(f"**Sensitive local-only:** `{status.get('sensitivity', {}).get('local_only_model', '—')}`")
            lines.append(f"**Config:** `{status.get('config_path', '—')}`")
            return "\n".join(lines)
        elif arg == "test":
            results = router.run_tests()
            passed = results["passed"]
            total = results["total"]
            status_emoji = "✅" if passed == total else "❌"
            lines = [f"**Routing Test Suite — {passed}/{total} passed** {status_emoji}", ""]
            for r in results["results"]:
                emoji = "✅" if r["passed"] else "❌"
                lines.append(f"{emoji} Test {r['test']}: `{r['input'][:50]}`")
                lines.append(f"   → {r['actual']['model']}")
            return "\n".join(lines)
        else:
            decision = router.classify(arg)
            lines = [
                "**Routing Decision**",
                "",
                f"• **Model:** `{decision.model}`",
                f"• **Tier:** {decision.tier}",
                f"• **Role:** {decision.role}",
                f"• **Difficulty:** {decision.difficulty}",
                f"• **Sensitivity:** {decision.sensitivity}",
                f"• **Delegate:** {'YES → subagent' if decision.should_delegate else 'NO → handle inline'}",
                "",
                f"**Reason:** {decision.reason}",
                "",
                "**Fallback chain:**",
            ]
            for i, m in enumerate(decision.candidates):
                label = "primary" if i == 0 else f"fallback {i}"
                lines.append(f"  `{label}` → `{m}`")
            return "\n".join(lines)
    except Exception as e:
        logger.exception("route command failed")
        return f"Route command failed: {e}"


# ── CLI command handler ────────────────────────────────────────────────


def handle_cli_route(args) -> int:
    """Handle `hermes route` CLI subcommand."""
    import sys

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
                model = tier_cfg.get("model", "—")
                desc = tier_cfg.get("description", "")
                print(f"  {tier_name:12s} → {model}")
                if desc:
                    print(f"  {' ':12s}   {desc}")
            print()
            print("ROLES:")
            for role_name, role_cfg in status.get("roles", {}).items():
                model = role_cfg.get("model", "—")
                desc = role_cfg.get("description", "")
                auxiliary = role_cfg.get("auxiliary", False)
                marker = " (auxiliary)" if auxiliary else ""
                print(f"  {role_name:12s} → {model}{marker}")
                if desc:
                    print(f"  {' ':12s}   {desc}")
            print()
            sens = status.get("sensitivity", {})
            print("SENSITIVITY:")
            print(f"  local_only  → {sens.get('local_only_model', '—')}")
            print(f"  patterns    → {sens.get('pattern_count', 0)} regex rules")
            print()
            deleg = status.get("delegation", {})
            print("DELEGATION:")
            print(f"  primary model    → {deleg.get('primary_model', '—')}")
            print(f"  skip for tiers   → {deleg.get('skip_for_tier', [])}")
            print(f"  skip if same     → {deleg.get('skip_if_same_as_primary', True)}")
            print()
            print(f"CONFIG: {status.get('config_path', '—')}")
            print("=" * 60)
        elif arg == "test":
            results = router.run_tests()
            passed = results["passed"]
            total = results["total"]
            print()
            print("=" * 60)
            print(f"  ROUTER TEST SUITE — {total} cases")
            print("=" * 60)
            print()
            for r in results["results"]:
                emoji = "✅" if r["passed"] else "❌"
                print(f"  Test {r['test']}: {emoji}")
                print(f"    Input:    {r['input']}")
                print(f"    Model:    {r['actual']['model']}")
                print(f"    Tier:     {r['actual']['tier']}")
                print(f"    Role:     {r['actual']['role']}")
                print(f"    Delegate: {r['actual']['delegate']}")
                print()
            print(f"  Result: {passed}/{total} passed")
            if passed == total:
                print("  ALL TESTS PASSED ✅")
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
            print(f"  Input:      {arg[:80]}{'...' if len(arg) > 80 else ''}")
            print()
            print(f"  Model:      {decision.model}")
            print(f"  Provider:   {decision.provider}")
            print(f"  Tier:       {decision.tier}")
            print(f"  Role:       {decision.role}")
            print(f"  Difficulty: {decision.difficulty}")
            print(f"  Sensitivity:{decision.sensitivity}")
            print()
            delegate_str = "YES → subagent" if decision.should_delegate else "NO → handle inline"
            print(f"  Delegate:   {delegate_str}")
            print()
            print(f"  Reason:     {decision.reason}")
            print()
            print("  Fallback chain:")
            for i, m in enumerate(decision.candidates):
                marker = "primary" if i == 0 else f"fallback {i}"
                print(f"    {marker:12s} → {m}")
            print()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


# ── Registration ───────────────────────────────────────────────────────


def register(ctx):
    """Register all plugin components with Hermes."""

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
    )

    # ── CLI subcommand ─────────────────────────────────────────────
    ctx.register_cli_command(
        name="route",
        help="Hybrid contextual model routing — classify tasks, show config, run tests",
        setup_fn=lambda subparser: subparser.add_argument(
            "args", nargs="*", help="status | test | <text to classify>"
        ),
        handler_fn=lambda args: handle_cli_route(args.args if hasattr(args, "args") else []),
    )

    # ── Bundled skill ──────────────────────────────────────────────
    skill_path = Path(__file__).parent / "skill" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            name="hybrid-contextual-routing",
            path=str(skill_path),
        )

    logger.info("hybrid-contextual-routing plugin registered")