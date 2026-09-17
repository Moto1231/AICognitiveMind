#!/usr/bin/env python3
"""Run behavioral acceptance cases against a live Cognitive Mind instance."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_CASES = Path("acceptance/cases.json")
DEFAULT_TIMEOUT_SECONDS = 120
CONTROL_REQUEST_TIMEOUT_SECONDS = 30
INTERACTION_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("ACCEPTANCE_INTERACTION_TIMEOUT", "1800")
)


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout_seconds: int = CONTROL_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except (TimeoutError, URLError) as exc:
        raise RuntimeError(f"Unable to reach {url}: {exc}") from exc

    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {payload[:500]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"Expected JSON object from {url}, got {type(result).__name__}")
    return result


def _wait_for_revision(base_url: str, expected_revision: str) -> None:
    deadline = time.monotonic() + int(
        os.getenv("ACCEPTANCE_SYNC_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    )
    last_revision = "unavailable"
    while time.monotonic() < deadline:
        try:
            payload = _request_json(f"{base_url}/debug/revision")
            last_revision = str(payload.get("revision", "unknown"))
            if last_revision == expected_revision:
                print(f"Runtime synchronized to {expected_revision[:12]}")
                return
        except RuntimeError as exc:
            last_revision = str(exc)
        time.sleep(3)
    raise RuntimeError(
        "Runtime did not synchronize to the tested commit. "
        f"Expected {expected_revision}, last observed {last_revision}"
    )


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"{path} must contain a non-empty JSON list")
    for index, case in enumerate(payload, start=1):
        if not isinstance(case, dict) or not case.get("name"):
            raise RuntimeError(f"Case {index} in {path} requires a name")
        if not case.get("message") and not case.get("steps"):
            raise RuntimeError(f"Case {index} in {path} requires message or steps")
    return payload


def _indicates_identity_clarification(response_text: str) -> bool:
    normalized = response_text.casefold()
    identity_targets = (
        "who you are",
        "who are you",
        "your name",
        "identify yourself",
        "identifying information",
        "about yourself",
    )
    clarification_cues = (
        "not sure",
        "don't know",
        "do not know",
        "can you",
        "could you",
        "would you",
        "please",
        "tell me",
        "what is",
        "who are",
    )
    return any(target in normalized for target in identity_targets) and any(
        cue in normalized for cue in clarification_cues
    )


def _evaluate(expectation: dict[str, Any], response_text: str) -> list[str]:
    failures: list[str] = []
    normalized = response_text.casefold()
    for required in expectation.get("must_contain", []):
        if str(required).casefold() not in normalized:
            failures.append(f"missing required text: {required!r}")
    required_any = expectation.get("must_contain_any", [])
    if required_any and not any(str(value).casefold() in normalized for value in required_any):
        failures.append(f"missing any required alternative: {required_any!r}")
    if expectation.get("must_request_identity") and not _indicates_identity_clarification(
        response_text
    ):
        failures.append("did not request clarification of the current speaker's identity")
    for forbidden in expectation.get("must_not_contain", []):
        if str(forbidden).casefold() in normalized:
            failures.append(f"contained forbidden text: {forbidden!r}")
    return failures


def _run_step(base_url: str, step: dict[str, Any]) -> tuple[str, list[str]]:
    if step.get("checkpoint"):
        result = _request_json(f"{base_url}/v1/mind/checkpoint", method="POST")
        context = result.get("context", {})
        failures = [] if context == {} else [f"checkpoint did not clear context: {context!r}"]
        return "checkpoint", failures

    message = str(step.get("message", ""))
    if not message:
        return "", ["step requires message or checkpoint"]
    result = _request_json(
        f"{base_url}/v1/mind/interactions",
        method="POST",
        body={"message": message},
        timeout_seconds=INTERACTION_REQUEST_TIMEOUT_SECONDS,
    )
    response_text = str(result.get("response_text", ""))
    failures = _evaluate(step, response_text)

    expected_context = step.get("working_context")
    if expected_context is not None:
        state = _request_json(f"{base_url}/v1/mind/working-memory")
        actual_context = state.get("context", {})
        if actual_context != expected_context:
            failures.append(
                "working context mismatch: "
                f"expected {expected_context!r}, got {actual_context!r}"
            )

    return response_text, failures


def _write_summary(lines: list[str]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")


def main() -> int:
    base_url = os.getenv("COGNITIVE_MIND_TEST_URL", "").strip().rstrip("/")
    if not base_url:
        print("COGNITIVE_MIND_TEST_URL is not configured", file=sys.stderr)
        return 2
    expected_revision = os.getenv("EXPECTED_REVISION", "").strip()
    cases_path = Path(os.getenv("ACCEPTANCE_CASES", str(DEFAULT_CASES)))

    try:
        if expected_revision:
            _wait_for_revision(base_url, expected_revision)
        health = _request_json(f"{base_url}/health")
        if health.get("status") != "healthy":
            raise RuntimeError(f"Health check failed: {health}")
        cases = _load_cases(cases_path)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Acceptance infrastructure failure: {exc}", file=sys.stderr)
        return 2

    failed = 0
    total = 0
    summary = ["## Cognitive acceptance", ""]

    for case in cases:
        name = str(case["name"])
        steps = case.get("steps") or [case]
        case_failed = False
        for index, step in enumerate(steps, start=1):
            total += 1
            try:
                response_text, failures = _run_step(base_url, step)
            except RuntimeError as exc:
                response_text = ""
                failures = [str(exc)]
            label = f"{name} step {index}"
            if failures:
                failed += 1
                case_failed = True
                print(f"FAIL {label}")
                for failure in failures:
                    print(f"  - {failure}")
                if response_text:
                    print(f"  response: {response_text}")
                summary.append(f"- ❌ **{label}** — {'; '.join(failures)}")
                break
            print(f"PASS {label}: {response_text}")
            summary.append(f"- ✅ **{label}** — {response_text}")
        if case_failed:
            continue

    summary.append("")
    summary.append(f"Result: {total - failed}/{total} executed steps passed")
    _write_summary(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
