from pathlib import Path
p=Path('backend/app/models/basket.py');s=p.read_text().replace('    conditional_variant_choice: bool = False','    pending_group_checkout: bool = False\n    conditional_variant_choice: bool = False').replace('        if self.conditional_variant_choice:','        if self.pending_group_checkout or self.conditional_variant_choice:');p.write_text(s)
p=Path('backend/app/services/user_pricing.py');s=p.read_text();needle='    contracts = price_contracts_for_candidate(candidate)\n    target_date = on_date or current_pricing_date()';replacement='''    target_date = on_date or current_pricing_date()
    candidate = candidate.model_copy(update={"promotion_groups": tuple(
        g for g in candidate.promotion_groups
        if g.valid_from <= target_date <= g.valid_to
        and (g.membership_program is None or g.membership_program in context.memberships)
    )}) if candidate.promotion_groups else candidate
    contracts = price_contracts_for_candidate(candidate)''';assert needle in s;s=s.replace(needle,replacement);p.write_text(s)
p=Path('backend/app/services/basket_calculator.py');s=p.read_text();s=s.replace('    conditional_variant_choice: bool = False','    pending_group_checkout: bool = False\n    conditional_variant_choice: bool = False').replace('            conditional_variant_choice=self.conditional_variant_choice,','            conditional_variant_choice=self.conditional_variant_choice,\n            pending_group_checkout=self.pending_group_checkout,')
s=s.replace('                        "total_price": float(charged),','                        "pending_group_checkout": False,\n                        "total_price": float(charged),')
s=s.replace('        candidate: ProductCandidate,\n    ) -> BasketItemQuote:', '        candidate: ProductCandidate,\n        *, defer_group_checkout: bool = False,\n    ) -> BasketItemQuote:')
needle='        resolution = self.resolver.resolve(\n';pos=s.index(needle,s.index('    def quote_item('));s=s[:pos]+'''        if defer_group_checkout:
            if not checkout_candidate.promotion_groups or checkout_candidate.sale_model != SaleModel.FIXED_PACKAGE:
                raise ValueError('Deferred checkout requires a source-bound fixed-package campaign group')
            # Quantity only: the whole-basket group solver must authorize cost.
            # This request-local projection never changes the source offer.
            if quantity_candidate.purchase_terms:
                quantity_candidate = quantity_candidate.model_copy(update={
                    'purchase_terms': quantity_candidate.purchase_terms.model_copy(update={'complete_group_size':1})})
'''+s[pos:]
needle='''            total, unit_price, applied_offer, offer_description = _best_checkout_price(
                checkout_candidate, package_count
            )''';assert needle in s;s=s.replace(needle,'''            if defer_group_checkout:
                total, unit_price = resolution.total_price, resolution.unit_price
            else:
                total, unit_price, applied_offer, offer_description = _best_checkout_price(
                    checkout_candidate, package_count
                )''')
# Keep pending state until a complete allocation has been independently priced.
needle='            conditional_variant_choice=checkout_candidate.conditional_variant_choice,';assert needle in s;s=s.replace(needle,needle+'\n            pending_group_checkout=defer_group_checkout,');p.write_text(s)
p=Path('backend/app/services/basket_optimizer.py');s=p.read_text();needle='''                quotes = self._candidate_quotes(ingredient, [candidate])
                if not quotes:
                    continue
                quote = quotes[0]
                if candidate.promotion_groups or candidate.price is None:''';assert needle in s;s=s.replace(needle,'''                if groups and type(self.calculator) is BasketCalculator:
                    try:
                        quote = self.calculator.quote_item(ingredient, candidate, defer_group_checkout=True)
                    except ValueError:
                        continue
                    if not self.verification_policy.allows_quote(quote):
                        continue
                else:
                    quotes = self._candidate_quotes(ingredient, [candidate])
                    if not quotes:
                        continue
                    quote = quotes[0]
                if candidate.promotion_groups or candidate.price is None:''');p.write_text(s)
