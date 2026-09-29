from pathlib import Path
p=Path('grocery_data/app/services/source_artifact.py');s=p.read_text(encoding='utf-8')
s=s.replace('    source_scope: SourceScopeDescriptor\n','    source_scope: SourceScopeDescriptor\n    municipality_boundary: dict[str, Any] | None = None\n')
s=s.replace('def _willys_completion(documents: tuple[RawFetch, ...]) -> dict[str, CatalogCompletion]:','def _willys_completion(documents: tuple[RawFetch, ...], *, area=None, boundary=None, contexts=APPROVED_WILLYS_CONTEXTS) -> dict[str, CatalogCompletion]:')
s=s.replace('    allowed = APPROVED_WILLYS_CONTEXTS\n','    allowed = contexts\n',1)
start=s.index('    parser = WillysParser()\n',s.index('def _willys_completion'))
end=s.index('    chosen = ',start)
s=s[:start]+'''    stores = _source_stores(tuple(discovery), area or GeographicArea(city="Lund"), boundary)
'''+s[end:]
insert=s.index('def _willys_completion')
s=s[:insert]+'''def _source_stores(documents, area, boundary):
    raw = RawBatch(chain=Chain.WILLYS, documents=documents)
    refs = ["artifact:stores"] * len(documents)
    if area.mode == "municipality":
        from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
        from grocery_data.app.domain import SourceStore

        inventory = build_inventory(area, raw, refs, boundary)
        return [SourceStore.model_validate(row["store"]) for row in inventory["stores"]
                if row["collection_selected"]]
    if boundary is not None:
        raise SourceArtifactError("municipal evidence on legacy locality contract")
    return WillysParser().parse_stores(raw, refs, area)


def _verify_scope(manifest):
    area = manifest.source_scope.geographic_area
    if area.mode == "municipality":
        if (manifest.source_scope.scope_key != area.area_key or not manifest.municipality_boundary
                or manifest.source_policy_version != "willys-municipality-policy-v1"
                or not manifest.context_ids or tuple(sorted(set(manifest.context_ids))) != manifest.context_ids):
            raise SourceArtifactError("invalid municipal source contract")
    elif (manifest.source_scope.scope_key != "lund" or area.city.casefold() != "lund"
          or manifest.context_ids != APPROVED_WILLYS_CONTEXTS or manifest.municipality_boundary is not None
          or manifest.source_policy_version != "willys-source-policy-v1"):
        raise SourceArtifactError("unapproved legacy geographic source scope")


'''+s[insert:]
s=s.replace('            if manifest.context_ids != APPROVED_WILLYS_CONTEXTS:\n                raise SourceArtifactError("source context allowlist mismatch")','            _verify_scope(manifest)')
s=s.replace('            if manifest.source_policy_version != "willys-source-policy-v1":\n                raise SourceArtifactError("unsupported source policy version")\n','')
a=s.index('            if (\n                manifest.source_scope.scope_key != "lund"',s.index('def verify_source_artifact'));b=s.index('            policy = ',a);s=s[:a]+s[b:]
s=s.replace('policy.store_allowlist != APPROVED_WILLYS_CONTEXTS','policy.store_allowlist != manifest.context_ids')
s=s.replace('d.store_external_id not in (*APPROVED_WILLYS_CONTEXTS, None)','d.store_external_id not in (*manifest.context_ids, None)')
s=s.replace('    completion = _willys_completion(tuple(documents))','''    area = manifest.source_scope.geographic_area
    if area.mode == "municipality":
        chosen = _source_stores(tuple(d for d in documents if d.kind == "stores"), area, manifest.municipality_boundary)
        if {s.external_id for s in chosen} != set(manifest.context_ids):
            raise SourceArtifactError("municipal contexts differ from independently verified inventory")
    completion = _willys_completion(tuple(documents), area=area, boundary=manifest.municipality_boundary, contexts=manifest.context_ids)''')
a=s.index('    stores = parser.parse_stores(',s.index('def _verify_product_counts'));b=s.index('    processor = ',a)
s=s[:a]+'''    stores = _source_stores(discovery, manifest.source_scope.geographic_area, manifest.municipality_boundary)
'''+s[b:]
s=s.replace('if store.external_id not in APPROVED_WILLYS_CONTEXTS:','if store.external_id not in manifest.context_ids:')
s=s.replace('client=OfflineWillysClient(verified), allowed_store_ids=APPROVED_WILLYS_CONTEXTS','client=OfflineWillysClient(verified), allowed_store_ids=verified.manifest.context_ids,\n        municipality_boundary=verified.manifest.municipality_boundary')
s=s.replace('connector, GeographicArea(city="Lund"), auto_promote=False','connector, verified.manifest.source_scope.geographic_area, auto_promote=False,\n        scope_key=verified.manifest.source_scope.scope_key')
s=s.replace('    original_request_count: int | None = None,\n','    original_request_count: int | None = None,\n    municipality_boundary: dict | None = None,\n')
s=s.replace('    completion = _willys_completion(docs)','''    scope = SourceScopeDescriptor.model_validate(snapshot.metrics["source_scope"])
    contexts = tuple(sorted(s.external_id for s in _source_stores(tuple(d for d in docs if d.kind == "stores"), scope.geographic_area, municipality_boundary))) if municipality_boundary else APPROVED_WILLYS_CONTEXTS
    completion = _willys_completion(docs, area=scope.geographic_area, boundary=municipality_boundary, contexts=contexts)''')
s=s.replace('        context_ids=APPROVED_WILLYS_CONTEXTS,','        context_ids=contexts,\n        municipality_boundary=municipality_boundary,')
s=s.replace('        source_policy_version="willys-source-policy-v1",','        source_policy_version="willys-municipality-policy-v1" if municipality_boundary else "willys-source-policy-v1",')
p.write_text(s,encoding='utf-8')
