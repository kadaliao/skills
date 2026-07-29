#!/usr/bin/env python3
"""Deterministic tier selection for privacy-safe model-router signals."""

from __future__ import annotations

from dataclasses import dataclass


TIERS = ("passthrough", "fast", "balanced", "deep", "critical")

BYPASS_REASONS = {"simple", "explicit-skill", "single-step"}
FAST_REASONS = {"bounded", "low-risk", "deterministic-verification"}
DEEP_STRONG_REASONS = {
    "cross-system",
    "ambiguous-root-cause",
    "concurrency-performance",
    "unfamiliar-api",
    "long-verification",
    "independent-review",
    "model-unavailable",
    "verification-failed",
}
DEEP_COMBINATION_REASONS = {
    "multi-source",
    "evidence-needed",
    "high-impact",
}


@dataclass(frozen=True)
class Decision:
    tier: str
    confidence: float
    rule: str


def decide_tier(reasons: set[str], override_tier: str | None = None) -> Decision:
    """Choose one tier from already-classified, privacy-safe task signals."""
    if override_tier is not None:
        if override_tier not in TIERS:
            raise ValueError(f"unknown override tier: {override_tier}")
        return Decision(override_tier, 1.0, "user-override")

    if reasons & BYPASS_REASONS:
        return Decision("passthrough", 0.98, "bypass")

    if "high-impact" in reasons and (
        "hard-to-reverse" in reasons or "difficult-to-verify" in reasons
    ):
        return Decision("critical", 0.92, "high-impact-and-hard-to-recover")

    strong = reasons & DEEP_STRONG_REASONS
    if strong:
        return Decision("deep", 0.90, f"strong-signal:{sorted(strong)[0]}")

    combined = reasons & DEEP_COMBINATION_REASONS
    if "multi-module" in reasons and combined:
        return Decision("deep", 0.84, f"combined-signal:{sorted(combined)[0]}")

    if FAST_REASONS <= reasons:
        return Decision("fast", 0.90, "bounded-low-risk-deterministic")

    return Decision("balanced", 0.82, "balanced-default")
