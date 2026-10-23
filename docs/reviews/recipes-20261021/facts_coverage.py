import json
from collections import Counter
from pathlib import Path

for city in ("malmo","lund"):
    u=json.loads(Path(f".local/fixes-review-20261018/data/{city}/combined-prices.json").read_bytes())
    stores={s["store_id"]:(s["chain"],s["coverage"]) for s in u["stores"]}
    del u
    f=json.loads(Path(f".local/fixes-review-20261018/data/{city}/product-facts.json").read_bytes())
    tot=Counter(); withing=Counter(); withnut=Counter()
    for r in f["rows"]:
        k=stores.get(r["store_id"],("?","?"))
        tot[k]+=1
        if r["facts"].get("ingredients"): withing[k]+=1
        if r["facts"].get("nutrition"): withnut[k]+=1
    print("==",city)
    for k in sorted(tot, key=lambda k:-tot[k])[:10]:
        print(f"   {k[0]:10} {k[1]:20} fakta {tot[k]:6}  med ingredienser {withing[k]:6} ({withing[k]/tot[k]:.0%})  med näring {withnut[k]/tot[k]:.0%}")
