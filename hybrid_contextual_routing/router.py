"""Hybrid Contextual Model Router — classification engine.

Classifies incoming tasks by three signals:
  1. Data sensitivity (secrets/PII → local-only models)
  2. Role (coding, research, creative, strategy, vision, general)
  3. Difficulty (simple, standard, hard)

Returns a routing decision: which model to use, whether to delegate,
and why. Designed for Hermes' delegation-based architecture where the
primary model stays fixed (preserving prompt caching) and specialized
tasks are delegated to subagents running the appropriate model.
"""
from __future__ import annotations

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────
SENSITIVE = "sensitive"
NORMAL = "normal"
SIMPLE = "simple"
STANDARD = "standard"
HARD = "hard"
TIER_FAST = "fast"
TIER_BALANCED = "balanced"
TIER_STRONG = "strong"

_DIFFICULTY_TO_TIER = {
    SIMPLE: TIER_FAST,
    STANDARD: TIER_BALANCED,
    HARD: TIER_STRONG,
}


@dataclass
class RoutingDecision:
    """The result of classifying a task."""
    model: str
    provider: str
    model_id: str
    tier: str
    role: str
    difficulty: str
    sensitivity: str
    should_delegate: bool
    reason: str
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "model_id": self.model_id,
            "tier": self.tier,
            "role": self.role,
            "difficulty": self.difficulty,
            "sensitivity": self.sensitivity,
            "should_delegate": self.should_delegate,
            "reason": self.reason,
            "fallback_chain": self.candidates,
        }

    def __str__(self) -> str:
        return (
            f"RoutingDecision(model={self.model}, tier={self.tier}, "
            f"role={self.role}, difficulty={self.difficulty}, "
            f"sensitivity={self.sensitivity}, delegate={self.should_delegate})\n"
            f"  Reason: {self.reason}"
        )


class HybridRouter:
    """Classifies tasks and selects the appropriate model.

    Reads routing config from the plugin data directory, with an
    optional user override path. Falls back gracefully — if no config
    is found, returns the default model.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        default_config_path: Optional[str] = None,
    ):
        self.user_config_path = Path(config_path) if config_path else None
        # Default config ships with the plugin
        if default_config_path is None:
            self.default_config_path = Path(__file__).parent / "data" / "routing_config.yaml"
        else:
            self.default_config_path = Path(default_config_path)
        self._config: Optional[dict] = None
        self._compiled_sensitive: list[re.Pattern] = []
        self._compiled_hard: list[re.Pattern] = []
        self._compiled_simple: list[re.Pattern] = []
        self._compiled_role_cues: dict[str, list[re.Pattern]] = {}
        self._loaded = False

    @property
    def config_path(self) -> Path:
        """Use user config if it exists, otherwise the shipped default."""
        if self.user_config_path and self.user_config_path.exists():
            return self.user_config_path
        return self.default_config_path

    @property
    def config(self) -> dict:
        """Load and cache the routing config."""
        if self._config is None:
            path = self.config_path
            if not path.exists():
                raise FileNotFoundError(
                    f"Routing config not found at {path}. "
                    f"Create one using the template."
                )
            with open(path) as f:
                self._config = yaml.safe_load(f) or {}
        return self._config

    def _ensure_compiled(self) -> None:
        """Compile regex patterns once, lazily."""
        if self._loaded:
            return
        cfg = self.config
        for pattern in cfg.get("sensitivity", {}).get("patterns", []):
            self._compiled_sensitive.append(re.compile(pattern))
        diff_cfg = cfg.get("difficulty", {})
        for cue in diff_cfg.get("hard_cues", []):
            self._compiled_hard.append(re.compile(cue, re.IGNORECASE))
        for cue in diff_cfg.get("simple_cues", []):
            self._compiled_simple.append(re.compile(cue))
        for role_name, role_cfg in cfg.get("roles", {}).items():
            cues = role_cfg.get("cues", [])
            if cues:
                self._compiled_role_cues[role_name] = [
                    re.compile(re.escape(cue), re.IGNORECASE) for cue in cues
                ]
        self._loaded = True

    def classify_sensitivity(self, text: str) -> str:
        if not text:
            return NORMAL
        self._ensure_compiled()
        for pattern in self._compiled_sensitive:
            if pattern.search(text):
                return SENSITIVE
        return NORMAL

    def classify_difficulty(self, text: str) -> str:
        if not text:
            return STANDARD
        self._ensure_compiled()
        t = text.strip()
        words = t.split()
        diff_cfg = self.config.get("difficulty", {})
        if diff_cfg.get("hard_if_code_block") and "```" in t:
            return HARD
        for pattern in self._compiled_hard:
            if pattern.search(t):
                return HARD
        if len(t) > diff_cfg.get("hard_if_long_input", 600):
            return HARD
        if len(words) > diff_cfg.get("hard_if_many_words", 80):
            return HARD
        if t.count("\n") >= diff_cfg.get("hard_if_many_lines", 8):
            return HARD
        for pattern in self._compiled_simple:
            if pattern.search(t):
                return SIMPLE
        if len(words) <= diff_cfg.get("simple_if_short_words", 4):
            return SIMPLE
        return STANDARD

    def classify_role(self, text: str) -> str:
        if not text:
            return "general"
        self._ensure_compiled()
        t = text.strip().lower()
        best_role = "general"
        best_score = 0
        for role_name, patterns in self._compiled_role_cues.items():
            score = sum(1 for p in patterns if p.search(t))
            if score > best_score:
                best_score = score
                best_role = role_name
        return best_role

    def _resolve_model_ref(self, model_ref: str) -> tuple[str, str]:
        parts = model_ref.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", model_ref

    def _tier_model(self, tier: str) -> Optional[str]:
        model = self.config.get("tiers", {}).get(tier, {}).get("model", "")
        return model if model and model.strip() else None

    def _role_model(self, role: str) -> Optional[str]:
        model = self.config.get("roles", {}).get(role, {}).get("model", "")
        return model if model and model.strip() else None

    def _local_only_model(self) -> Optional[str]:
        model = self.config.get("sensitivity", {}).get("local_only_model", "")
        return model if model and model.strip() else None

    def _is_configured(self) -> bool:
        """Check whether any models have been configured."""
        for tier in (TIER_FAST, TIER_BALANCED, TIER_STRONG):
            if self._tier_model(tier):
                return True
        for role in self.config.get("roles", {}):
            if self._role_model(role):
                return True
        if self._local_only_model():
            return True
        return False

    def classify(self, text: str) -> RoutingDecision:
        """Classify a task and return a routing decision."""
        self._ensure_compiled()

        # Check if any models are configured
        if not self._is_configured():
            return RoutingDecision(
                model="",
                provider="",
                model_id="",
                tier="",
                role="",
                difficulty=self.classify_difficulty(text),
                sensitivity=self.classify_sensitivity(text),
                should_delegate=False,
                reason="No models configured. Run 'hermes route' to set up your routing config, "
                       "or copy the default config to ~/.hermes/profiles/<profile>/hybrid_routing/routing_config.yaml "
                       "and fill in your model refs.",
                candidates=[],
            )

        sensitivity = self.classify_sensitivity(text)
        difficulty = self.classify_difficulty(text)
        role = self.classify_role(text)
        tier = _DIFFICULTY_TO_TIER.get(difficulty, TIER_BALANCED)

        candidates: list[str] = []

        if sensitivity == SENSITIVE:
            local_model = self._local_only_model()
            if local_model:
                candidates.append(local_model)
                reason = f"Sensitive content detected → routing to local-only model '{local_model}'"
            else:
                candidates.append(self._tier_model(TIER_BALANCED) or "ollama-cloud/glm-5.2")
                reason = "Sensitive content detected but no local model configured → using balanced tier"
        else:
            role_model = self._role_model(role) if role != "general" else None
            tier_model = self._tier_model(tier)
            if role_model:
                candidates.append(role_model)
                reason = f"Role '{role}' detected → routing to role model '{role_model}'"
            elif tier_model:
                candidates.append(tier_model)
                reason = f"Difficulty '{difficulty}' (tier '{tier}') → routing to tier model '{tier_model}'"
            else:
                default = self._tier_model(TIER_BALANCED) or "ollama-cloud/glm-5.2"
                candidates.append(default)
                reason = f"No specific routing match → using balanced tier default '{default}'"

        for t in (TIER_FAST, TIER_BALANCED, TIER_STRONG):
            m = self._tier_model(t)
            if m and m not in candidates:
                candidates.append(m)

        primary_model = candidates[0]
        provider, model_id = self._resolve_model_ref(primary_model)

        deleg_cfg = self.config.get("delegation", {})
        should_delegate = True
        if tier in deleg_cfg.get("skip_for_tier", []) and sensitivity != SENSITIVE:
            should_delegate = False
            reason += " (handled inline — fast tier)"
        primary_session_model = deleg_cfg.get("primary_model", "")
        if deleg_cfg.get("skip_if_same_as_primary", True) and primary_model == primary_session_model:
            should_delegate = False
            reason += " (handled inline — same as primary model)"
        if sensitivity == SENSITIVE and primary_model != primary_session_model:
            should_delegate = True
            reason += " (delegated — sensitive content isolated to subagent)"

        return RoutingDecision(
            model=primary_model,
            provider=provider,
            model_id=model_id,
            tier=tier,
            role=role,
            difficulty=difficulty,
            sensitivity=sensitivity,
            should_delegate=should_delegate,
            reason=reason,
            candidates=candidates,
        )

    def explain(self, text: str) -> dict:
        d = self.classify(text)
        result = d.to_dict()
        result["input_preview"] = text[:200] + ("..." if len(text) > 200 else "")
        return result

    def get_status(self) -> dict:
        """Return the current routing configuration as a dict."""
        cfg = self.config
        return {
            "configured": self._is_configured(),
            "config_path": str(self.config_path),
            "tiers": cfg.get("tiers", {}),
            "roles": cfg.get("roles", {}),
            "sensitivity": {
                "local_only_model": self._local_only_model(),
                "pattern_count": len(cfg.get("sensitivity", {}).get("patterns", [])),
            },
            "difficulty": cfg.get("difficulty", {}),
            "delegation": cfg.get("delegation", {}),
        }

    def run_tests(self) -> dict:
        """Run the 9-case test suite and return results."""
        cases = [
            ("hi", "fast", "general", "normal", False),
            ("ok thanks", "fast", "general", "normal", False),
            ("Debug this Python function that has a bug in the import logic", "strong", "coding", "normal", False),
            ("Write a creative blog post about AI consciousness", "balanced", "creative", "normal", True),
            ("Analyze the strategic trade-offs of our go-to-market roadmap", "strong", "strategy", "normal", True),
            ("Research the latest arxiv papers on RLHF and compare three approaches", "strong", "research", "normal", False),
            ("Review this document marked Highly Confidential with password=secret123", "balanced", "general", "sensitive", True),
            ("What is 2+2?", "fast", "general", "normal", False),
            ("Design a distributed system architecture and explain why each component is needed", "strong", "general", "normal", True),
        ]
        results = []
        passed = 0
        for i, (text, exp_tier, exp_role, exp_sens, exp_del) in enumerate(cases, 1):
            d = self.classify(text)
            ok = (d.tier == exp_tier and d.role == exp_role
                  and d.sensitivity == exp_sens and d.should_delegate == exp_del)
            if ok:
                passed += 1
            results.append({
                "test": i,
                "input": text[:60],
                "passed": ok,
                "expected": {"tier": exp_tier, "role": exp_role, "sensitivity": exp_sens, "delegate": exp_del},
                "actual": {"tier": d.tier, "role": d.role, "sensitivity": d.sensitivity, "delegate": d.should_delegate, "model": d.model},
            })
        return {"passed": passed, "total": len(cases), "results": results}