from pathlib import Path
p=Path('backend/app/services/product_search.py');s=p.read_text(encoding='utf-8').replace('PromotionMechanism.SINGLE','PromotionMechanism.SALE_PRICE');p.write_text(s,encoding='utf-8')
p=Path('backend/app/services/basket_calculator.py');s=p.read_text(encoding='utf-8').replace('''        if contracts and any(not i.ordinary_price_known for i in items):
            raise GroupPricingError("group discounts require independent ordinary price evidence")''','''        if any(g.pricing_rule != "fixed_total" and any(
            not i.ordinary_price_known for i in items
            if i.store_id == g.store_id and i.product_id in g.eligible_product_ids
        ) for g in contracts):
            raise GroupPricingError("group discounts require independent ordinary price evidence")''')
s=s.replace('Decimal(str(i.regular_unit_price or i.base_checkout_unit_price)) for i in items','Decimal(str(i.regular_unit_price or i.base_checkout_unit_price or 1)) for i in items')
s=s.replace('''            best = (sum(residual_rows(remaining), Decimal(0)), ())''','''            try:
                best = (sum(residual_rows(remaining), Decimal(0)), ())
            except ValueError:
                best = (Decimal('Infinity'), ())  # No separately evidenced residual purchase.''')
s=s.replace('''        remaining = list(counts)
        charges''','''        if not total.is_finite():
            raise GroupPricingError("Hela kampanjgrupper krävs; separat restpris saknas.")
        remaining = list(counts)
        charges''')
p.write_text(s,encoding='utf-8')
