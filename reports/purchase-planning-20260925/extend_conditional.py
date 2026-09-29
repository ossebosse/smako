from pathlib import Path
root=Path('.')
def edit(path, old, new, count=-1):
 p=root/path;s=p.read_text(encoding='utf-8');assert old in s,(path,old[:70]);p.write_text(s.replace(old,new,count),encoding='utf-8')
edit('backend/app/models/product.py','    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)\n\n', '    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)\n    conditional_variant_choice: bool = Field(default=False, exclude_if=lambda v: not v)\n\n',1)
# Ensure inserted into semantics, not offer (inspect field later).
edit('backend/app/models/personal.py','Literal["generic", "exact"]','Literal["generic", "exact", "campaign"]')
edit('backend/app/models/personal.py','if self.kind == "exact" and not self.product_key:', 'if self.kind in {"exact", "campaign"} and not self.product_key:')
edit('backend/app/models/personal.py','        if self.kind == "generic" and self.product_key:', '        if self.kind == "campaign" and (self.unit != "st" or self.quantity != int(self.quantity) or self.use_pantry):\n            raise ValueError("Villkorat kampanjval kräver hela antal och får inte använda skafferi.")\n        if self.kind == "generic" and self.product_key:')
edit('backend/app/services/user_pricing.py','    planning_mode: str = "exact",\n) -> ProductCandidate:', '    planning_mode: str = "exact",\n    allow_campaign_choice: bool = False,\n) -> ProductCandidate:')
edit('backend/app/services/user_pricing.py',"    if terms and terms.usage in {'blocked', 'variant_selection_required'}:\n        raise ValueError('Purchase requires completion: ' + terms.usage)","""    if terms and terms.usage == 'variant_selection_required' and allow_campaign_choice:
        if terms.purchase_form not in {'piece', 'fixed_package'} or any(o.price_basis_unit != 'package' for o in candidate.offers):
            raise ValueError('Conditional campaign needs a verified count purchase')
        candidate = candidate.model_copy(update={
            'conditional_variant_choice': True, 'sale_model': SaleModel.SOLD_BY_PIECE,
            'package_quantity': 1, 'package_unit': 'st', 'usable_quantity': 1, 'usable_unit': 'st',
            'quantity_confidence': 'exact', 'estimated_piece_weight': None,
            'variable_weight': False, 'piece_price': candidate.effective_price,
            'semantic_confidence': 'high',
            'semantic_evidence': ['user-confirmed campaign sales unit; actual variant unresolved'],
        })
    elif terms and terms.usage in {'blocked', 'variant_selection_required'}:
        raise ValueError('Purchase requires completion: ' + terms.usage)""")
edit('backend/app/services/purchase_quantity_resolver.py',"if product.purchase_terms and product.purchase_terms.usage in {'blocked', 'variant_selection_required'}:","if product.purchase_terms and (product.purchase_terms.usage == 'blocked' or (product.purchase_terms.usage == 'variant_selection_required' and not product.conditional_variant_choice)):")
edit('backend/app/services/purchase_quantity_resolver.py','            pieces = _ceil(required_base[0])\n            purchased_usable', '            pieces = _ceil(required_base[0])\n            if product.purchase_terms:\n                multiple = product.purchase_terms.complete_group_size\n                pieces = _ceil(Decimal(pieces) / multiple) * multiple\n            purchased_usable')
edit('grocery_data/app/domain/counted_offer_checkout.py',"if terms and terms.purchase_form == 'piece' and terms.usage == 'exact':", "if terms and ((terms.purchase_form == 'piece' and terms.usage == 'exact') or getattr(item, 'conditional_variant_choice', False)):")
edit('backend/app/models/basket.py','    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)','    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)\n    conditional_variant_choice: bool = Field(default=False, exclude_if=lambda v: not v)')
edit('backend/app/models/basket.py','        if self.sale_model == SaleModel.UNKNOWN:', '        if self.conditional_variant_choice:\n            return BasketVerificationStatus.UNVERIFIED\n        if self.sale_model == SaleModel.UNKNOWN:',1)
edit('backend/app/services/basket_calculator.py','    purchase_terms: object = None','    purchase_terms: object = None\n    conditional_variant_choice: bool = False')
edit('backend/app/services/basket_calculator.py','            purchase_terms=self.purchase_terms,','            purchase_terms=self.purchase_terms,\n            conditional_variant_choice=self.conditional_variant_choice,')
edit('backend/app/services/basket_calculator.py',"if candidate.purchase_terms and candidate.purchase_terms.usage in {'blocked', 'variant_selection_required'}:","if candidate.purchase_terms and (candidate.purchase_terms.usage == 'blocked' or (candidate.purchase_terms.usage == 'variant_selection_required' and not candidate.conditional_variant_choice)):")
edit('backend/app/services/basket_calculator.py','        resolution_warning = resolution.warning','        resolution_warning = ("Villkorat kampanjval: välj en kampanjmärkt variant. Innehåll, allergener och näring är inte verifierade. " + "; ".join(checkout_candidate.purchase_terms.exclusions)) if checkout_candidate.conditional_variant_choice else resolution.warning')
edit('backend/app/services/basket_calculator.py','            purchase_terms=checkout_candidate.purchase_terms,','            purchase_terms=checkout_candidate.purchase_terms,\n            conditional_variant_choice=checkout_candidate.conditional_variant_choice,')
edit('backend/app/services/basket_auditor.py','            purchase_terms=item.purchase_terms,','            purchase_terms=item.purchase_terms,\n            conditional_variant_choice=item.conditional_variant_choice,')
edit('backend/app/services/basket_optimizer.py','        if quote.quantity_confidence == QuantityConfidence.ESTIMATED:', '        if quote.conditional_variant_choice:\n            return BasketVerificationStatus.UNVERIFIED\n        if quote.quantity_confidence == QuantityConfidence.ESTIMATED:',1)
edit('backend/app/services/personal_planner.py','        food=True,\n    ):','        food=True,\n        campaign_choice=False,\n    ):',1)
edit('backend/app/services/personal_planner.py','            organic_animals,\n            food,','            organic_animals,\n            food,\n            campaign_choice,',1)
edit('backend/app/services/personal_planner.py','            if product.store_id not in self.store_ids or product.usable_unit != unit:\n                continue', '''            if product.store_id not in self.store_ids:
                continue
            weight_terms = product.purchase_terms and product.purchase_terms.usage == 'estimated'
            if product.usable_unit != unit and not (weight_terms and unit == 'g') and not (campaign_choice and unit == 'st'):
                continue
            if campaign_choice and (not product.purchase_terms or product.purchase_terms.usage != 'variant_selection_required'):
                continue
            if campaign_choice and (profile.allergies or profile.exclusions or organic_animals):
                conflicts.append(PolicyConflict('Kampanjens öppna varianter kan inte styrka allergi-, uteslutnings- eller ekokrav.', code='DATA_BLOCKED'))
                continue''',1)
edit('backend/app/services/personal_planner.py','planning_mode=self.request.purchase_planning_mode)','planning_mode=self.request.purchase_planning_mode, allow_campaign_choice=campaign_choice)',1)
edit('backend/app/services/personal_planner.py','                    "product_key": extra.product_key,','                    "product_key": extra.product_key,\n                    "campaign_choice": extra.kind == "campaign",',1)
edit('backend/app/services/personal_planner.py','                food=row["food"],','                food=row["food"],\n                campaign_choice=row.get("campaign_choice", False),',1)
edit('backend/app/services/personal_store.py','                          quantity = item.purchased_usable_quantity','                          quantity = item.purchased_usable_quantity') if False else None
edit('backend/app/services/personal_store.py','                        quantity = item.purchased_usable_quantity', '''                        if item.conditional_variant_choice:
                            raise PersonalConflict('Välj den faktiskt köpta produktvarianten före bokföring i skafferiet.')
                        quantity = item.purchased_usable_quantity''',1)
