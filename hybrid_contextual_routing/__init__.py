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

from .router import MAX_CLASSIFY_CHARS, HybridRouter

logger = logging.getLogger(__name__)

__version__ = "1.1.1"
__description__ = (
    "Advisory contextual model routing for Hermes agents by sensitivity, role, "
    "and difficulty"
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


def _egress_provenance_label(
    egress: object,
    declaration: object,
    render,
    *,
    force: bool = False,
) -> str:
    """Render egress metadata without presenting declared locality as verified."""
    if not egress:
        return ""
    rendered = render(egress)
    if egress != "local" and not force:
        return rendered
    declaration_label = (
        "operator-declared" if declaration == "operator" else "not declared"
    )
    return f"{rendered}, {declaration_label}; transport not verified"


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
    if len(text) > MAX_CLASSIFY_CHARS:
        return json.dumps(
            {"error": f"text must be at most {MAX_CLASSIFY_CHARS} characters"}
        )
    try:
        router = _get_router()
        decision = router.classify(text)
        logger.info(
            "route_classify disposition=%s sensitivity=%s role=%s difficulty=%s",
            decision.disposition,
            decision.sensitivity,
            decision.role,
            decision.difficulty,
        )
        return json.dumps(decision.to_dict(), indent=2)
    except Exception as e:
        logger.error("route_classify failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Classification failed: {_safe_output_text(e)}"})


def handle_route_status(args: dict, **kwargs) -> str:
    """Return the current routing configuration as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        status = router.get_status()
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error("route_status failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Status failed: {_safe_output_text(e)}"})


def handle_route_test(args: dict, **kwargs) -> str:
    """Run the classifier smoke suite and return results as JSON."""
    del args, kwargs
    try:
        router = _get_router()
        results = router.run_tests()
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.error("route_test failed: %s", _safe_output_text(e))
        return json.dumps({"error": f"Test failed: {_safe_output_text(e)}"})


# ── Slash command handler ──────────────────────────────────────────────


def handle_route_command(args: str, **kwargs) -> str:
    """Handle /route slash command.

    Usage:
      /route                  — show routing config
      /route test             — run test suite
      /route classify <text>  — classify reserved or arbitrary text
      /route <text>           — classify the text
    """
    del kwargs
    arg = (args or "").strip()
    explicit_classify_text = None
    if arg == "classify":
        return "Usage: `/route classify <text>`"
    if arg.startswith("classify "):
        explicit_classify_text = arg.removeprefix("classify ").strip()
        if not explicit_classify_text:
            return "Usage: `/route classify <text>`"
    try:
        router = _get_router()
        if not arg or (arg == "status" and explicit_classify_text is None):
            status = router.get_status()
            lines = ["**Hybrid Contextual Routing — Configuration**", ""]
            lines.append("**Tiers:**")
            for tier_name, tier_cfg in status.get("tiers", {}).items():
                model = tier_cfg.get("model") or "—"
                egress = tier_cfg.get("egress") or ""
                egress_label = _egress_provenance_label(
                    egress,
                    tier_cfg.get("egress_declaration"),
                    _markdown_code,
                )
                egress_suffix = f" ({egress_label})" if egress_label else ""
                lines.append(
                    f"  • {_markdown_code(tier_name)} → "
                    f"{_markdown_code(model)}{egress_suffix}"
                )
            lines.append("")
            lines.append("**Roles:**")
            for role_name, role_cfg in status.get("roles", {}).items():
                model = role_cfg.get("model") or "—"
                egress = role_cfg.get("egress") or ""
                egress_label = _egress_provenance_label(
                    egress,
                    role_cfg.get("egress_declaration"),
                    _markdown_code,
                )
                egress_suffix = f" ({egress_label})" if egress_label else ""
                lines.append(
                    f"  • {_markdown_code(role_name)} → "
                    f"{_markdown_code(model)}{egress_suffix}"
                )
            lines.append("")
            sensitivity = status.get("sensitivity", {})
            local_only = sensitivity.get("local_only_model") or "—"
            local_egress = sensitivity.get("local_only_egress") or ""
            if local_egress:
                local_label = _egress_provenance_label(
                    local_egress,
                    sensitivity.get("local_only_egress_declaration"),
                    _markdown_code,
                    force=True,
                )
                readiness = (
                    "ready" if sensitivity.get("local_route_ready") else "blocked"
                )
                local_suffix = f" ({local_label}; {readiness})"
            else:
                local_suffix = ""
            lines.append(
                f"**Sensitive model:** {_markdown_code(local_only)}{local_suffix}"
            )
            egress_metadata = status.get("egress_metadata", {})
            completeness = (
                "complete" if egress_metadata.get("metadata_complete") else "incomplete"
            )
            unknown_count = egress_metadata.get("unknown_count", 0)
            orphan_count = egress_metadata.get("orphan_count", 0)
            lines.append(
                f"**Egress metadata:** {completeness} "
                f"({_markdown_code(unknown_count)} unknown, "
                f"{_markdown_code(orphan_count)} orphan)"
            )
            lines.append(
                f"**Egress schema:** "
                f"{_markdown_code(egress_metadata.get('schema_version', 0))} "
                f"(supported "
                f"{_markdown_code(egress_metadata.get('supported_schema_version', 1))})"
            )
            migration = (
                "yes" if egress_metadata.get("sensitive_migration_required") else "no"
            )
            lines.append(f"**Sensitive migration required:** {migration}")
            if migration == "yes":
                lines.append(
                    "**Migration action:** retain `egress_schema_version: 1` and "
                    "add the exact sensitive model ref to `model_egress` as "
                    "`local` only after verifying its endpoint."
                )
            lines.append(
                f"**Config:** {_markdown_code(status.get('config_path', '—'))}"
            )
            return "\n".join(lines)
        elif arg == "test" and explicit_classify_text is None:
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
            decision = router.classify(explicit_classify_text or arg)
            decision_egress = _egress_provenance_label(
                decision.egress,
                decision.egress_declaration,
                _markdown_code,
            )
            execution = {
                "separate": "**RECOMMENDED**",
                "inline": "not required",
                "block": "**BLOCKED — do not process inline**",
                "unavailable": "**UNAVAILABLE**",
            }[decision.disposition]
            lines = [
                "**Routing Decision**",
                "",
                f"• **Model:** {_markdown_code(decision.model or '—')}",
                f"• **Tier:** {_markdown_code(decision.tier)}",
                f"• **Role:** {_markdown_code(decision.role)}",
                f"• **Difficulty:** {_markdown_code(decision.difficulty)}",
                f"• **Sensitivity:** {_markdown_code(decision.sensitivity)}",
                f"• **Egress:** {decision_egress or _markdown_code('—')}",
                f"• **Egress declaration:** "
                f"{_markdown_code(decision.egress_declaration or 'none')}",
                f"• **Disposition:** {_markdown_code(decision.disposition)}",
                f"• **Separate execution:** {execution}",
                "",
                f"**Reason:** {_markdown_code(decision.reason)}",
                "",
                "**Fallback chain:**",
            ]
            for i, route in enumerate(decision.candidate_routes):
                label = "primary" if i == 0 else f"fallback {i}"
                route_egress = _egress_provenance_label(
                    route["egress"],
                    route.get("egress_declaration"),
                    _markdown_code,
                )
                lines.append(
                    f"  {_markdown_code(label)} → {_markdown_code(route['model'])} "
                    f"({route_egress})"
                )
            return "\n".join(lines)
    except Exception as e:
        logger.error("route command failed: %s", _safe_output_text(e))
        return f"Route command failed: {_markdown_code(e)}"


# ── CLI command handler ────────────────────────────────────────────────


def handle_cli_route(args) -> int:
    """Handle `hermes route` CLI subcommand."""
    raw_args = list(args or [])
    explicit_classify = bool(raw_args and raw_args[0] == "classify")
    if explicit_classify:
        arg = " ".join(raw_args[1:]).strip()
        if not arg:
            print("Usage: hermes route classify <text>")
            return 1
    else:
        arg = " ".join(raw_args)
    try:
        router = _get_router()
        if not arg or (arg == "status" and not explicit_classify):
            status = router.get_status()
            print("=" * 60)
            print("  HYBRID CONTEXTUAL ROUTING — Configuration")
            print("=" * 60)
            print()
            print("TIERS:")
            for tier_name, tier_cfg in status.get("tiers", {}).items():
                model = tier_cfg.get("model") or "—"
                egress = tier_cfg.get("egress") or ""
                egress_label = _egress_provenance_label(
                    egress,
                    tier_cfg.get("egress_declaration"),
                    _safe_output_text,
                )
                egress_suffix = f" [{egress_label}]" if egress_label else ""
                desc = tier_cfg.get("description", "")
                print(
                    f"  {_safe_output_text(tier_name):12s} → "
                    f"{_safe_output_text(model)}{egress_suffix}"
                )
                if desc:
                    print(f"  {' ':12s}   {_safe_output_text(desc)}")
            print()
            print("ROLES:")
            for role_name, role_cfg in status.get("roles", {}).items():
                model = role_cfg.get("model") or "—"
                egress = role_cfg.get("egress") or ""
                desc = role_cfg.get("description", "")
                auxiliary = role_cfg.get("auxiliary", False)
                egress_label = _egress_provenance_label(
                    egress,
                    role_cfg.get("egress_declaration"),
                    _safe_output_text,
                )
                marker = f" [{egress_label}]" if egress_label else ""
                marker += " (auxiliary)" if auxiliary else ""
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
            local_egress = sens.get("local_only_egress") or ""
            if local_egress:
                local_label = _egress_provenance_label(
                    local_egress,
                    sens.get("local_only_egress_declaration"),
                    _safe_output_text,
                    force=True,
                )
                readiness = "ready" if sens.get("local_route_ready") else "blocked"
                local_suffix = f" [{local_label}; {readiness}]"
            else:
                local_suffix = ""
            print(
                f"  model       → {_safe_output_text(local_only_model)}{local_suffix}"
            )
            print(f"  patterns    → {sens.get('pattern_count', 0)} regex rules")
            print()
            egress_metadata = status.get("egress_metadata", {})
            completeness = (
                "complete" if egress_metadata.get("metadata_complete") else "incomplete"
            )
            unknown_count = egress_metadata.get("unknown_count", 0)
            orphan_count = egress_metadata.get("orphan_count", 0)
            migration = (
                "required"
                if egress_metadata.get("sensitive_migration_required")
                else "not required"
            )
            print("EGRESS METADATA:")
            print(
                f"  metadata       → {completeness} "
                f"({unknown_count} unknown, {orphan_count} orphan)"
            )
            print(
                f"  schema         → {egress_metadata.get('schema_version', 0)} "
                f"(supported {egress_metadata.get('supported_schema_version', 1)})"
            )
            print(f"  migration      → {migration}")
            if migration == "required":
                print(
                    "  action         → retain egress_schema_version: 1 and add "
                    "the exact sensitive model ref as local only after verifying "
                    "its endpoint"
                )
            print()
            deleg = status.get("delegation", {})
            print("DELEGATION:")
            primary_model = deleg.get("primary_model") or "—"
            primary_egress = deleg.get("primary_egress") or ""
            primary_label = _egress_provenance_label(
                primary_egress,
                deleg.get("primary_egress_declaration"),
                _safe_output_text,
            )
            primary_suffix = f" [{primary_label}]" if primary_label else ""
            print(
                f"  primary model    → {_safe_output_text(primary_model)}"
                f"{primary_suffix}"
            )
            print(f"  skip for tiers   → {deleg.get('skip_for_tier', [])}")
            print(f"  skip if same     → {deleg.get('skip_if_same_as_primary', True)}")
            print()
            print(f"CONFIG: {_safe_output_text(status.get('config_path', '—'))}")
            print("=" * 60)
        elif arg == "test" and not explicit_classify:
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
            return 0 if passed == total else 1
        else:
            decision = router.classify(arg)
            decision_egress = _egress_provenance_label(
                decision.egress,
                decision.egress_declaration,
                _safe_output_text,
            )
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
            print(f"  Egress:    {decision_egress or '—'}")
            print(f"  Egress declaration: {decision.egress_declaration or 'none'}")
            print(f"  Disposition: {decision.disposition}")
            print()
            execution = {
                "separate": "RECOMMENDED",
                "inline": "not required",
                "block": "BLOCKED — do not process inline",
                "unavailable": "UNAVAILABLE",
            }[decision.disposition]
            print(f"  Separate:   {execution}")
            print()
            print(f"  Reason:     {_safe_output_text(decision.reason)}")
            print()
            print("  Fallback chain:")
            for i, route in enumerate(decision.candidate_routes):
                marker = "primary" if i == 0 else f"fallback {i}"
                route_egress = _egress_provenance_label(
                    route["egress"],
                    route.get("egress_declaration"),
                    _safe_output_text,
                )
                print(f"    {marker:12s} → {route['model']} [{route_egress}]")
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
        description="Model routing: /route [status|test|classify <text>|<text>]",
        args_hint="[status|test|classify <text>|text]",
    )

    # ── CLI subcommand ─────────────────────────────────────────────
    ctx.register_cli_command(
        name="route",
        help="Hybrid contextual model routing — classify tasks, show config, run tests",
        setup_fn=lambda subparser: subparser.add_argument(
            "args", nargs="*", help="status | test | classify <text> | <text>"
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
    else:
        logger.warning("bundled skill missing at %s", skill_path)

    logger.info("hybrid-contextual-routing plugin registered")
