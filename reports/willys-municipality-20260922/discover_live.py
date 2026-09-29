import asyncio,json
from pathlib import Path
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.services.municipality_geometry import fetch_boundary
ROOT=Path(__file__).parent
def save(name,value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
    client=WillysClient(retry_policy=RetryPolicy(attempts=1))
    try:
        raw=await client.fetch_stores()
        save('registry.json',raw.model_dump(mode='json'))
        print('registry',len(raw.documents[0].json_payload()),flush=True)
    except Exception as e:
        save('registry-error.json',{'error':type(e).__name__,'detail':str(e)[:500]})
        print(type(e).__name__,str(e)[:250],flush=True)
    finally: await client.aclose()
    for code in ('1281','1280'):
        try:
            boundary=await fetch_boundary(code)
            save('boundary-'+code+'.json',boundary)
            print(code,'boundary validated',flush=True)
        except Exception as e: save('boundary-'+code+'-error.json',{'error':type(e).__name__,'detail':str(e)[:500]})
asyncio.run(main())
