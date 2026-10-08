"""Exact lifecycle evidence is required; error text never grants an exception."""

from copy import deepcopy

import pytest
from transport_evidence import classify_navigation_aborts


def fixture():
    common = {"document_id": "old", "generation": 1, "request_id": "intent", "job": "job"}
    traces = [
        dict(common, event="start", reference="get", at=1),
        dict(common, event="pagehide", at=2),
        dict(common, event="request-abort", reference="get", reason="pagehide", at=3),
        dict(common, event="terminal", document_id="new", status=201, at=4),
    ]
    failure = {"request_id": "get", "method": "GET", "url": "http://local/jobs/job", "error": "any"}
    return failure, traces, {"reloaded_during_job": True, "job_count": 1}


def test_correlated_navigation():
    failure, traces, generation = fixture()
    assert len(classify_navigation_aborts([failure], traces, generation)) == 1


@pytest.mark.parametrize(
    "fault", ["reference", "method", "job", "navigation", "abort", "document", "jobs", "intent"]
)
def test_uncorrelated_failure_stays_failure(fault):
    failure, traces, generation = deepcopy(fixture())
    if fault == "reference":
        failure["request_id"] = "other"
    if fault == "method":
        failure["method"] = "POST"
    if fault == "job":
        failure["url"] += "other"
    if fault == "navigation":
        traces[1]["event"] = "visibilitychange"
    if fault == "abort":
        traces[2]["reason"] = "timeout"
    if fault == "document":
        traces[3]["document_id"] = "old"
    if fault == "jobs":
        generation["job_count"] = 2
    if fault == "intent":
        generation["reloaded_during_job"] = False
    with pytest.raises(AssertionError):
        classify_navigation_aborts([failure], traces, generation)
