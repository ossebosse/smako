"""Coop's public physical-page response; no online catalogue or inferred GTIN.

externalId is an opaque product variant ID, even when it resembles an EAN.
The price belongs to the individual child record, never to a name match.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from grocery_data.app.domain import ParseFailure, ProductParseResult, SourceOffer, SourceProduct
from grocery_data.app.domain.purchase_terms import PurchaseTerms

POLICY = "coop-physical-structured-v1"
PARSER = "coop-parser-v5"
_ROW_KEYS = ("id", "externalId", "campaignStartDate", "campaignEndDate", "weekNumber",
             "storeLedgerAccountNumber", "channelCodes", "roleDescriptions", "eagId", "isPil",
             "ageRestriction", "simplifiedAgeRestriction")
_PRICE_KEYS = ("discountValue", "isMemberPrice", "isItemPriceDiscount", "minimumAmount",
               "unit", "dealType", "termStyle", "quantity", "isPercentageDiscount", "steps")
_STEP_KEYS = ("discountValue", "quantity", "unit", "comparisonPrice", "dealType")
_CONTENT_KEYS = ("title", "brand", "description", "amountInformation", "comparativePriceText",
                 "formattedComparativePriceText", "limitations", "dealOfferLimitText",
                 "recyclingInformationText", "weightVolume", "netContentUnit",
                 "onlineProductName", "parentTitle", "parentAmountInformation", "dealOfferRulesText")


def confirmed_empty_response(captures, store):
    """Only an exact, successful public all-offers response can prove zero."""
    if len(captures or []) != 1:
        return False
    evidence = captures[0]
    if not isinstance(evidence, dict):
        return False
    ledger = str(store.source_fields.get("ledger_account_number") or "")
    if (not ledger or evidence.get("http_status") != 200 or evidence.get("error")
            or evidence.get("store_external_id") != store.external_id
            or evidence.get("ledger_account_number") != ledger
            or evidence.get("source_url") != f"https://external.api.coop.se/dke/offers/sorting-groups/{ledger}"):
        return False
    data = evidence.get("data")
    groups = data.get("sortingGroups") if isinstance(data, dict) else None
    return (isinstance(groups, list) and all(isinstance(g, dict) for g in groups)
            and sum(g.get("id") == "alla" for g in groups) == 1
            and all(g.get("offers") == [] and type(g.get("offerAmount")) is int
                    and g["offerAmount"] == 0 for g in groups))


def sanitized_response(payload):
    def row(value):
        known_row = {*_ROW_KEYS, "priceInformation", "content", "clusterInteriorOffers",
                     "otherLogos", "unifiedSplash", "categoryGroup", "categoryTeam"}
        unknown = sorted([*('row.' + k for k in set(value) - known_row),
            *('priceInformation.' + k for k in set(value.get("priceInformation", {})) - set(_PRICE_KEYS)),
            *('content.' + k for k in set(value.get("content", {})) - {*_CONTENT_KEYS, "imageUrl", "enrichedComparisonPrice"})])
        if unknown:
            raise ValueError("new public offer fields require schema review: " + ", ".join(unknown))
        result = {k: value[k] for k in _ROW_KEYS if k in value}
        for key, allowed in (("priceInformation", _PRICE_KEYS), ("content", _CONTENT_KEYS)):
            result[key] = {k: value.get(key, {})[k] for k in allowed if k in value.get(key, {})}
        steps = result["priceInformation"].get("steps")
        if steps is not None and (not isinstance(steps, list) or any(
                not isinstance(step, dict) or set(step) - set(_STEP_KEYS) for step in steps)):
            raise ValueError("priceInformation.steps requires schema review")
        rules = result["content"].get("dealOfferRulesText")
        if rules is not None and not isinstance(rules, str):
            raise ValueError("content.dealOfferRulesText requires schema review")
        if "clusterInteriorOffers" in value:
            result["clusterInteriorOffers"] = [row(c) for c in value["clusterInteriorOffers"]]
        return result
    return {"sortingGroups": [{"id": g["id"], "offerAmount": g["offerAmount"],
                                "offers": [row(v) for v in g["offers"]]}
                               for g in payload["sortingGroups"]]}


async def capture_public_response(response, store, captures):
    url = urlsplit(response.url)
    ledger = str(store.source_fields.get("ledger_account_number") or "")
    if (url.scheme != "https" or url.hostname != "external.api.coop.se"
            or url.path != f"/dke/offers/sorting-groups/{ledger}" or not ledger):
        return
    evidence = {"source_url": f"https://{url.hostname}{url.path}",
                "store_external_id": store.external_id, "ledger_account_number": ledger,
                "http_status": response.status}
    try:
        if response.status != 200:
            raise ValueError("public structured response not HTTP 200")
        evidence["data"] = sanitized_response(await response.json())
    except (ValueError, KeyError, TypeError) as exc:
        evidence["error"] = "public_structured_schema_unrecognized"
        # Persist only our schema diagnostics, never arbitrary response text.
        if isinstance(exc, ValueError) and "schema review" in str(exc):
            evidence["schema_review_reason"] = str(exc)
    captures.append(evidence)


def _date(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    # This Sweden-only physical feed supplies local, zone-less midnight/end.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(ZoneInfo("Europe/Stockholm"))
    return parsed.date()


def parse_structured(envelope, *, store, document, reference):
    from .parser import _display_quantity
    evidence = envelope["structured_offers"]
    ledger = str(store.source_fields.get("ledger_account_number") or "")
    products, failures = [], []
    def fail(reason, ref=reference):
        failures.append(ParseFailure(raw_record_reference=ref, error_code="schema_changed",
                                     error_message=reason, parser_version=PARSER))
    if (not ledger or evidence.get("ledger_account_number") != ledger
            or evidence.get("store_external_id") != store.external_id
            or evidence.get("source_url") != f"https://external.api.coop.se/dke/offers/sorting-groups/{ledger}"
            or document.store_external_id != store.external_id
            or document.url != "https://www.coop.se" + store.source_fields.get("store_page_path", "")
            or envelope.get("store_external_id") != store.external_id
            or envelope.get("store_page_path") != store.source_fields.get("store_page_path")):
        fail("Coop shared structured store/source evidence mismatch")
        return ProductParseResult(failures=failures)
    if evidence.get("http_status") != 200:
        fail("Coop shared structured response not HTTP 200")
        return ProductParseResult(failures=failures)
    if evidence.get("error"):
        fail("Coop shared structured response rejected: " + str(evidence["error"])
             + ("; " + str(evidence["schema_review_reason"]) if evidence.get("schema_review_reason") else ""))
        return ProductParseResult(failures=failures)
    try:
        groups = evidence["data"]["sortingGroups"]
        all_groups = [g for g in groups if g["id"] == "alla"]
        if len(all_groups) != 1:
            raise ValueError("missing unique all-offers group")
        top = all_groups[0]["offers"]
        # The legacy DOM selector recognises monetary cards, not percentage
        # signs. Keep percentage campaigns in the FULL structured denominator.
        monetary_total = sum(r["priceInformation"].get("termStyle") != "Percentage Off" for r in top)
        if (all_groups[0]["offerAmount"] != len(top)
                or envelope["captured_total"] not in {len(top), monetary_total}):
            raise ValueError("source/DOM offer totals disagree")
        by_id = {r["id"]: r for r in top}
        if len(by_id) != len(top):
            raise ValueError("duplicate top-level campaign identity")
        for group in groups:
            if group["offerAmount"] != len(group["offers"]):
                raise ValueError("category total mismatch")
            if any(row != by_id.get(row["id"]) for row in group["offers"]):
                raise ValueError("conflicting category campaign")
        rows = []
        for parent in top:
            children = parent.get("clusterInteriorOffers") or []
            variants = children or [parent]
            ids = [v["externalId"] for v in variants]
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate variant in campaign group")
            rows.extend((parent, variant, len(variants)) for variant in variants)
        if any(str(v.get("storeLedgerAccountNumber")) != ledger
               or str(p.get("storeLedgerAccountNumber")) != ledger for p,v,n in rows):
            raise ValueError("variant belongs to different physical store")
    except (KeyError, TypeError, ValueError) as exc:
        fail("Coop shared structured schema: " + str(exc))
        return ProductParseResult(failures=failures)
    for parent, row, count in rows:
        ref = f"{reference}#offer={row['id']}"
        try:
            p, c = row["priceInformation"], row["content"]
            blockers = []
            if any(v.get(k) for v in (parent, row) for k in ("ageRestriction", "simplifiedAgeRestriction")):
                blockers.append("age_restriction_eligibility_unverified")
            parent_price = parent["priceInformation"]
            # These are real eligibility/price conditions, not decorative fields.
            # Keep the complete evidence but do not flatten tiers into one price.
            stepped = any(v.get("steps") is not None for v in (parent_price, p))
            if stepped:
                blockers.append("tiered_price_steps_requires_review")
            if any(v["content"].get("dealOfferRulesText") for v in (parent, row)):
                blockers.append("additional_purchase_rules_requires_review")
            def terms(price):
                return (price.get("discountValue"), price.get("isMemberPrice", False),
                        price.get("unit"), price.get("quantity", price.get("minimumAmount")),
                        price.get("termStyle"), price.get("isPercentageDiscount", False))
            if terms(p) != terms(parent_price):
                blockers.append("variant_price_conditions_conflict")
            if row.get("channelCodes") != parent.get("channelCodes") or "DR" not in row.get("channelCodes", []):
                blockers.append("physical_campaign_channel_unverified")
            if p.get("termStyle") not in {"Discount Price", "Regular Price", None} or p.get("dealType") not in {"styckpris", "pris"}:
                blockers.append("purchase_price_role_unverified")
            # Retain the newly observed flag, but do not guess its purchase meaning.
            if parent.get("isPil") or row.get("isPil"):
                blockers.append("source_is_pil_requires_review")
            # Older retained versions omit the flag. A true flag must never
            # turn a percentage into a monetary purchase price.
            if ("isPercentageDiscount" in p
                    and p["isPercentageDiscount"] != (p.get("termStyle") == "Percentage Off")):
                blockers.append("percentage_role_conflict")
            amount = None if stepped else Decimal(str(p["discountValue"]))
            quantity = None if stepped else p.get("quantity", p.get("minimumAmount"))
            if not stepped and (isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1):
                raise ValueError("invalid offer quantity")
            if not stepped and p.get("minimumAmount", quantity) != quantity:
                blockers.append("quantity_condition_conflict")
            member = p.get("isMemberPrice", False)
            if not isinstance(member, bool):
                blockers.append("audience_unverified")
            description = "; ".join(dict.fromkeys(filter(None, [
                str(parent["content"].get("description") or ""), str(c.get("description") or "")])) )
            def inherited_condition(field, parent_content, child_content, errors):
                parent_value, child_value = parent_content.get(field), child_content.get(field)
                if parent_value and child_value and parent_value != child_value:
                    errors.append("variant_shared_condition_conflict")
                return child_value or parent_value
            limit_text = str(inherited_condition("dealOfferLimitText", parent["content"], c, blockers) or "")
            rules_text = str(inherited_condition("dealOfferRulesText", parent["content"], c, blockers) or "")
            deposit_text = str(inherited_condition("recyclingInformationText", parent["content"], c, blockers) or "")
            if c.get("limitations") != ["0"] or parent["content"].get("limitations") != ["0"]:
                blockers.append("unrecognized_source_limitations")
            limit = re.fullmatch(r"Max (\d+) (st|köp)/hushåll\.", limit_text)
            if limit_text and not limit:
                blockers.append("purchase_limit_unrecognized")
            if quantity is not None and quantity > 1 and limit and limit[2] == "st":
                blockers.append("package_limit_on_multibuy_requires_review")
            if re.search(r"personlig|aktivera|kupong|vid köp|handla för|endast|måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag|helg|\d{1,2}/\d{1,2}", description, re.IGNORECASE):
                blockers.append("additional_eligibility_requires_review")
            if re.search(r"gäller ej ekologisk", description, re.IGNORECASE) and re.search(r"\beko\b|ekologisk", title if (title := c.get("onlineProductName")) else "", re.IGNORECASE):
                blockers.append("variant_excluded_by_campaign")
            if re.search(r"gäller ej laktosfri", description, re.IGNORECASE) and re.search(r"laktosfri", title or "", re.IGNORECASE):
                blockers.append("variant_excluded_by_campaign")
            if deposit_text:
                blockers.append("deposit_amount_unverified")
            pack_text = str(c.get("weightVolume") or "") + " " + str(c.get("netContentUnit") or "")
            pack, unit, approximate = _display_quantity(pack_text)
            # Existing normalizer accepts grams/ml, not an invented one-kg unit.
            if unit is None and c.get("netContentUnit") == "Kilogram":
                pack, unit, approximate = _display_quantity(str(c.get("weightVolume")) + " kg")
            title = c.get("onlineProductName") or c.get("title")
            if not title or not row.get("externalId"):
                blockers.append("exact_variant_unverified")
            approximate_text = str(c.get('amountInformation') or '')
            approx_match = re.fullmatch(r'\s*(?:ca\.?|cirka)\s*(\d+(?:[.,]\d+)?)\s*(g|kg)\.?\s*', approximate_text, re.IGNORECASE)
            approx_g = (Decimal(approx_match[1].replace(',', '.')) * (1000 if approx_match[2].lower()=='kg' else 1)) if approx_match else None
            variable = p.get('unit')=='kg' and approx_g is not None and quantity==1
            loose = (p.get('unit')=='kg' and not approximate_text.strip() and quantity==1 and not limit
                     and bool(re.search(r'\blösvikt\b', description, re.IGNORECASE)))
            if p.get('unit')=='kg' and not (variable or loose):
                blockers.append('weight_purchase_form_unproven')
            if not (variable or loose) and (p.get("unit") != "st" or pack is None or approximate):
                blockers.append("fixed_purchase_package_unverified")
            # Never multiply a per-kg campaign by a guessed average package.
            if not variable and re.search(r"\bca\b|cirka|ungefär", approximate_text, re.IGNORECASE):
                blockers.append("approximate_package")
            start, end = _date(row.get("campaignStartDate")), _date(row.get("campaignEndDate"))
            for field, expected in (("campaignStartDate", "00:00:00"), ("campaignEndDate", "23:59:59")):
                if row.get(field):
                    moment = datetime.fromisoformat(row[field])
                    if moment.tzinfo is not None:
                        moment = moment.astimezone(ZoneInfo("Europe/Stockholm"))
                    if moment.strftime("%H:%M:%S") != expected:
                        blockers.append("subday_campaign_time_requires_review")
            if start is None or end is None:
                blockers.append("campaign_dates_unverified")
            # Explicit shorter child dates survive; a child may not extend its parent.
            ps, pe = _date(parent.get("campaignStartDate")), _date(parent.get("campaignEndDate"))
            if (start and ps and start < ps) or (end and pe and end > pe):
                blockers.append("variant_campaign_outside_parent")
            contract = f"coop:physical:{store.external_id}:{parent['id']}:{start}:{end}"
            # Conservatively share household caps for the same source campaign
            # family and period. This shares ONLY a consumption limit, never
            # price, eligibility, identity or store applicability.
            if limit:
                if not parent.get("eagId"):
                    blockers.append("household_campaign_identity_unverified")
                else:
                    contract = f"coop:household:{parent['eagId']}:{start}:{end}"
            payload = {"policy": POLICY, "price_contract_id": contract,
                       "source_offer_id": row["id"], "source_product_id": row["externalId"],
                       "group_offer_id": parent["id"], "variant_count": count,
                       "source_url": evidence["source_url"], "source_sha256": document.payload_hash,
                       "observed_at": document.fetched_at.isoformat(), "price_role": "campaign_purchase",
                       "conditions": description, "purchase_limit_text": limit_text,
                       "purchase_rules_text": rules_text, "parent_price_steps": parent_price.get("steps"),
                       "deposit_text": deposit_text, "sale_unit": p.get("unit"),
                       "source_campaign_start": row.get("campaignStartDate"),
                       "source_campaign_end": row.get("campaignEndDate"),
                       "comparison_text": c.get("comparativePriceText"), "source_record": row}
            # Even source label Regular Price is bounded by THIS advertised
            # campaign. It proves neither an ordinary rest price nor later use.
            role_supported = not stepped and p.get("termStyle") in {"Discount Price", "Regular Price", None} and not p.get("isPercentageDiscount", False)
            if not role_supported:
                payload["price_role"] = "percent_discount" if p.get("termStyle") == "Percentage Off" or p.get("isPercentageDiscount") else "unknown"
            purchase_terms = None
            if not blockers:
                mixing = (count > 1 and quantity > 1 and p.get('unit')=='st'
                          and bool(re.search(r'välj och blanda|blanda fritt', description, re.IGNORECASE)))
                # Explicit children are the source's eligible variants. Only those
                # that individually pass every gate will bind to OWN identities.
                # A shared parent alone does not prove that different variants
                # can be combined into the same multibuy purchase.
                eligible = tuple(sorted(f"{v['id']}:{v['externalId']}" for v in parent.get('clusterInteriorOffers', []))) if mixing else ()
                purchase_terms = PurchaseTerms(
                    source_reference=f'{reference}#group={parent["id"]}' if mixing else ref,
                    purchase_form='variable_package' if variable else 'loose_weight' if loose else 'piece' if unit=='st' and pack==1 else 'fixed_package',
                    quantity_basis='source_approximation' if variable else 'requirement' if loose else 'source_exact',
                    approximate_package_g=float(approx_g) if variable else None,
                    complete_group_size=quantity or 1, mixing_allowed=mixing,
                    eligible_variant_ids=eligible, campaign_group_id=contract if mixing else None,
                    limit_scope='household_campaign' if limit else 'offer').model_dump(mode='json')
                payload.update(purchase_terms=purchase_terms, price_basis_unit='kg' if variable or loose else 'package')
            offer = SourceOffer(external_id=row["id"], type="other" if stepped else "percent_discount" if p.get("termStyle") == "Percentage Off" or p.get("isPercentageDiscount") else "multibuy" if quantity is not None and quantity > 1 else
                                "member_price" if member else "sale_price", price=amount if role_supported else None,
                                quantity=quantity if quantity is not None and quantity > 1 else None, member_only=member is True,
                                valid_from=start, valid_to=end,
                                max_quantity=int(limit[1]) if limit else None,
                                description="; ".join(filter(None, [c.get("parentTitle") or title,
                                                       description, rules_text, limit_text, deposit_text])),
                                source_payload=payload)
            identity = f"{row['id']}:{row['externalId']}"
            products.append(SourceProduct(chain="coop", store_external_id=store.external_id,
                external_product_id=identity, gtin=None, name=title, brand=c.get("brand"),
                package_text=pack_text.strip(), package_quantity=pack, package_unit=unit,
                sale_price=None, regular_price=None, member_price=None, sale_unit=p.get("unit"),
                offers=(offer,), raw_reference=ref, fetched_at=document.fetched_at, basket_type="VIKT" if loose else "ST",
                average_weight_kg=approx_g/1000 if variable else None,
                source_fields={"coop_physical_policy": POLICY, "verified_store_scope": True,
                    "regular_price_current_verified": False, "source_variant_id": row["externalId"],
                    **({'purchase_terms':purchase_terms, 'purchase_terms_reference':purchase_terms['source_reference']} if purchase_terms else {}),
                    "variant_count": 1, "group_variant_count": count,
                    "source_group_id": parent["id"], "source_url": evidence["source_url"],
                    "source_sha256": document.payload_hash, "purchase_blockers": blockers,
                    "conditions": description, "source_package_text": c.get("amountInformation"),
                    "price_context_verified": True}))
        except (ValueError, KeyError, TypeError) as exc:
            fail("Coop structured row requires review: " + str(exc), ref)
    return ProductParseResult(products=products, failures=failures)
