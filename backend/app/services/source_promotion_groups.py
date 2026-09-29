"""Bind explicit source variant IDs to OWN identities, never names or GTIN guesses."""

from collections import defaultdict

from app.models.product import PromotionGroup


def attach_source_groups(products, identity_rows):
    """Only a verified subset with matching group contracts becomes executable.

    Other eligible source IDs may be absent. Their identities are not invented,
    and their prices are not copied to the known subset.
    """
    external = defaultdict(set)
    for row in identity_rows:
        product_id = row.get("product_id") or row.get("id")
        identity = row.get("external_product_id")
        if product_id and identity:
            scope = (
                str(product_id),
                str(row.get("store_id")),
                str(row.get("source_snapshot_id") or row.get("snapshot_id")),
            )
            external[scope].add(str(identity))
    groups = defaultdict(list)
    for p in products:
        prov = p.source_provenance
        for offer in p.offers:
            terms = offer.purchase_terms
            if not terms or not terms.mixing_allowed or terms.usage != "exact" or not prov:
                continue
            ids = external.get((p.product_id, p.store_id, prov.source_snapshot_id), set())
            if len(ids) != 1 or not ids <= set(terms.eligible_variant_ids):
                continue
            if (
                offer.required_packages < 2
                or offer.price_basis_unit != "package"
                or not offer.valid_from
                or not offer.valid_to
                or offer.deposit
                or terms.purchase_form != "fixed_package"
            ):
                continue
            key = (p.chain, p.store_id, prov.source_snapshot_id, terms.campaign_group_id)
            signature = (
                terms.model_dump_json(),
                offer.price,
                offer.required_packages,
                offer.valid_from,
                offer.valid_to,
                offer.membership_program,
                offer.max_quantity,
            )
            groups[key].append((p, offer, signature))
    attached = defaultdict(list)
    for (_, store_id, snapshot, group_id), rows in groups.items():
        if len({r[2] for r in rows}) != 1:
            continue  # Conflicting contracts remain independent offers, never cheapest-wins.
        p, offer, _ = rows[0]
        terms = offer.purchase_terms
        eligible = tuple(sorted({r[0].product_id for r in rows}))
        group = PromotionGroup(
            group_id=group_id,
            chain=p.chain,
            store_id=store_id,
            eligible_product_ids=eligible,
            required_packages=offer.required_packages,
            pricing_rule="fixed_total",
            amount=offer.price,
            valid_from=offer.valid_from,
            valid_to=offer.valid_to,
            membership_program=offer.membership_program,
            max_groups=offer.max_quantity,
            source=p.source_provenance.source_provider,
            source_snapshot_id=snapshot,
            limit_scope="household_campaign"
            if terms.limit_scope == "household_campaign" and offer.max_quantity
            else "store",
            limit_key=group_id
            if terms.limit_scope == "household_campaign" and offer.max_quantity
            else None,
        )
        for identity in eligible:
            attached[(store_id, identity)].append(group)
    return [
        p.model_copy(update={"promotion_groups": tuple(attached[(p.store_id, p.product_id)])})
        if (p.store_id, p.product_id) in attached
        else p
        for p in products
    ]


def groups_in_context(product, store_id):
    """Municipality adapters re-key the same physical store, not its prices."""
    return tuple(
        g.model_copy(update={"store_id": store_id})
        for g in product.promotion_groups
        if g.store_id == product.store_id
    )
