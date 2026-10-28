"""Read-only municipal dashboard over existing audit, snapshots and runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from app.services.store_collection_history import offer_collection_history
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.campaign_validity import STOCKHOLM, is_campaign_only
from grocery_data.app.services.freshness import FreshnessPolicy, assess_freshness
from grocery_data.app.services.price_context_audit import PriceContextAuditor
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    PhysicalStoreModel,
    PriceObservationModel,
    StoreContextLinkModel,
    StoreModel,
)

MUNICIPALITIES = ("Lund", "Malmö")


def _describe_context(context):
    reasons = []
    collection = context["collection"]
    if collection["status"] == "failed":
        attempts = collection.get("failed_attempts")
        reasons.append(f"{attempts} misslyckade insamlingsförsök i följd." if attempts
                       else "Senaste insamlingen misslyckades.")
    if not context["runtime_active"]:
        reasons.append("Prisunderlaget är inte aktivt i Smako.")
    if not context["available_prices"]:
        reasons.append("Inga tillgängliga priser i detta underlag.")
    if not context["campaign_only"] and context["freshness"] in {"aging", "stale"}:
        reasons.append("Underlaget har passerat varningsgränsen för ålder." if
                       context["freshness"] == "aging" else "Underlaget har passerat åldersgränsen för användning.")
    price_status = ("campaign" if context["campaign_valid"] else
                    "expired" if context["campaign_only"] and not context["available_prices"] else
                    context["freshness"] if context["available_prices"] or context["freshness"] == "stale"
                    else "missing")
    context.update(
        price_status=price_status,
        status="failed" if collection["status"] == "failed" else price_status,
        attention_reasons=reasons,
        needs_attention=bool(reasons),
    )


def _describe_store(row):
    contexts = row["contexts"]
    priority = {"failed": 0, "stale": 1, "expired": 2, "missing": 3,
                "broken": 3, "aging": 4, "campaign": 5, "fresh": 6}
    row["status"] = min((c["status"] for c in contexts),
                        key=lambda s: priority.get(s, 3), default="missing")
    row["attention_reasons"] = list(dict.fromkeys(
        reason for c in contexts for reason in c["attention_reasons"]
    )) if contexts else ["Ingen verifierad priskälla är kopplad till butiken."]
    row["needs_attention"] = not contexts or any(c["needs_attention"] for c in contexts)


def _latest_collection(session: Session, snapshot_id: str | None) -> dict[str, Any]:
    snapshot = session.get(CatalogSnapshotModel, snapshot_id) if snapshot_id else None
    if snapshot is None:
        return {"status": "unknown"}
    # Scope AND chain: a Malmö failure must never mark a Lund store broken.
    run = session.scalar(
        select(CollectorRunModel)
        .where(
            CollectorRunModel.chain == snapshot.chain,
            CollectorRunModel.scope["scope_key"].as_string() == snapshot.scope_key,
        )
        .order_by(CollectorRunModel.started_at.desc(), CollectorRunModel.id.desc())
        .limit(1)
    )
    if run is None:
        return {"status": "unknown"}
    status = (
        "succeeded"
        if run.successful is True
        else "failed"
        if run.successful is False
        else "running"
        if run.finished_at is None
        else "unknown"
    )
    return {
        "status": status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_seconds": (
            max(0, (run.finished_at - run.started_at).total_seconds()) if run.finished_at else None
        ),
        # Do not expose free-form error_summary/metrics/transport data.
        "error": "Insamlingen misslyckades" if status == "failed" else None,
        "retained_snapshot": status == "failed" and snapshot.is_active,
    }


def municipal_store_status(
    session: Session,
    settings: Settings,
    city: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    city = next((name for name in MUNICIPALITIES if name.casefold() == city.casefold()), "")
    if not city:
        raise ValueError("unsupported municipality")
    now = now or datetime.now(UTC)
    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    audit = PriceContextAuditor(session, max_price_age_hours=policy.stale_age_hours).audit(
        city,
        now=now,
    )
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active(f"city:{city.casefold()}")
    runtime = {store.store_id: store for store in prepared.stores} if prepared else {}
    usable_contexts = set()
    runtime_observations = {}
    if prepared:
        usable, _, _ = prepared._context_partition(now=now, stale_age_hours=policy.stale_age_hours)
        usable_contexts = set(usable)
        runtime_observations = dict(prepared._context_oldest_observed_at)
    links = {
        (link.physical_store_id, link.grocery_context_id): link
        for link in session.scalars(
            select(StoreContextLinkModel).where(
                StoreContextLinkModel.is_active.is_(True),
            )
        )
    }
    context_cache: dict[tuple, dict[str, Any]] = {}
    offer_history = offer_collection_history(city, session.get_bind().url.database)
    local_stores = {
        (s.chain, s.external_id): s.id
        for s in session.scalars(select(StoreModel).where(StoreModel.is_active.is_(True)))
    }

    def context_status(context_id, name, source, scope, snapshot_id, observed_at, local_id):
        active_store = runtime.get(context_id)
        if active_store and active_store.source_provenance:
            provenance = active_store.source_provenance
            snapshot_id = provenance.source_snapshot_id
            source = provenance.source_provider
            if source == "own":
                local_id = local_stores.get(
                    (
                        active_store.chain,
                        provenance.provider_store_id or active_store.source_store_id,
                    )
                )
        key = (context_id, snapshot_id, local_id)
        if key in context_cache:
            return context_cache[key]
        products = prepared.universe.products_for_context(context_id) if active_store else ()
        # Use the deployed runtime policy, including verified campaign validity.
        if active_store:
            observed_at = runtime_observations.get(context_id)
            if observed_at == datetime.min.replace(tzinfo=UTC):
                observed_at = None
        freshness = assess_freshness(observed_at, now=now, policy=policy)
        snapshot = session.get(CatalogSnapshotModel, snapshot_id) if snapshot_id else None
        collected = None
        if local_id and snapshot and snapshot.is_active and snapshot.state == "promoted":
            collected = session.scalar(
                select(func.count())
                .select_from(PriceObservationModel)
                .where(
                    PriceObservationModel.catalog_snapshot_id == snapshot_id,
                    PriceObservationModel.store_id == local_id,
                    or_(
                        PriceObservationModel.sale_price > 0,
                        PriceObservationModel.regular_price > 0,
                    ),
                )
            )
        collection = _latest_collection(session, snapshot_id)
        if (
            active_store and active_store.source_provenance
            and active_store.source_provenance.source_provider == "own"
            and active_store.price_context_type == "physical_store"
            and products and all(p.coverage == "offers_only" for p in products)
        ):
            # Never apply a physical offer result to the chain's online catalog.
            history = offer_history.get((active_store.chain, active_store.physical_store_external_id))
            collection = dict(history) if history else {"status": "unknown"}
            collection["retained_snapshot"] = collection["status"] == "failed" and bool(products)
        on_date = now.astimezone(STOCKHOLM).date()
        available = (
            sum(
                not is_campaign_only(p) or any(o.is_active(on_date) for o in p.offers)
                for p in products
            )
            if context_id in usable_contexts
            else 0
        )
        campaigns = [p for p in products if is_campaign_only(p)]
        campaign_only = bool(products) and len(campaigns) == len(products)
        available_campaigns = [p for p in campaigns if context_id in usable_contexts
                               and any(o.is_active(on_date) for o in p.offers)]
        campaign_ends = [o.valid_to for p in available_campaigns for o in p.offers
                         if o.is_active(on_date) and o.valid_to]
        campaign_valid = campaign_only and available > 0
        result = {
            "context_id": context_id,
            "name": name or context_id,
            "source": source,
            "scope": (active_store.price_semantics or active_store.price_context_type or scope)
            if active_store
            else scope,
            "snapshot_id": snapshot_id,
            "observed_at": observed_at,
            "freshness": freshness.state.value if observed_at else "missing",
            "age_hours": freshness.age_hours,
            "collected_prices": collected,
            "retained_prices": len(products),
            "available_prices": available,
            "runtime_active": active_store is not None,
            "campaign_valid": campaign_valid,
            "campaign_only": campaign_only,
            "available_campaign_prices": len(available_campaigns),
            "available_base_prices": available - len(available_campaigns),
            "next_campaign_end": min(campaign_ends) if campaign_ends else None,
            "collection": collection,
        }
        _describe_context(result)
        context_cache[key] = result
        return result

    stores = []
    linked_runtime_ids = set()
    for chain in audit.chains.values():
        for store in chain.stores:
            contexts = []
            for context in store.contexts:
                if not context.active:
                    continue
                link = links.get((store.physical_store_id, context.grocery_context_id))
                contexts.append(
                    context_status(
                        context.grocery_context_id,
                        context.context_name,
                        context.source_provider,
                        context.price_context_type or context.relation_type,
                        context.snapshot_id,
                        context.observed_at,
                        link.local_store_id if link else None,
                    )
                )
                linked_runtime_ids.add(context.grocery_context_id)
            # Regional evidence can be selected by the audit without a physical link.
            if store.grocery_context_id and not any(
                c["context_id"] == store.grocery_context_id for c in contexts
            ):
                contexts.append(
                    context_status(
                        store.grocery_context_id,
                        store.context_name,
                        store.price_source,
                        store.context_scope,
                        store.snapshot_id,
                        store.observed_at,
                        None,
                    )
                )
                linked_runtime_ids.add(store.grocery_context_id)
            stores.append(
                {
                    "id": store.physical_store_id,
                    "name": store.name,
                    "chain": store.chain.value,
                    "address": store.address,
                    "state": store.state.value,
                    "contexts": contexts,
                }
            )
    # Current artifacts use canonical context IDs; the legacy registry may still
    # contain older OWN/Primat IDs. Reconcile only explicit chain + physical ID,
    # including verified aliases. No name/address guessing and no persisted edits.
    identities = {}
    for physical in session.scalars(
        select(PhysicalStoreModel).where(
            PhysicalStoreModel.is_active.is_(True),
        )
    ):
        for identity in {physical.external_store_id, *(physical.external_store_aliases or [])}:
            if identity:
                identities.setdefault((physical.chain, identity), []).append(physical)
    by_id = {row["id"]: row for row in stores}
    current_rows = set()
    for context_id, store in runtime.items():
        external_id = store.physical_store_external_id
        if not external_id or store.price_context_type == "online_fulfillment":
            continue
        matches = identities.get((store.chain, external_id), [])
        physical = matches[0] if len(matches) == 1 else None
        identity = physical.id if physical else f"runtime:{store.chain}:{external_id}"
        if identity not in by_id:
            by_id[identity] = {
                "id": identity,
                "name": physical.name if physical else store.name,
                "chain": store.chain,
                "address": physical.address if physical else store.address,
                "state": "runtime_verified_physical_identity",
                "contexts": [],
            }
        row = by_id[identity]
        if identity not in current_rows:
            # Current published sources replace superseded legacy context IDs.
            row["contexts"] = []
            current_rows.add(identity)
        row["contexts"].append(
            context_status(
                context_id,
                store.name,
                None,
                store.price_context_type,
                None,
                None,
                None,
            )
        )
    stores = sorted(by_id.values(), key=lambda row: (row["chain"], row["name"], row["id"]))
    for row in stores:
        _describe_store(row)
    linked_runtime_ids = {c["context_id"] for row in stores for c in row["contexts"]}
    other_contexts = []
    for context_id, store in runtime.items():
        if context_id in linked_runtime_ids:
            continue
        other_contexts.append(
            context_status(
                context_id,
                store.name,
                store.source_provenance.source_provider if store.source_provenance else None,
                store.price_context_type,
                None,
                None,
                None,
            )
        )
    # Shared online/regional contexts are counted once, never once per physical site.
    unique = {row["context_id"]: row for store in stores for row in store["contexts"]}
    unique.update({row["context_id"]: row for row in other_contexts})
    return {
        "city": city,
        "municipalities": MUNICIPALITIES,
        "checked_at": now,
        "runtime_active": prepared is not None,
        "warning_age_hours": policy.warning_age_hours,
        "stale_age_hours": policy.stale_age_hours,
        "summary": {
            "physical_stores": len(stores),
            "stores_with_prices": sum(
                any(c["available_prices"] for c in s["contexts"]) for s in stores
            ),
            "requiring_attention": sum(s["needs_attention"] for s in stores),
            "available_prices": sum(c["available_prices"] for c in unique.values()),
        },
        "stores": stores,
        "other_contexts": other_contexts,
        "live_provider_requests": 0,
    }
