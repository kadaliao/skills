#!/usr/bin/env python3
"""Append privacy-safe model-router events and summarize them."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


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


def command_summary(args: argparse.Namespace) -> int:
    if not args.log_file.exists():
        print(json.dumps({"routes": 0, "completed": 0}, sort_keys=True))
        return 0

    selected = Counter()
    final = Counter()
    outcomes = Counter()
    verifications = Counter()
    route_ids: set[str] = set()
    completed_ids: set[str] = set()

    with args.log_file.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
            if event.get("event") == "selected":
                route_ids.add(event["route_id"])
                selected[event["selected_tier"]] += 1
            elif event.get("event") == "completed":
                completed_ids.add(event["route_id"])
                final[event["final_tier"]] += 1
                outcomes[event["outcome"]] += 1
                verifications[event["verification"]] += 1

    summary = {
        "routes": len(route_ids),
        "completed": len(completed_ids),
        "selected_tiers": dict(sorted(selected.items())),
        "final_tiers": dict(sorted(final.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "verifications": dict(sorted(verifications.items())),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


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

    summary = subparsers.add_parser("summary", help="summarize route metadata")
    summary.set_defaults(func=command_summary)
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
