"""Reuse official declarations by complete identity, never prices or store scope.

The whole active catalog is searched, not a campaign-specific product list.
An unknown-GTIN offer needs one unique supplier GTIN for its complete branded
name and fixed pack. Different variants or contradictory declarations veto
the join. Missing retained raw evidence is never replaced by a name guess.
"""
import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.services.product_declarations import identity_text


def identity(p):
    return [identity_text(p.name), identity_text(p.brand or ''), p.package_quantity,
            p.package_unit, p.gtin]


def eligible(p):
    prov = p.source_provenance
    return bool((not p.purchase_terms or p.purchase_terms.identity_scope == "product")
        and prov and prov.source_role == 'offers' and prov.source_snapshot_id
        and prov.retailer_id_namespace in {'willys:flyer-document-ad', 'lidl:public-product'}
        and p.brand and p.package_quantity and p.package_unit in {'g','ml'}
        and p.package_quantity == p.usable_quantity and p.package_unit == p.usable_unit
        and p.offers and all(o.campaign_evidence for o in p.offers))


def candidates(products, database):
    """Return full-identity candidate declarations, including their raw paths."""
    selected = [p for p in products if eligible(p)]
    packs = sorted({p.package_quantity for p in selected})
    if not packs or not Path(database).is_file():
        return {}
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute('''SELECT sp.*, r.payload_hash, r.payload_location, r.http_status,
            r.url AS declaration_url FROM source_products sp
            JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
            JOIN raw_snapshots r ON r.id=sp.raw_snapshot_id
            WHERE cs.is_active=1 AND cs.state='promoted' AND cs.coverage='full_online_catalog'
            AND sp.chain='coop' AND sp.gtin IS NOT NULL
            AND sp.package_quantity IN ('''+','.join('?' for _ in packs)+')',packs).fetchall()
    indexed = defaultdict(list)
    for r in rows:
        indexed[(identity_text(r['name']),identity_text(r['brand'] or ''),
                 float(r['package_quantity']),r['package_unit'])].append(r)
    result = {}
    for p in selected:
        matched = []
        for r in indexed[tuple(identity(p)[:4])]:
            if r['http_status'] != 200:
                continue
            try:
                gtin = normalize_gtin(r['gtin']).normalized_gtin
                observed = datetime.fromisoformat(r['fetched_at'])
                if observed.tzinfo is None:
                    from datetime import UTC
                    observed = observed.replace(tzinfo=UTC)
                if abs((observed-p.source_provenance.source_observed_at).total_seconds()) > 7*86400:
                    continue
                if p.gtin and normalize_gtin(p.gtin).normalized_gtin != gtin:
                    continue
            except (TypeError, ValueError):
                continue
            matched.append(dict(r))
        if matched and len({normalize_gtin(r['gtin']).normalized_gtin for r in matched}) == 1:
            result[(p.store_id,p.product_id)] = matched
    return result


def complete(products, database, raw_root):
    from app.services.personal_source_facts import project_raw_facts, raw_product

    raw_root = Path(raw_root).resolve()
    indexed = {(p.store_id,p.product_id):p for p in products}
    result = {}
    cache = {}
    for key, rows in candidates(products,database).items():
        p = indexed[key]
        facts = []
        for r in rows:
            path = (raw_root/r['payload_location']).resolve()
            if not path.is_relative_to(raw_root):
                continue
            try:
                if path not in cache:
                    body = path.read_bytes()
                    cache[path] = hashlib.sha256(body).hexdigest(), json.loads(body)
                digest, document = cache[path]
                if digest != r['payload_hash']:
                    continue
                raw = raw_product(document,r['raw_reference'])
                if str(raw.get('id') if r['chain']=='coop' else raw.get('code')) != r['external_product_id']:
                    continue
                units = {'Gram':(1,'g'),'Kilogram':(1000,'g'),
                         'Milliliter':(1,'ml'),'Liter':(1000,'ml')}
                factor, unit = units.get(raw.get('packageSizeUnit'), (None,None))
                if (not factor or unit != p.package_unit
                    or float(raw.get('packageSize') or 0)*factor != p.package_quantity
                    or identity_text(raw.get('name') or '') != identity_text(p.name)
                    or identity_text(raw.get('manufacturerName') or '') != identity_text(p.brand)
                    or p.gtin and normalize_gtin(p.gtin).normalized_gtin != normalize_gtin(r['gtin']).normalized_gtin
                    or normalize_gtin(raw.get('ean')).normalized_gtin != normalize_gtin(r['gtin']).normalized_gtin):
                    continue
                fact = project_raw_facts(raw,chain=r['chain'],product_id=p.product_id,
                    snapshot_id=p.source_provenance.source_snapshot_id,
                    source_reference=f"{r['declaration_url']}#{r['raw_reference']}:{digest}",
                    observed_at=r['fetched_at'])
                if fact.conflicts or not fact.nutrition or fact.nutrition_preparation != 'as_sold':
                    continue
                facts.append((r,fact))
            except (OSError, ValueError, KeyError, IndexError, TypeError):
                continue
        if not facts:
            continue
        # Require all available full declarations to agree, never pick cheapest/newest.
        if len({json.dumps([f.nutrition,f.nutrition_unit,f.ingredients],sort_keys=True) for _,f in facts}) != 1:
            continue
        r, fact = facts[0]
        evidence = {'target_identity':identity(p),'supplier_gtin':r['gtin'],
            'method':'unique_complete_brand_variant_fixed_pack_verified_raw_declaration',
            'donors':[{'chain':r['chain'],'snapshot':r['catalog_snapshot_id'],
                'product_id':r['external_product_id'],'raw_sha256':r['payload_hash'],
                'url':r['declaration_url'],'observed_at':r['fetched_at']} for r,_ in facts]}
        result[key] = replace(fact,source='verified_exact_catalog_declaration',
            retailer_product_id=p.source_provenance.retailer_product_id,
            field_sources={**fact.field_sources,'declaration_identity':(evidence,)})
    return result


def matches_product(p,fact):
    binding = fact.field_sources.get('declaration_identity',())
    return bool(eligible(p) and len(binding)==1 and binding[0].get('target_identity')==identity(p)
        and fact.source_product_id==p.product_id
        and fact.source_snapshot_id==p.source_provenance.source_snapshot_id)
