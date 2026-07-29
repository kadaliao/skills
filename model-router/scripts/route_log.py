#!/usr/bin/env python3
"""Append privacy-safe model-router events and review routing history."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from route_policy import (
    DEEP_COMBINATION_REASONS,
    DEEP_STRONG_REASONS,
    decide_tier,
)


TASK_TYPES = (
    "question",
    "research",
    "diagnosis",
    "implementation",
    "review",
    "planning",
    "operations",
    "artifact",
    "other",
)
TIERS = ("passthrough", "fast", "balanced", "deep", "critical")
TIER_TARGETS = {
    "passthrough": ("root-session", "current"),
    "fast": ("gpt-5.6-luna", "low"),
    "balanced": ("gpt-5.6-terra", "medium"),
    "deep": ("gpt-5.6-sol", "high"),
    "critical": ("gpt-5.6-sol", "max"),
}
REASONS = (
    "simple",
    "explicit-skill",
    "single-step",
    "bounded",
    "low-risk",
    "deterministic-verification",
    "evidence-needed",
    "multi-source",
    "multi-file",
    "multi-module",
    "cross-system",
    "ambiguous-root-cause",
    "concurrency-performance",
    "unfamiliar-api",
    "long-verification",
    "high-impact",
    "hard-to-reverse",
    "difficult-to-verify",
    "independent-review",
    "user-override",
    "model-unavailable",
    "verification-failed",
)
OUTCOMES = ("succeeded", "failed", "blocked", "cancelled", "abandoned")
VERIFICATIONS = ("passed", "partial", "failed", "not-applicable")
TIER_FITS = ("appropriate", "over", "under", "unknown")
DEFAULT_STALE_HOURS = 24


def default_log_file() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "state" / "model-router" / "routes.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("confidence must be between 0 and 1")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def iso_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "timestamp must be ISO 8601, for example 2026-07-14 or 2026-07-14T08:00:00Z"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def until_timestamp(value: str) -> datetime:
    parsed = iso_timestamp(value)
    if "T" not in value and " " not in value:
        return parsed + timedelta(days=1) - timedelta(microseconds=1)
    return parsed


def event_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("event timestamp must be a string")
    try:
        return iso_timestamp(value)
    except argparse.ArgumentTypeError as exc:
        raise ValueError(str(exc)) from exc


def append_event(log_file: Path, event: dict[str, object]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n")


def selected_event(
    *,
    task_type: str,
    tier: str,
    reasons: list[str],
    confidence: float,
    user_override: bool,
    decision_rule: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 2,
        "event": "selected",
        "timestamp": utc_now(),
        "route_id": str(uuid.uuid4()),
        "task_type": task_type,
        "selected_tier": tier,
        "reasons": sorted(set(reasons)),
        "confidence": confidence,
        "user_override": user_override,
    }
    if decision_rule:
        event["decision_rule"] = decision_rule
    return event


def command_select(args: argparse.Namespace) -> int:
    event = selected_event(
        task_type=args.task_type,
        tier=args.tier,
        reasons=args.reason,
        confidence=args.confidence,
        user_override=args.user_override,
        decision_rule="manual-selection",
    )
    append_event(args.log_file, event)
    print(event["route_id"])
    return 0


def command_decide(args: argparse.Namespace) -> int:
    reasons = set(args.reason)
    if args.tier is not None:
        reasons.add("user-override")
    decision = decide_tier(reasons, args.tier)
    result: dict[str, object] = {
        "tier": decision.tier,
        "confidence": decision.confidence,
        "rule": decision.rule,
        "reasons": sorted(reasons),
        "configured_target": "/".join(TIER_TARGETS[decision.tier]),
    }
    if not args.dry_run:
        event = selected_event(
            task_type=args.task_type,
            tier=decision.tier,
            reasons=list(reasons),
            confidence=decision.confidence,
            user_override=args.tier is not None,
            decision_rule=decision.rule,
        )
        append_event(args.log_file, event)
        result["route_id"] = event["route_id"]
    print(json.dumps(result, sort_keys=True))
    return 0


def route_by_id(log_file: Path, route_id: str) -> dict[str, Any]:
    for route in load_routes(log_file):
        if route["route_id"] == route_id:
            return route
    raise ValueError(f"route not found: {route_id}")


def elapsed_seconds(start: Any, end: Any | None = None) -> int:
    started = event_timestamp(start)
    finished = event_timestamp(end) if end is not None else datetime.now(timezone.utc)
    return max(0, int((finished - started).total_seconds()))


def command_complete(args: argparse.Namespace) -> int:
    route_id = str(args.route_id)
    route = route_by_id(args.log_file, route_id)
    if route.get("completed") and not args.revise:
        raise ValueError(
            f"route already completed: {route_id}; pass --revise to append a correction"
        )
    timestamp = utc_now()
    duration_seconds = args.duration_seconds
    duration_source = "reported"
    if duration_seconds is None:
        duration_seconds = elapsed_seconds(route["selected"]["timestamp"], timestamp)
        duration_source = "wall-clock"
    event = {
        "schema_version": 2,
        "event": "completed",
        "timestamp": timestamp,
        "route_id": route_id,
        "outcome": args.outcome,
        "verification": args.verification,
        "final_tier": args.final_tier or route["selected"]["selected_tier"],
        "duration_seconds": duration_seconds,
        "duration_source": duration_source,
        "tier_fit": args.tier_fit,
        "escalation_reasons": sorted(set(args.escalation_reason)),
    }
    if args.active_duration_seconds is not None:
        event["active_duration_seconds"] = args.active_duration_seconds
    if args.revise:
        event["revision"] = True
    if args.completion_reason:
        event["completion_reason"] = args.completion_reason
    append_event(args.log_file, event)
    return 0


def load_routes(log_file: Path) -> list[dict[str, Any]]:
    if not log_file.exists():
        return []

    routes: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    with log_file.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
            route_id = event.get("route_id")
            if not isinstance(route_id, str):
                raise ValueError(f"missing route_id on line {line_number}")
            if event.get("event") == "selected":
                if route_id not in routes:
                    order.append(route_id)
                routes.setdefault(route_id, {})["selected"] = event
            elif event.get("event") == "completed":
                route = routes.setdefault(route_id, {})
                route.setdefault("completion_events", []).append(event)
                route["completed"] = event

    return [
        {"route_id": route_id, **routes[route_id]}
        for route_id in order
        if "selected" in routes[route_id]
    ]


def filtered_routes(args: argparse.Namespace) -> list[dict[str, Any]]:
    routes = load_routes(args.log_file)
    if args.days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
    else:
        since = args.since
    until = args.until
    if since and until and since > until:
        raise ValueError("--since must not be later than --until")

    result = []
    for route in routes:
        selected = route["selected"]
        timestamp = event_timestamp(selected.get("timestamp"))
        if since and timestamp < since:
            continue
        if until and timestamp > until:
            continue
        if args.task_type and selected.get("task_type") != args.task_type:
            continue
        if args.tier and selected.get("selected_tier") != args.tier:
            continue
        result.append(route)
    return result


def rounded(value: float) -> float:
    return round(value, 2)


def count_values(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def percentile(values: list[int | float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def is_stale(
    route: dict[str, Any], stale_hours: int, now: datetime | None = None
) -> bool:
    if route.get("completed"):
        return False
    current = now or datetime.now(timezone.utc)
    selected_at = event_timestamp(route["selected"]["timestamp"])
    return current - selected_at >= timedelta(hours=stale_hours)


def aggregate_metrics(
    routes: list[dict[str, Any]], key_values: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for key, matching in sorted(key_values.items()):
        completed = [route for route in matching if route.get("completed")]
        metrics[key] = {
            "selected": len(matching),
            "completed": len(completed),
            "succeeded": sum(
                route["completed"].get("outcome") == "succeeded" for route in completed
            ),
            "passed": sum(
                route["completed"].get("verification") == "passed"
                for route in completed
            ),
            "partial": sum(
                route["completed"].get("verification") == "partial"
                for route in completed
            ),
            "blocked": sum(
                route["completed"].get("outcome") == "blocked" for route in completed
            ),
            "tiers": count_values(
                [route["selected"]["selected_tier"] for route in matching]
            ),
        }
    return metrics


def current_policy_supports_deep(selected: dict[str, Any]) -> bool:
    reasons = set(selected.get("reasons", []))
    if selected.get("user_override"):
        return True
    if reasons & DEEP_STRONG_REASONS:
        return True
    return "multi-module" in reasons and bool(reasons & DEEP_COMBINATION_REASONS)


def build_summary(
    routes: list[dict[str, Any]],
    stale_hours: int = DEFAULT_STALE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    completed_routes = [route for route in routes if route.get("completed")]
    incomplete_routes = [route for route in routes if not route.get("completed")]
    stale_routes = [
        route for route in incomplete_routes if is_stale(route, stale_hours, now)
    ]
    active_routes = [route for route in incomplete_routes if route not in stale_routes]
    selected_tiers = [route["selected"]["selected_tier"] for route in routes]
    final_tiers = [route["completed"]["final_tier"] for route in completed_routes]
    durations = [
        route["completed"]["duration_seconds"]
        for route in completed_routes
        if route["completed"].get("outcome") != "abandoned"
        if isinstance(route["completed"].get("duration_seconds"), (int, float))
    ]
    active_durations = [
        route["completed"]["active_duration_seconds"]
        for route in completed_routes
        if route["completed"].get("outcome") != "abandoned"
        if isinstance(route["completed"].get("active_duration_seconds"), (int, float))
    ]
    confidences = [
        route["selected"]["confidence"]
        for route in routes
        if isinstance(route["selected"].get("confidence"), (int, float))
    ]
    escalated = sum(
        TIERS.index(route["completed"]["final_tier"])
        > TIERS.index(route["selected"]["selected_tier"])
        for route in completed_routes
    )
    target_models = ["/".join(TIER_TARGETS[tier]) for tier in selected_tiers]
    tier_groups = {
        tier: [route for route in routes if route["selected"]["selected_tier"] == tier]
        for tier in TIERS
        if any(route["selected"]["selected_tier"] == tier for route in routes)
    }
    observed_reasons = sorted(
        {reason for route in routes for reason in route["selected"].get("reasons", [])}
    )
    reason_groups = {
        reason: [
            route for route in routes if reason in route["selected"].get("reasons", [])
        ]
        for reason in observed_reasons
    }

    summary: dict[str, Any] = {
        "routes": len(routes),
        "completed": len(completed_routes),
        "incomplete": len(incomplete_routes),
        "active": len(active_routes),
        "stale": len(stale_routes),
        "stale_hours": stale_hours,
        "completion_rate": rounded(len(completed_routes) / len(routes))
        if routes
        else 0,
        "selected_tiers": count_values(selected_tiers),
        "configured_targets": count_values(target_models),
        "final_tiers": count_values(final_tiers),
        "task_types": count_values(
            [route["selected"]["task_type"] for route in routes]
        ),
        "selection_reasons": count_values(
            [
                reason
                for route in routes
                for reason in route["selected"].get("reasons", [])
            ]
        ),
        "outcomes": count_values(
            [route["completed"]["outcome"] for route in completed_routes]
        ),
        "verifications": count_values(
            [route["completed"]["verification"] for route in completed_routes]
        ),
        "tier_fits": count_values(
            [
                route["completed"].get("tier_fit", "unknown")
                for route in completed_routes
            ]
        ),
        "duration_sources": count_values(
            [
                route["completed"].get("duration_source", "legacy-reported")
                for route in completed_routes
            ]
        ),
        "completion_revisions": sum(
            max(0, len(route.get("completion_events", [])) - 1) for route in routes
        ),
        "deep_without_current_strong_signal": sum(
            route["selected"].get("selected_tier") == "deep"
            and not current_policy_supports_deep(route["selected"])
            for route in routes
        ),
        "tier_metrics": aggregate_metrics(routes, tier_groups),
        "reason_metrics": aggregate_metrics(routes, reason_groups),
        "escalated": escalated,
        "escalation_rate": rounded(escalated / len(completed_routes))
        if completed_routes
        else 0,
        "escalation_reasons": count_values(
            [
                reason
                for route in completed_routes
                for reason in route["completed"].get("escalation_reasons", [])
            ]
        ),
        "user_overrides": sum(
            bool(route["selected"].get("user_override")) for route in routes
        ),
    }
    summary["confidence"] = (
        {
            "average": rounded(statistics.mean(confidences)),
            "minimum": min(confidences),
            "maximum": max(confidences),
        }
        if confidences
        else {}
    )
    summary["duration_seconds"] = (
        {
            "total": sum(durations),
            "average": rounded(statistics.mean(durations)),
            "median": rounded(statistics.median(durations)),
            "minimum": min(durations),
            "maximum": max(durations),
            "p90": rounded(percentile(durations, 0.90)),
        }
        if durations
        else {}
    )
    summary["active_duration_seconds"] = (
        {
            "average": rounded(statistics.mean(active_durations)),
            "median": rounded(statistics.median(active_durations)),
            "p90": rounded(percentile(active_durations, 0.90)),
            "maximum": max(active_durations),
        }
        if active_durations
        else {}
    )
    return summary


def command_summary(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            build_summary(filtered_routes(args), stale_hours=args.stale_hours),
            sort_keys=True,
        )
    )
    return 0


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def format_duration(seconds: int | float) -> str:
    seconds = int(seconds)
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {remainder}s"
    if minutes:
        return f"{minutes}m {remainder}s"
    return f"{remainder}s"


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0


def verification_pass_rate(summary: dict[str, Any]) -> float:
    verifications = summary["verifications"]
    denominator = sum(
        verifications.get(value, 0) for value in ("passed", "partial", "failed")
    )
    return ratio(verifications.get("passed", 0), denominator)


def command_report(args: argparse.Namespace) -> int:
    routes = filtered_routes(args)
    summary = build_summary(routes, stale_hours=args.stale_hours)
    print("# Model Router Report")
    print()
    print(
        f"Routes: {summary['routes']} | Completed: {summary['completed']} "
        f"({percent(summary['completion_rate'])}) | Active: {summary['active']} | "
        f"Stale: {summary['stale']} (>{summary['stale_hours']}h)"
    )
    duration = summary["duration_seconds"]
    if duration:
        print(
            f"Wall duration: p50 {format_duration(duration['median'])}, "
            f"p90 {format_duration(duration['p90'])}, "
            f"average {format_duration(duration['average'])}, "
            f"max {format_duration(duration['maximum'])}"
        )
    active_duration = summary["active_duration_seconds"]
    if active_duration:
        print(
            f"Active duration: p50 {format_duration(active_duration['median'])}, "
            f"p90 {format_duration(active_duration['p90'])}, "
            f"max {format_duration(active_duration['maximum'])}"
        )
    print(
        f"Escalated: {summary['escalated']} ({percent(summary['escalation_rate'])}) "
        f"| User overrides: {summary['user_overrides']}"
    )
    if args.days is not None:
        now = datetime.now(timezone.utc)
        previous_args = argparse.Namespace(**vars(args))
        previous_args.days = None
        previous_args.since = now - timedelta(days=args.days * 2)
        previous_args.until = now - timedelta(days=args.days, microseconds=1)
        previous = build_summary(
            filtered_routes(previous_args), stale_hours=args.stale_hours, now=now
        )
        current_pass_rate = verification_pass_rate(summary)
        previous_pass_rate = verification_pass_rate(previous)
        print()
        print("## Window Comparison")
        print()
        print("| Window | Routes | Completion | Deep share | Passed | Stale |")
        print("| --- | ---: | ---: | ---: | ---: | ---: |")
        print(
            f"| Last {args.days}d | {summary['routes']} | "
            f"{percent(summary['completion_rate'])} | "
            f"{percent(ratio(summary['selected_tiers'].get('deep', 0), summary['routes']))} | "
            f"{percent(current_pass_rate)} | {summary['stale']} |"
        )
        print(
            f"| Previous {args.days}d | {previous['routes']} | "
            f"{percent(previous['completion_rate'])} | "
            f"{percent(ratio(previous['selected_tiers'].get('deep', 0), previous['routes']))} | "
            f"{percent(previous_pass_rate)} | {previous['stale']} |"
        )
    print()
    print("## Tier Quality")
    print()
    print(
        "| Tier | Configured target | Selected | Final | Passed | Partial | Blocked |"
    )
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for tier in TIERS:
        model, effort = TIER_TARGETS[tier]
        metrics = summary["tier_metrics"].get(tier, {})
        print(
            f"| {tier} | {model}/{effort} | "
            f"{summary['selected_tiers'].get(tier, 0)} | "
            f"{summary['final_tiers'].get(tier, 0)} | "
            f"{metrics.get('passed', 0)} | {metrics.get('partial', 0)} | "
            f"{metrics.get('blocked', 0)} |"
        )
    print()
    print(
        "Passed, partial, and blocked are grouped by initially selected tier; "
        "Final counts the latest final tier."
    )

    print()
    print("## Outcomes")
    print()
    print(f"Outcomes: {json.dumps(summary['outcomes'], sort_keys=True)}")
    print(f"Verification: {json.dumps(summary['verifications'], sort_keys=True)}")
    print(f"Tier fit: {json.dumps(summary['tier_fits'], sort_keys=True)}")
    print(
        f"Duration sources: {json.dumps(summary['duration_sources'], sort_keys=True)}"
    )
    if summary["escalation_reasons"]:
        print(
            f"Escalation reasons: {json.dumps(summary['escalation_reasons'], sort_keys=True)}"
        )

    signals = []
    if summary["stale"]:
        signals.append(
            f"{summary['stale']} route(s) are stale; run reconcile to preview cleanup."
        )
    if summary["deep_without_current_strong_signal"]:
        signals.append(
            f"{summary['deep_without_current_strong_signal']} recorded deep selection(s) "
            "do not meet the current strong-signal policy; historical routes are included."
        )
    if summary["completion_revisions"]:
        signals.append(
            f"{summary['completion_revisions']} completion revision(s) were recorded."
        )
    if summary["completed"] and summary["verifications"].get("passed", 0) == 0:
        signals.append("No completed route has passed verification.")
    failed = summary["outcomes"].get("failed", 0) + summary["outcomes"].get(
        "blocked", 0
    )
    if failed:
        signals.append(f"{failed} completed route(s) failed or were blocked.")
    if signals:
        print()
        print("## Signals")
        print()
        for signal in signals:
            print(f"- {signal}")

    print()
    print("## Selection Reasons")
    print()
    print("| Reason | Tier split | Selected | Passed | Partial | Blocked |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    reason_rows = sorted(
        summary["reason_metrics"].items(),
        key=lambda item: (-item[1]["selected"], item[0]),
    )[: args.top_reasons]
    for reason, metrics in reason_rows:
        tier_split = ", ".join(
            f"{tier}:{count}" for tier, count in metrics["tiers"].items()
        )
        print(
            f"| {reason} | {tier_split} | {metrics['selected']} | {metrics['passed']} | "
            f"{metrics['partial']} | {metrics['blocked']} |"
        )

    print()
    print("## Recent Routes")
    print()
    print("| Time (UTC) | ID | Task | Tiers | Outcome | Verification | Duration |")
    print("| --- | --- | --- | --- | --- | --- | ---: |")
    for route in reversed(routes[-args.limit :]):
        selected = route["selected"]
        completed = route.get("completed")
        route_change = selected["selected_tier"]
        if completed and completed["final_tier"] != selected["selected_tier"]:
            route_change += f" -> {completed['final_tier']}"
        if completed:
            outcome = completed["outcome"]
            verification = completed["verification"]
            duration_text = format_duration(completed["duration_seconds"])
        else:
            outcome = "stale" if is_stale(route, args.stale_hours) else "active"
            verification = "-"
            duration_text = "-"
        print(
            f"| {selected['timestamp']} | {route['route_id'][:8]} | "
            f"{selected['task_type']} | {route_change} | "
            f"{outcome} | {verification} | {duration_text} |"
        )
    print()
    print(
        "Configured targets are inferred from the router tier mapping; this report does not "
        "audit provider-side model calls, tokens, or cost. It covers only successfully "
        "written router events."
    )
    return 0


def command_reconcile(args: argparse.Namespace) -> int:
    candidates = [
        route
        for route in load_routes(args.log_file)
        if is_stale(route, args.stale_hours)
    ]
    result: dict[str, Any] = {
        "stale_hours": args.stale_hours,
        "candidates": [
            {
                "route_id": route["route_id"],
                "selected_at": route["selected"]["timestamp"],
                "task_type": route["selected"]["task_type"],
                "tier": route["selected"]["selected_tier"],
            }
            for route in candidates
        ],
        "applied": 0,
    }
    if args.apply:
        timestamp = utc_now()
        for route in candidates:
            append_event(
                args.log_file,
                {
                    "schema_version": 2,
                    "event": "completed",
                    "timestamp": timestamp,
                    "route_id": route["route_id"],
                    "outcome": "abandoned",
                    "verification": "not-applicable",
                    "final_tier": route["selected"]["selected_tier"],
                    "duration_seconds": elapsed_seconds(
                        route["selected"]["timestamp"], timestamp
                    ),
                    "duration_source": "stale-age",
                    "tier_fit": "unknown",
                    "completion_reason": "stale-reconciled",
                    "escalation_reasons": [],
                },
            )
        result["applied"] = len(candidates)
    print(json.dumps(result, sort_keys=True))
    return 0


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--days", type=positive_int, help="include the last N days")
    window.add_argument(
        "--since", type=iso_timestamp, help="include routes at or after ISO time"
    )
    parser.add_argument(
        "--until",
        type=until_timestamp,
        help="include routes at or before ISO time; a date includes the full UTC day",
    )
    parser.add_argument("--task-type", choices=TASK_TYPES)
    parser.add_argument(
        "--tier", choices=TIERS, help="filter by initially selected tier"
    )
    parser.add_argument("--stale-hours", type=positive_int, default=DEFAULT_STALE_HOURS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", type=Path, default=default_log_file())
    subparsers = parser.add_subparsers(dest="command", required=True)

    select = subparsers.add_parser("select", help="record a routing decision")
    select.add_argument("--task-type", choices=TASK_TYPES, required=True)
    select.add_argument("--tier", choices=TIERS, required=True)
    select.add_argument("--reason", choices=REASONS, action="append", required=True)
    select.add_argument("--confidence", type=probability, required=True)
    select.add_argument("--user-override", action="store_true")
    select.set_defaults(func=command_select)

    decide = subparsers.add_parser(
        "decide", help="choose a tier from privacy-safe task signals and record it"
    )
    decide.add_argument("--task-type", choices=TASK_TYPES, required=True)
    decide.add_argument("--reason", choices=REASONS, action="append", required=True)
    decide.add_argument("--tier", choices=TIERS, help="explicit user tier override")
    decide.add_argument("--dry-run", action="store_true", help="do not append an event")
    decide.set_defaults(func=command_decide)

    complete = subparsers.add_parser("complete", help="record a routing outcome")
    complete.add_argument("--route-id", type=uuid.UUID, required=True)
    complete.add_argument("--outcome", choices=OUTCOMES, required=True)
    complete.add_argument("--verification", choices=VERIFICATIONS, required=True)
    complete.add_argument("--final-tier", choices=TIERS)
    complete.add_argument(
        "--duration-seconds",
        type=nonnegative_int,
        help="reported wall duration; omit to calculate it from event timestamps",
    )
    complete.add_argument("--active-duration-seconds", type=nonnegative_int)
    complete.add_argument("--tier-fit", choices=TIER_FITS, default="unknown")
    complete.add_argument("--revise", action="store_true")
    complete.add_argument("--completion-reason", choices=("normal", "stale-reconciled"))
    complete.add_argument(
        "--escalation-reason", choices=REASONS, action="append", default=[]
    )
    complete.set_defaults(func=command_complete)

    summary = subparsers.add_parser(
        "summary", help="output filtered route metrics as JSON"
    )
    add_filter_arguments(summary)
    summary.set_defaults(func=command_summary)

    report = subparsers.add_parser(
        "report", help="output a human-readable routing review"
    )
    add_filter_arguments(report)
    report.add_argument(
        "--limit", type=positive_int, default=10, help="recent route rows"
    )
    report.add_argument(
        "--top-reasons", type=positive_int, default=10, help="selection reason rows"
    )
    report.set_defaults(func=command_report)

    reconcile = subparsers.add_parser(
        "reconcile", help="preview or close incomplete routes older than a threshold"
    )
    reconcile.add_argument(
        "--stale-hours", type=positive_int, default=DEFAULT_STALE_HOURS
    )
    reconcile.add_argument(
        "--apply", action="store_true", help="close candidates as abandoned"
    )
    reconcile.set_defaults(func=command_reconcile)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"route_log: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
