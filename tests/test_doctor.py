"""researchhq doctor: returns CheckResults across all categories."""

from __future__ import annotations

from researchhq.doctor import (
    CheckResult,
    CRITICAL,
    has_critical_failure,
    run_checks,
)


def test_run_checks_returns_results():
    results = run_checks()
    assert results
    assert all(isinstance(r, CheckResult) for r in results)


def test_run_checks_includes_python_version():
    names = [r.name for r in run_checks()]
    assert "Python version" in names


def test_run_checks_required_deps_present_in_test_env():
    results = run_checks()
    required = [r for r in results if r.name.startswith("dep:")]
    assert required
    # In our venv all required deps are installed.
    assert all(r.ok for r in required), [r for r in required if not r.ok]


def test_has_critical_failure_with_synthetic_failure():
    results = [CheckResult("synthetic", ok=False, severity=CRITICAL, message="x")]
    assert has_critical_failure(results)


def test_has_critical_failure_false_when_only_warnings():
    results = [CheckResult("synthetic", ok=False, severity="warn", message="x")]
    assert not has_critical_failure(results)
