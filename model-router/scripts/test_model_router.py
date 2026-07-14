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
            "final_tiers": {"deep": 1},
            "outcomes": {"succeeded": 1},
            "routes": 1,
            "selected_tiers": {"balanced": 1},
            "verifications": {"passed": 1},
        }

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


def main() -> int:
    validate_eval_cases()
    test_logging()
    print("model-router tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

