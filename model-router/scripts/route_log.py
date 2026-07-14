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
    "evidence-needed",
    "multi-source",
    "multi-file",
    "multi-module",
    "cross-system",
    "ambiguous-root-cause",
    "long-verification",
    "high-impact",
    "hard-to-reverse",
    "independent-review",
    "user-override",
    "model-unavailable",
    "verification-failed",
)
OUTCOMES = ("succeeded", "failed", "blocked", "cancelled")
VERIFICATIONS = ("passed", "partial", "failed", "not-applicable")


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


def command_select(args: argparse.Namespace) -> int:
    route_id = str(uuid.uuid4())
    event = {
        "schema_version": 1,
        "event": "selected",
        "timestamp": utc_now(),
        "route_id": route_id,
        "task_type": args.task_type,
        "selected_tier": args.tier,
        "reasons": sorted(set(args.reason)),
        "confidence": args.confidence,
        "user_override": args.user_override,
    }
    append_event(args.log_file, event)
    print(route_id)
    return 0


def command_complete(args: argparse.Namespace) -> int:
    event = {
        "schema_version": 1,
        "event": "completed",
        "timestamp": utc_now(),
        "route_id": str(args.route_id),
        "outcome": args.outcome,
        "verification": args.verification,
        "final_tier": args.final_tier,
        "duration_seconds": args.duration_seconds,
        "escalation_reasons": sorted(set(args.escalation_reason)),
    }
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
                routes.setdefault(route_id, {})["completed"] = event

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


def build_summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    completed_routes = [route for route in routes if route.get("completed")]
    incomplete_routes = [route for route in routes if not route.get("completed")]
    selected_tiers = [route["selected"]["selected_tier"] for route in routes]
    final_tiers = [route["completed"]["final_tier"] for route in completed_routes]
    durations = [route["completed"]["duration_seconds"] for route in completed_routes]
    confidences = [route["selected"]["confidence"] for route in routes]
    escalated = sum(
        TIERS.index(route["completed"]["final_tier"])
        > TIERS.index(route["selected"]["selected_tier"])
        for route in completed_routes
    )
    target_models = [
        "/".join(TIER_TARGETS[tier]) for tier in selected_tiers
    ]

    summary: dict[str, Any] = {
        "routes": len(routes),
        "completed": len(completed_routes),
        "incomplete": len(incomplete_routes),
        "completion_rate": rounded(len(completed_routes) / len(routes)) if routes else 0,
        "selected_tiers": count_values(selected_tiers),
        "configured_targets": count_values(target_models),
        "final_tiers": count_values(final_tiers),
        "task_types": count_values(
            [route["selected"]["task_type"] for route in routes]
        ),
        "selection_reasons": count_values(
            [reason for route in routes for reason in route["selected"].get("reasons", [])]
        ),
        "outcomes": count_values(
            [route["completed"]["outcome"] for route in completed_routes]
        ),
        "verifications": count_values(
            [route["completed"]["verification"] for route in completed_routes]
        ),
        "escalated": escalated,
        "escalation_rate": rounded(escalated / len(completed_routes)) if completed_routes else 0,
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
        }
        if durations
        else {}
    )
    return summary


def command_summary(args: argparse.Namespace) -> int:
    print(json.dumps(build_summary(filtered_routes(args)), sort_keys=True))
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


def command_report(args: argparse.Namespace) -> int:
    routes = filtered_routes(args)
    summary = build_summary(routes)
    print("# Model Router Report")
    print()
    print(
        f"Routes: {summary['routes']} | Completed: {summary['completed']} "
        f"({percent(summary['completion_rate'])}) | Incomplete: {summary['incomplete']}"
    )
    duration = summary["duration_seconds"]
    if duration:
        print(
            f"Duration: median {format_duration(duration['median'])}, "
            f"average {format_duration(duration['average'])}, "
            f"total {format_duration(duration['total'])}"
        )
    print(
        f"Escalated: {summary['escalated']} ({percent(summary['escalation_rate'])}) "
        f"| User overrides: {summary['user_overrides']}"
    )
    print()
    print("## Tier Usage")
    print()
    print("| Tier | Configured target | Selected | Final |")
    print("| --- | --- | ---: | ---: |")
    for tier in TIERS:
        model, effort = TIER_TARGETS[tier]
        print(
            f"| {tier} | {model}/{effort} | "
            f"{summary['selected_tiers'].get(tier, 0)} | "
            f"{summary['final_tiers'].get(tier, 0)} |"
        )

    print()
    print("## Outcomes")
    print()
    print(f"Outcomes: {json.dumps(summary['outcomes'], sort_keys=True)}")
    print(f"Verification: {json.dumps(summary['verifications'], sort_keys=True)}")
    print(f"Selection reasons: {json.dumps(summary['selection_reasons'], sort_keys=True)}")
    if summary["escalation_reasons"]:
        print(
            f"Escalation reasons: {json.dumps(summary['escalation_reasons'], sort_keys=True)}"
        )

    signals = []
    if summary["incomplete"]:
        signals.append(
            f"{summary['incomplete']} route(s) have no completion event; completion logging needs attention."
        )
    if summary["completed"] and summary["verifications"].get("passed", 0) == 0:
        signals.append("No completed route has passed verification.")
    failed = summary["outcomes"].get("failed", 0) + summary["outcomes"].get("blocked", 0)
    if failed:
        signals.append(f"{failed} completed route(s) failed or were blocked.")
    if signals:
        print()
        print("## Signals")
        print()
        for signal in signals:
            print(f"- {signal}")

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
        print(
            f"| {selected['timestamp']} | {route['route_id'][:8]} | "
            f"{selected['task_type']} | {route_change} | "
            f"{completed['outcome'] if completed else 'incomplete'} | "
            f"{completed['verification'] if completed else '-'} | "
            f"{format_duration(completed['duration_seconds']) if completed else '-'} |"
        )
    print()
    print(
        "Configured targets are inferred from the router tier mapping; this report does not "
        "audit provider-side model calls, tokens, or cost. It covers only successfully "
        "written router events."
    )
    return 0


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--days", type=positive_int, help="include the last N days")
    window.add_argument("--since", type=iso_timestamp, help="include routes at or after ISO time")
    parser.add_argument(
        "--until",
        type=until_timestamp,
        help="include routes at or before ISO time; a date includes the full UTC day",
    )
    parser.add_argument("--task-type", choices=TASK_TYPES)
    parser.add_argument("--tier", choices=TIERS, help="filter by initially selected tier")


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

    complete = subparsers.add_parser("complete", help="record a routing outcome")
    complete.add_argument("--route-id", type=uuid.UUID, required=True)
    complete.add_argument("--outcome", choices=OUTCOMES, required=True)
    complete.add_argument("--verification", choices=VERIFICATIONS, required=True)
    complete.add_argument("--final-tier", choices=TIERS, required=True)
    complete.add_argument("--duration-seconds", type=nonnegative_int, required=True)
    complete.add_argument(
        "--escalation-reason", choices=REASONS, action="append", default=[]
    )
    complete.set_defaults(func=command_complete)

    summary = subparsers.add_parser("summary", help="output filtered route metrics as JSON")
    add_filter_arguments(summary)
    summary.set_defaults(func=command_summary)

    report = subparsers.add_parser("report", help="output a human-readable routing review")
    add_filter_arguments(report)
    report.add_argument("--limit", type=positive_int, default=10, help="recent route rows")
    report.set_defaults(func=command_report)
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
