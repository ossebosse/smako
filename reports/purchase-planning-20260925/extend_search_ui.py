from pathlib import Path
p=Path('backend/app/services/product_search.py');s=p.read_text(encoding='utf-8');s=s.replace('''        resolution = resolve_effective_price(contracts, 1, user, on_date=target_date)
        public = resolve_effective_price(contracts, 1, UserPricingContext(), on_date=target_date)
        effective = float(resolution.displayed_unit_price)''','''        quantity = 1
        eligible = True
        try:
            resolution = resolve_effective_price(contracts, 1, user, on_date=target_date)
            applied = resolution.applied_promotion
            effective = float(resolution.checkout_total)
        except ValueError:
            active = [c for c in contracts if c.is_active(target_date) and c.price is not None
                      and c.mechanism in {PromotionMechanism.SINGLE, PromotionMechanism.MULTIBUY}]
            permitted = [c for c in active if user.allows(c)]
            if not active:
                raise
            # Display the complete quoted purchase, never an invented residual unit price.
            applied = min(permitted or active, key=lambda c: (c.required_packages, c.price, c.reference))
            eligible = bool(permitted)
            quantity = applied.required_packages
            effective = float(applied.price)
        try:
            public = resolve_effective_price(contracts, quantity, UserPricingContext(), on_date=target_date)
            public_price = float(public.checkout_total)
        except ValueError:
            public_price = None''')
s=s.replace('        applied = resolution.applied_promotion\n        source = product.source_provenance', '        source = product.source_provenance')
s=s.replace('"quoted_price": effective,','"quoted_price": effective,\n            "quoted_quantity": quantity,\n            "purchase_eligible": eligible,')
s=s.replace('"current_public_price": float(public.displayed_unit_price),','"current_public_price": public_price,')
s=s.replace('"effective_price": effective if fixed else None,','"effective_price": effective if fixed and quantity == 1 and eligible else None,')
s=s.replace('                effective * (1 if unit == "st" else 1000) / product.package_quantity, 2','                effective * (1 if unit == "st" else 1000) / (quantity * product.package_quantity), 2')
p.write_text(s,encoding='utf-8')
p=Path('backend/app/static/personal.js');s=p.read_text(encoding='utf-8')
s=s.replace('function extraDialog(product=null){const box=', 'function extraDialog(product=null,campaign=false){const box=')
s=s.replace('product?"Lägg till exakt vara":"Lägg till generisk vara"', 'campaign?"Villkorat kampanjval":product?"Lägg till exakt vara":"Lägg till generisk vara"')
s=s.replace('product?.package_quantity||1,{min:', '(campaign?1:product?.package_quantity||1),{min:',1)
s=s.replace('product?.package_unit||"g");const properties=', '(campaign?"st":product?.package_unit||"g"));if(campaign)unit.disabled=true;const properties=',1)
s=s.replace('kind:product?"exact":"generic"','kind:campaign?"campaign":product?"exact":"generic"',1)
s=s.replace('use_pantry:use.checked,food:', 'use_pantry:campaign?false:use.checked,food:',1)
s=s.replace('let interpreted=Boolean(product),original=query.value;', 'if(campaign){use.disabled=true;explanation.textContent="Välj en kampanjmärkt variant i butiken enligt erbjudandets undantag och villkor. Hela kampanjgrupper debiteras. Näring och allergener är inte godkända.";}let interpreted=Boolean(product),original=query.value;',1)
s=s.replace('row.kind==="exact"?"Exakt produkt låst":"Generisk vara"','row.kind==="campaign"?"Villkorat kampanjval":row.kind==="exact"?"Exakt produkt låst":"Generisk vara"')
s=s.replace('productActions(product){const box=el("div",null,"personal-actions");box.append(', '''productActions(product){const box=el("div",null,"personal-actions");const usages=product.prices.map(p=>p.purchase_usage);if(usages.every(u=>u==="blocked")){box.append(el("p","Varupriset är bevarat. Komplettera kritiska köp-/pantuppgifter före beräkning."));return box;}if(usages.includes("variant_selection_required")){box.append(button("Lägg till som villkorat kampanjval",async()=>extraDialog(product,true)));return box;}box.append(''',1)
s=s.replace('top.append(actions);if(saved.prices_changed', 'top.append(actions);if(plan.optimized_basket.stores.some(g=>g.items.some(i=>i.conditional_variant_choice)))top.append(el("p","Villkorad inköpsplan: välj kampanjmärkta varianter enligt radernas villkor. Inte ett verifierat slutkvitto."));if(saved.prices_changed',1)
p.write_text(s,encoding='utf-8')
