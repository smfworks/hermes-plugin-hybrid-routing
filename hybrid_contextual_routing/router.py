"""Hybrid Contextual Model Router — classification engine.

Classifies incoming tasks by three signals:
  1. Data sensitivity (secrets/PII → local-only models)
  2. Role (coding, research, creative, strategy, vision, general)
  3. Difficulty (simple, standard, hard)

Returns an advisory routing decision: which configured model best fits,
whether a separate execution context is recommended, and why. The
primary session model stays fixed; the caller is responsible for using
an execution path that can select the recommended provider and model.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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

_TIER_FALLBACK_ORDER = {
    TIER_FAST: (TIER_FAST, TIER_BALANCED, TIER_STRONG),
    TIER_BALANCED: (TIER_BALANCED, TIER_STRONG, TIER_FAST),
    TIER_STRONG: (TIER_STRONG, TIER_BALANCED, TIER_FAST),
}

_MAX_ROLE_CUES = 64
_MAX_ROLE_CUE_LENGTH = 128
_DOUBLED_FINAL_CONSONANT_WORDS = frozenset(
    {
        "admit",
        "blog",
        "bug",
        "commit",
        "debug",
        "drop",
        "fit",
        "plan",
        "stop",
        "submit",
    }
)


def _compile_patterns(patterns, field_name: str, flags: int = 0) -> list[re.Pattern]:
    if not isinstance(patterns, list):
        raise ValueError(f"{field_name} must be a list of regular expressions")
    compiled = []
    for index, pattern in enumerate(patterns):
        if not isinstance(pattern, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        try:
            compiled.append(re.compile(pattern, flags))
        except re.error as exc:
            raise ValueError(f"Invalid regex in {field_name}[{index}]: {exc}") from exc
    return compiled


def _nonnegative_int(value, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _regular_word_forms(word: str) -> set[str]:
    """Return conservative regular inflections for a cue's final word."""
    forms = {word}
    if len(word) < 3:
        return forms

    lowered = word.lower()
    if lowered == "analysis":
        forms.add(word[:-2] + "es")
        return forms
    if re.search(r"[^aeiou]y$", lowered):
        forms.add(word[:-1] + "ies")
    elif lowered.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(word + "es")
    else:
        forms.add(word + "s")

    if re.search(r"[^aeiou]y$", lowered):
        forms.add(word[:-1] + "ied")
        forms.add(word + "ing")
    elif lowered.endswith("ie"):
        forms.add(word + "d")
        forms.add(word[:-2] + "ying")
    elif lowered.endswith("e"):
        forms.add(word + "d")
        forms.add(word + "ing" if lowered.endswith("ee") else word[:-1] + "ing")
    else:
        stem = word
        if lowered in _DOUBLED_FINAL_CONSONANT_WORDS:
            stem += word[-1]
        forms.add(stem + "ed")
        forms.add(stem + "ing")
    return forms


def _compile_role_cue(cue: str) -> re.Pattern:
    """Compile a literal role cue with token boundaries and inflections."""
    match = re.fullmatch(r"(.*?)([A-Za-z]+)", cue)
    forms = {cue}
    if match:
        prefix, final_word = match.groups()
        forms = {prefix + form for form in _regular_word_forms(final_word)}
    alternatives = "|".join(
        re.escape(form) for form in sorted(forms, key=len, reverse=True)
    )
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


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
            "candidates": list(self.candidates),
            # Kept for compatibility with the original 1.0 response shape.
            "fallback_chain": list(self.candidates),
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
    optional user override path. Blank or incomplete configurations
    remain advisory and never invent an unconfigured model.
    """

    def __init__(
        self,
        config_path: str | None = None,
        default_config_path: str | None = None,
    ):
        self.user_config_path = Path(config_path) if config_path else None
        # Default config ships with the plugin
        if default_config_path is None:
            self.default_config_path = (
                Path(__file__).parent / "data" / "routing_config.yaml"
            )
        else:
            self.default_config_path = Path(default_config_path)
        self._config: dict | None = None
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
            self._config = self._load_config_mapping(path)
        return self._config

    @staticmethod
    def _load_config_mapping(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(
                f"Routing config not found at {path}. Create one using the template."
            )
        with open(path, encoding="utf-8") as config_file:
            loaded = yaml.safe_load(config_file) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Routing config at {path} must contain a YAML mapping")
        return loaded

    def _ensure_compiled(self) -> None:
        """Compile regex patterns once, lazily."""
        if self._loaded:
            return
        sensitivity_cfg = self._section("sensitivity")
        sensitivity_patterns = sensitivity_cfg.get("patterns")
        if not sensitivity_patterns:
            raise ValueError("sensitivity.patterns must contain at least one pattern")

        bundled_config = self._load_config_mapping(self.default_config_path)
        bundled_sensitivity = bundled_config.get("sensitivity")
        if not isinstance(bundled_sensitivity, dict):
            raise ValueError("Bundled sensitivity config must be a YAML mapping")
        bundled_patterns = bundled_sensitivity.get("patterns")
        if not bundled_patterns:
            raise ValueError(
                "Bundled sensitivity.patterns must contain at least one pattern"
            )
        compiled_sensitive = _compile_patterns(
            bundled_patterns,
            "bundled sensitivity.patterns",
            flags=re.IGNORECASE,
        )
        if self.config_path.resolve() != self.default_config_path.resolve():
            compiled_sensitive.extend(
                _compile_patterns(
                    sensitivity_patterns, "sensitivity.patterns", flags=re.IGNORECASE
                )
            )
        seen_sensitive: set[tuple[str, int]] = set()
        for pattern in compiled_sensitive:
            key = (pattern.pattern, pattern.flags)
            if key not in seen_sensitive:
                seen_sensitive.add(key)
                self._compiled_sensitive.append(pattern)
        diff_cfg = self._section("difficulty")
        hard_if_code_block = diff_cfg.get("hard_if_code_block", True)
        if not isinstance(hard_if_code_block, bool):
            raise ValueError("difficulty.hard_if_code_block must be a boolean")
        for field_name, default in (
            ("hard_if_long_input", 600),
            ("hard_if_many_words", 80),
            ("hard_if_many_lines", 8),
            ("simple_if_short_words", 4),
        ):
            _nonnegative_int(
                diff_cfg.get(field_name, default),
                f"difficulty.{field_name}",
            )
        self._compiled_hard.extend(
            _compile_patterns(
                diff_cfg.get("hard_cues", []), "difficulty.hard_cues", re.IGNORECASE
            )
        )
        self._compiled_simple.extend(
            _compile_patterns(
                diff_cfg.get("simple_cues", []), "difficulty.simple_cues", re.IGNORECASE
            )
        )
        tiers = self._section("tiers")
        validated_tier_names = {
            self._identifier_value(tier_name, "tiers key") for tier_name in tiers
        }
        if validated_tier_names != set(_TIER_FALLBACK_ORDER):
            allowed = ", ".join(_TIER_FALLBACK_ORDER)
            raise ValueError(f"tiers must contain exactly: {allowed}")
        for tier_name in _TIER_FALLBACK_ORDER:
            tier_cfg = tiers[tier_name]
            if not isinstance(tier_cfg, dict):
                raise ValueError(f"tiers.{tier_name} must be a YAML mapping")
            self._tier_model(tier_name)
            self._display_text(
                tier_cfg.get("description", ""), f"tiers.{tier_name}.description"
            )
            if "max_input_tokens" in tier_cfg:
                _nonnegative_int(
                    tier_cfg["max_input_tokens"],
                    f"tiers.{tier_name}.max_input_tokens",
                )

        for role_name, role_cfg in self._section("roles").items():
            role_name = self._identifier_value(role_name, "roles key")
            if not isinstance(role_cfg, dict):
                raise ValueError(f"roles.{role_name} must be a YAML mapping")
            self._role_model(role_name)
            self._display_text(
                role_cfg.get("description", ""), f"roles.{role_name}.description"
            )
            auxiliary = role_cfg.get("auxiliary", False)
            if not isinstance(auxiliary, bool):
                raise ValueError(f"roles.{role_name}.auxiliary must be a boolean")
            cues = role_cfg.get("cues", [])
            if not isinstance(cues, list):
                raise ValueError(f"roles.{role_name}.cues must be a list of strings")
            if len(cues) > _MAX_ROLE_CUES:
                raise ValueError(
                    f"roles.{role_name}.cues must contain at most {_MAX_ROLE_CUES} cues"
                )
            compiled_cues = []
            seen_cues: set[str] = set()
            for index, cue in enumerate(cues):
                field_name = f"roles.{role_name}.cues[{index}]"
                if not isinstance(cue, str):
                    raise ValueError(f"{field_name} must be a string")
                if not cue.strip():
                    raise ValueError(f"{field_name} must not be empty or whitespace")
                if cue != cue.strip():
                    raise ValueError(
                        f"{field_name} must not have leading or trailing whitespace"
                    )
                if len(cue) > _MAX_ROLE_CUE_LENGTH:
                    raise ValueError(
                        f"{field_name} must be at most "
                        f"{_MAX_ROLE_CUE_LENGTH} characters"
                    )
                self._display_text(cue, field_name)
                normalized = cue.casefold()
                if normalized in seen_cues:
                    continue
                seen_cues.add(normalized)
                compiled_cues.append(_compile_role_cue(cue))
            if compiled_cues:
                self._compiled_role_cues[role_name] = compiled_cues
        self._local_only_model()
        self._delegation_settings()
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
        diff_cfg = self._section("difficulty")
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

    def _section(self, name: str) -> dict:
        section = self.config.get(name, {})
        if section is None:
            return {}
        if not isinstance(section, dict):
            raise ValueError(f"{name} must be a YAML mapping")
        return section

    @staticmethod
    def _identifier_value(value: object, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        if not value:
            raise ValueError(f"{field_name} must not be empty")
        if len(value) > 64:
            raise ValueError(f"{field_name} must be at most 64 characters")
        if any(not (character.isalnum() or character in "-_.:") for character in value):
            raise ValueError(f"{field_name} contains unsupported characters")
        return value

    @staticmethod
    def _display_text(value: object, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        if len(value) > 512:
            raise ValueError(f"{field_name} must be at most 512 characters")
        if any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in value
        ):
            raise ValueError(f"{field_name} contains control characters")
        return value

    @staticmethod
    def _model_value(value, field_name: str) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        if len(value) > 512:
            raise ValueError(f"{field_name} must be at most 512 characters")
        if value != value.strip() or any(
            character.isspace()
            or unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in value
        ):
            raise ValueError(f"{field_name} contains whitespace or control characters")
        provider, separator, model_id = value.partition("/")
        if not separator or not provider or not model_id or "//" in value:
            raise ValueError(
                f"{field_name} must use a non-empty provider/model reference"
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", provider):
            raise ValueError(f"{field_name} contains an invalid provider name")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+~-]*", model_id):
            raise ValueError(f"{field_name} contains an invalid model name")
        return value

    def _tier_model(self, tier: str) -> str | None:
        tier_cfg = self._section("tiers").get(tier, {})
        if tier_cfg is None:
            tier_cfg = {}
        if not isinstance(tier_cfg, dict):
            raise ValueError(f"tiers.{tier} must be a YAML mapping")
        return self._model_value(tier_cfg.get("model", ""), f"tiers.{tier}.model")

    def _role_model(self, role: str) -> str | None:
        role_cfg = self._section("roles").get(role, {})
        if role_cfg is None:
            role_cfg = {}
        if not isinstance(role_cfg, dict):
            raise ValueError(f"roles.{role} must be a YAML mapping")
        return self._model_value(role_cfg.get("model", ""), f"roles.{role}.model")

    def _local_only_model(self) -> str | None:
        value = self._section("sensitivity").get("local_only_model", "")
        return self._model_value(value, "sensitivity.local_only_model")

    def _delegation_settings(self) -> tuple[list[str], bool, str]:
        delegation = self._section("delegation")
        skip_for_tier = delegation.get("skip_for_tier", [])
        if not isinstance(skip_for_tier, list):
            raise ValueError("delegation.skip_for_tier must be a list of strings")
        validated_skip_for_tier = []
        for index, item in enumerate(skip_for_tier):
            field_name = f"delegation.skip_for_tier[{index}]"
            tier = self._identifier_value(item, field_name)
            if tier not in _TIER_FALLBACK_ORDER:
                allowed = ", ".join(_TIER_FALLBACK_ORDER)
                raise ValueError(f"{field_name} must be one of: {allowed}")
            validated_skip_for_tier.append(tier)
        skip_if_same = delegation.get("skip_if_same_as_primary", True)
        if not isinstance(skip_if_same, bool):
            raise ValueError("delegation.skip_if_same_as_primary must be a boolean")
        primary_model = (
            self._model_value(
                delegation.get("primary_model", ""), "delegation.primary_model"
            )
            or ""
        )
        return validated_skip_for_tier, skip_if_same, primary_model

    def _is_configured(self) -> bool:
        """Check whether any models have been configured."""
        for tier in (TIER_FAST, TIER_BALANCED, TIER_STRONG):
            if self._tier_model(tier):
                return True
        for role in self._section("roles"):
            if self._role_model(role):
                return True
        return bool(self._local_only_model())

    def classify(self, text: str) -> RoutingDecision:
        """Classify a task and return a routing decision."""
        self._ensure_compiled()

        sensitivity = self.classify_sensitivity(text)
        difficulty = self.classify_difficulty(text)
        role = self.classify_role(text)
        tier = _DIFFICULTY_TO_TIER.get(difficulty, TIER_BALANCED)

        # Classification remains useful before the user configures models.
        if not self._is_configured():
            return RoutingDecision(
                model="",
                provider="",
                model_id="",
                tier=tier,
                role=role,
                difficulty=difficulty,
                sensitivity=sensitivity,
                should_delegate=False,
                reason=(
                    "No models configured. Run 'hermes route' to inspect the "
                    "routing config, then copy the default config to "
                    "$HERMES_HOME/hybrid_routing/"
                    "routing_config.yaml and fill in your model refs."
                ),
                candidates=[],
            )

        candidates: list[str] = []

        if sensitivity == SENSITIVE:
            local_model = self._local_only_model()
            if not local_model:
                return RoutingDecision(
                    model="",
                    provider="",
                    model_id="",
                    tier=tier,
                    role=role,
                    difficulty=difficulty,
                    sensitivity=sensitivity,
                    should_delegate=False,
                    reason=(
                        "Sensitive content detected, but a local-only model is "
                        "not configured. No route was selected to prevent a "
                        "cloud fallback recommendation."
                    ),
                    candidates=[],
                )
            candidates.append(local_model)
            reason = (
                "Sensitive content detected → routing to local-only model "
                f"'{local_model}'"
            )
        else:
            role_model = self._role_model(role) if role != "general" else None
            tier_model = self._tier_model(tier)
            if role_model:
                candidates.append(role_model)
                reason = (
                    f"Role '{role}' detected → routing to role model '{role_model}'"
                )
            elif tier_model:
                candidates.append(tier_model)
                reason = (
                    f"Difficulty '{difficulty}' (tier '{tier}') → routing to "
                    f"tier model '{tier_model}'"
                )
            else:
                default = next(
                    (
                        model
                        for fallback_tier in _TIER_FALLBACK_ORDER[tier]
                        if (model := self._tier_model(fallback_tier))
                    ),
                    None,
                ) or self._role_model("general")
                if not default:
                    return RoutingDecision(
                        model="",
                        provider="",
                        model_id="",
                        tier=tier,
                        role=role,
                        difficulty=difficulty,
                        sensitivity=sensitivity,
                        should_delegate=False,
                        reason=(
                            "Models are configured, but none apply to this task. "
                            "No route was selected."
                        ),
                        candidates=[],
                    )
                candidates.append(default)
                reason = (
                    f"No specific routing match → using configured fallback '{default}'"
                )

        if sensitivity != SENSITIVE:
            for fallback_tier in _TIER_FALLBACK_ORDER[tier]:
                model = self._tier_model(fallback_tier)
                if model and model not in candidates:
                    candidates.append(model)

        primary_model = candidates[0]
        provider, model_id = self._resolve_model_ref(primary_model)

        skip_for_tier, skip_if_same, primary_session_model = self._delegation_settings()
        selected_is_primary = bool(primary_session_model) and (
            primary_model == primary_session_model
        )
        should_delegate = True
        if skip_if_same and selected_is_primary:
            should_delegate = False
            reason += " (handled inline — same as primary model)"
        elif sensitivity == SENSITIVE:
            reason += " (separate execution on the local-only model recommended)"
        elif tier in skip_for_tier and selected_is_primary:
            should_delegate = False
            reason += " (handled inline — tier skip and same as primary model)"

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
        """Return a validated, JSON-safe routing configuration summary."""
        self._ensure_compiled()
        tiers_status: dict[str, dict[str, object]] = {}
        for tier_name in _TIER_FALLBACK_ORDER:
            tier_cfg = self._section("tiers")[tier_name]
            tier_status: dict[str, object] = {
                "model": self._tier_model(tier_name) or "",
                "description": self._display_text(
                    tier_cfg.get("description", ""),
                    f"tiers.{tier_name}.description",
                ),
            }
            if "max_input_tokens" in tier_cfg:
                tier_status["max_input_tokens"] = _nonnegative_int(
                    tier_cfg["max_input_tokens"],
                    f"tiers.{tier_name}.max_input_tokens",
                )
            tiers_status[tier_name] = tier_status

        roles_status = {}
        for raw_role_name, role_cfg in self._section("roles").items():
            role_name = self._identifier_value(raw_role_name, "roles key")
            roles_status[role_name] = {
                "model": self._role_model(role_name) or "",
                "description": self._display_text(
                    role_cfg.get("description", ""),
                    f"roles.{role_name}.description",
                ),
                "auxiliary": role_cfg.get("auxiliary", False),
                "cues": list(role_cfg.get("cues", [])),
            }

        diff_cfg = self._section("difficulty")
        difficulty_status = {
            "hard_if_code_block": diff_cfg.get("hard_if_code_block", True),
            "hard_if_long_input": _nonnegative_int(
                diff_cfg.get("hard_if_long_input", 600),
                "difficulty.hard_if_long_input",
            ),
            "hard_if_many_words": _nonnegative_int(
                diff_cfg.get("hard_if_many_words", 80),
                "difficulty.hard_if_many_words",
            ),
            "hard_if_many_lines": _nonnegative_int(
                diff_cfg.get("hard_if_many_lines", 8),
                "difficulty.hard_if_many_lines",
            ),
            "simple_if_short_words": _nonnegative_int(
                diff_cfg.get("simple_if_short_words", 4),
                "difficulty.simple_if_short_words",
            ),
            "hard_cues": list(diff_cfg.get("hard_cues", [])),
            "simple_cues": list(diff_cfg.get("simple_cues", [])),
        }
        skip_for_tier, skip_if_same, primary_model = self._delegation_settings()
        delegation = {
            "skip_for_tier": skip_for_tier,
            "skip_if_same_as_primary": skip_if_same,
            "primary_model": primary_model,
        }
        return {
            "configured": self._is_configured(),
            "config_path": str(self.config_path),
            "tiers": tiers_status,
            "roles": roles_status,
            "sensitivity": {
                "local_only_model": self._local_only_model(),
                "pattern_count": len(self._compiled_sensitive),
            },
            "difficulty": difficulty_status,
            "delegation": delegation,
        }

    def run_tests(self) -> dict:
        """Run the 9-case classifier smoke suite and return results."""
        cases = [
            ("hi", "fast", "general", "normal"),
            ("ok thanks", "fast", "general", "normal"),
            (
                "Debug this Python function that has a bug in the import logic",
                "strong",
                "coding",
                "normal",
            ),
            (
                "Write a creative blog post about AI consciousness",
                "balanced",
                "creative",
                "normal",
            ),
            (
                "Analyze the strategic trade-offs of our go-to-market roadmap",
                "strong",
                "strategy",
                "normal",
            ),
            (
                "Research the latest arxiv papers on RLHF and compare three approaches",
                "strong",
                "research",
                "normal",
            ),
            (
                "Review this document marked Highly Confidential with "
                "password=secret123",
                "balanced",
                "general",
                "sensitive",
            ),
            ("What is 2+2?", "fast", "general", "normal"),
            (
                "Design a distributed system architecture and explain why "
                "each component is needed",
                "strong",
                "general",
                "normal",
            ),
        ]
        results = []
        passed = 0
        for i, (text, exp_tier, exp_role, exp_sens) in enumerate(cases, 1):
            d = self.classify(text)
            ok = d.tier == exp_tier and d.role == exp_role and d.sensitivity == exp_sens
            if ok:
                passed += 1
            results.append(
                {
                    "test": i,
                    "input": text[:60],
                    "passed": ok,
                    "expected": {
                        "tier": exp_tier,
                        "role": exp_role,
                        "sensitivity": exp_sens,
                    },
                    "actual": {
                        "tier": d.tier,
                        "role": d.role,
                        "sensitivity": d.sensitivity,
                        "delegate": d.should_delegate,
                        "model": d.model,
                    },
                }
            )
        return {"passed": passed, "total": len(cases), "results": results}
