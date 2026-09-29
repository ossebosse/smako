import hashlib
import json
from datetime import UTC, datetime

def snapshot():
    from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
    current = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request('22350', {})
    rows = {}
    products = []
    for p in current.universe.products:
        products.append(p.model_dump(mode='json'))
        row = rows.setdefault(p.store_id, {'name':p.store_name,'chain':p.chain,'count':0,
            'channel':str(p.price_context_type),'active_offers':0,'expired_offers':0,'future_offers':0,'observations':set(),'snapshots':set(),'campaigns':set()})
        row['count'] += 1
        if p.source_provenance:
            row['observations'].add(str(p.source_provenance.source_observed_at))
            row['snapshots'].add(p.source_provenance.source_snapshot_id)
        for offer in p.offers:
            today=datetime.now(UTC).date()
            row['active_offers' if offer.is_active(today) else 'future_offers' if offer.valid_from and offer.valid_from>today else 'expired_offers'] += 1
            row['campaigns'].add((str(offer.valid_from),str(offer.valid_to)))
    for row in rows.values():
        for key in ['observations','snapshots','campaigns']:row[key] = sorted(row[key],key=str)
    return {'at':datetime.now(UTC).isoformat(),'universe_id':current.universe.universe_id,
        'products':len(products),'products_sha256':hashlib.sha256(json.dumps(products,sort_keys=True).encode()).hexdigest(),
        'stores':rows}
