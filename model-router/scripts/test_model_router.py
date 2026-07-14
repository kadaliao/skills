#!/usr/bin/env python3
"""Validate model-router fixtures and exercise privacy-safe logging."""

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


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LOG_SCRIPT), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def validate_eval_cases() -> None:
    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 10
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert set(case) == {"id", "request", "expected_tier"}
        assert case["expected_tier"] in VALID_TIERS
        assert case["request"].strip()


def test_logging() -> None:
    with tempfile.TemporaryDirectory() as directory:
        log_file = Path(directory) / "routes.jsonl"
        selected = run(
            "--log-file",
            str(log_file),
            "select",
            "--task-type",
            "implementation",
            "--tier",
            "balanced",
            "--reason",
            "multi-module",
            "--confidence",
            "0.82",
        )
        route_id = selected.stdout.strip()
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
            "--escalation-reason",
            "verification-failed",
        )
        summary = json.loads(
            run("--log-file", str(log_file), "summary").stdout
        )
        assert summary == {
            "completed": 1,
            "completion_rate": 1.0,
            "confidence": {"average": 0.82, "maximum": 0.82, "minimum": 0.82},
            "configured_targets": {"gpt-5.6-terra/medium": 1},
            "duration_seconds": {
                "average": 42,
                "maximum": 42,
                "median": 42,
                "minimum": 42,
                "total": 42,
            },
            "escalated": 1,
            "escalation_rate": 1.0,
            "escalation_reasons": {"verification-failed": 1},
            "final_tiers": {"deep": 1},
            "incomplete": 0,
            "outcomes": {"succeeded": 1},
            "routes": 1,
            "selection_reasons": {"multi-module": 1},
            "selected_tiers": {"balanced": 1},
            "task_types": {"implementation": 1},
            "user_overrides": 0,
            "verifications": {"passed": 1},
        }

        run(
            "--log-file",
            str(log_file),
            "select",
            "--task-type",
            "question",
            "--tier",
            "fast",
            "--reason",
            "low-risk",
            "--confidence",
            "0.91",
            "--user-override",
        )
        filtered = json.loads(
            run(
                "--log-file",
                str(log_file),
                "summary",
                "--tier",
                "fast",
            ).stdout
        )
        assert filtered["routes"] == 1
        assert filtered["completed"] == 0
        assert filtered["incomplete"] == 1
        assert filtered["configured_targets"] == {"gpt-5.6-luna/low": 1}
        assert filtered["user_overrides"] == 1

        report = run(
            "--log-file",
            str(log_file),
            "report",
            "--limit",
            "2",
        ).stdout
        assert "# Model Router Report" in report
        assert "gpt-5.6-terra/medium" in report
        assert "balanced -> deep" in report
        assert "completion logging needs attention" in report
        assert "does not audit provider-side model calls, tokens, or cost" in report
        assert "only successfully written router events" in report

        empty = json.loads(
            run(
                "--log-file",
                str(log_file),
                "summary",
                "--since",
                "2999-01-01",
            ).stdout
        )
        assert empty["routes"] == 0
        assert empty["confidence"] == {}
        assert empty["duration_seconds"] == {}

        through_today = json.loads(
            run(
                "--log-file",
                str(log_file),
                "summary",
                "--until",
                "2999-01-01",
            ).stdout
        )
        assert through_today["routes"] == 2

        lines = [json.loads(line) for line in log_file.read_text().splitlines()]
        allowed = {
            "schema_version",
            "event",
            "timestamp",
            "route_id",
            "task_type",
            "selected_tier",
            "reasons",
            "confidence",
            "user_override",
            "outcome",
            "verification",
            "final_tier",
            "duration_seconds",
            "escalation_reasons",
        }
        assert all(set(line) <= allowed for line in lines)
        serialized = log_file.read_text(encoding="utf-8")
        assert "gpt-5.6" not in serialized
        assert "tokens" not in serialized


def main() -> int:
    validate_eval_cases()
    test_logging()
    print("model-router tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
