# Beslutsunderlag för eventuell fortsatt release

Ingen aktivering har utförts. Detta dokument godkänner inte en produktionsändring.

## Två olika basstrategier

**Originalpolicy:** fortsatt spärrad. Den kräver sex angivna kontexter, däribland Primat Clemenstorget full_catalog. Källan anger nu offers_only. För återställning behövs en belagd aktuell butiksspecifik bas med godkänd revalidering, prisinsamling och komplett originalfederation. Enbart ett grönt tier-fält är inte ett fullsortimentsbevis. Gunnesbo får inte lånas som ersättning för Clemenstorget.

**Alternativ testpolicy:** `lund-own-five-base-20260928-v1`, obligatoriskt Coop Online Syd, Hemköp Karhögstorg/Brunnshög och Willys Lund/Nova. Dessa är fem onlinebaskontexter. Godkända fysiska erbjudanden är frivilliga tillskott; de utgör inte fulla butikskataloger. Faktiska profil- och driftresultat: VERIFICATION.md. Policyn och källkonfigurationen är beständiga i den separata testmiljön.

Ett separat, uttryckligt beslut krävs om denna alternativa omfattning får bli en framtida releasepolicy: fem specificerade obligatoriska onlinebaskataloger, inga Primat-baser, partiella ICA/Coop/X:-tra/Lidl/Willys-fysiska erbjudanden. Ett sådant beslut måste också acceptera/redovisa att ICA:s fulla katalog saknas och att ICA/Hemköp inte har full gemensam kommuninventering. Testet är inte godkännande enligt originalpolicyn och ändrar inte användarens butik/inköpsområde.

## Kontroller vid ett senare beslut

- Använd den innehållsidentifierade bilden och kontrollera policyhash, källkonfiguration och samtliga fem obligatoriska kontexter. App, collector och refresh måste använda kompatibelt paket.
- Kopiera/verifiera även de råfiler som behövs för faktakoppling; en databas och ett fungerande PriceUniverse räcker inte. Testpaketets 2 232 refererade råfiler är hashkontrollerade. Kör motsvarande förkontroll på det aktuella paketet.
- Behåll gränserna 36 h varning / 48 h stopp. Dessa källor observerades 27 september, inte vid rebuilden. Willys har tidigast ordinarie basuppdatering 29 september 02:13:51 UTC och hård gräns 15:13:51 UTC, om ingen ny observation har skett. Kontrollera varje faktisk butikskälla igen, inte bara dessa rapporttider.
- Kör behovsstyrd hämtning för förfallna källor, validera basens fullständighet och upprepa relevanta profil-, audit-, reload- och återläsningsprov på samma aktuella frysta data. Inga gamla kampanjgodkännanden får ärvas av ny utgåva.
- Behåll konkreta frivilliga källfel synliga. Coops fysiska strukturerade flöde avvisade dagens nya butik-/källbevis; giltig LKG är tillåten endast till faktisk kampanjutgång. Kontrollera aktuella fysiska erbjudanden och ändrade utgåvor på nytt.
- Kontrollera atomiskt manifest och vad serving faktiskt läser. Sparade planer ska inte tyst räknas om. Behåll en separat återställningspunkt; tidigare läskompatibilitet är inte bevis för att äldre kod kan räkna om nya beredningsmetoder.

## Separata öppna uppgifter

ICA-/Hemköpsluckan i kommunstyrningen och äldre köptermer i kedjeimporterna är inte ombyggda här. Fullständigt Malmö-publiceringsprov är inte utfört och är inget bevis från detta Lund-prov. Historisk Lidl-fixture `reports/source-implementation-20260915/lidl_offer_adapter.py` saknas fortsatt; den historiska deklarations-/identitets-/beredningsregressionen är inte återställd. De aktuella prövade fallen och tidigare hashstabila tester ersätter inte detta historiska skydd. Ingen ny generell dispens ges för Lidl.

Windows-uppgifter, scheman, sparade användarprofiler och produktionsmanifest förblir oförändrade.
