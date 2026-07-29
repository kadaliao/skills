#!/usr/bin/env python3
"""Exercise model-router policy, lifecycle logging, and reporting."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
LOG_SCRIPT = SKILL_DIR / "scripts" / "route_log.py"
EVAL_CASES = SKILL_DIR / "references" / "eval-cases.json"
VALID_TIERS = {"passthrough", "fast", "balanced", "deep", "critical"}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LOG_SCRIPT), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def validate_and_run_eval_cases() -> None:
    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 15
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert set(case) == {"id", "request", "reasons", "expected_tier"}
        assert case["expected_tier"] in VALID_TIERS
        assert case["request"].strip()
        assert case["reasons"]
        command = [
            "decide",
            "--dry-run",
            "--task-type",
            "implementation",
        ]
        for reason in case["reasons"]:
            command.extend(("--reason", reason))
        decision = json.loads(run(*command).stdout)
        assert decision["tier"] == case["expected_tier"], case["id"]
        assert "route_id" not in decision


def test_logging_and_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as directory:
        log_file = Path(directory) / "routes.jsonl"
        decision = json.loads(
            run(
                "--log-file",
                str(log_file),
                "decide",
                "--task-type",
                "implementation",
                "--reason",
                "multi-module",
            ).stdout
        )
        route_id = decision["route_id"]
        assert decision["tier"] == "balanced"
        run(
            "--log-file",
            str(log_file),
            "complete",
            "--route-id",
            route_id,
            "--outcome",
            "succeeded",
            "--verification",
            "passed",
            "--final-tier",
            "deep",
            "--duration-seconds",
            "42",
            "--active-duration-seconds",
            "30",
            "--tier-fit",
            "under",
            "--escalation-reason",
            "verification-failed",
        )
        summary = json.loads(run("--log-file", str(log_file), "summary").stdout)
        assert summary["completed"] == 1
        assert summary["stale"] == 0
        assert summary["duration_seconds"]["median"] == 42
        assert summary["duration_seconds"]["p90"] == 42
        assert summary["active_duration_seconds"]["median"] == 30
        assert summary["tier_fits"] == {"under": 1}
        assert summary["duration_sources"] == {"reported": 1}
        assert summary["escalated"] == 1
        assert summary["tier_metrics"]["balanced"]["passed"] == 1
        assert summary["reason_metrics"]["multi-module"]["passed"] == 1

        duplicate = run(
            "--log-file",
            str(log_file),
            "complete",
            "--route-id",
            route_id,
            "--outcome",
            "succeeded",
            "--verification",
            "passed",
            check=False,
        )
        assert duplicate.returncode == 1
        assert "already completed" in duplicate.stderr

        run(
            "--log-file",
            str(log_file),
            "complete",
            "--route-id",
            route_id,
            "--outcome",
            "succeeded",
            "--verification",
            "passed",
            "--tier-fit",
            "appropriate",
            "--revise",
        )
        revised = json.loads(run("--log-file", str(log_file), "summary").stdout)
        assert revised["completion_revisions"] == 1
        assert revised["duration_sources"] == {"wall-clock": 1}

        open_decision = json.loads(
            run(
                "--log-file",
                str(log_file),
                "decide",
                "--task-type",
                "question",
                "--reason",
                "bounded",
                "--reason",
                "low-risk",
                "--reason",
                "deterministic-verification",
            ).stdout
        )
        assert open_decision["tier"] == "fast"
        lines = [json.loads(line) for line in log_file.read_text().splitlines()]
        for line in lines:
            if line["route_id"] == open_decision["route_id"]:
                line["timestamp"] = "2000-01-01T00:00:00+00:00"
        log_file.write_text(
            "".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines),
            encoding="utf-8",
        )

        stale = json.loads(
            run("--log-file", str(log_file), "summary", "--stale-hours", "24").stdout
        )
        assert stale["incomplete"] == 1
        assert stale["active"] == 0
        assert stale["stale"] == 1

        preview = json.loads(
            run("--log-file", str(log_file), "reconcile", "--stale-hours", "24").stdout
        )
        assert preview["applied"] == 0
        assert len(preview["candidates"]) == 1
        applied = json.loads(
            run(
                "--log-file",
                str(log_file),
                "reconcile",
                "--stale-hours",
                "24",
                "--apply",
            ).stdout
        )
        assert applied["applied"] == 1
        closed = json.loads(run("--log-file", str(log_file), "summary").stdout)
        assert closed["stale"] == 0
        assert closed["outcomes"]["abandoned"] == 1

        report = run("--log-file", str(log_file), "report", "--limit", "2").stdout
        assert "# Model Router Report" in report
        assert "## Tier Quality" in report
        assert "## Selection Reasons" in report
        assert "Wall duration: p50" in report
        assert "completion revision(s)" in report
        assert "does not audit provider-side model calls, tokens, or cost" in report

        serialized = log_file.read_text(encoding="utf-8")
        assert "gpt-5.6" not in serialized
        assert "tokens" not in serialized


def test_legacy_log_compatibility() -> None:
    with tempfile.TemporaryDirectory() as directory:
        log_file = Path(directory) / "routes.jsonl"
        route_id = "0761d2cf-c367-4109-87c5-279b95ee8280"
        events = [
            {
                "schema_version": 1,
                "event": "selected",
                "timestamp": "2026-07-14T07:16:13+00:00",
                "route_id": route_id,
                "task_type": "implementation",
                "selected_tier": "balanced",
                "reasons": ["multi-module"],
                "confidence": 0.86,
                "user_override": False,
            },
            {
                "schema_version": 1,
                "event": "completed",
                "timestamp": "2026-07-14T07:31:14+00:00",
                "route_id": route_id,
                "outcome": "succeeded",
                "verification": "partial",
                "final_tier": "balanced",
                "duration_seconds": 420,
                "escalation_reasons": [],
            },
        ]
        log_file.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        summary = json.loads(run("--log-file", str(log_file), "summary").stdout)
        assert summary["completed"] == 1
        assert summary["duration_sources"] == {"legacy-reported": 1}
        assert summary["tier_fits"] == {"unknown": 1}


def main() -> int:
    validate_and_run_eval_cases()
    test_logging_and_lifecycle()
    test_legacy_log_compatibility()
    print("model-router tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
