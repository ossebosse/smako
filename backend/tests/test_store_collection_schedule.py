import json
from datetime import datetime

import pytest
from app.services.store_collection_history import offer_collection_history


@pytest.mark.parametrize("chain", ["ica", "coop", "willys"])
def test_dashboard_projects_current_cadence_without_changing_source_history(tmp_path, monkeypatch, chain):
    monkeypatch.setenv("PRICE_COLLECTION_CADENCE", "mon_thu")
    monkeypatch.setenv("ICA_STRUCTURED_OFFERS_ROOT", str(tmp_path))
    monkeypatch.setenv("COOP_MUNICIPAL_OFFERS_ROOT", str(tmp_path))
    monkeypatch.setenv("WILLYS_FLYER_ROOT", str(tmp_path))
    row = {"store_id": "123", "selected": True, "status": "failed", "failed_attempts": 14,
           "last_success": "2026-10-25T23:32:17+00:00", "last_attempt": "2026-10-28T14:27:30+00:00",
           "next_fetch_at": "2026-10-28T20:27:30+00:00"}
    state = ({"coverage": {"area": {"municipality_code": "1281"}}, "store_schedule": {"123": row}}
             if chain == "ica" else {"municipality_code": "1281",
                 "selection": {"municipality_code": "1281", "stores": [row]}})
    directory = tmp_path / "1281"
    directory.mkdir()
    path = directory / ("structured-source.json" if chain == "ica" else "source-state.json")
    original = json.dumps(state).encode()
    path.write_bytes(original)
    result = offer_collection_history("Lund", str(tmp_path / "db.sqlite"),
                                      now=datetime.fromisoformat("2026-10-28T21:00:00+00:00"))[(chain, "123")]
    assert result["next_fetch_at"].isoformat() == "2026-10-29T02:17:00+00:00"
    assert result["last_success_at"].isoformat() == row["last_success"]
    assert result["failed_attempts"] == 14 and result["status"] == "failed"
    assert path.read_bytes() == original
