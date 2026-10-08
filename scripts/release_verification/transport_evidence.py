"""Strict classification of a deliberately exercised status-navigation abort."""


def classify_navigation_aborts(failures, traces, generation):
    expected = []
    for failure in failures:
        reference = failure.get("request_id")
        starts = [t for t in traces if t.get("reference") == reference and t["event"] == "start"]
        aborts = [
            t for t in traces if t.get("reference") == reference and t["event"] == "request-abort"
        ]
        assert reference and len(starts) == len(aborts) == 1, failure
        start, abort = starts[0], aborts[0]
        identity = (start["document_id"], start["generation"], start["request_id"])

        def same(event, identity=identity):
            return (
                event.get("document_id"),
                event.get("generation"),
                event.get("request_id"),
            ) == identity

        assert same(abort) and failure["method"] == "GET", failure
        assert abort["reason"] in {"beforeunload", "pagehide"}, failure
        assert start["job"] == failure["url"].rsplit("/", 1)[-1], failure
        assert any(
            same(t) and t["event"] == abort["reason"] and start["at"] <= t["at"] <= abort["at"]
            for t in traces
        ), failure
        assert any(
            t["event"] == "terminal"
            and t.get("status") == 201
            and t.get("job") == start["job"]
            and t.get("request_id") == start["request_id"]
            and t["document_id"] != start["document_id"]
            for t in traces
        ), failure
        assert generation and generation["reloaded_during_job"] and generation["job_count"] == 1, (
            failure
        )
        expected.append(
            {
                **failure,
                "classification": "explicit_navigation_abort_reconnected",
                "document_id": start["document_id"],
                "generation": start["generation"],
                "job": start["job"],
                "start_request_id": start["request_id"],
            }
        )
    return expected
