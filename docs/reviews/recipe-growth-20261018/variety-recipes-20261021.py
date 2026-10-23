import json
import sys


def I(name, form, q, role="vegetable", label=None): return {"name": name, "form": form, "quantity": q, "role": role, "label": label or name}
def R(base, name, mt, cuisine, family, primary, method, side, flavor, equipment, comps, steps, servings=None, level=None):
    r = {"base_id": f"smako-{base}", "name": name, "servings": servings or (2 if mt == "dinner" else 1), "meal_type": mt,
         "cuisine": cuisine, "family": family, "primary": primary, "method": method, "side": side, "flavor": flavor,
         "equipment": equipment, "components": [{"id": c, "name": n, "ingredients": ing} for c, n, ing in comps],
         "steps": [{"text": t, "uses": u, "minutes": m, **({"after": a} if a else {}), **({"passive": True} if p else {})}
                   for t, u, m, a, p in steps]}
    if level: r["level"] = level
    return r
S = lambda t, u, m, a=None, p=False: (t, u, m, a, p)
olja = lambda q=15: I("rapsolja", "as_sold", q, "cooking"); salt = lambda q=2: I("salt", "as_sold", q, "flavour")
L = []
# ---- Fisk (6) ----
L.append(R("thai-salmon-coconut-curry", "Laxcurry med kokos, ingefära och broccoli, med ris", "dinner", "thai", "curry", "lax", "pot", "ris",
  ["kokos", "ingefära", "citron"], ["Kastrull", "Gryta"],
  [("c1", "Curry", [I("lax", "raw_edible", 250, "primary", "Laxfilé, rå"), I("kokosmjölk", "as_sold", 250, "sauce"), I("broccoli", "raw_edible", 200),
    I("ingefära", "raw_edible", 10, "flavour"), I("vitlök", "raw_edible", 6, "flavour"), I("gul lök", "raw_edible", 80), I("gurkmeja", "dry", 1, "flavour"),
    I("sojasås", "as_sold", 15, "flavour"), I("citronjuice", "as_sold", 10, "flavour"), I("tomatpuré", "as_sold", 15, "sauce"), olja(10), salt(1)]),
   ("c2", "Ris", [I("ris", "dry", 140, "side")])],
  [S("Koka riset i 280 ml vatten under lock cirka 15 minuter.", ["ris"], 18, None, True),
   S("Hacka lök, vitlök och ingefära. Dela broccolin i buketter och laxen i bitar.", ["gul lök", "vitlök", "ingefära", "broccoli", "lax"], 8),
   S("Fräs lök, vitlök, ingefära, gurkmeja och tomatpuré i oljan 3 minuter. Tillsätt kokosmjölk och broccoli och sjud 5 minuter.", ["gul lök", "vitlök", "ingefära", "gurkmeja", "tomatpuré", "rapsolja", "kokosmjölk", "broccoli"], 8, [2]),
   S("Lägg i laxen och sjud 5 minuter tills den når minst 63 °C. Smaka av med sojasås, citronjuice och salt. Servera med riset.", ["lax", "sojasås", "citronjuice", "salt", "ris"], 6, [1, 3])]))
L.append(R("swedish-baked-salmon-dill-potatoes", "Ugnsbakad lax med citron, dillpotatis och gurksallad", "dinner", "swedish", "ugnsfisk", "lax", "oven", "potatis",
  ["citron", "dill", "senap"], ["Ugn", "Ugnsform", "Kastrull", "Skål"],
  [("c1", "Lax", [I("lax", "raw_edible", 280, "primary", "Laxfilé, rå"), I("citronjuice", "as_sold", 15, "flavour"), olja(10), salt(2), I("svartpeppar", "dry", 0.5, "flavour")]),
   ("c2", "Dillpotatis", [I("potatis", "raw_edible", 450, "side"), I("dill", "raw_edible", 8, "flavour")]),
   ("c3", "Gurksallad och sås", [I("gurka", "raw_edible", 150), I("rödlök", "raw_edible", 30), I("yoghurt naturell", "as_sold", 100, "sauce"),
    I("senap", "as_sold", 10, "flavour"), I("persilja", "raw_edible", 6, "flavour"), I("strösocker", "dry", 3, "flavour")])],
  [S("Sätt ugnen på 200 °C. Koka potatisen i saltat vatten cirka 20 minuter.", ["potatis"], 22, None, True),
   S("Lägg laxen i en smord form, ringla över citronjuice, salt och peppar. Baka cirka 15 minuter tills den når minst 63 °C.", ["lax", "citronjuice", "rapsolja", "salt", "svartpeppar"], 17, None, True),
   S("Skiva gurka och rödlök tunt och blanda med socker. Rör ihop yoghurt, senap och hackad persilja.", ["gurka", "rödlök", "strösocker", "yoghurt naturell", "senap", "persilja"], 6),
   S("Vänd potatisen med hackad dill och servera med laxen, gurksalladen och såsen.", ["potatis", "dill", "lax"], 2, [1, 2, 3])]))
L.append(R("greek-cod-tomato-couscous", "Torsk i tomat- och paprikasås med oregano och couscous", "dinner", "greek", "fiskgryta", "fisk", "pan", "couscous",
  ["tomat", "oregano", "citron"], ["Stekpanna med lock", "Kastrull"],
  [("c1", "Fisk i sås", [I("fisk", "raw_edible", 300, "primary", "Torskfilé, rå"), I("krossade tomater", "as_sold", 400, "sauce"), I("paprika", "raw_edible", 150),
    I("gul lök", "raw_edible", 80), I("vitlök", "raw_edible", 6, "flavour"), I("oregano", "dry", 1, "flavour"), I("citronjuice", "as_sold", 10, "flavour"),
    I("persilja", "raw_edible", 8, "flavour"), olja(15), salt(2)]),
   ("c2", "Couscous", [I("couscous", "dry", 140, "side"), I("fetaost", "as_sold", 60, "flavour")])],
  [S("Hacka lök och vitlök och skär paprikan i strimlor.", ["gul lök", "vitlök", "paprika"], 6),
   S("Fräs lök, vitlök och paprika i oljan 5 minuter. Tillsätt krossade tomater, oregano och salt och sjud 8 minuter.", ["gul lök", "vitlök", "paprika", "rapsolja", "krossade tomater", "oregano", "salt"], 13, [1]),
   S("Lägg fisken i såsen och sjud under lock 8 minuter tills den når minst 63 °C. Smaka av med citronjuice och persilja.", ["fisk", "citronjuice", "persilja"], 9, [2]),
   S("Häll 200 ml kokande vatten över couscousen, låt svälla 5 minuter och toppa med smulad fetaost.", ["couscous", "fetaost"], 6)]))
L.append(R("indian-fish-spinach-chickpea-curry", "Fiskcurry med spenat och kikärtor, med ris", "dinner", "indian", "curry", "fisk", "pot", "ris",
  ["spiskummin", "ingefära", "tomat"], ["Gryta", "Kastrull"],
  [("c1", "Curry", [I("fisk", "raw_edible", 250, "primary", "Torskfilé, rå"), I("kikärtor", "cooked_drained", 200, "primary"), I("spenat", "as_sold", 150),
    I("krossade tomater", "as_sold", 300, "sauce"), I("gul lök", "raw_edible", 80), I("vitlök", "raw_edible", 6, "flavour"), I("ingefära", "raw_edible", 10, "flavour"),
    I("spiskummin", "dry", 1, "flavour"), I("gurkmeja", "dry", 1, "flavour"), I("malen koriander", "dry", 1, "flavour"), olja(15), salt(2)]),
   ("c2", "Ris", [I("ris", "dry", 140, "side")])],
  [S("Koka riset i 280 ml vatten under lock cirka 15 minuter.", ["ris"], 18, None, True),
   S("Hacka lök, vitlök och ingefära. Skär fisken i bitar.", ["gul lök", "vitlök", "ingefära", "fisk"], 6),
   S("Fräs lök, vitlök, ingefära, spiskummin, gurkmeja och koriander i oljan 3 minuter. Tillsätt tomater, kikärtor och spenat och sjud 8 minuter.", ["gul lök", "vitlök", "ingefära", "spiskummin", "gurkmeja", "malen koriander", "rapsolja", "krossade tomater", "kikärtor", "spenat"], 11, [2]),
   S("Lägg i fisken, salta och sjud 6 minuter tills den når minst 63 °C. Servera med riset.", ["fisk", "salt", "ris"], 6, [1, 3])]))
L.append(R("mexican-fish-tacos-slaw", "Fisktacos med kålsallad, tomat och yoghurtsås", "dinner", "mexican", "tacos", "fisk", "pan", "tortilla",
  ["spiskummin", "citron", "paprika"], ["Stekpanna", "Skål"],
  [("c1", "Fisk", [I("fisk", "raw_edible", 300, "primary", "Torskfilé, rå"), I("spiskummin", "dry", 1, "flavour"), I("paprikapulver", "dry", 2, "flavour"), olja(15), salt(1)]),
   ("c2", "Kålsallad", [I("vitkål", "raw_edible", 200), I("morot", "raw_edible", 80), I("citronjuice", "as_sold", 15, "flavour"), I("tomat", "raw_edible", 150)]),
   ("c3", "Servering", [I("tortillas", "as_sold", 160, "side"), I("yoghurt naturell", "as_sold", 100, "sauce"), I("vitlök", "raw_edible", 3, "flavour"), I("ost", "as_sold", 40, "flavour")])],
  [S("Strimla kålen, riv moroten och blanda med citronjuice. Tärna tomaten.", ["vitkål", "morot", "citronjuice", "tomat"], 8),
   S("Rör ihop yoghurt och riven vitlök.", ["yoghurt naturell", "vitlök"], 2),
   S("Krydda fisken med spiskummin, paprikapulver och salt och stek i oljan 3–4 minuter per sida tills den når minst 63 °C. Dela i bitar.", ["fisk", "spiskummin", "paprikapulver", "salt", "rapsolja"], 9),
   S("Värm tortillorna och fyll med fisk, kålsallad, tomat, ost och yoghurtsås.", ["tortillas", "fisk", "vitkål", "tomat", "ost", "yoghurt naturell"], 4, [1, 2, 3])]))
L.append(R("thai-soy-glazed-salmon-noodles", "Sojaglaserad lax med nudlar, broccoli och sesam", "dinner", "thai", "nudlar", "lax", "pan", "nudlar",
  ["soja", "ingefära", "sesam"], ["Stekpanna", "Kastrull"],
  [("c1", "Lax", [I("lax", "raw_edible", 250, "primary", "Laxfilé, rå"), I("sojasås", "as_sold", 30, "flavour"), I("strösocker", "dry", 6, "flavour"),
    I("ingefära", "raw_edible", 10, "flavour"), I("vitlök", "raw_edible", 6, "flavour"), olja(10)]),
   ("c2", "Nudlar och grönt", [I("nudlar", "dry", 150, "side"), I("broccoli", "raw_edible", 200), I("morot", "raw_edible", 100), I("vitkål", "raw_edible", 120),
    I("sesamfrön", "as_sold", 8, "flavour"), I("citronjuice", "as_sold", 10, "flavour")])],
  [S("Rör ihop sojasås, socker, riven ingefära och vitlök.", ["sojasås", "strösocker", "ingefära", "vitlök"], 4),
   S("Koka nudlarna enligt förpackningen, de sista 3 minuterna med broccolin.", ["nudlar", "broccoli"], 8),
   S("Stek laxen i oljan 3 minuter per sida, häll över glasyren och låt den koka in tills laxen når minst 63 °C.", ["lax", "rapsolja", "sojasås"], 9, [1]),
   S("Strimla kål och morot och vänd med nudlar, broccoli och citronjuice. Toppa laxen med rostade sesamfrön.", ["vitkål", "morot", "nudlar", "broccoli", "citronjuice", "sesamfrön", "lax"], 5, [2, 3])]))
# ---- Frukost (5) ----
L.append(R("swedish-breakfast-scrambled-eggs-spinach", "Äggröra med spenat, tomat och rostat bröd", "breakfast", "swedish", "äggröra", "ägg", "pan", "bröd",
  ["ägg", "tomat"], ["Stekpanna"],
  [("c1", "Äggröra", [I("ägg", "raw_edible", 100, "primary", "Ägg"), I("mjölk", "as_sold", 30, "sauce"), I("spenat", "as_sold", 40), I("rapsolja", "as_sold", 5, "cooking"), salt(0.5)]),
   ("c2", "Servering", [I("bröd", "as_sold", 50, "side"), I("tomat", "raw_edible", 80)])],
  [S("Vispa ägg, mjölk och salt.", ["ägg", "mjölk", "salt"], 2),
   S("Fräs spenaten i oljan, häll i äggen och rör på låg värme tills äggen precis stelnat.", ["spenat", "rapsolja", "ägg"], 5, [1]),
   S("Rosta brödet, skiva tomaten och servera med röran.", ["bröd", "tomat"], 3)], level="simple"))
L.append(R("swedish-breakfast-mushroom-omelette", "Omelett med champinjoner, ost och persilja", "breakfast", "swedish", "omelett", "ägg", "pan", "bröd",
  ["svamp", "ost"], ["Stekpanna"],
  [("c1", "Omelett", [I("ägg", "raw_edible", 100, "primary", "Ägg"), I("champinjoner", "raw_edible", 80), I("ost", "as_sold", 25, "flavour"), I("persilja", "raw_edible", 3, "flavour"),
    I("rapsolja", "as_sold", 5, "cooking"), salt(0.5)]), ("c2", "Bröd", [I("bröd", "as_sold", 40, "side")])],
  [S("Skiva champinjonerna och stek dem i oljan 4 minuter.", ["champinjoner", "rapsolja"], 5),
   S("Vispa ägg och salt, häll över svampen och låt stelna på låg värme. Strö över ost och persilja och vik omeletten.", ["ägg", "salt", "ost", "persilja"], 5, [1]),
   S("Servera med brödet.", ["bröd"], 1, [2])], level="simple"))
L.append(R("greek-breakfast-shakshuka", "Shakshuka med ägg, paprika och bröd", "breakfast", "greek", "shakshuka", "ägg", "pan", "bröd",
  ["tomat", "spiskummin", "paprika"], ["Liten stekpanna med lock"],
  [("c1", "Shakshuka", [I("ägg", "raw_edible", 100, "primary", "Ägg"), I("krossade tomater", "as_sold", 200, "sauce"), I("paprika", "raw_edible", 80), I("gul lök", "raw_edible", 40),
    I("vitlök", "raw_edible", 3, "flavour"), I("spiskummin", "dry", 0.5, "flavour"), I("paprikapulver", "dry", 1, "flavour"), I("rapsolja", "as_sold", 5, "cooking"), salt(0.5)]),
   ("c2", "Servering", [I("fetaost", "as_sold", 25, "flavour"), I("bröd", "as_sold", 50, "side")])],
  [S("Hacka lök, vitlök och paprika och fräs i oljan med spiskummin och paprikapulver 5 minuter.", ["gul lök", "vitlök", "paprika", "rapsolja", "spiskummin", "paprikapulver"], 6),
   S("Tillsätt tomaterna och salt och sjud 5 minuter. Gör gropar och knäck i äggen. Sjud under lock tills vitorna stelnat.", ["krossade tomater", "salt", "ägg"], 10, [1]),
   S("Smula över fetaost och servera med brödet.", ["fetaost", "bröd"], 1, [2])]))
L.append(R("swedish-breakfast-apple-cinnamon-porridge", "Havregrynsgröt med äpple, kanel och jordnötter", "breakfast", "swedish", "gröt", "havregryn", "pot", "mjölk",
  ["kanel", "äpple"], ["Kastrull"],
  [("c1", "Gröt", [I("havregryn", "dry", 50, "primary"), I("mjölk", "as_sold", 150, "side"), I("äpple", "raw_edible", 100), I("kanel", "dry", 1, "flavour"), salt(0.3)]),
   ("c2", "Topping", [I("jordnötter", "as_sold", 10, "flavour"), I("strösocker", "dry", 3, "flavour")])],
  [S("Koka havregryn i 150 ml vatten med salt 3 minuter under omrörning.", ["havregryn", "salt"], 5),
   S("Riv äpplet och rör ner det med kanel. Servera med mjölk, hackade jordnötter och socker.", ["äpple", "kanel", "mjölk", "jordnötter", "strösocker"], 3, [1])], level="simple"))
L.append(R("mexican-breakfast-egg-bean-wrap", "Frukostwrap med ägg, kidneybönor och ost", "breakfast", "mexican", "wrap", "ägg", "pan", "tortilla",
  ["spiskummin", "tomat"], ["Stekpanna"],
  [("c1", "Fyllning", [I("ägg", "raw_edible", 100, "primary", "Ägg"), I("kidneybönor", "cooked_drained", 80, "primary"), I("spiskummin", "dry", 0.5, "flavour"),
    I("rapsolja", "as_sold", 5, "cooking"), salt(0.5)]), ("c2", "Wrap", [I("tortillas", "as_sold", 70, "side"), I("ost", "as_sold", 25, "flavour"), I("tomat", "raw_edible", 60)])],
  [S("Värm bönorna i oljan med spiskummin och mosa lätt.", ["kidneybönor", "rapsolja", "spiskummin"], 3),
   S("Vispa ägg och salt och rör ihop med bönorna tills äggen stelnat.", ["ägg", "salt"], 4, [1]),
   S("Fyll tortillan med äggröran, ost och tärnad tomat och rulla ihop.", ["tortillas", "ost", "tomat", "ägg"], 2, [2])], level="simple"))
# ---- Mellanmål (3) ----
L.append(R("swedish-snack-yoghurt-apple", "Yoghurt med äpple, kanel och rostad havre", "snack", "swedish", "yoghurt", "yoghurt", "pan", "ingen",
  ["kanel", "äpple"], ["Liten stekpanna", "Skål"],
  [("c1", "Skål", [I("yoghurt naturell", "as_sold", 150, "primary"), I("äpple", "raw_edible", 100), I("kanel", "dry", 0.5, "flavour"), I("havregryn", "dry", 20, "side"), I("jordnötter", "as_sold", 10, "flavour")])],
  [S("Rosta havregryn och hackade jordnötter i torr panna 3 minuter.", ["havregryn", "jordnötter"], 4),
   S("Tärna äpplet och servera på yoghurten med kanel och den rostade havren.", ["äpple", "yoghurt naturell", "kanel"], 3, [1])], level="simple"))
L.append(R("greek-snack-veg-sticks-yoghurt-dip", "Morots- och gurkstavar med vitlöksyoghurt och sesam", "snack", "greek", "dipp", "yoghurt", "cold_assembly", "grönsaker",
  ["vitlök", "citron"], ["Skål"],
  [("c1", "Dipp", [I("yoghurt naturell", "as_sold", 100, "primary"), I("vitlök", "raw_edible", 2, "flavour"), I("citronjuice", "as_sold", 5, "flavour"), I("sesamfrön", "as_sold", 5, "flavour"), salt(0.3)]),
   ("c2", "Stavar", [I("morot", "raw_edible", 80), I("gurka", "raw_edible", 80)])],
  [S("Rör ihop yoghurt, riven vitlök, citronjuice och salt och strö över sesamfrön.", ["yoghurt naturell", "vitlök", "citronjuice", "salt", "sesamfrön"], 3),
   S("Skär morot och gurka i stavar och servera med dippen.", ["morot", "gurka"], 4)], level="simple"))
L.append(R("greek-snack-tomato-feta-toast", "Rostat bröd med tomat, fetaost och oregano", "snack", "greek", "smörgås", "fetaost", "pan", "bröd",
  ["tomat", "oregano"], ["Stekpanna eller brödrost"],
  [("c1", "Smörgås", [I("bröd", "as_sold", 50, "side"), I("tomat", "raw_edible", 80), I("fetaost", "as_sold", 30, "primary"), I("oregano", "dry", 0.3, "flavour"),
    I("rapsolja", "as_sold", 5, "cooking"), I("svartpeppar", "dry", 0.2, "flavour")])],
  [S("Rosta brödet. Skiva tomaten.", ["bröd", "tomat"], 3),
   S("Lägg tomat och smulad fetaost på brödet, ringla över olja och strö över oregano och peppar.", ["tomat", "fetaost", "rapsolja", "oregano", "svartpeppar", "bröd"], 2, [1])], level="simple"))
# ---- Vegetariska middagar i fler kök (6) ----
L.append(R("italian-zucchini-mushroom-pasta", "Pasta med zucchini, champinjoner, bönor, citron och ost", "dinner", "italian", "pasta", "pasta", "pan", "pasta",
  ["citron", "vitlök", "ost"], ["Kastrull", "Stekpanna"],
  [("c1", "Pasta", [I("pasta", "dry", 180, "side"), I("zucchini", "raw_edible", 200), I("champinjoner", "raw_edible", 200), I("gul lök", "raw_edible", 60),
    I("vitlök", "raw_edible", 6, "flavour"), I("citronjuice", "as_sold", 15, "flavour"), I("crème fraiche", "as_sold", 100, "sauce"), I("ost", "as_sold", 40, "flavour"),
    I("persilja", "raw_edible", 8, "flavour"), I("bönor", "cooked_drained", 200, "primary"), olja(15), salt(2), I("svartpeppar", "dry", 0.5, "flavour")])],
  [S("Koka pastan enligt förpackningen.", ["pasta"], 12, None, True),
   S("Skiva svamp och zucchini och hacka lök och vitlök. Stek i oljan tills de fått färg.", ["champinjoner", "zucchini", "gul lök", "vitlök", "rapsolja"], 10),
   S("Tillsätt bönor, crème fraiche och citronjuice och värm. Smaka av med salt och peppar.", ["bönor", "crème fraiche", "citronjuice", "salt", "svartpeppar"], 4, [2]),
   S("Vänd ner pastan och toppa med riven ost och persilja.", ["pasta", "ost", "persilja"], 2, [1, 3])]))
L.append(R("indian-sweet-potato-lentil-curry", "Sötpotatis- och linscurry med spenat och yoghurt", "dinner", "indian", "curry", "linser", "pot", "ris",
  ["spiskummin", "ingefära", "kokos"], ["Gryta", "Kastrull"],
  [("c1", "Curry", [I("sötpotatis", "raw_edible", 300), I("linser", "dry", 100, "primary"), I("kokosmjölk", "as_sold", 200, "sauce"), I("spenat", "as_sold", 100),
    I("gul lök", "raw_edible", 80), I("vitlök", "raw_edible", 6, "flavour"), I("ingefära", "raw_edible", 10, "flavour"), I("spiskummin", "dry", 1, "flavour"),
    I("gurkmeja", "dry", 1, "flavour"), I("krossade tomater", "as_sold", 200, "sauce"), olja(15), salt(2)]),
   ("c2", "Servering", [I("ris", "dry", 120, "side"), I("yoghurt naturell", "as_sold", 80, "sauce")])],
  [S("Koka riset i 240 ml vatten under lock cirka 15 minuter.", ["ris"], 18, None, True),
   S("Hacka lök, vitlök och ingefära och tärna sötpotatisen.", ["gul lök", "vitlök", "ingefära", "sötpotatis"], 8),
   S("Fräs lök, vitlök, ingefära, spiskummin och gurkmeja i oljan. Tillsätt sötpotatis, linser, tomater, kokosmjölk, salt och 300 ml vatten och sjud 20 minuter.", ["gul lök", "vitlök", "ingefära", "spiskummin", "gurkmeja", "rapsolja", "sötpotatis", "linser", "krossade tomater", "kokosmjölk", "salt"], 22, [2]),
   S("Rör ner spenaten och servera med ris och yoghurt.", ["spenat", "ris", "yoghurt naturell"], 3, [1, 3])]))
L.append(R("greek-roast-vegetables-feta-couscous", "Ugnsrostade grönsaker med kikärtor, fetaost och couscous", "dinner", "greek", "ugnsgrönsaker", "kikärtor", "oven", "couscous",
  ["oregano", "citron", "vitlök"], ["Ugn", "Plåt", "Skål"],
  [("c1", "Grönsaker", [I("zucchini", "raw_edible", 200), I("paprika", "raw_edible", 150), I("rödlök", "raw_edible", 80), I("aubergine", "raw_edible", 200),
    I("kikärtor", "cooked_drained", 200, "primary"), I("oregano", "dry", 1, "flavour"), I("vitlök", "raw_edible", 6, "flavour"), olja(25), salt(2)]),
   ("c2", "Servering", [I("couscous", "dry", 120, "side"), I("fetaost", "as_sold", 80, "flavour"), I("citronjuice", "as_sold", 15, "flavour"), I("persilja", "raw_edible", 8, "flavour")])],
  [S("Sätt ugnen på 225 °C. Skär grönsakerna i bitar och vänd med kikärtor, olja, vitlök, oregano och salt.", ["zucchini", "paprika", "rödlök", "aubergine", "kikärtor", "rapsolja", "vitlök", "oregano", "salt"], 10),
   S("Rosta på plåt cirka 25 minuter.", ["zucchini", "kikärtor"], 25, [1], True),
   S("Häll 200 ml kokande vatten över couscousen och låt svälla. Vänd med citronjuice och persilja.", ["couscous", "citronjuice", "persilja"], 6),
   S("Servera grönsakerna på couscousen med smulad fetaost.", ["fetaost", "couscous", "zucchini"], 2, [2, 3])]))
L.append(R("mexican-kidney-bean-sweet-potato-chili", "Bönchili med sötpotatis, kidneybönor och yoghurt, med ris", "dinner", "mexican", "chili", "kidneybönor", "pot", "ris",
  ["spiskummin", "rökt paprika", "tomat"], ["Gryta", "Kastrull"],
  [("c1", "Chili", [I("kidneybönor", "cooked_drained", 250, "primary"), I("sötpotatis", "raw_edible", 250), I("krossade tomater", "as_sold", 400, "sauce"),
    I("gul lök", "raw_edible", 80), I("vitlök", "raw_edible", 6, "flavour"), I("paprika", "raw_edible", 120), I("spiskummin", "dry", 2, "flavour"),
    I("rökt paprikapulver", "dry", 1, "flavour"), olja(15), salt(2)]),
   ("c2", "Servering", [I("ris", "dry", 120, "side"), I("yoghurt naturell", "as_sold", 80, "sauce")])],
  [S("Koka riset i 240 ml vatten under lock cirka 15 minuter.", ["ris"], 18, None, True),
   S("Hacka lök och vitlök, tärna sötpotatis och paprika.", ["gul lök", "vitlök", "sötpotatis", "paprika"], 8),
   S("Fräs lök, vitlök, paprika och kryddor i oljan. Tillsätt sötpotatis, bönor, tomater, salt och 200 ml vatten och sjud 20 minuter.", ["gul lök", "vitlök", "paprika", "spiskummin", "rökt paprikapulver", "rapsolja", "sötpotatis", "kidneybönor", "krossade tomater", "salt"], 22, [2]),
   S("Servera chilin med ris och yoghurt.", ["ris", "yoghurt naturell", "kidneybönor"], 1, [1, 3])]))
L.append(R("thai-tofu-coconut-peanut-noodles", "Tofu i kokos- och jordnötssås med nudlar, broccoli och morot", "dinner", "thai", "nudlar", "tofu", "pan", "nudlar",
  ["jordnöt", "soja", "ingefära"], ["Stekpanna", "Kastrull"],
  [("c1", "Tofu och sås", [I("tofu", "as_sold", 250, "primary"), I("kokosmjölk", "as_sold", 150, "sauce"), I("sojasås", "as_sold", 25, "flavour"), I("citronjuice", "as_sold", 15, "flavour"),
    I("ingefära", "raw_edible", 10, "flavour"), I("vitlök", "raw_edible", 6, "flavour"), olja(15)]),
   ("c2", "Nudlar och grönt", [I("nudlar", "dry", 150, "side"), I("broccoli", "raw_edible", 200), I("morot", "raw_edible", 100), I("jordnötter", "as_sold", 40, "flavour")])],
  [S("Tärna tofun och stek den gyllene i oljan.", ["tofu", "rapsolja"], 10),
   S("Koka nudlarna enligt förpackningen, de sista 3 minuterna med broccoli och strimlad morot.", ["nudlar", "broccoli", "morot"], 8, None, True),
   S("Finhacka hälften av jordnötterna och riv ingefära och vitlök. Rör ihop med kokosmjölk, sojasås och citronjuice till en sås och värm den.", ["jordnötter", "kokosmjölk", "sojasås", "citronjuice", "ingefära", "vitlök"], 5),
   S("Vänd nudlar, grönsaker och tofu med såsen och toppa med resten av jordnötterna, hackade.", ["nudlar", "broccoli", "tofu", "jordnötter"], 3, [1, 2, 3])]))
L.append(R("indian-egg-curry-spinach", "Äggcurry med spenat och tomat, med ris", "dinner", "indian", "curry", "ägg", "pot", "ris",
  ["koriander", "ingefära", "kokos"], ["Gryta", "Kastrull"],
  [("c1", "Curry", [I("ägg", "raw_edible", 300, "primary", "Ägg"), I("spenat", "as_sold", 150), I("krossade tomater", "as_sold", 300, "sauce"), I("kokosmjölk", "as_sold", 150, "sauce"),
    I("gul lök", "raw_edible", 80), I("vitlök", "raw_edible", 6, "flavour"), I("ingefära", "raw_edible", 10, "flavour"), I("spiskummin", "dry", 1, "flavour"),
    I("gurkmeja", "dry", 1, "flavour"), I("malen koriander", "dry", 1, "flavour"), olja(15), salt(2)]),
   ("c2", "Ris", [I("ris", "dry", 140, "side")])],
  [S("Koka riset i 280 ml vatten under lock cirka 15 minuter.", ["ris"], 18, None, True),
   S("Koka äggen 9 minuter tills både vita och gula stelnat, kyl och skala dem.", ["ägg"], 12, None, True),
   S("Hacka lök, vitlök och ingefära och fräs med spiskummin, gurkmeja och koriander i oljan. Tillsätt tomater, kokosmjölk, spenat och salt och sjud 10 minuter.", ["gul lök", "vitlök", "ingefära", "spiskummin", "gurkmeja", "malen koriander", "rapsolja", "krossade tomater", "kokosmjölk", "spenat", "salt"], 16),
   S("Dela äggen, lägg dem i såsen och värm 2 minuter. Servera med riset.", ["ägg", "ris"], 3, [1, 2, 3])]))
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump({"schema_version": "smako-recipe-authoring-v1", "pack_id": "smako-variety-recipes-20261021", "recipes": L},
              out, ensure_ascii=False, indent=1)
print(len(L))
