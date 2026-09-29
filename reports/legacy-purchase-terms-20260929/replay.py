"""Identical retained inputs, no external calls; old and new code in separate processes."""
import json
import sys
import os
from collections import Counter
from pathlib import Path
from datetime import datetime

O=Path(__file__).resolve().parent
ROOT=Path('/srv/app') if Path('/srv/app/grocery_data').exists() else O.parents[1]
PRIOR=Path(os.getenv('REPLAY_PRIOR_RESULTS',str(ROOT/'reports/ica-hemkop-municipality-20260928/results')))
mode=sys.argv[1] if len(sys.argv)>1 else 'after'
sys.path.insert(0,str(O/'before' if mode=='before' else ROOT))
from grocery_data.app.domain import RawBatch, RawFetch, SourceStore
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.connectors.coop.parser import CoopParser
from grocery_data.app.connectors.hemkop.physical_offers import parse as hemkop_parse
from grocery_data.app.services.offer_rows import qualify_rows

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def inputs():
    folder=O/'inputs/ica-structured/1281/20260928T145357-0c7287ca'
    for row in read(folder/'coverage.json')['stores']:
        store=SourceStore.model_validate(row['store'])
        batch=RawBatch.model_validate_json((folder/f'offers-{store.external_id}-batch.json').read_bytes())
        yield 'ica',store,batch,IcaParser().parse_catalog
    folder=O/'inputs/coop-municipal/1281/attempts/20260928T110111-54abec7fc898/structured/sources'
    for f in sorted(folder.glob('*-store.json')):
        store=SourceStore.model_validate_json(f.read_bytes())
        batch=RawBatch.model_validate_json(f.with_name(f.name.replace('-store','-batch')).read_bytes())
        yield 'coop',store,batch,CoopParser().parse_catalog
    for code in ['1281','1280']:
        folder=PRIOR/f'hemkop-municipal/{code}'
        state=read(folder/'source-state.json')
        for row in state['inventory']['stores']:
            if row['geographic_evidence']['status']!='inside':continue
            store=SourceStore.model_validate(row['store'])
            store=store.model_copy(update={'source_fields':{**store.source_fields,'official_store_url':f'https://www.hemkop.se/butik/{store.external_id}',
                'offer_policy':'hemkop-physical-singleton-offers-v1'}})
            f=next(folder.rglob(f'{store.external_id}-offers.json'))
            batch=RawBatch.model_validate_json(f.read_bytes())
            yield 'hemkop',store,batch,hemkop_parse
    from grocery_data.app.connectors.coop.xtra_pdf import parse_pdf
    folder=O/'inputs/coop-municipal/1281/attempts/20260928T070313-cfce2f18c7f5/xtra-3658/1'
    meta=read(folder/'result.json')
    inventory=read(folder/'inventory.json')
    store=SourceStore.model_validate(next(r['store'] for r in inventory['stores'] if r['store']['external_id']==meta['store_id']))
    store=store.model_copy(update={'source_fields':{**store.source_fields,'offer_policy':'coop-xtra-pdf-text-v1',
        'pdf_sha256':meta['sha256'],'pdf_observed_at':meta['observed_at'],'pdf_pages':meta['document_pages']}})
    doc=RawFetch(chain='coop',store_external_id=store.external_id,kind='xtra_pdf',method='GET',url=meta['source_url'],
        fetched_at=datetime.fromisoformat(meta['observed_at']),http_status=200,content_type='application/pdf',
        payload=(folder/'source.pdf').read_bytes(),connector_version='retained-official-xtra-pdf-v1')
    assert doc.payload_hash==meta['sha256']
    yield 'xtra',store,RawBatch(chain='coop',documents=(doc,)),lambda raw,refs,s:parse_pdf(raw.documents[0],s,refs[0])[0]

def main():
    report=[]
    for chain,store,batch,parse in inputs():
        refs=[f'retained:{chain}:{store.external_id}:{d.payload_hash}' for d in batch.documents]
        parsed=parse(batch,refs,store)
        accepted,evidence=qualify_rows(parsed,store=store,observed_at=max(d.fetched_at for d in batch.documents))
        report.append({'chain':chain,'store':store.model_dump(mode='json'),'raw_hashes':[d.payload_hash for d in batch.documents],
            'source_rows':len(parsed.products)+len(parsed.failures),'products':[p.model_dump(mode='json') for p in accepted.products],
            'all_parsed':[p.model_dump(mode='json') for p in parsed.products], 'evidence':evidence})
        print(chain,store.external_id,'rows',len(parsed.products)+len(parsed.failures),'accepted',len(accepted.products),
            Counter(r for d in evidence['decisions'] for r in d['blockers']),flush=True)
    (O/f'{mode}-rows.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
