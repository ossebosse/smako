from pathlib import Path
p=Path('backend/tests/test_price_universe.py');s=p.read_text().replace('def test_retained_public_catalog_price_equal_to_member_price_does_not_stop_build():','def test_retained_public_catalog_price_equal_to_member_price_does_not_stop_build(monkeypatch):').replace("    key = _key(product.source_provenance.source_snapshot_id, memberships={'willys':False})",'''    # Replay the retained campaign on its original observation day. The wall
    # clock advancing must neither age this regression out nor refresh data.
    from app.models import product as product_module
    observed = product.source_provenance.source_observed_at
    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return observed.astimezone(tz) if tz else observed.replace(tzinfo=None)
    monkeypatch.setattr(product_module, 'datetime', ReplayClock)
    key = _key(product.source_provenance.source_snapshot_id, memberships={'willys':False})''');p.write_text(s)
