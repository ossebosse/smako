# Komplettering efter fullkatalog 2026-10-29

App och scheduler kör redan source-ops-2600390d3943. Fyra tomma Malmö-källor
är verifierade i dashboarden med lyckad kontroll, noll fel och noll priskontexter.

Normal fullhämtning för 730400 gav 816 sidor/748 kategorier, 12381 råposter,
11237 unika produkter och 1144 identiska dubbletter mellan kategorier. Inga
konflikter, transportfel eller karantänposter. Kandidaten 4ce8bec702854547882efb58acdb3fc2
stoppades av tre nya fältsökvägar; tidigare LKG förblev aktivt.
Incident source-c861b36e7feaec4e533683b5, signatur
c861b36e7feaec4e533683b545f694088f07f9c62c3fb47c19edf70c987e784e.

Verifierade råbytes visar availablePromotions som listor med FIXED_PRICE,
MULTI_BUY_FIXED_PRICE eller PERCENTAGE_DISCOUNT. Parser v5 kräver kända,
unika typer som stämmer med de faktiska kampanjraderna. En okänd/motstridig
sammanfattning undanhåller kampanjer och behåller verifierat baspris. Pris,
medlemskap, datum och köpgräns kommer fortsatt från faktiska kampanjfält;
en sammanfattning ger aldrig rabatt eller obegränsad köpgräns.
energyLabel.imageUrl är en presentationslänk som inte används i prissättningen.
Endast dessa tre exakta sökvägar på 730400:s kategoriyta granskas i v5.
Typbyten och andra nya fält förblir blockerade.

Kompletteringen distribueras bara till scheduler. Appen och all recept-/
beräkningskod kan fortsätta på 2600390d3943; appen läser redan kvalificerade
OWN-priser och kräver ingen ny insamlingsparser. Tre grocery-källfiler ändras.
Den fullständiga färska hämtningen återspelas med sin verkliga observationstid;
ingen ny nättraversering eller omstämpling görs.

Lunds befintliga prisversion har den kanoniska onlinekontexten
context:coop:23eaae11c9661e68. Malmö har ingen sådan kontext i sitt valda scope
och ska behålla sina butikskopplade källor. Källreparationen utökar inga val.
