"""Compare completed independent planner tracks through the existing checkout.

No pricing, qualification or search engine lives here. Track callbacks use the
existing MenuOptimizer with their own local search state. Retained search prices
only order audit work; selection always uses the newly audited whole basket.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

from app.errors import IncompleteBasketError

POLICY = "smako-verified-reference-v1"
# Pilot 1024 exhausted the old seed before reaching any added generation.
# Full-pool-first work has fixed limits, independent of recipe count.
IMPROVEMENT_EVALUATIONS = 4096
IMPROVEMENT_PROPOSALS = 32768
IMPROVEMENT_SAFETY_SECONDS = 900


class SearchBudgetReached(RuntimeError):
    """Internal control flow; deliberately outside the search's ValueError catch."""


class VerifiedSearchIncomplete(IncompleteBasketError):
    code = "SEARCH_INCOMPLETE"
    stage = "week_search"


@dataclass(slots=True)
class SearchBudget:
    evaluations: int
    proposals: int
    seconds: float = 120
    evaluations_used: int = 0
    proposals_used: int = 0
    reason: str | None = None
    started: float = field(default_factory=monotonic)

    def __post_init__(self):
        if min(self.evaluations, self.proposals, self.seconds) <= 0:
            raise ValueError("Search limits must be positive")

    def _check(self):
        if monotonic() - self.started >= self.seconds:
            self.reason = "wall_time_safety_stop"
            raise SearchBudgetReached(self.reason)

    def evaluation(self):
        self._check()
        if self.evaluations_used >= self.evaluations:
            self.reason = "evaluations"
            raise SearchBudgetReached(self.reason)
        self.evaluations_used += 1

    def proposal(self):
        self._check()
        if self.proposals_used >= self.proposals:
            self.reason = "proposals"
            raise SearchBudgetReached(self.reason)
        self.proposals_used += 1


def verified_search(search, *, audit, accepts, rank, budget, previous=(), archive_limit=8):
    """Return a freshly audited winner, protecting reference and previous winner.

    ``emit`` observes completed results without feeding them into either track.
    The bounded archive protects the reference and previous verified winner.
    At most ``archive_limit`` full candidates survive; no product graphs are
    copied. The caller persists identities only AFTER this final checkout.
    """
    if archive_limit < 3:
        raise ValueError("Archive needs reference, previous and improvement slots")
    candidates = []
    report = {"policy": POLICY, "global_optimum_proven": False,
              "audit_rejected": 0, "constraint_rejected": 0, "tracks": [], "rejections": []}

    def emit(slots, result, *, protected=False, source="improvement"):
        candidate = (tuple(slots), result, protected, source)
        if any(row[0] == candidate[0] for row in candidates):
            return
        if protected and source == "reference":
            existing = next((i for i, row in enumerate(candidates) if row[3] == source), None)
            if existing is not None:
                if rank(slots, result) >= rank(*candidates[existing][:2]):
                    return
                candidates.pop(existing)
        candidates.append(candidate)
        if len(candidates) > archive_limit:
            evictable = [i for i, row in enumerate(candidates) if not row[2]]
            index = max(evictable, key=lambda i: rank(*candidates[i][:2]))
            candidates.pop(index)

    # Only the first earlier winner is pinned; additional predecessor results
    # may be evicted. Keep earlier insertion on exact rank ties.
    for index, (slots, result) in enumerate(previous):
        emit(slots, result, protected=index == 0, source="previous")
    for track in ("reference", "improvement"):
        row = {"track": track, "status": "completed"}
        report["tracks"].append(row)
        try:
            search(track, lambda slots, result, track=track: emit(
                slots, result, protected=track == "reference", source=track))
        except SearchBudgetReached:
            row["status"] = "incomplete"
            row["reason"] = budget.reason
        except (ValueError, IncompleteBasketError) as exc:
            row["status"] = "data_blocked" if getattr(exc, "code", None) == "DATA_BLOCKED" else "search_miss"
            row["code"] = getattr(exc, "code", None)
            row["stage"] = getattr(exc, "stage", None)
    # Re-evaluate every potential winner. An earlier search price must never
    # prevent a newly cheaper (or more expensive) checkout from competing.
    verified = []
    for slots, _old_result, _protected, source in candidates:
        if not accepts(slots):
            report["constraint_rejected"] += 1
            report["rejections"].append({"source": source, "stage": "weekly_distribution_or_variation"})
            continue
        try:
            result = audit(slots)
        except (ValueError, IncompleteBasketError) as exc:
            report["audit_rejected"] += 1
            report["rejections"].append({"source": source, "code": getattr(exc, "code", None),
                                         "stage": getattr(exc, "stage", "checkout_audit"), "reason": str(exc)})
            continue
        verified.append((slots, result, source))
    report["evaluations"] = budget.evaluations_used
    report["proposals"] = budget.proposals_used
    report["budget_stop"] = budget.reason
    if not verified:
        error = VerifiedSearchIncomplete("Sökning ofullständig: ingen slutkontrollerad meny finns.")
        error.search_report = report
        raise error
    winner = min(verified, key=lambda row: rank(*row[:2]))
    report["selected_track"] = winner[2]
    report["verified_candidates"] = len(verified)
    return winner[0], winner[1], report
