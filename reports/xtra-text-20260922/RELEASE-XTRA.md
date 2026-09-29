# Separat kandidat: X:-tra PDF-text

Endast lokal testverifiering, ingen aktivering eller schemakoppling.
Detta tillägg behöver inte ingå i de nio Coop-butikernas release.

Verifierat: officiell Skansvägen-PDF, åtta sidor, 57 identifierade textannonser,
10 radgodkända priser i isolerat OWN, 9 aktuella i PriceUniverse och en framtida
post (Snacktomater 24–27 september). Tre verkliga ingrediensköp passerar
matcher/checkout/audit. Fullsnapshot är underkänd 10/57, 95 % oförändrat.
47 textannonser har kvarvarande köphinder. Alla uppgifter är från faktisk
observation 21 september 17:56:02 UTC; slutverifiering 22 september 07:46 Stockholm.

Kod: textadapter `xtra_pdf.py`, isolerad importer `import_xtra_pdf_text.py`,
explicit tillåten policy i befintliga `offer_rows.py` och `catalog.py`.
PyMuPDF 1.28.2 fanns redan. Inga nya installationer eller externa anrop.

Innan en framtida aktivering: verifiera nästa då aktuella officiella dokument
med samma källbindning, dokumentmall och pris-/villkorskontroller; kontrollera
okända layoutfall och nya sidvillkor. Testa den opt-in-kopplingen i avsedd
driftmiljö. Ett fungerande kommandotest är inte ett installerat driftschema.
Näringsgodkänd planering och produktkoppling utan GTIN är fortfarande separata
releasevillkor. Begränsade medlemskampanjer över butiker kräver belagt gemensamt
kampanj-ID; okända sådana köp förblir blockerade. Full reklambladstäckning kan
inte påstås eftersom bildinnehållets okända annonser inte räknats.

Villkor för ett separat framtida aktiveringsbeslut och rollback är samma som
Coop-paketets: validerad kandidat, färska baser, rätt inköpsdag, lås/backup,
atomisk aktivering och processverifiering; återgång endast till giltig bas.
Ingen del av detta har skarpt aktiverats i denna etapp.
