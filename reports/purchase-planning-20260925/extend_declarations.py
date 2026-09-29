from pathlib import Path
p=Path('grocery_data/app/services/product_declarations.py');s=p.read_text(encoding='utf-8');i=s.index('\n\ndef declarations():')
s=s[:i]+'''

def parse_arla(body, acquisition):
    """Official JSON-LD identity plus explicit labelled declaration; no campaign data."""
    if (urlparse(acquisition['url']).hostname != 'www.arla.se'
            or not urlparse(acquisition['url']).path.startswith('/produkter/')
            or acquisition.get('status') != 200 or not acquisition.get('observed_at')
            or hashlib.sha256(body).hexdigest() != acquisition['sha256']):
        raise ValueError('official_declaration_acquisition_unverified')
    soup=BeautifulSoup(body,'html.parser'); rows=[]
    for node in soup.select('script[type="application/ld+json"]'):
        value=json.loads(node.get_text());rows.extend(value if isinstance(value,list) else [value])
    rows=[r for r in rows if r.get('@type')=='Product']
    if len(rows)!=1:raise ValueError('declaration_product_identity_not_unique')
    row=rows[0]; gtin=normalize_gtin(row['gtin13']).normalized_gtin
    name=re.fullmatch(r'(.+?)\\s+(\\d+(?:[,.]\\d+)?)%\\s+ca\\s*(\\d+(?:[,.]\\d+)?)\\s*(kg|g)',row['name'])
    if not name:raise ValueError('declaration_explicit_fat_and_approximate_pack_required')
    quantity=float(name[3].replace(',','.'))*(1000 if name[4]=='kg' else 1)
    def labelled(label):
        headings=[h for h in soup.select('h3,h4') if h.get_text(' ',strip=True)==label]
        if len(headings)!=1:raise ValueError('declaration_label_not_unique:'+label)
        return headings[0].find_next_sibling('p').get_text(' ',strip=True)
    if labelled('Streckkod')!=gtin or labelled('Vikt/volym') != f'{quantity:g} g':
        raise ValueError('declaration_identity_conflict')
    macros={}; texts=[]
    for tr in soup.select('table.c-product-tab__nutrition-table tr'):
        key=tr.select_one('strong').get_text(' ',strip=True)
        if key not in {'Energi','Fett','Kolhydrat','Protein'}:continue
        spans=[x.get_text(' ',strip=True) for x in tr.select('span')]
        if len(spans)!=2 or spans[0]!='pr. 100 g':raise ValueError('declaration_basis_unverified')
        amount=re.fullmatch(r'(?:[0-9.,]+ kJ / )?([0-9.,]+) (kcal|gram)',spans[1])
        if not amount or (key=='Energi') != (amount[2]=='kcal'):raise ValueError('declaration_value_unverified')
        field={'Energi':'kcal','Fett':'fat_g','Kolhydrat':'carbs_g','Protein':'protein_g'}[key]
        if field in macros:raise ValueError('duplicate_macronutrient')
        macros[field]=float(amount[1].replace(',','.'));texts.append(tr.get_text(' ',strip=True))
    if len(macros)!=4 or not all(math.isfinite(v) and v>=0 for v in macros.values()):raise ValueError('incomplete_macronutrients')
    return {'gtin':gtin,'name':name[1],'brand':row['brand']['name'].replace('®','').strip(),
        'package_quantity':quantity,'package_unit':'g',
        'identity_qualifiers':{'fat_percent':float(name[2].replace(',','.')),'package_basis':'source_approximation'},
        'ingredients':labelled('Ingredienser'),'nutrition':macros,'basis_quantity':100,'basis_unit':'g',
        'preparation':'as_sold','description':row['description'],'nutrition_text':' '.join(texts),
        'source':dict(acquisition),'parser':'arla-jsonld-labelled-declaration-v1'}


def parse_declaration(body, acquisition):
    host=urlparse(acquisition['url']).hostname
    if host=='www.arla.se':return parse_arla(body,acquisition)
    return parse_garant(body,acquisition)
'''+s[i:]
s=s.replace('*, gtin=None, rows=None):','*, gtin=None, rows=None, identity_qualifiers=None):')
s=s.replace("and r['package_quantity'] == float(quantity) and r['package_unit'] == unit]", "and r['package_quantity'] == float(quantity) and r['package_unit'] == unit\n                  and (not r.get('identity_qualifiers') or r['identity_qualifiers'] == identity_qualifiers)]")
p.write_text(s,encoding='utf-8')
p=Path('grocery_data/scripts/import_product_declarations.py');s=p.read_text(encoding='utf-8').replace('import parse_garant','import parse_declaration').replace('row = parse_garant','row = parse_declaration');p.write_text(s,encoding='utf-8')
p=Path('backend/app/services/official_product_facts.py');s=p.read_text(encoding='utf-8').replace('import json','import json\nimport re',1)
s=s.replace('        row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit, gtin=p.gtin)', '''        qualifiers=None
        if p.purchase_terms and p.purchase_terms.purchase_form == 'variable_package':
            fat={float(v.replace(',','.')) for o in p.offers
                 for v in re.findall(r'Fetthalt:\\s*(\\d+(?:[,.]\\d+)?)\\s*%',o.description,re.IGNORECASE)}
            if len(fat)!=1 or p.purchase_terms.approximate_package_g != p.package_quantity:
                continue
            qualifiers={'fat_percent':fat.pop(),'package_basis':p.purchase_terms.quantity_basis}
        row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit, gtin=p.gtin,
            identity_qualifiers=qualifiers)''')
s=s.replace("'unique_exact_complete_brand_variant_fixed_pack',", "('unique_complete_brand_variant_fat_source_approximate_pack' if qualifiers else 'unique_exact_complete_brand_variant_fixed_pack'),\n                  'identity_qualifiers': qualifiers,")
p.write_text(s,encoding='utf-8')
