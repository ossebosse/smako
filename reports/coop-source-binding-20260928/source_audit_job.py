"""Revalidate actual new bytes with final image; never change observations/approvals."""
import json
from pathlib import Path
from collections import Counter
from job import configure, save
configure()
from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.domain import RawBatch, SourceStore, ProductParseResult
from grocery_data.app.services.offer_rows import qualify_rows

P=Path('/work');root=P/'coop-municipal/1281'
state=json.loads((root/'source-state.json').read_bytes())
attempt=sorted(root.glob('attempts/*/structured/coverage.json'))[-1].parent
coverage=json.loads((attempt/'coverage.json').read_bytes());rows=[]
for row in coverage['stores']:
    sid=row['store_id'];source=attempt/'sources'
    store=SourceStore.model_validate_json((source/(sid+'-store.json')).read_bytes())
    batch=RawBatch.model_validate_json((source/(sid+'-batch.json')).read_bytes())
    retained=ProductParseResult.model_validate_json((source/(sid+'-extracted.json')).read_bytes())
    ref=retained.products[0].raw_reference.split('#offer=')[0]
    parsed=CoopParser().parse_catalog(batch,[ref],store)
    assert parsed == retained, sid
    approved,evidence=qualify_rows(parsed,store=store,observed_at=batch.documents[0].fetched_at)
    assert evidence == row['qualification'], sid
    assert len(approved.products)==row['own'] and not evidence['shared_blockers']
    assert all(r['observed_at']==row['observed_at'] for r in state['approved'][sid])
    rows.append({'store_id':sid,'name':store.name,'parsed':len(parsed.products),
        'approved':len(approved.products),'quarantined':len(approved.failures),
        'source_url':json.loads(batch.documents[0].payload)['structured_offers']['source_url'],
        'observed_at':row['observed_at'],'document_hash':batch.documents[0].payload_hash,
        'identical_final_image_parse':True,'identical_independent_qualification':True,
        'periods':sorted({(str(p.offers[0].valid_from),str(p.offers[0].valid_to)) for p in approved.products}),
        'blockers':dict(Counter(b for d in evidence['decisions'] for b in d['blockers']))})
save('final-source-audit',{'kind':'replay of actual new collection with final image, unchanged observations',
    'attempt':str(attempt),'rows':rows,'total_approved':sum(r['approved'] for r in rows)})
print('final image exact parse/qualification equivalence',len(rows),'stores',sum(r['approved'] for r in rows),'approved')
