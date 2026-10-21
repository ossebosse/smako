import pytest


@pytest.fixture
def verified_smako_member(monkeypatch):
    """Planner algorithm tests retain their five-dinner numerical baselines.

    This supplies the trusted authentication boundary only. Real registration,
    cookies, revocation and guest admission are exercised in test_smako_membership.
    Ownership/isolation tests deliberately do not use this fixture.
    """
    from app.api import account

    monkeypatch.setattr(account, "verified_owner", lambda _request: "e" * 64)
