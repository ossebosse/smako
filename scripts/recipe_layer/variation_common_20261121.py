"""Shared ingredient and step helpers for the 2026-11-21 variation bases."""
from cheap_bases_20261119 import ALL, I, St

def tv(s, t, e=None):
    return {"S": s, "T": t, "E": e if e is not None else t}

POT = lambda v=ALL, q=1000, comp="c2": I("potatis", "raw_edible", q, "side", "Potatis, rå", v=v, comp=comp)
RIS = lambda v=ALL, q=320, comp="c2", label="Ris, torr vikt": I("ris", "dry", q, "side", label, v=v, comp=comp)
PASTA = lambda v=ALL, q=400, comp="c2": I("pasta", "dry", q, "side", "Pasta, torr vikt", v=v, comp=comp)
SALT = lambda q=5, v=ALL, comp="c1": I("salt", "as_sold", q, "flavour", "Salt", v=v, comp=comp)
PEPPER = lambda q=1, v=ALL, comp="c1": I("svartpeppar", "dry", q, "flavour", "Svartpeppar, malen", v=v, comp=comp)
OIL = lambda q=30, v=ALL, comp="c1": I("rapsolja", "as_sold", q, "cooking", "Rapsolja", v=v, comp=comp)
OLIVE = lambda q=30, v=ALL, comp="c1": I("olivolja", "as_sold", q, "cooking", "Olivolja", v=v, comp=comp)
ONION = lambda q=150, v=ALL, comp="c1": I("gul lök", "raw_edible", q, "vegetable", "Gul lök, rå", v=v, comp=comp)
GARLIC = lambda q=10, v=ALL, comp="c1": I("vitlök", "raw_edible", q, "flavour", "Vitlök, skalad", v=v, comp=comp)
TOM = lambda q=400, v=ALL, comp="c1": I("krossade tomater", "as_sold", q, "sauce", "Krossade tomater", v=v, comp=comp)

def boil_potatoes(after=(), v=ALL, peeled=True, key="p"):
    first = "Skala potatisen, dela större potatisar och lägg dem" if peeled else "Skrubba potatisen och lägg den"
    return [St(key + "0", f"{first} i en kastrull med kallt vatten och en nypa av saltet.", ["potatis", "salt"], 6, after=after, v=v),
            St(key + "1", "Koka potatisen cirka 20 minuter tills den är mjuk. Häll av vattnet.", ["potatis"], 20, after=[key + "0"], passive=True, v=v)]

def cook_rice(after=(), v=ALL, water=640, key="r"):
    return [St(key + "0", f"Skölj riset och koka upp det med {water} ml vatten och en nypa av saltet.", ["ris", "salt"], 4, after=after, v=v),
            St(key + "1", "Låt riset sjuda under lock på svag värme i 15 minuter tills vattnet har kokat in och riset är mjukt.", ["ris"], 15, after=[key + "0"], passive=True, v=v)]

def cook_pasta(after=(), v=ALL, key="n"):
    return [St(key + "0", "Koka pastan i rikligt med saltat vatten enligt anvisningen på paketet. Spara 100 ml av kokvattnet och häll av resten.", ["pasta", "salt"], 12, after=after, v=v)]
