from pathlib import Path
p=Path('grocery_data/source_cli.py');s=p.read_text(encoding='utf-8')
s=s.replace('        connector = WillysConnector(client=client, allowed_store_ids=APPROVED_WILLYS_CONTEXTS)','''        municipality = getattr(args, "municipality", None)
        area = GeographicArea(city="Lund")
        connector = WillysConnector(client=client, allowed_store_ids=APPROVED_WILLYS_CONTEXTS)
        if municipality:
            from grocery_data.app.domain.municipality import municipality_name
            area = GeographicArea(city=municipality_name(municipality), mode="municipality", municipality_code=municipality)
            connector = WillysConnector(client=client)
            discovery = await connector.fetch_stores(area)
            selected = connector.parse_stores(discovery, ["live:registry"] * len(discovery.documents), area)
            connector.allowed_store_ids = frozenset(s.external_id for s in selected)
            atomic_write_bytes(run / "municipality-inventory.json", json.dumps(connector.municipality_inventory, ensure_ascii=False).encode())
            if not selected:
                await connector.aclose()
                engine.dispose()
                raise SourceArtifactError("no verified municipal online contexts")''')
s=s.replace('connector, GeographicArea(city="Lund"), auto_promote=False','connector, area, auto_promote=False,\n                scope_key=area.area_key if municipality else None',1)
s=s.replace('factory, raw, result.snapshot_id, destination, original_request_count=count','factory, raw, result.snapshot_id, destination, original_request_count=count,\n                municipality_boundary=connector.municipality_boundary',1)
s=s.replace('    c.add_argument("--workspace", type=Path, required=True)','    c.add_argument("--workspace", type=Path, required=True)\n    c.add_argument("--municipality", help="Official municipality code; opt-in store-bound online catalogs")')
p.write_text(s,encoding='utf-8')
p=Path('grocery_data/app/services/source_artifact.py');s=p.read_text(encoding='utf-8').replace('manifest.source_scope.scope_key != area.area_key','manifest.source_scope.scope_key != area.area_key.casefold()');p.write_text(s,encoding='utf-8')
