"""Build reviewed stages, register locally, then require basket proofs before merge."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    pack_diff,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

SOURCE = ROOT / 'incoming/authoring-1000-20261101'
OUTPUT = ROOT / 'reviewed-expansion-round2-20261101'
REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')
STAGES = {
    1: {
        'smako-greek-horiatiki': 'Råa grovskurna grönsaker med stora fetaskivor och separat bröd; inte panzanellas inarbetade bröd eller bakade grönsaker.',
        'smako-greek-tahinopita': 'Tunn jästdeg fylls med tahini, tvinnas och plattas till spiral; skild från smörfyllda kanelbullar och smulpaj.',
        'smako-italian-gnocchi-di-susine': 'Plommon innesluts i potatisdeg, sjuds och vänds i smörsmulor; inte plommonkaka eller ugnsbakad äggsmet.',
        'smako-swedish-semla': 'Kardemummabulle fylls efter gräddning med mandelkräm och vispad grädde; inte conchas kakdegsskal eller babas indränkning.',
        'smako-indian-chana-madra': 'Kikärtor tillagas i varsamt uppvärmd yoghurtsås med ghee; inte tomatmasala eller kall raita till annan huvudrätt.',
        'smako-indian-khichu': 'Rismjöl skållas till mjuk skedbar massa och ångas i skål; inte utbakade risbröd eller separata ångade risbullar.',
        'smako-swedish-stompa': 'Bikarbonat- och fildeg med råg kavlas till tunna bröd i torr panna; skild från ugnsbakad filmjölkslimpa.',
    },
    2: {
        'smako-indian-doi-maach': 'Först brynt fisk sjuds varsamt i tempererad lök-yoghurtsås; skild från tomatfiskgryta, kokosfisk och kall raita.',
        'smako-mexican-pescado-zarandeado': 'Adobopasta kokas separat och bryns på fisk i het ugn; uttrycklig hemanpassning, skild från pocherad fisk eller stekt fisk i tacos.',
        'smako-mexican-tacos-de-canasta': 'Mjuka majstacos med separata potatis- och bönfyllningar penslas med chiliolja och ångvilar tätt inpackade; skild från frasiga flautas/tostadas.',
        'smako-mexican-chilorio': 'Rivet långkokt fläsk steks torrt i ancho-vinägerpasta; skild från saftiga citruskokta carnitas och kött i buljong.',
        'smako-italian-spaghetti-aglio-olio': 'Kokt spaghetti vänds i vitlöksolja emulgerad med pastavatten; skild från råstekt spaghetti assassina eller pasta blandad med bönsås.',
    },
    3: {
        'smako-italian-panforte': 'Tät nöt-honungskaka med kanderat apelsinskal, ingen äggvispning eller jäst. Skild från rulltårta, nötmaräng och kanderat skal som eget godis.',
        'smako-swedish-bryta-filmjolk': 'Hårt tunnbröd bryts direkt i fil och mjuknar kort; skild från gröt, müsli och ugnsbakat bröd.',
        'smako-italian-schiacciata-uva': 'Druvor bakas både mellan två jästdegslager och ovanpå; skild från tahinifylld spiral och paj med frukt på botten.',
        'smako-mexican-enfrijoladas': 'Mjuka majstortillas doppas och viks i slät svartbönsås. Skild från tjocka fyllda majskakor, frasiga flautas och korgtacos med separat fyllning.',
    },
    4: {
        'smako-greek-fanouropita': 'Äggfri oljebaserad apelsin-russinkaka; skild från friterad skållad churro, filokaka och jäst fruktbröd.',
        'smako-greek-halvas-simigdalenios': 'Mannagryn rostas i olja, skållas med sirap och formas kallt; skild från bakad grynkaka och mjölkkokt kräm i filopaket.',
        'smako-greek-portokalopita': 'Torkad sönderriven filodeg binds med yoghurt och ägg, bakas och dränks med apelsinsirap; skild från grynig mannagrynskaka.',
        'smako-italian-budino-riso-toscana': 'Mjölkkokt ris och ägg bakas i eget mördegsskal; skild från jäst concha, fruktsmet/clafoutis och skiktad citronpudding.',
        'smako-mexican-camotes-poblanos': 'Sötpotatismos kokas med socker till formbar mjuk konfekt och kyls; skild från fruktgranita, knäck och kanderat skal.',
        'smako-italian-ricciarelli-siena': 'Ovispad mandel-äggvitedeg vilar åtta timmar och bakas till mjuka ovala kakor; skild från vispade mandelmarängskal med kräm.',
    },
    5: {
        'smako-swedish-isterband-dillpotatis': 'Syrad grynkorv serveras med mjölkstuvad tärnad potatis och rödbetor; skild från Lindströms rödbetsfärsbiffar, rårakor och mjölklimpar.',
        'smako-greek-kollyva-veteskal': 'Kokta hela matvetekorn kyls och blandas med nötter och frukt; uttrycklig frukostanpassning, skild från rostad havregranola och fylld bakad frukt.',
    },
    6: {
        'smako-swedish-porterstek': 'Hel nötstek bräseras i porter, koncentrerad vinbärssaft och soja; spadet blir gräddsås. Skild från plommonspäckad fläskkarré och pressat stekt fläsk.',
        'smako-italian-zuppa-imperiale': 'Mannagryn, ägg, smör och parmesan bakas till platta, skärs i kuber och värms i buljong. Skild från ströbrödsbaserade pressade passatelli.',
        'smako-italian-pizzoccheri': 'Handskurna boveteband samkokas med potatis och kål, varvas med ost och vitlökssmör. Skild från mjölklimpar, stekt potatis och stuvad potatis.',
    },
    7: {
        'smako-greek-revithada': 'Torra kikärtor och lök bakas sex timmar under tätt lock och avslutas med citron. Skild från tomatkokt fasolada och kalla kikärtssallader.',
        'smako-italian-pasta-alla-genovese': 'Nötkött och stor mängd lök långkokas till reducerad löksås för pasta. Skild från tomatragu, linssoppa och pressade passatelli.',
        'smako-greek-tirokafteri': 'Rostad skalad paprika mosas med feta och chili till dipp; skild från grov rå sallad och ugnsbakad fetapaj.',
        'smako-greek-melitzanosalata': 'Aubergine rostas mjuk, skalas och hackas till kall citron-vitlöksröra; skild från fyllda auberginebåtar och rullar.',
    },
    8: {
        'smako-thai-pa-tong-ko': 'Luftig osötad jästdeg paras till dubbla remsor och friteras, med varm sojadryck. Skild från fyllda runda jästmunkar.',
        'smako-mexican-bunuelos-de-viento': 'Tunn ägg-mjölksmet fastnar på rosettjärn och friteras till ihåliga spröda mönster; skild från spritsad skållad churrodeg.',
        'smako-indian-mangalore-buns': 'Banan-yoghurtdeg utan jäst vilar åtta timmar och friteras som tjocka puffade rundlar. Skild från stekt bananmos, ångad risdeg och jästa remsor.',
        'smako-greek-loukoumades': 'Lös jästsmet skedas till små friterade bollar och vänds i honung; skild från kesoplättar och fasta fyllda munkar.',
        'smako-indian-gulab-jamun': 'Mjölkpulverdeg formas till släta bollar, friteras vid lägre temperatur och drar i kardemummasirap. Skild från mjölbaserade churros och honungsjästbollar.',
    },
    9: {
        'smako-swedish-bohuslansk-aggost': 'Mjölk, fil och ägg värmekoaguleras, silas och varvas med socker; skild från bakad karamelläggkräm och gräddtårta.',
        'smako-indian-shrikhand': 'Yoghurt silas kall åtta timmar och vispas med socker och kardemumma; skild från långreducerad varm mjölkkräm och kokt ostkonfekt.',
        'smako-indian-chhena-poda': 'Nysyrad och silad mjölkost knådas med mannagryn och bakas till karamelliserad kaka; skild från pannkokt sandesh och morotshalwa.',
        'smako-italian-torta-pasqualina': 'Oljedeg omsluter ricotta och gröna blad med hela ägg i gropar, som bakas inne i pajen; skild från öppen tomatpaj och fyllda crespelle.',
    },
    10: {
        'smako-indian-phirni': 'Rått blötlagt ris mals fint och sjuds i mjölk till kyld kräm; skild från risgrynsgröt med hela gryn och bakad rispudding.',
        'smako-thai-hor-mok-pla': 'Fiskbitar och mald fisk binds med ägg och kokosmjölk och ångas i skålar ovanpå kål; skild från rinnande fisksås till nudlar och puffad omelett.',
        'smako-thai-kluai-buat-chi': 'Bananbitar sjuds varsamt i saltad söt kokosmjölk; skild från klibbigt ris med mango, kokosäggkräm och friterad banan.',
        'smako-italian-pasticciotto-leccese': 'Ett slutet mördegsskal omsluter förkokt äggkräm; uttrycklig smöranpassning, skild från öppna smördegsformar och staplade millefoglie.',
        'smako-mexican-sopa-de-lima': 'Klar kycklingsoppa med lime och frasiga stekta tortillastrimlor; skild från tjock bönsås runt mjuka tortillas och kycklingtinga på bröd.',
    },
    11: {
        'smako-thai-kai-palo': 'Hårdkokta hela ägg och fläskkarré bräseras i karamell, soja och Five Spice; skild från wokat äggris, friterad omelett i soppa och basilikatofu.',
    },
    12: {
        'smako-indian-dal-baati': 'Fasta ofyllda fullkornsbrödbollar bakas, bryts och smöras till linsgryta; skild från råa degbitar som kokas direkt i dal och fyllda stekta bröd.',
        'smako-mexican-salpicon-de-res': 'Långkokt högrev rivs, kyls och vänds i rå grönsakssallad med lime; skild från kycklingtinga på bröd och kall räkcocktail.',
        'smako-swedish-inkokt-lax': 'Lax sjuds i söt-syrlig dillag, kyls i lagen och lyfts ur före servering; skild från ugnsbakad lax, gratäng och varm laxsoppa.',
    },
    13: {
        'smako-indian-murgh-musallam': 'Hel marinerad kyckling fylls med ris och kokt ägg och bakas täckt; skild från benfria nötpanerade bitar, cafreal och risgryta.',
        'smako-italian-coda-vaccinara': 'Oxsvans på ben långkokas och benas ur i selleri-tomatsås; skild från bönsoppa, lammragù med polenta och löksås till pasta.',
        'smako-swedish-flasklagg-rotmos': 'Rimmad lägg långkokas och serveras med rotmos som späds med en del av kokspadet; skild från stekt fläsk med bruna bönor och späckad karré.',
    },
}
STAGES[14] = {
    'smako-italian-pasta-amatriciana': 'Guancialefett bär en reducerad tomatsås som avslutas med fårhårdost; skild från olja-vitlöksemulsion, sardell-olivsås och råstekt tomatspaghetti.',
    'smako-italian-pasta-cacio-pepe': 'Fårhårdost emulgeras utanför värmen med stärkelsevatten och rostad peppar; skild från gräddsås, äggbaserad carbonara och vitlöksolja.',
    'smako-mexican-torta-ahogada': 'Fläskfylld surdegsfralla dränks i varm lös tomatsalsa strax före servering. Uttrycklig svensk brödanpassning, skild från majsskålar och mjuka bönsåstortillas.',
}
SELECTED_VARIANTS = {
    14: {'smako-mexican-torta-ahogada': {'simple', 'standard'}},
    8: {'smako-indian-gulab-jamun': {'simple'}},
    9: {'smako-italian-torta-pasqualina': {'simple'}},
    10: {name: {'simple'} for name in ('smako-indian-phirni', 'smako-thai-hor-mok-pla',
                                      'smako-thai-kluai-buat-chi', 'smako-italian-pasticciotto-leccese')},
    12: {'smako-indian-dal-baati': {'simple'}},
}
STAGES[15] = {
    'smako-swedish-janssons-frestelse': 'Råstrimlad potatis varvas med lök och kryddad skarpsill och bakas länge med grädde. Skild från potatispuré, stekt köttpanna och gratänger med färdigkokt potatis.',
    'smako-swedish-gubbrora-ansjovis': 'Hårdkokta ägg och kryddad skarpsill tärnas till kall röra på knäckebröd; skild från matjessill med potatis, varm kycklingfyllning och bakad linspaté.',
}
STAGES[16] = {
    'smako-mexican-carlota-limon': 'Kyld lime-mjölkkräm varvas med mariekex som mjuknar utan gräddning; skild från fruktsorbet, grynpudding och gräddad paj.',
    'smako-swedish-blodpalt': 'Rå potatis och nötblod binds med råg/vetemjöl runt fläskfyllning och sjuds som palt; skild från äggpannkaka, kolbulle och rökt korv.',
}
STAGES[17] = {
    'smako-indian-gulab-jamun': STAGES[8]['smako-indian-gulab-jamun'],
    'smako-indian-phirni': STAGES[10]['smako-indian-phirni'],
    'smako-mexican-carne-en-su-jugo': 'Tunt nötkött avger sitt eget spad i en grön tomatillobuljong, med krispigt fläsk och bönor. Uttrycklig såsanpassning, skild från tjock chili, rivet långkokt fläsk och kall köttsallad.',
}
SELECTED_VARIANTS[17] = {name: {'extended'} for name in ('smako-indian-gulab-jamun', 'smako-indian-phirni')}
STAGES[18] = {
    'smako-italian-fegato-veneziana-flasklever': 'Tunna leverstrimlor steks till mjuk riklig lök, vinägersky och polenta. Uttrycklig ungnötsleverversion, skild från fintärnat förkokt fläsk/lever i indisk kryddsås.',
    'smako-swedish-korvkaka': 'Rå lever finfördelas och bakas med mjölkkokta korngryn, russin och ägg till skivbar kaka. Skild från äggakaka, blodpalt och lös korngryta.',
}
STAGES[19] = {
    'smako-mexican-manchamanteles': 'Kyckling sjuds i mixad röd ancho-tomatsås med ananas och stekt mogen kokbanan; frukten ingår i själva molen. Skild från cashewkyckling och fyllda tomater.',
}
STAGES[20] = {
    'smako-mexican-arroz-tumbada': 'Soppigt tomatris tillagas i samma spad som vit fisk, råa räkor och musselkött. Skild från risotto, torr paella och separat ris till fisksoppa.',
}
SELECTED_VARIANTS[20] = {'smako-mexican-arroz-tumbada': {'simple'}}
STAGES[21] = {
    'smako-swedish-sillsallad': 'Kall potatis-rödbets-äppelsallad med ätklar inläggningssill och saltgurka; skild från ägg-ansjovisröra på bröd och matjessill med separata tillbehör.',
}
STAGES[22] = {
    'smako-swedish-lapskojs': 'Finfördelat saltat nötkött arbetas in i grovt potatismos; uttrycklig konservversion, skild från skivat kött med mos, stekt biffpanna och rimmad lägg med rotmos.',
}
STAGES[23] = {'smako-italian-torta-pasqualina': STAGES[9]['smako-italian-torta-pasqualina']}
SELECTED_VARIANTS[23] = {'smako-italian-torta-pasqualina': {'standard', 'extended'}}
STAGES[24] = {
    'smako-mexican-frijoles-puercos': 'Kokta bönor mosas och steks med rå kryddad korvfärs, hela dess fett och smält ost till tjock röra med tortilla. Svensk färsk chorizo anges öppet; skild från frijol con puerco med hela bönor i buljong och enfrijoladas släta bönsås runt vikta tortillas.',
}
STAGES[25] = {
    'smako-indian-rogan-josh': 'Lamm bräseras i yoghurt med fänkålsfrö och torkad ingefära utan tomat. Öppet namngiven paprika-cayenneanpassning; skild från tomatmasala, palak och sötsyrlig vinägerbaserad vindaloo. Ainsley Harriotts egen rogan josh visar paprika/cayenne som kulinarisk väg: https://www.ainsley-harriott.com/recipe/lamb-rogan-josh/ . Dos och övrigt innehåll är separat granskade, inte hämtade som en kopia av det receptet.',
}
STAGES[26] = {
    'smako-greek-patatato-amorgos': 'Tomat-kanelbräserat lamm där potatisen tillsätts senare och binder själva spadet. Skild från tätt paketbakat kleftiko, lökdominerad stifado med separat korn och italiensk ragu med separat polenta. Lammversionen stöds av grekiska turistmyndighetens beskrivning: https://www.visitgreece.gr/el/experiences/architecture/local-architecture/amorgos-gastronomy . Det ursprungliga getutkastet bevaras.',
}
STAGES[27] = {
    'smako-greek-tsigariasto-get': 'Brynning följd av mycket låg tillagning i köttets eget lilla spad, med bröd till. Ingen tomat- eller potatisgryta och inget paketbakat kleftiko. Den kreten­siska restaurangens lammversion dokumenteras i https://www.gastronomos.gr/syntagh/tsigariasto/50594/ ; här är benfritt lamm och vin/lök/citron i tilläggsvarianterna uttryckliga anpassningar, inte en kopia av deras recept.',
}


STAGES[28] = {
    'smako-greek-spetsofai': 'Skivad kryddig färskkorv bräseras med breda paprikabitar i tomat, serverad med bröd. Skild från stroganoffs gräddsås, böngryta och ugnsbakad korv. Öppet salsicciaalternativ till grekisk lantkorv. Receptförfattarens egen kommentar till https://www.mygreekdish.com/recipe/spetsofai-sausages-with-peppers-and-tomato-sauce/ stöder kryddiga alternativa korvar; detta är ingen loukaniko-identitet.',
}
STAGES[29] = {
    'smako-italian-pasta-alla-norma': 'Separat brynt aubergine vänds med pasta i basilika-tomatsås och toppas med lagrad pecorino. Skild från ugnsgratäng, köttsås och tomatfri ostemulsion. Pecorinoalternativ finns i kockens egen https://www.jamieoliver.com/recipes/pasta/sicilian-spaghetti-alla-norma/ ; här behålls leveransens grundmetod med en separat angiven ostdos, utan påstående om ricotta salata.',
}
STAGES[30] = {
    'smako-greek-pitarakia-milos': 'Tunn oljedeg utan jäst omsluter ost och lök och friteras till halvmånar. Skild från filodegstrianglar, potatisfylld pakora och ostbollar utan degskal. Pecorino- och gulostalternativ stöds av https://www.mygreekdish.com/recipe/greek-cheese-pies-milos-pitarakia-milou/ ; här används uttryckligt feta- och pecorinoalternativ till manoura.',
}
STAGES[31] = {
    'smako-mexican-rajas-con-crema': 'Rostade och skalade paprikastrimlor sjuds med lök och majs i gräddsås och serveras i mjuka majstortillas. Skild från fylld paprika, chilirostad tomatsalsa och stekt grönsaksris. Paprika och separat jalapeño är öppna alternativ med stöd i författarens https://www.maricruzavalos.com/rajas-con-crema/ ; inte ett alias eller smaklöfte för poblano.',
}
STAGES[32] = {
    'smako-thai-nam-prik-ong': 'Tjock, reducerad tomat- och fläskdipp med rostad schalottenlök, chili, grönsaksstavar och separat ris. Skild från en rinnande curry eller varm köttfärssås över pasta. Uttrycklig fisksåsversion utan räkpasta, med separat granskad dos; författaren anger fisksås som ett alternativ i https://thai-foodie.com/thaifood/thai-style-lettuce-wraps-nam-prik-ong-น้ำพริกอ่อง/ . Ingen identitets- eller smaklikhet mellan såserna påstås.',
}
STAGES[33] = {
    'smako-indian-patishapta': 'Tunna ris-vetepannkakor rullas kring kokt kokos-sockerfyllning; skild från tjocka plättar och panerad banan. Öppet muscovadoalternativ till jaggery med egen dos. Brunt socker i kokosfyllningen finns i receptförfattarens https://culturecheesemag.com/recipes/indian-sweet-crepes-patishapta/ ; den publicerade mängden eller andra receptdelar kopieras inte.',
}
STAGES[34] = {
    'smako-thai-khao-tom-mat': 'Förkokt kokosklibbris omsluter banan och ångas i täta små paket. Skild från lös kokosrisgröt, mango ovanpå ris och stekt banan. Synlig bakpappersversion utan bananbladens arom; egen erfarenhet av bakpapper redovisas av receptförfattaren https://charinyaskitchen.wordpress.com/2018/06/22/khow-tom-mud/ . Endast enkel variant granskas; pandanvarianten kvarstår.',
}
SELECTED_VARIANTS[34] = {'smako-thai-khao-tom-mat': {'simple'}}
STAGES[35] = {
    'smako-italian-pasta-ncasciata': 'Kort pasta blandas med brynt aubergine, nötragù, fast ägginlägg och ost och gratineras. Skild från köttfri Norma, skiktad lasagne och äggemulsion. Öppet mozzarellaalternativ till caciocavallo; tillverkaren har egen sådan version på https://www.galbani.it/ricette/pasta-ncasciata . Ny avrunnen ostdos granskas självständigt; ingen identitet eller lika smak påstås.',
}
STAGES[36] = {
    'smako-thai-tod-man-pla': 'Rå fisk mixas till seg massa med röd curry och ägg, små gröna bönbitar vänds i och tunna kakor steks. Skild från tonfisk-kikärtskakor, panerad filé och kokosångad fiskkräm. Öppet citrongräsalternativ till makrutblad med stöd för själva bytet från kockskolan https://www.ateliersetsaveurs.com/uploads/recipes/culinary/pdf/thai-fish-cakes-with-sweet-and-sour-chili-sauce-en-751-v1.pdf . Mängd och beredning granskas självständigt; ingen lika arom eller utbytesfaktor påstås.',
}
STAGES[37] = {
    'smako-greek-tsouxti-mani': 'Pasta får nötigt brynt smör, smulad feta och separat stekt ägg med fast gula. Skild från carbonaras äggemulsion, tomatpasta och oststuvning. Uttrycklig fetaversion med stöd i receptförfattarens egna alternativ på https://www.greekcookingmadeeasy.com/allrecipes/greek-sizzling-tsouhti-pasta-with-charred-butter-grated-cheese-and-fried-eggs-from-mani . Fetan bryns inte som torr myzithra; egen dos och justerad arbetsmetod framgår.',
}
STAGES[38] = {
    'smako-italian-pasta-patate-provola': 'Torr kort pasta kokas direkt med potatistärningar och binds av deras stärkelse, sedan vänds ost i utanför värmen. Skild från avrunnen pasta med ragù, ugnsgratäng och boveteband med kål. Öppet orökt mozzarellaalternativ finns hos receptförfattaren https://www.gennarino.org/wordpress2/ricetta-della-pasta-e-patate/ . Ingen provolaidentitet eller rökarom påstås.',
}
STAGES[39] = {
    'smako-indian-chicken-65-pannstekt': 'Yoghurtmarinerade kycklingbitar får ett tunt stärkelsehölje och pannsteks till ris. Skild från tandooriugnskyckling, tomatgrytor och nötpanerad kyckling. Uttrycklig pannversion utan curryblad; författaren anger bladen som valfria på https://mistyricardo.com/chicken-65-recipe/ . Paprika och chili används i Genevieve Taylors egen version https://curryforchange.org.uk/recipes/chicken-65 . Vår dos paprika/cayenne och pannmetod är separat granskade, utan anspråk på samma arom eller hetta.',
}
STAGES[40] = {
    'smako-thai-pad-prik-king-tofu': 'Tofu och gröna bönor steks med röd currypasta till torr kryddbeläggning utan kokosmjölk. Skild från kokosgryta, basilikawok och tofu i jordnötssås. Granskad version med separat infusion av KRUA torkade makrutlimeblad, som importören uttryckligen anger för curry och wok på https://achaulien.se/products/dried-lime-leaves-12-x-25g-krua . Egen torr dos 1 g ersätter 4 g färska blad, utan omräkningsfaktor eller lika arom. Bladen silas bort; överförd näring är okänd.',
}
STAGES[41] = {
    'smako-mexican-chiles-en-nogada': 'Rostade paprikahalvor fylls med fruktig fläskfärs och serveras med kall valnötssås och granatäpple. Skild från risfyllda tomater och tomatsåsgratinerad paprika. Öppet milt paprikaalternativ till poblano, som stöds av receptförfattaren https://stefangourmet.com/2019/12/20/chile-relleno-en-nogada-stuffed-chile-with-walnut-sauce-and-pomegranate/ . Vår valfria paprikafärg, halvering och dos är egen granskad anpassning, inte samma smak eller påstående om traditionella flaggfärger.',
}
STAGES[42] = {
    'smako-swedish-polsa': 'Finhackat kokt nötkött och lever blandas med korngryn och stekt lök till skedbar pölsa, med potatis och rödbetor. Skild från bakad korvkaka med ägg, leverpastej och potatisbaserad lapskojs. Nötkött och nötlever utan obligatoriskt hjärta stöds av ICA-kökets egen metod https://www.ica.se/recept/polsa-729947/ och Coops allmänna kokta köttalternativ https://www.coop.se/recept/polsa/ . Vår särskilda högrevsdos och grossa ungnötslever är nya granskade insatser, inte hjärt-/leveralias eller lika ätliga mängder.',
}
STAGES[43] = {
    'smako-indian-pindi-chole': 'Te-kokta mörka kikärtor vänds torra i syrlig kryddbeläggning till handgräddade bröd. Skild från tomatbaserad chana masala, yoghurtsjudna kikärtor och bönsoppa. Egen kryddblandning stöds av författarens metod https://www.padhuskitchen.com/2015/02/pindi-chole-recipe-how-to-make-pindi.html och citron i stället för amchur anges av författaren https://www.spicingyourlife.com/how-to-make-pindi-chole/ . Vår blandning och citrondos är separat granskade; inget identiskt cholemasala- eller mangopulver påstås.',
}
STAGES[44] = {
    'smako-indian-chivda': 'Krispig kryddad fling- och nötblandning som torrt mellanmål, skild från gröt, yoghurtflingor och söta kakor. Cornflakes-version med färdiga frukostflingor och varsam pannvändning stöds av författaren https://www.cookwithmanali.com/cornflakes-chivda/ . Curryblad är valfria i Coles köks version https://www.coles.com.au/recipes-inspiration/recipes/chivda . Vår milda gurkmeja/socker/salt-kryddning och doser bevarar originalutkastets variantidé; inget påstående om samma risflingor eller identisk smak.',
}
STAGES[45] = {
    'smako-thai-khua-kling': 'Torrstekt fläskfärscurry utan kokosmjölk eller tillsatt olja, med citrongräs och ris; skild från såsig röd curry och basilikawok. Författaren https://hungryinthailand.com/khua-kling/ anger uttryckligen röd currypasta som alternativ och använder vatten som sedan kokas bort. Vår torra makrutinfusion och grossa citrongräsdos är egna granskade anpassningar. Ingen identisk sydthailändsk pastasmak eller färsk-torr-omräkning påstås.',
}
STAGES[46] = {
    'smako-mexican-arroz-tumbada': 'Två ytterligare nivåer av den buljongrika fisk-/skaldjursrisgrytan, med vitlök/jalapeño och morot/selleri/lime. Uttrycklig korianderversion utan epazote stöds av receptförfattaren https://mysliceofmexico.ca/2025/02/06/arroz-a-la-tumbada-a-rice-and-seafood-mish-mash/ som använder koriander och gör epazote valfri. Ny dos och genomkokning av fryst ört, inte samma örtidentitet eller arom.',
}
SELECTED_VARIANTS[46] = {'smako-mexican-arroz-tumbada': {'standard', 'extended'}}
STAGES[47] = {
    'smako-mexican-papadzules': 'Mjuka majstortillas fylls med hackat kokt ägg och täcks med pumpakärnssås plus separat tomatsås; skild från ostgratinerade enchiladas och chilaquiles. Barilla Foundations eget recept anger koriander som alternativ till epazote: https://fondazionebarilla.com/en/recipes-archive/papadzules/ . Vår dos 20 g fryst koriander, åtta hela råa ägg och 400 g färdiga majstortillas är uttryckliga nya receptinsatser, inte omräkningsfaktorer.',
}
STAGES[48] = {
    'smako-indian-vada-pav': 'Kikärtsmjölsdoppad mosad potatis steks i grunt oljebad och läggs i mjukt bröd med separat torr kokos-vitlökschutney; skild från aloo tikki utan frityrsmet och grönsaksburgare. Dan Toombs anger mjuka hamburgerbröd https://greatcurryrecipes.net/2018/04/30/vada-pav/ och Rohit Ghai mjuka brödrullar https://www.greatbritishchefs.com/recipes/vada-pav-recipe . Vår uttryckliga Pågen-version har ny gramdos och behåller originalets enkla kryddning; syskon med curryblad är fortsatt blockerade.',
}
SELECTED_VARIANTS[48] = {'smako-indian-vada-pav': {'simple'}}
STAGES[49] = {
    'smako-indian-kosha-mangsho': 'Lamm i mörk reducerad lök-yoghurtmasala, utan tomat; skild från fänkålsdominerad rogan josh och rinnig curry. Uttryckligt alternativ med lamm och neutral olja stöds av Shinta https://carameltintedlife.com/203/ . Benfri lammstek och sjudning följd av koncentrerad reduktion stöds även av Lee Jackson https://www.cookeatworld.com/kosha-mangsho-bengali-lamb-curry/ . Doser och kryddvarianter kommer från leveransen, medan köttbasis och metod är egna angivna anpassningar.',
}
STAGES[50] = {
    'smako-indian-recheado-makrill': 'Vinägerkryddpasta mellan två fiskfiléer steks i panna och serveras med ris; skild från såsig fiskcurry, kokosfisk och panerad fisk. Uttrycklig laxversion med rökt paprika. Kocken Tony Coelho anger både lax och rökt paprika som alternativ i sitt eget recheadorecept https://beta.kuwaittimes.com/article/13274/lifestyle/art-fashion/whats-cooking-in-our-kitchens/ . Ingen makrill- eller kashmirchiliidentitet påstås; originalet bevaras.',
}
STAGES[51] = {
    'smako-indian-undhiyu-vardagsversion': 'Fyllda auberginebitar och rotfrukter ångkokas med formade kikärtsmjölsdumplingar ovanpå, i grov kokos-örtmasala. Skild från slät grönsakscurry och separat friterad pakora. Uttryckliga spenat-muthiya ersätter methi-muthiya; Dassana Amit beskriver spenat som eget muthiyagrönt i https://www.vegrecipesofindia.com/methi-muthia-steamed-methi-muthia-fried/ . Bockhornsklöverns smak påstås inte, och frön används inte som bladalias.',
}
STAGES[52] = {
    'smako-italian-tiella-barese': 'Ris och tunna potatisskivor bakas lagrade med musselkött och tomat; skild från omrörd risotto och buljongrik arroz a la tumbada. Skalfri tiella finns i Miria Onestas eget recept https://www.dueamicheincucina.it/2020/06/riso-patate-e-cozze-ricetta-tiella-barese.html . Vår frysta produkt, nya dos 400 g och lagrade pecorino är uttryckliga anpassningar; inget skalutbyte antas.',
}
STAGES[53] = {
    'smako-italian-zuppa-valpellinentze': 'Torkat bröd varvas med kål, egen grönsaksbuljong och smält ost och gratineras; skild från öppen brödsoppa, brödsallad och krutonger som tillbehör. Uttrycklig Gruyère- och vitkålsversion. Emily anger både Gruyère och vanlig grön kål som alternativ i https://www.insidetherustickitchen.com/zuppa-alla-valpellinese/ . Vår svenska surdegsfralla, grönsaksbas och vätskedos är öppet granskade, inte samma fontina/savojkål eller den lokala originalrätten.',
}
STAGES[54] = {
    'smako-indian-vada-pav': 'Standardvarianten behåller separat senapsfrö-ingefärsfräs, potatisfyllning, kikärtssmet och torr kokos-vitlökschutney. Egen öppet namngiven version utan curryblad, inte ett påstående om samma arom. Raks Anands tidigare indexerade receptkort på https://rakskitchen.net/vada-pav-recipe-indian-snack-recipes/ angav curryblad som valfria; den nu öppnade uppdaterade sidan listar dem. Utelämningen är vår uttryckliga innehållsbedömning, inte en nuvarande källinstruktion. Svenskt mjukt hamburgerbröd enligt steg 48; utökad variant med tamarind behöver separat mängdbasis.',
}
SELECTED_VARIANTS[54] = {'smako-indian-vada-pav': {'standard'}}
STAGES[55] = {
    'smako-thai-woon-kati': 'Två gelélager med agar: klar sockerbas och saltad kokosmjölk, kylda och skurna. Skild från ångade stärkelselager, tapiokapärlor och fruktsorbet. Talard Thais eget recept https://talardthai.com/coconut-milk-jelly/ anger pandan som valfri arom. Här anges tydligt utan pandan, utan att tillföra färg eller falskt identitetsalias. Originalets agar-, socker- och kokosdoser behålls; 120 ml direkt processvatten ersätter den avsedda slutvolymen efter infusion.',
}
STAGES[56] = {
    'smako-thai-kluai-buat-chi': 'Samma varsamt sjudna banan i söt-salt kokosmjölk som enkelversionen, nu med leveransens meningsfulla rostade kokos- och sesamtopping. Pandan utelämnas öppet, inte ersatt av identisk arom. Receptutgivaren anger valfri pandan i https://talardthai.com/bananas-in-coconut-milk/ . Övriga matdoser bevaras; ingen dublett av en ny grundrätt skapas.',
}
SELECTED_VARIANTS[56] = {'smako-thai-kluai-buat-chi': {'extended'}}
STAGES[57] = {
    'smako-mexican-cochinita-pibil': 'Citrusmarinerat fläsk tillagas länge under tätt lock och rivs i hela sitt saftiga spad, med separat limesyrad rödlök och mjuka majstortillas. Skild från chilorios ancho-vinägerpasta och avslutande torrstekning. Uttrycklig paprikaversion i pibilstil utan achiote; Cocina de Addys egen videobeskrivning https://www.youtube.com/watch?v=KopKSu9oFR4 anger söt paprika som alternativ. Även Milk Streets eget recept https://www.177milkstreet.com/recipes/dutch-oven-cochinita-pibil-tacos beskriver paprikabaserad ersättningspasta. Här granskas en egen dos 12 g paprikapulver; samma annattosmak eller traditionell bananblads-/jordugnsteknik påstås inte.',
}
STAGES[58] = {
    'smako-mexican-tacos-al-pastor': 'Mycket tunna marinerade fläskskivor rostas glest vid hög ugnsvärme med separat ananas och hackas till mjuka majstacos; skild från chilorios förkokning/torrstekning och pibilstilens tre timmar under tätt lock. Rick Bayless egen https://www.rickbayless.com/recipe/pastor-style-tacos/ använder ancho, tillåter mald chili och anger achiote som rekommenderad men inte nödvändig. Här behålls leveransens öppna ugnsanpassning, 25 g mald ancho ersätter guajillo och achiote utelämnas synligt. Färdiga majstortillas och utökad färdig tomatillosalsa har nya uttryckliga doser; inte samma råvaror eller restaurangens trompo.',
}
STAGES[59] = {
    'smako-indian-vada-pav': 'Utökad vada pav behåller standardens senapsfrö/ingefära och separata sötsyrliga dadelchutney. Samma öppna bröd-/utan-currybladsanpassning som steg 54. Det redan granskade tamarindkoncentratet i ml används som egen ny dos 20 ml i stället för 30 g pasta; ingen ny produktkälla, densitet eller gram/ml-konvertering. Alla 60 g urkärnade dadlar, 15 g koriander och 25 ml limejuice behålls; fryst koriander genomkokas i chutneyn.',
}
SELECTED_VARIANTS[59] = {'smako-indian-vada-pav': {'extended'}}
STAGES[60] = {
    'smako-thai-hor-mok-pla': 'Ångad stannad fisk-äggkräm på kål bevaras. Två tydligt namngivna örtalternativ använder vanlig basilika och 1 g torkade makrutblad som silas ur fiskkomponentens kokosmjölk före kylning och äggblandning. Pailin Chongchitnant anger italiensk basilika som alternativ och torra blad för curry: https://hot-thai-kitchen.com/thai-ingredients/ . Hennes haw mok beskriver samma skål-/ångteknik och paprika som garnering: https://hot-thai-kitchen.com/haw-mok-red-curry-custard/ . Egna doser, ingen likvärdig arom eller färsk-torr-faktor. Utökad behåller separat kokoskräm och limegurka; 20 g röd paprika ersätter 5 g färsk chili. Okänd extraktion och kokosmjölksförlust i silade blad redovisas.',
}
SELECTED_VARIANTS[60] = {'smako-thai-hor-mok-pla': {'standard', 'extended'}}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check_process_water(recipes):
    """Stop new local stages before issue when explicit water would stay fixed."""
    pattern = re.compile(r'(?<![\d,.])(\d+(?:[,.]\d+)?) ml (?:(?:ljummet|hett|kokande|kallt|nytt kallt|sjudande|sparat|stärkelserikt) )?(?:dricksvatten|vatten|kokvatten)\b')
    for recipe in recipes:
        for step in recipe.design.steps:
            tokens = {token for token, _ in (step.scalable_amounts or ())}
            for match in pattern.finditer(step.text):
                if match.group(1) + ' ml' not in tokens:
                    raise ValueError(f'{identity(recipe)} {step.id}: write explicit process water as N ml vatten so it scales')


def insert_step(row, index, step):
    """Insert a one-based step while preserving the original dependency graph."""
    for later in row['steps'][index - 1:]:
        later['after'] = [n + 1 if n >= index else n for n in later.get('after', [])]
    for process in row.get('unmeasured_processes', []):
        if process['step'] >= index:
            process['step'] += 1
    row['steps'].insert(index - 1, step)


def rename_ingredient(row, old, new):
    for component in row['components']:
        for item in component['ingredients']:
            if item['name'] == old:
                item.update(name=new, label=new)
                item.pop('requirements', None)
    for step in row['steps']:
        step['uses'] = [new if n == old else n for n in step['uses']]


def prepend_thaw(row, name, minutes, purpose):
    from admit_expansion_20261101 import prepend_steps

    prepend_steps(row, [
        {'text': f'Väg upp fryst {name} i ett täckt kärl i kylskåp. Behåll all vätska.', 'uses': [name], 'minutes': 1, 'after': []},
        {'text': f'Tina helt i kylskåp enligt förpackningen. Planera {minutes} minuter och förläng vid behov tills ingen iskärna återstår. {purpose}', 'uses': [name], 'minutes': minutes, 'passive': True, 'after': [1]},
    ])


def mark_process(row, index, ingredients, operation, description):
    step = row['steps'][index - 1]
    step['uses'] = list(dict.fromkeys([*step['uses'], *ingredients]))
    row.setdefault('unmeasured_processes', []).append({
        'step': index, 'ingredients': ingredients, 'operation': operation, 'description': description})


def correct(row, vocabulary):
    base, changes = row['base_id'], []
    if base.endswith('tacos-al-pastor'):
        rename_ingredient(row,'guajillochili','anchochili')
        rename_ingredient(row,'masa harina','majstortillas')
        rename_ingredient(row,'tomatillo','salsa verde av tomatillo')
        row['name']='Tacos al pastor i ugn – ancho utan achiote – '+{'simple':'enkel','standard':'med apelsin och kryddor','extended':'med tomatillosalsa'}[row['variant_id']]
        row['flavor']=['ancho','vinäger','rostad ananas']
        row['side']='färdiga mjuka majstortillas'
        row['notes']='Granskad ugnsversion med 25 g mald Ancho Style-chili i stället för 25 g guajillo; 30 g achiotepasta utelämnas uttryckligen. Annan chilismak och utan achiotearom. 400 g färdiga mjuka majstortillas ersätter 280 g masa harina, degvatten och 2 g tortillassalt. Utökad använder 250 g färdig tomatillosalsa i stället för 300 g rå tomatillo och dess 2 g extra salt; löken, vitlöken och koriandern behålls och genomhettas. Alla köttråvaror, ananas, marinad, plåtsky och fett serveras. Inte provlagad.'
        for c in row['components']:
            has_tortilla=any(i['name']=='majstortillas' for i in c['ingredients'])
            has_salsa=any(i['name']=='salsa verde av tomatillo' for i in c['ingredients'])
            c['ingredients']=[i for i in c['ingredients'] if i['name']!='achiotepasta' and not (i['name']=='salt' and (has_tortilla or has_salsa))]
            for i in c['ingredients']:
                if i['name']=='anchochili':i['label']='Mald Ancho Style-chili'
                if i['name']=='majstortillas':i.update(quantity=400,form='as_sold',label='Färdigbakade mjuka majstortillas')
                if i['name']=='salsa verde av tomatillo':i.update(quantity=250,form='as_sold',label='Färdig kryddad tomatillosalsa, ny dos')
                if i['name']=='ananas':i['label']='Frysta ansade ananasbitar, hela mängden och saften används'
        extra=row['variant_id']!='simple'
        row['steps']=[
            {'text':'Mixa hela mängden mald anchochili med 20 ml vatten, äppelcidervinäger, färsk eller fryst hackad vitlök och köttets salt'+(' samt oregano, spiskummin och apelsinjuice' if extra else '')+'. Använd helt tinad benfri fläskkarré, väg rå ätlig mängd och skär tre till fyra millimeter tunna skivor tvärs fibrerna. Vänd med hela marinaden och täck. Ingen chili silas eller blötläggs separat.','uses':['anchochili','äppelcidervinäger','vitlök','salt','fläskkarré']+(['oregano','spiskummin','apelsinjuice'] if extra else []),'minutes':12},
            {'text':'Marinera fyra timmar i kylskåp vid högst 4 °C, avskilt från färdig mat.','uses':['fläskkarré'],'minutes':240,'passive':True},
        ]
        if row['variant_id']=='extended':
            row['steps'].append({'text':'Skala löken, väg ätlig mängd och hacka. Lägg i liten kastrull med 40 ml vatten och salsans färska eller frysta hackade vitlök. Sjud under omrörning cirka fem minuter. Tillsätt den uppvägda färdiga tomatillosalsan och all fryst koriander; sjud minst tre minuter eller längre enligt förpackningen. Mixa slätt med allt spad. Salsan innehåller redan kryddor och salt; tillsätt inget extra salt. Håll varm.','uses':['gul lök','vitlök','salsa verde av tomatillo','koriander'],'minutes':11})
        row['steps'].extend([
            {'text':'Värm ugnen till 230 °C. Fördela fläskskivorna glest i ett lager på ugnståliga plåtar med kanter, med hela marinaden tunt över. Lägg de tinade ananasbitarna bredvid och häll all fruktsaft på plåtarna. Använd fler plåtar eller omgångar om maten annars staplas.','uses':['fläskkarré','ananas','anchochili'],'minutes':6},
            {'text':'Rosta under tillsyn cirka arton minuter, byt plats på plåtarna halvvägs och kontrollera noga mot slutet. Kött och marinad ska vara helt genomlagade, minst 72 °C i de tjockaste skivorna, och ananasen genomhet med brynta kanter; förläng vid behov. Håll färdiga omgångar varma över 60 °C.','uses':['fläskkarré','ananas'],'minutes':18},
            {'text':'Lyft kött och ananas till ett fat. Skrapa all plåtsky och allt fett i en liten kastrull; använd sammanlagt 20 ml vatten för att lossa kvarvarande sky. Koka upp och reducera under omrörning cirka fem minuter till tjockare sås. Ingen sky eller fett hälls bort. Hacka kött och ananas grovt och vänd med hela såsen.','uses':['fläskkarré','ananas'],'minutes':8},
            {'text':'Väg de färdiga mjuka majstortillorna, värm kort i torr panna och fördela jämnt mellan portionerna. Fyll med allt kött, ananas och sky'+(' och servera all tomatillosalsa till' if row['variant_id']=='extended' else '')+'.','uses':['majstortillas','fläskkarré','ananas']+(['salsa verde av tomatillo'] if row['variant_id']=='extended' else []),'minutes':5},
        ])
        prepend_thaw(row,'ananas',120,'Behåll hela den ansade uppvägda frukten och all saft; använd allt vid rostningen.')
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit oven-pastor adaptation with ground ancho 25 g instead of guajillo and no achiote; use 400 g ready corn tortillas instead of masa dough, remove dough salt/water. Extended salsa is an explicit 250 g prepared product plus retained onion/garlic/coriander with no extra salsa salt. Plan frozen-pineapple thaw, retain and boil all meat marinade/fruit juice/pan fat; four-hour marinade and supervised thin-slice roast remain distinct from slow braises.')
    if base.endswith('cochinita-pibil'):
        rename_ingredient(row,'achiotepasta','paprikapulver')
        rename_ingredient(row,'tortillas','majstortillas')
        row['name']='Citrusbräserat fläsk i pibilstil – paprikaversion – '+{'simple':'enkel','standard':'med oregano och spiskummin','extended':'med bönor och avokado'}[row['variant_id']]
        row['family']='citrusbräserat fläsk i pibilstil'
        row['flavor']=['paprika','citrus','rödlök']
        row['notes']='Uttrycklig paprikaversion utan achiote. 12 g sött paprikapulver ersätter 35 g achiotepasta som ny författardos; inte samma arom, salt eller omräkningsfaktor. Övriga matmängder bevaras. Apelsin och lime är redan utkastets alternativ till pomerans, och tätt lock dess alternativ till jordugn/bananblad. Hela köttspadet, allt utsmält fett och lökens lag serveras. Standard behåller vitlök, oregano och spiskummin; utökad dessutom bönor och avokado. Inte provlagad.'
        for c in row['components']:
            if c['id']=='flask':c['name']='Citrus- och paprikabräserat fläsk'
            for i in c['ingredients']:
                if i['name']=='paprikapulver':i.update(quantity=12,form='dry',role='flavour',label='Sött paprikapulver, ny dos utan achiote')
                if i['name']=='majstortillas':i['label']='Mjuka färdigbakade majstortillas'
        extra=row['variant_id']!='simple'
        row['steps']=[
            {'text':'Använd helt tinad benfri fläskkarré. Väg rå ätlig mängd och skär cirka sex centimeter stora bitar. Rör ut paprikapulvret i apelsinjuice och köttdelens limejuice och salt.'+(' Rör ner färsk eller fryst hackad vitlök, oregano och spiskummin.' if extra else '')+' Vänd köttet i all marinad och täck.','uses':['fläskkarré','paprikapulver','apelsinjuice','limejuice','salt']+(['vitlök','oregano','spiskummin'] if extra else []),'minutes':10},
            {'text':'Marinera två timmar i kylskåp, högst 4 °C. Håll kött och marinad åtskilda från råa tillbehör.','uses':['fläskkarré'],'minutes':120,'passive':True},
            {'text':'Värm ugnen till 160 °C. Lägg kött och all marinad i en ugnssäker gryta, tillsätt 100 ml vatten och täck tätt med lock.','uses':['fläskkarré','paprikapulver'],'minutes':5},
            {'text':'Tillaga i ugnen under tätt lock två timmar.','uses':['fläskkarré'],'minutes':120,'passive':True},
            {'text':'Kontrollera att bottnen inte kokat torr. Tillsätt vid behov 100 ml vatten och sätt tillbaka locket.','uses':['fläskkarré'],'minutes':2},
            {'text':'Fortsätt i ugnen under lock ytterligare cirka sextio minuter.','uses':['fläskkarré'],'minutes':60,'passive':True},
            {'text':'Kontrollera att köttet faller isär lätt med gaffel och är helt genomlagat, minst 72 °C i tjockaste biten. Förläng annars tillagningen under lock. Behåll allt fett och spad. Ta ut grytan och håll täckt. Skala rödlöken, väg den ätliga mängden och skiva tunt. Krama med lökdelens limejuice och salt; behåll all lag.','uses':['fläskkarré','rödlök','limejuice','salt'],'minutes':8},
            {'text':'Låt köttet vila tio minuter i spadet medan löken drar i sin lag.','uses':['fläskkarré','rödlök'],'minutes':10,'passive':True},
            {'text':'Dra isär köttet med två gafflar och blanda med hela det heta paprika-citrusspadet och allt fett. Ingen sky silas eller hälls bort. Värm de mjuka majstortillorna kort i torr panna; förvara varmt under lock.','uses':['fläskkarré','majstortillas'],'minutes':8},
        ]
        if row['variant_id']=='extended':
            row['steps'].append({'text':'Väg redan kokta svarta bönor efter avrinning. Värm med 30 ml vatten och all fryst hackad koriander, sjud minst tre minuter eller längre enligt förpackningen och behåll allt spad. Lägg den helt tinade avokadon med all sin saft bredvid.','uses':['svarta bönor','koriander','avokado'],'minutes':7})
            prepend_thaw(row,'avokado',120,'Använd alla ansade frysta avokadobitar och all saft som tillbehör.')
        row['steps'].append({'text':'Fördela hela köttet och allt spad, tortillorna, rödlöken med all lag och eventuella bönor/avokado jämnt mellan portionerna.','uses':[],'minutes':2})
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit pibil-style paprika/citrus adaptation: 12 g sweet paprika replaces 35 g achiote paste without equivalence; same 850 g pork and all other food doses retained, tortillas restricted to soft corn. Preserve 2 h cold marinade and 3 h covered oven braise with separate active liquid/tenderness checks. Serve every sauce/fat/onion liquid; extended frozen coriander boils with beans and avocado thaws with all juice.')
    if base.endswith('woon-kati'):
        for component in row['components']:
            component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'pandanblad']
            component['name'] = component['name'].replace('pandan', 'klar gelé').replace('Pandan', 'Klar gelé')
        row['name'] = 'Woon kati – tvålagers kokosgelé utan pandan – ' + ('enkel' if row['variant_id']=='simple' else 'med mango och lime')
        row['flavor'] = ['kokos', 'söt-salt'] + (['mango', 'lime'] if row['variant_id']=='extended' else [])
        row['notes'] = 'Uttryckligen utan pandan och dess arom. Klar socker-agarbas med separat kokosmjölkslager; originalets 1,6 g agar, 100 ml kokosmjölk, 20 g socker och 0,2 g salt per portion bevaras. 120 ml vatten används direkt i klara lagret i stället för 160 ml till bladinfusion som sedan skulle mätas till 120 ml. Ingen infusion eller bladförlust återstår. Utökad variant behåller 100 g mango och 8 ml limejuice. Inte provlagad.'
        row['steps'] = [
            {'text':'Mät upp 120 ml vatten i en liten kastrull. Vispa ner hälften av agarpulvret. Koka upp under omrörning och koka försiktigt tre minuter eller längre enligt förpackningen tills agarn är helt löst. Rör ner hälften av sockret tills det lösts. Häll hela blandningen i en liten värmetålig form.','uses':['agar agar','strösocker'],'minutes':6},
            {'text':'Låt det klara lagret stå cirka tio minuter tills ytan precis har satt sig men fortfarande är varm.','uses':[],'minutes':10,'passive':True},
            {'text':'Vispa resten av agarn i kokosmjölken med 40 ml vatten. Koka upp under omrörning och småkoka tre minuter eller längre enligt förpackningen tills agarn är helt löst. Rör ner resten av sockret och saltet. Låt bara svalna kort så blandningen fortfarande är flytande. Kontrollera det klara lagret: ytan ska bära men vara varm och lite klibbig. Häll kokoslagret försiktigt över baksidan av en sked ovanpå det klara lagret.','uses':['agar agar','kokosmjölk','strösocker','salt'],'minutes':8},
            {'text':'Låt de båda lagren sätta sig och svalna cirka tjugo minuter.','uses':[],'minutes':20,'passive':True},
            {'text':'Flytta formen till kylskåp och täck när den inte längre avger ånga.','uses':[],'minutes':1},
            {'text':'Kyl minst sextio minuter tills gelén är helt kall och stadig; förläng vid behov.','uses':[],'minutes':60,'passive':True},
        ]
        if row['variant_id']=='extended':
            row['steps'].append({'text':'Dela vid behov de tinade mangobitarna och vänd med limejuice och all fruktsaft. Skär gelén i små bitar och servera hela mängden tillsammans med all mango och saft.','uses':['mango','limejuice','kokosmjölk','agar agar'],'minutes':4})
            prepend_thaw(row,'mango',120,'Behåll hela mängden och all fruktsaft till serveringen; vikten avser fryst ansat fruktkött utan skal eller kärna.')
        else:
            row['steps'].append({'text':'Skär eller skeda upp hela den kalla gelén och servera.','uses':['kokosmjölk','agar agar'],'minutes':2})
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit no-pandan version of two-layer agar coconut jelly. Preserve all food amounts except removed 8 g leaves; use intended final 120 ml clear-layer water directly, retain separate 40 ml coconut-layer water, boil agar before sugar and separate fridge transfer from cooling. Extended thawed mango retains all juice and plans two hours.')
    if base.endswith('zuppa-valpellinentze'):
        rename_ingredient(row,'fontina','gruyère')
        rename_ingredient(row,'savojkål','vitkål')
        rename_ingredient(row,'bröd','surdegsfralla')
        row['primary']='vitkål och gruyère'
        row['name'] += ' – med gruyère, vitkål och surdegsfralla'
        row['notes']='Granskad bröd- och kålgratäng med 220 g inköpt Gruyère före kantputsning i stället för fontina, 600 g ansad vitkål och 300 g surdegsfralla. Inga identiska ostar eller kålformer påstås. Brödet torkas i ugnen före lagring och allt grönsaksspad används. Initialt kokvatten minskas uttryckligen från 1000 till 400 ml för en saftig gratäng utan bortkastad buljong. Eventuell ostkant har okänt utbyte. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name']=='gruyère':i['label']='Gruyère, inköpt mängd före borttagning av kant'
                if i['name']=='surdegsfralla':i['label']='Svensk surdegsfralla, uppvägd före torkning'
                if i['name']=='broccoli':i.update(form='as_sold',label='Frysta naturella broccolibuketter')
        original=copy.deepcopy(row['steps'])
        extra=row['variant_id']!='simple'
        row['steps']=[
            {'text':'Sätt ugnen på 150 °C. Väg surdegsfrallorna före torkning och skiva centimetertjockt. Lägg på en torr plåt; ingen extra olja används.','uses':['surdegsfralla'],'minutes':4},
            {'text':'Torka brödskivorna i ugnen cirka tjugo minuter. De ska bli torra utan att brännas.','uses':['surdegsfralla'],'minutes':20,'passive':True},
            {'text':'Ta ut brödet och höj ugnen till 210 °C. Väg osten före eventuell kantputsning, avlägsna hård kant och riv resten grovt utan att fylla på extra ost. Ta bort kålens hårda rotstock och ytterblad, väg den ätliga mängden och strimla tunt. Skala lök och morot, ansa selleri, väg ätliga mängder och tärna smått.'+(' Väg färsk eller fryst hackad vitlök.' if extra else ''),'uses':['surdegsfralla','gruyère','vitkål','gul lök','morot','selleri']+(['vitlök'] if extra else []),'minutes':13},
            {**original[1], 'text':original[1]['text'].replace('1000 ml vatten','400 ml vatten')},
            {'text':'Sjud kålen och övriga grönsaker under lock cirka tjugo minuter.','uses':['vitkål','gul lök','morot','selleri'],'minutes':20,'passive':True},
            {'text':'Kontrollera att kålen är mjuk. Är den fortfarande hård, tillsätt vid behov 100 ml vatten och förläng sjudningen. Behåll alla grönsaker och allt spad. Smörj en ugnsform med en del av återstående smör. Varva torkat bröd, grönsaker och ost; avsluta med ost. Fördela allt spad jämnt och klicka resten av smöret ovanpå.'+(' Strö över muskot.' if extra else ''),'uses':['surdegsfralla','vitkål','gruyère','smör']+(['muskot'] if extra else []),'minutes':9},
            {**original[4]},
            {'text':'Kontrollera att mitten är genomhet och ytan gyllene; förläng gräddningen vid behov. Behåll och servera hela formens innehåll.','uses':['surdegsfralla','gruyère','vitkål'],'minutes':2},
        ]
        if row['variant_id']=='extended':
            row['steps'].extend([
                {'text':'Väg frysta broccolibuketter utan att tina eller sila. Vänd med tillbehörets olivolja på en plåt. Håll brödformen täckt och varm över 60 °C medan broccolin rostas.','uses':['broccoli','olivolja'],'minutes':3},
                {'text':'Rosta broccolin i den varma ugnen cirka tjugotvå minuter eller längre enligt förpackningen.','uses':['broccoli'],'minutes':22,'passive':True},
                {'text':'Kontrollera mjuk, helt genomhet broccoli. Vänd med citronjuicen och all kvarvarande plåtsky och servera med den varma gratängen.','uses':['broccoli','citronjuice','olivolja'],'minutes':3},
            ])
        else:row['steps'].append({'text':'Fördela den varma gratängen och all dess sky mellan portionerna.','uses':[],'minutes':2})
        row['unmeasured_processes']=[]
        mark_process(row,3,['gruyère'],'trim_before_cooking','Gruyère vägs före eventuell kantputsning. Kantens andel och kvarvarande ätlig vikt är inte uppmätta.')
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit Gruyere/white-cabbage/sourdough-roll version, retaining numerical food doses but measuring cheese before rind trimming with unknown yield. Dry bread 20 minutes, then cook cabbage with 400 ml initial water rather than discard part of a litre. All vegetable broth/butter is layered and served. Extended frozen broccoli is oven-roasted with all oil/juice, not treated as fresh raw heads.')
    if base.endswith('tiella-barese'):
        rename_ingredient(row,'blåmusslor med skal','blåmusselkött utan skal')
        rename_ingredient(row,'pecorino romano','lagrad pecorino')
        row['primary']='blåmusselkött utan skal'
        row['name']+=' – med fryst musselkött utan skal'
        row['equipment']=['ugn','djup ugnsform med lock','kanna','rivjärn','termometer']
        row['notes']='Granskad skalfri tiella med 400 g fryst musselkött i stället för 1600 g levande musslor med skal. Ny kulinarisk dos, ingen faktor för skalutbyte. Standard och utökad använder 45 g inköpt lagrad pecorino före eventuell kantputsning. Tolv timmars kylupptining ingår. All vätska används i lagren; inga levande musslor öppnas. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name']=='blåmusselkött utan skal':i.update(quantity=400,label='Fryst musselkött utan skal, deklarerad produktvikt')
                if i['name']=='lagrad pecorino':i['label']='Lagrad pecorino, inköpt gramvikt före kantputsning'
        extra=row['variant_id']!='simple'
        row['steps']=[
            {'text':'Väg upp fryst musselkött utan skal i ett täckt kärl i kylskåp. Behåll all vätska.','uses':['blåmusselkött utan skal'],'minutes':1},
            {'text':'Tina helt i kylskåp enligt förpackningen; planera tolv timmar och förläng vid behov.','uses':['blåmusselkött utan skal'],'minutes':720,'passive':True},
            {'text':'Sätt ugnen på 190 °C. Skala potatis och lök, väg rå ätlig mängd och skiva cirka två millimeter tunt. Hacka tomaten och väg färsk eller fryst hackad vitlök. Väg riset torrt.'+(' Väg osten före eventuell kantputsning, ta bort hård kant och riv resten utan att fylla på extra ost. Väg fryst hackad persilja.' if extra else ''),'uses':['potatis','gul lök','tomat','vitlök','ris']+(['lagrad pecorino','persilja'] if extra else []),'minutes':12},
            {'text':'Olja en djup form med hälften av tiellans olivolja. Lägg lök och hälften av potatisen i botten, sedan musselkött, ris, tomat och vitlök'+(' samt hälften av persiljan och osten' if extra else '')+'. Täck med resten av potatisen. Tillsätt salt och svartpeppar. Mät upp 850 ml vatten i en kanna; ta bort lika mycket vatten som mängden upptiningsvätska och ersätt med denna. Häll hela blandningen runt kanten. Behåll alla lager och all vätska.','uses':['olivolja','gul lök','potatis','blåmusselkött utan skal','ris','tomat','vitlök','salt','svartpeppar']+(['lagrad pecorino','persilja'] if extra else []),'minutes':10},
            {'text':'Fördela resten av olivoljan över ytan'+(' tillsammans med ströbröd och resten av osten och persiljan' if extra else '')+'. Täck formen med ugnssäkert lock och sätt in i ugnen.','uses':['olivolja']+(['ströbröd','lagrad pecorino','persilja'] if extra else []),'minutes':2},
            {'text':'Baka täckt i trettiofem minuter.','uses':['ris','potatis','blåmusselkött utan skal'],'minutes':35,'passive':True},
            {'text':'Ta av locket och kontrollera vätskan utan att röra om lagren. Tillsätt vid behov 100 ml vatten om det torkat innan riset mjuknat.','uses':['ris','potatis'],'minutes':2},
            {'text':'Baka ytterligare tjugo minuter utan lock.','uses':['ris','potatis','blåmusselkött utan skal'],'minutes':20,'passive':True},
            {'text':'Kontrollera att ris och potatis är helt mjuka, mitten minst 75 °C och musselköttet genomhett enligt förpackningen. Förläng annars täckt med 100 ml vatten vid behov. Ta ut formen.','uses':['ris','potatis','blåmusselkött utan skal'],'minutes':2},
            {'text':'Låt formen vila tio minuter.','uses':[],'minutes':10,'passive':True},
        ]
        if row['variant_id']=='extended':row['steps'].append({'text':'Ansa fänkålen, väg den råa ätliga mängden och strimla tunt. Vänd med tillbehörets olivolja och citronjuice; behåll all dressing.','uses':['fänkål','olivolja','citronjuice'],'minutes':5})
        row['steps'].append({'text':'Fördela tiellan mellan portionerna med allt musselkött, ris, potatis och all kvarvarande sky.'+(' Servera fänkålen och all dess dressing till.' if row['variant_id']=='extended' else ''),'uses':[],'minutes':2})
        row['unmeasured_processes']=[]
        if extra:mark_process(row,3,['lagrad pecorino'],'trim_before_cooking','Osten vägs före kantputsning utan antagen ätlig andel.')
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('New 400 g frozen shell-free mussel-meat dose replaces 1600 g live shell-on mussels with no yield equivalence. Retain all thaw liquid within the authored 850 ml total liquid. Keep dry rice/potato layers; separately time lid removal, temperature/softness check and passive rest. Standard/extended use purchased aged pecorino with unknown rind loss; all frozen parsley/garlic bakes through and all oil/juice is served.')
    if base.endswith('undhiyu-vardagsversion'):
        rename_ingredient(row,'bockhornsklöverblad','spenat')
        rename_ingredient(row,'jordnötter','rostade jordnötter')
        row['name']=row['name'].replace('methi-muthiya','spenat-muthiya')
        row['side']='spenat-muthiya'
        row['flavor']=['kokos','koriander','spenat']
        row['notes']='Uttrycklig granskad vardags-undhiyu med spenat-muthiya. 80 g fryst naturell spenat ersätter 80 g färska bockhornsklöverblad; annan grönsak och smak, ingen utbytesfaktor. Spenaten värms och all vätska används i degen. 70 g rostade osaltade jordnötter anges öppet. Grönsaker, kokos-örtmasala och dumplingar ångkokas tillsammans, utan att sila eller kasta någon sky. Inte provlagad.'
        for c in row['components']:
            c['name']=c['name'].replace('Methi-muthiya','Spenat-muthiya')
            for i in c['ingredients']:
                if i['name']=='spenat':i.update(form='as_sold',label='Fryst naturell spenat')
                if i['name']=='rostade jordnötter':i['label']='Rostade osaltade jordnötter'
        original=copy.deepcopy(row['steps'])
        row['steps']=[
            {'text':'Väg fryst naturell spenat och lägg i en liten kastrull med 20 ml vatten. Värm under omrörning tills allt tinat och är genomhett; sjud minst tre minuter eller längre enligt förpackningen. Behåll all vätska. Finhacka eventuella hela blad.','uses':['spenat'],'minutes':7},
            {'text':'Låt spenaten med sin vätska svalna tio minuter så att degen kan hanteras.','uses':['spenat'],'minutes':10,'passive':True},
            {'text':'Arbeta ihop all spenat och vätska med kikärtsmjöl, muthiyans olja och salt samt 25 ml vatten. Degen ska vara fast och formbar; tillsätt vid behov ytterligare 15 ml vatten efter vilan, inte extra mjöl.','uses':['spenat','kikärtsmjöl','rapsolja','salt'],'minutes':4},
            {'text':'Låt degen vila tio minuter medan mjölet suger upp vätskan.','uses':['kikärtsmjöl','spenat'],'minutes':10,'passive':True},
            {**original[1], 'text':original[1]['text'].replace('jordnötter, koriander, vitlök','rostade osaltade jordnötter, fryst hackad koriander, färsk eller fryst hackad vitlök')+' Skala eventuell ingefära och väg efter skalning. All ört- och vitlöksvätska används och genomkokas senare i grytan.'},
            {**original[2], 'text':original[2]['text'].replace('Skala potatisen och dela i grova bitar.','Skala potatisen, väg den råa ätliga mängden och dela i bitar omkring tre centimeter. Ansa och väg auberginen.').replace('Skala och dela sötpotatisen grovt.','Skala sötpotatisen, väg efter skalning och dela i tre centimeter stora bitar.').replace('tolv små avlånga bitar','tre små avlånga bitar per portion, högst två centimeter tjocka')},
            original[3],
            {'text':'Sjud försiktigt under tätt lock tjugo minuter; dumplingarna ska ligga ovanpå grönsakerna.','uses':['potatis','aubergine','spenat','kikärtsmjöl'],'minutes':20,'passive':True},
            {'text':'Skaka grytan försiktigt och kontrollera bottnen utan att röra sönder dumplingarna. Tillsätt vid behov 100 ml vatten.','uses':['potatis','kikärtsmjöl'],'minutes':2},
            {'text':'Sjud ytterligare tjugo minuter under lock.','uses':['potatis','aubergine','spenat','kikärtsmjöl'],'minutes':20,'passive':True},
            {'text':'Kontrollera mjuk potatis och genomkokta dumplingar utan rå mjölkärna; förläng annars sjudningen. Lyft locket och reducera försiktigt vid behov. Fördela alla grönsaker, hela kokosmasalan och tre muthiya per portion med all sky. Ingen olja eller vätska hälls bort.','uses':['potatis','aubergine','kokosflingor','kikärtsmjöl','spenat'],'minutes':8},
        ]
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit spinach-muthiya version: 80 g frozen plain spinach replaces fresh fenugreek leaf, not its aroma or an alias. Heat then retain all spinach liquid in besan dough; total initial process water stays 45 ml split 20/25 ml. Use reviewed roasted unsalted peanuts. Frozen coriander/garlic cook in retained masala; three dumplings per portion and separate active checks preserve scaling and honest waiting time.')
    if base.endswith('kosha-mangsho'):
        rename_ingredient(row, 'getkött', 'benfri lammstek')
        rename_ingredient(row, 'senapsolja', 'rapsolja')
        row['primary'] = 'benfri lammstek'
        row['family'] = 'kosha mangsho i reducerad lök-yoghurtmasala'
        row['name'] = 'Kosha mangsho med benfri lammstek och rapsolja – ' + row['variant_id']
        row['equipment'].append('termometer')
        row['notes'] = 'Uttrycklig lamm- och rapsoljeversion. 800 g inköpt benfri stek före putsning ersätter 800 g ätligt getkött; ingen utbytesfaktor eller samma senapsarom påstås. Upptining 24 timmar och marinering två timmar ingår. Ny metod med brynt lök, 90 minuters varsam sjudning och cirka 15 minuters aktiv reduktion ersätter utkastets långa ständiga bryning. Alla tider är uppskattningar, inte provlagade eller uppmätta; segt kött kräver längre tillagning. All marinad, upptiningsvätska och steksky används, putsförlusten är okänd.'
        for c in row['components']:
            c['name'] = c['name'].replace('getkött', 'lammstek')
            for i in c['ingredients']:
                if i['name'] == 'benfri lammstek': i.update(form='as_sold', label='Benfri lammstek, inköpt vikt före putsning')
        original = copy.deepcopy(row['steps'])
        names = {i['name'] for c in row['components'] for i in c['ingredients']}
        row['steps'] = [
            {'text':'Tina vid behov hela förpackningen benfri lammstek i ett täckt läckagesäkert kärl i kylskåp. Behåll all vätska.','uses':['benfri lammstek'],'minutes':2},
            {'text':'Planera 24 timmars kylupptining, eller längre enligt förpackningen tills ingen iskärna återstår. Redan kylförvarat kött går direkt vidare.','uses':['benfri lammstek'],'minutes':1440,'passive':True},
            {'text':'Väg den angivna inköpta mängden som kött med tillhörande upptiningsvätska före putsning. Spara vätskan kallt. Putsa endast bort grova senor utan att fylla på extra kött. Skär i jämna bitar omkring 2,5 cm. Skala lök och ingefära och väg efter ansning; skiva löken och riv ingefäran. Blanda köttet med hälften av yoghurten, hälften av ingefäran och grytans salt'+(' samt gurkmejan. Väg färsk eller fryst hackad vitlök och spara kallt till stekningen.' if 'vitlök' in names else '.')+' Ställ kött och övriga kylvaror täckta i kylskåp.','uses':['benfri lammstek','gul lök','ingefära','yoghurt naturell','salt']+(['gurkmeja','vitlök'] if 'vitlök' in names else []),'minutes':16},
            original[1],
            {**original[2], 'text':original[2]['text'].replace('senapsoljan','rapsoljan')},
            {**original[3], 'text':original[3]['text'].replace('samt kanel och kardemumma','samt malen kanel och malen kardemumma')+' Häll i all sparad upptiningsvätska och koka upp ordentligt. Allt fett och all marinad stannar i grytan.', 'minutes':17},
            {'text':'Tillsätt 350 ml vatten, rör upp bottenskyn och koka upp. Sänk värmen och lägg på lock.','uses':['benfri lammstek','yoghurt naturell'],'minutes':3},
            {'text':'Sjud försiktigt under lock trettio minuter.','uses':['benfri lammstek'],'minutes':30,'passive':True},
            {'text':'Rör om och kontrollera bottnen. Tillsätt vid behov 100 ml vatten så att det inte bränner.','uses':['benfri lammstek'],'minutes':1},
            {'text':'Sjud ytterligare trettio minuter under lock.','uses':['benfri lammstek'],'minutes':30,'passive':True},
            {'text':('Skala potatisen, väg den råa ätliga mängden och skär i två centimeter stora bitar. Lägg i grytan. ' if 'potatis' in names else '')+'Rör om och kontrollera vätskan; tillsätt vid behov 100 ml vatten.','uses':['benfri lammstek']+(['potatis'] if 'potatis' in names else []),'minutes':5 if 'potatis' in names else 1},
            {'text':'Sjud ytterligare cirka trettio minuter under lock.','uses':['benfri lammstek'],'minutes':30,'passive':True},
            {'text':'Kontrollera att lammet är helt genomlagat och delar sig lätt med gaffel'+(' och att potatisen är mjuk' if 'potatis' in names else '')+'. Förläng annars sjudningen. Ta av locket och reducera under tät omrörning cirka femton minuter tills mörk löksås klär köttet tätt. Skrapa bottnen ofta och sänk värmen om den bränner. Ingen sås eller fett hälls bort.','uses':['benfri lammstek','gul lök','yoghurt naturell']+(['potatis'] if 'potatis' in names else []),'minutes':17},
        ]
        finish = next(n for n,s in enumerate(original) if s['text'].startswith('Rör ner garam masala'))
        row['steps'].extend(original[finish:])
        for s in row['steps']:
            s['text'] = s['text'].replace('getköttet','lammet').replace('Skölj riset i sil. ','')
            if s['text'].startswith('Sjud riset'): s['text']='Sjud riset under lock cirka arton minuter eller längre enligt förpackningen tills kornen är mjuka och vattnet absorberats.'
        rice_rest = next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Ta riset från'))
        insert_step(row,rice_rest,{'text':'Kontrollera riset; tillsätt vid behov 50 ml vatten och fortsätt sjuda före vilan. Ta från värmen när riset är mjukt.','uses':['ris'],'minutes':1})
        row['steps'][rice_rest]['text']='Låt riset vila fem minuter under lock.'
        row['unmeasured_processes']=[]
        mark_process(row,3,['benfri lammstek'],'trim_before_cooking','Benfri lammstek vägs före putsning; borttagna senor och kvarvarande ätlig vikt är inte uppmätta.')
        for n,s in enumerate(row['steps']): s['after']=[n] if n else []
        changes.append('New explicit boneless-lamb/rapeseed version: 800 g purchased leg replaces edible goat; unknown trim loss and 24-hour thaw retained. Replace constant 130-minute active frying with 90-minute covered lamb simmer plus 15-minute active reduction, with separate checks and extensions if not tender. Preserve onion/yoghurt/spices and extended potato; all sauce/fat/ground spices served. No measured speed or cooking claim.')
    if base.endswith('recheado-makrill'):
        rename_ingredient(row,'makrill','lax')
        rename_ingredient(row,'kashmirchili','rökt paprikapulver')
        row['primary']='lax'
        row['family']='recheadofisk med vinägerpasta mellan filéer'
        row['name']='Lax recheado med rökt paprika – '+row['variant_id']
        row['notes']='Uttrycklig laxversion av recheadotekniken: 700 g rå benfri lax ersätter 700 g makrill och 6 g rökt paprika ersätter 8 g kashmirchili. Både fisksmak och hetta ändras; inga identiska råvaror påstås. Filépar med vinägerpasta behålls. Kylupptining ingår, vätska och all stekolja genomkokas och serveras. Ingen panering eller ny kryddstyrka tillsätts. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name']=='lax':i.update(label='Rå benfri laxfilé, ätlig vikt')
                if i['name']=='rökt paprikapulver':i.update(quantity=6,label='Rökt paprikapulver, ny mildare kryddversion')
        for s in row['steps']:
            if s['text'].startswith('Kontrollera makrillfiléerna'):
                s['text']='Kontrollera att laxfiléerna är helt tinade och utan ben. Behåll all upptiningsvätska för genomkokning i pannan. Dela i jämntjocka filébitar; skär vid behov längs tjockleken så att två lagda ihop blir högst cirka 3 cm. Mixa rökt paprika, vinäger, färsk eller fryst hackad vitlök, skalad uppvägd ingefära och fiskdelens salt till pasta.'+(' Mixa också ner spiskummin och gurkmeja. Skala och väg löken, skiva tunt.' if row['variant_id']!='simple' else '')
                s['minutes']=10
            if s['text'].startswith('Fördela pastan'):
                s['text']='Fördela all kryddpasta på hälften av laxfilébitarna och lägg de återstående ovanpå. Eventuellt skinn ska vara utåt och tillagas och serveras med fisken. Håll paren högst cirka 3 cm tjocka; fäst vid behov med tandpetare.'
            if s['text'].startswith('Värm oljan') or s['text'].startswith('Värm återstående olja'):
                s['text']='Värm '+('oljan' if row['variant_id']=='simple' else 'återstående olja')+' på medelvärme. Stek laxparen cirka fyra minuter per sida. Tillsätt all sparad upptiningsvätska och 30 ml vatten. Lägg på lock och sjud ytterligare minst fem minuter tills mitten mellan filéerna når minst 72 °C och vitlökspastan är genomlagad; förläng enligt förpackningen. Behåll all sky och olja.'
                s['minutes']=15
            if s['text'].startswith('Ta bort samtliga'):
                s['text']='Ta bort samtliga tandpetare och fördela laxen med ris och alla tillbehör. Skrapa ur och servera hela pannans genomkokta sky och olja.'
            if s['text'].startswith('Ta av värmen'):
                s['text']='Låt riset vila fem minuter under lock; det ska sedan hållas över 60 °C fram till servering.'
        rice_rest=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Låt riset vila'))
        insert_step(row,rice_rest,{'text':'Kontrollera riset. Är det hårt, tillsätt 50 ml vatten och förläng sjudningen; ta från värmen när det är mjukt.','uses':['ris'],'minutes':1})
        prepend_thaw(row,'lax',720,'Behåll all upptiningsvätska och koka den med fisken i pannan. Redan kylförvarad rå lax kan gå direkt vidare.')
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit salmon/smoked-paprika version supported by chef; raw salmon 700 g replaces unavailable raw mackerel and new 6 g smoked paprika replaces 8 g Kashmiri chili. No canned-tomato mackerel or false identity. Preserve paired-fillet vinegar filling, thaw planning, rice and variant sides. All thaw juice/30 ml pan water/oil are cooked and served; frozen garlic filling heats through to at least 72 C.')
    if base.endswith('vada-pav'):
        assert row['variant_id'] in {'simple', 'standard', 'extended'}
        rename_ingredient(row,'pavbröd','mjukt hamburgerbröd')
        row['name'] += ' – med mjukt svenskt hamburgerbröd'
        row['notes'] = 'Granskad enkel vada pav med 416 g mjukt svenskt hamburgerbröd i stället för 480 g pavbröd. Brödet innehåller sesam och är ingen identisk ladi pav-produkt. Potatis och all kikärtssmet serveras; överbliven smet steks som små frasiga bitar. Okänd potatisförlust vid avrinning och okänt upptag av det grunda oljebadet redovisas utan faktor. Enkelvariantens kryddning bevaras. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name']=='mjukt hamburgerbröd':i.update(quantity=416,label='Mjukt svenskt hamburgerbröd med sesam, vägd mängd')
        row['steps']=[
            {'text':'Skala potatisen och väg den råa ätliga mängden efter skalning. Tärna och lägg i kastrull med 1200 ml vatten utan salt. Koka upp.','uses':['potatis'],'minutes':7},
            {'text':'Sjud potatisen arton minuter.','uses':['potatis'],'minutes':18,'passive':True},
            {'text':'Kontrollera att potatisen är helt mjuk; förläng annars kokningen. Häll av och kasta kokvattnet. Ställ potatisen att ånga torr.','uses':['potatis'],'minutes':2},
            {'text':'Låt potatisen ånga torr åtta minuter.','uses':['potatis'],'minutes':8,'passive':True},
            {'text':'Rosta kokosflingorna i torr panna under omrörning till lätt gyllene. Flytta till ett fat. Lägg färsk eller fryst hackad vitlök i pannan med 20 ml vatten; sjud under omrörning minst tre minuter och låt allt vatten koka bort utan att bränna vitlöken. Vänd tillbaka all kokos, tillsätt chiliflakes och chutneyns salt. Mortla till grov, torr smulig chutney.','uses':['kokosflingor','vitlök','chiliflakes','salt'],'minutes':9},
            {'text':'Mosa potatisen med hälften av gurkmejan och hälften av vadans salt. Forma två platta potatisbollar per portion, ungefär 2 cm tjocka. Vispa allt kikärtsmjöl, resterande gurkmeja och vadasalt med 160 ml vatten till jämn doppsmet.','uses':['potatis','gurkmeja','salt','kikärtsmjöl'],'minutes':7},
            {'text':'Häll hela den angivna oljan i en liten djup stekpanna så den bildar ett grunt bad, högst en tredjedel av pannans höjd. Värm till cirka 170 °C. Doppa potatisbollarna i smeten och stek i omgångar cirka tre minuter per sida; anpassa antalet omgångar till portionsantalet. Kontrollera att smeten är helt genomstekt utan rått mjöl och att mitten är rykande varm. Stek eventuell kvarvarande smet som små tunna bitar och servera också dessa. Låt allt rinna av på galler. Olja som återstår i pannan serveras inte; använd torra redskap.','uses':['rapsolja','potatis','kikärtsmjöl'],'minutes':20},
            {'text':'Väg den angivna mängden mjukt hamburgerbröd och dela för fyllning; dela vid behov bröd så mängden kan fördelas över portionerna. Värm kort i torr panna. Fördela all kokos-vitlökschutney och två vada per portion i bröden, med eventuella frasiga smetbitar vid sidan. Servera genast.','uses':['mjukt hamburgerbröd','potatis','kokosflingor','vitlök'],'minutes':5},
        ]
        row['unmeasured_processes']=[]
        mark_process(row,3,['potatis'],'drain_after_cooking','Kokvattnet kasseras; potatisens kokförlust och slutvikt är inte uppmätta.')
        mark_process(row,7,['rapsolja'],'deep_fry_and_drain','Grunt oljebad, avrinning på galler och kvarvarande olja i pannan. Ingen oljeupptagningsandel antas.')
        if row['variant_id']!='simple':
            for component in row['components']:
                component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'curryblad']
            row['name'] += ', utan curryblad'
            row['notes'] = row['notes'].replace('Granskad enkel vada pav', 'Granskad vada pav, standardvariant').replace('Enkelvariantens kryddning bevaras.', 'Senapsfrö och ingefära bevaras i separat fräs. De 4 g curryblad som saknar kvalificerad produkt utelämnas uttryckligen; samma arom påstås inte. En sextondel av oljan används i fräset och resten i det grunda oljebadet.')
            row['steps'][6]['text'] = row['steps'][6]['text'].replace('hela den angivna oljan', 'resten av den angivna oljan')
            insert_step(row,6,{'text':'Skala, väg och finriv ingefäran. Mät ut en sextondel av den angivna rapsoljan och värm i panna på medelvärme. Låt senapsfröna börja knäppa och fräs sedan ingefäran en minut under omrörning. Häll allt fräs och all dess olja över potatisen; skrapa ur pannan. Resterande olja sparas till stekningen.','uses':['ingefära','rapsolja','senapsfrön','potatis'],'minutes':5})
            changes.append('Standard only: explicitly omit 4 g unavailable curry leaves without aromatic-equivalence claim; retain mustard 2 g and ginger 18 g in tempering. One sixteenth of total oil goes into retained tempering, remaining fifteen sixteenths into unmeasured shallow-fry process. Extended tamarind version remains blocked.')
            if row['variant_id']=='extended':
                changes[-1] = changes[-1].replace('Standard only:', 'Extended:').replace(' Extended tamarind version remains blocked.', '')
                rename_ingredient(row,'tamarindpasta','tamarindkoncentrat')
                for c in row['components']:
                    for i in c['ingredients']:
                        if i['name']=='tamarindkoncentrat':i.update(quantity=20,unit='ml',label='Syrligt tamarindkoncentrat, ny dos i milliliter')
                row['notes']=row['notes'].replace('standardvariant','utökad variant')+' Dadelchutneyn använder 20 ml redan granskat tamarindkoncentrat i stället för 30 g tamarindpasta. Ny kulinarisk dos, ingen densitet eller samma syrastyrka antas. Alla dadlar, koriander och limejuice behålls; fryst koriander genomkokas.'
                insert_step(row,8,{'text':'Kontrollera att dadlarna är urkärnade och väg den ätliga mängden utan kärnor. Hacka och sjud med det uppmätta tamarindkoncentratet och 120 ml vatten under omrörning cirka sex minuter tills mjuka. Mixa slätt. Rör ner all fryst hackad koriander och sjud under omrörning minst tre minuter eller längre enligt förpackningen. Ta från värmen och rör i all limejuice. Behåll hela chutneyn.','uses':['dadlar','tamarindkoncentrat','koriander','limejuice'],'minutes':13})
                row['steps'][-1]['text'] += ' Lägg en del av hela dadelchutneyn i bröden och servera resten vid sidan; inget silas eller kastas.'
                row['steps'][-1]['uses'] += ['dadlar','tamarindkoncentrat','koriander','limejuice']
                changes.append('New 20 ml already reviewed sour tamarind concentrate instead of 30 g generic tamarind paste, no density conversion. Preserve all pitted dates/coriander/lime; simmer frozen coriander at least three minutes and serve entire chutney. Keep same potato-drain and shallow-fry losses with step indices shifted by insertion.')
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('New 416 g soft Swedish sesame burger-bun version, not pav identity. Weigh peeled potato; separate simmer/drain/drying; boil frozen garlic then dry it for chutney. Two fritters per portion, all batter served, shallow-fry oil uptake unknown, process-water amounts scale.')
    if base.endswith('papadzules'):
        rename_ingredient(row, 'epazote', 'koriander')
        rename_ingredient(row, 'kokta ägg', 'ägg')
        rename_ingredient(row, 'masa harina', 'majstortillas')
        row['name'] += ' – koriander och färdiga majstortillas'
        row['notes'] = 'Granskad korianderversion med 20 g fryst hackad koriander i stället för 7 g epazote, åtta råa hela ägg i stället för 400 g färdigkokt ägg och 400 g färdigbakade majstortillas i stället för 260 g masa harina och tortillornas 2 g salt. Inga lika smaker, tillagade äggvikter eller degutbyten antas. Alla såser och allt örtspad serveras. Inte provlagad.'
        row['equipment'] = ['kastruller','stekpanna','stavmixer','termometer']
        row['method'] = 'pot'
        for c in row['components']:
            if c['id']=='majsbrod':
                c['ingredients']=[i for i in c['ingredients'] if i['name']!='salt']
            for i in c['ingredients']:
                if i['name']=='koriander': i.update(quantity=20,label='Fryst hackad koriander')
                if i['name']=='ägg': i.update(quantity=8,unit='st',form='as_sold',label='Hela råa ägg, räknade före kokning')
                if i['name']=='majstortillas': i.update(quantity=400,form='as_sold',label='Mjuka färdigbakade majstortillas')
        extra=row['variant_id']!='simple'
        row['steps']=[
            {'text':'Lägg det angivna antalet råa hela ägg i kastrull med 1600 ml vatten. Koka upp försiktigt.','uses':['ägg'],'minutes':6},
            {'text':'Sjud äggen tolv minuter så både vita och gula blir fasta.','uses':['ägg'],'minutes':12,'passive':True},
            {'text':'Häll bort kokvattnet och spola äggen hastigt svalt så de går att hantera. Skala, kasta skalen och skölj bort skalrester. Kontrollera fasta gulor och vitor, hacka äggen och blanda med fyllningens salt. Håll fyllningen täckt och varm över 60 °C, exempelvis i en skål över varmt vatten.','uses':['ägg','salt'],'minutes':6},
            {'text':'Rosta pumpakärnorna varsamt i torr panna under omrörning tills de doftar nötigt, utan att bränna dem. Ta från värmen.'+(' Skala, väg och finhacka såsens lök.' if extra else ''),'uses':['pumpakärnor']+(['gul lök'] if extra else []),'minutes':6},
            {'text':'Lägg fryst hackad koriander direkt i en kastrull med pumpasåsens salt och 550 ml vatten.'+(' Tillsätt den hackade löken.' if extra else '')+' Koka upp.','uses':['koriander','salt']+(['gul lök'] if extra else []),'minutes':3},
            {'text':'Sjud örtspadet fem minuter, eller längre enligt örtens förpackning.','uses':['koriander']+(['gul lök'] if extra else []),'minutes':5,'passive':True},
            {'text':('Kontrollera att löken är mjuk; förläng annars sjudningen. ' if extra else '')+'Mixa hela örtspadet med alla pumpakärnor slätt med stavmixer i ett högt värmetåligt kärl; undvik stänk. Håll såsen över 60 °C på mycket låg värme utan kraftig kokning. Rör vid behov; kasta inget spad.','uses':['koriander','pumpakärnor']+(['gul lök'] if extra else []),'minutes':4},
            {'text':'Tärna tomaterna och värm rapsoljan i en kastrull.'+(' Tillsätt färsk eller fryst hackad vitlök samt chiliflakes och rör kort.' if extra else '')+' Lägg i alla tomater och tomatsåsens salt. Sjud under omrörning tills tomaterna faller sönder, minst tio minuter. Eventuell fryst vitlök ska vara helt genomhettad. Behåll all olja och tomatvätska; håll tomat- och pumpakärnssås åtskilda.','uses':['tomat','rapsolja','salt']+(['vitlök','chiliflakes'] if extra else []),'minutes':14},
        ]
        row['unmeasured_processes']=[]
        mark_process(row,3,['ägg'],'peel_after_cooking','Råa ägg köps och doseras i antal; skal tas bort utan antagen styckvikt eller kokt gramvikt.')
        if row['variant_id']=='extended':
            row['steps'].append({'text':'Använd redan tinad avokado med all sin saft. Skiva gurkan och vänd med avokadon, all limejuice och salladens salt.','uses':['avokado','gurka','limejuice','salt'],'minutes':4})
        row['steps'] += [
            {'text':'Väg den angivna mängden mjuka färdigbakade majstortillas. Värm i omgångar i torr panna enligt förpackningen och håll mjuka under ren kökshandduk.','uses':['majstortillas'],'minutes':6},
            {'text':'Fördela hela äggfyllningen i tortillorna och rulla samman. Fördela över det angivna antalet portioner. Täck med hela pumpakärnssåsen och lägg tomatsåsen i en separat sträng över; servera eventuell sås som inte ryms vid sidan.'+(' Servera hela avokadosalladen med saften till.' if row['variant_id']=='extended' else '')+' Servera genast.','uses':['ägg','majstortillas','pumpakärnor','tomat']+(['avokado','gurka'] if row['variant_id']=='extended' else []),'minutes':5},
        ]
        if row['variant_id']=='extended':
            from admit_expansion_20261101 import prepend_steps
            prepend_steps(row,[
                {'text':'Väg upp fryst avokado i ett täckt kärl. Ställ i kylskåp och behåll all upptiningssaft.','uses':['avokado'],'minutes':1},
                {'text':'Tina avokadon helt i kylskåp enligt förpackningen; planera två timmar och förläng vid behov.','uses':['avokado'],'minutes':120,'passive':True},
            ])
            for process in row['unmeasured_processes']: process['step']+=2
        for n,s in enumerate(row['steps']):s['after']=[n] if n else []
        changes.append('Explicit coriander/ready-tortilla version with new herb, bread and counted raw-egg doses. Boil all frozen herbs into retained seed sauce, fully cook garlic, retain all sauces and salad juices; thaw frozen avocado under refrigeration. Egg-shell loss remains unknown, all portion language and process water scale.')
    if base.endswith('khua-kling'):
        rename_ingredient(row, 'sydthailändsk currypasta', 'röd currypasta')
        rename_ingredient(row, 'makrutlimeblad', 'torkade makrutlimeblad')
        rename_ingredient(row, 'kokta ägg', 'ägg')
        row['name'] += ' – röd currypasta och torkade limeblad'
        row['notes'] = 'Granskad Khua kling-anpassning med 55 g röd currypasta, 1 g torkade makrutlimeblad i silad infusion och 40 g helt citrongräs före ansning. Detta ersätter författarutkastets sydthailändska pasta, 4 g färska blad och 30 g rensat citrongräs utan lika smak eller ätlig vikt. Standard/utökad får fyra råa hela ägg i stället för 200 g färdigkokt ägg. Bladextraktion, citrongräsputsning och äggskal har okända förluster. Allt köttfett och all såskrydda serveras; rätten reduceras torr. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'torkade makrutlimeblad':
                    i.update(quantity=1,form='dry')
                if i['name'] == 'citrongräs':
                    i.update(quantity=40,form='as_sold',requirements=['pack:intake_all_shape_top5_whole_lemongrass'],label='Helt citrongräs före ansning')
                if i['name'] == 'ägg':
                    i.update(quantity=4,form='as_sold',unit='st',label='Råa hela ägg, räknade före kokning')
        row['unmeasured_processes'] = []
        row['steps'] = [
            {'text':'Lägg de uppvägda torkade limebladen i en liten kastrull med 100 ml vatten. Koka upp och sänk värmen.', 'uses':['torkade makrutlimeblad'],'minutes':3},
            {'text':'Sjud bladen under lock i femton minuter.', 'uses':['torkade makrutlimeblad'],'minutes':15,'passive':True},
            {'text':'Sila genom finmaskig sil och kasta alla blad och hårda fragment. Behåll hela infusionen och fyll upp till 100 ml vatten.', 'uses':['torkade makrutlimeblad'],'minutes':3},
            {'text':'Väg citrongräset före ansning. Skär bort torr rotände, hårda yttre lager och vedartad topp. Finhacka och mortla allt mjukt innanmäte mycket fint.', 'uses':['citrongräs'],'minutes':7},
            {'text':'Lägg riset och dess salt i en kastrull med 560 ml vatten. Koka upp och sänk värmen.', 'uses':['ris','salt'],'minutes':4},
            {'text':'Sjud riset under lock cirka arton minuter, eller enligt förpackningen.', 'uses':['ris'],'minutes':18,'passive':True},
            {'text':'Kontrollera att riset är mjukt och vattnet absorberat. Tillsätt vid behov 50 ml vatten och fortsätt tills mjukt innan kastrullen tas från värmen.', 'uses':['ris'],'minutes':2},
            {'text':'Låt riset vila under lock fem minuter.', 'uses':['ris'],'minutes':5,'passive':True},
            {'text':'Luckra riset och håll det varmt över 60 °C under lock. Skiva gurkan.' + (' Skala och väg moroten, ansa och väg vitkålen. Strimla och vänd med gurkan och all limejuice; behåll hela salladens vätska.' if row['variant_id']=='extended' else ''), 'uses':['ris','gurka']+(['morot','vitkål','limejuice'] if row['variant_id']=='extended' else []),'minutes':7 if row['variant_id']=='extended' else 3},
        ]
        mark_process(row,3,['torkade makrutlimeblad'],'remove_after_infusion','Torra blad och fragment silas bort; överförd ämnesmängd är okänd. Ingen torr/färsk- eller näringsfaktor antas.')
        mark_process(row,4,['citrongräs'],'trim_before_cooking','Helt citrongräs vägs före borttagning av hårda delar; ingen uppmätt ätlig andel finns.')
        if row['variant_id'] != 'simple':
            row['steps'] += [
                {'text':'Lägg det angivna antalet råa hela ägg i en kastrull med 1000 ml vatten. Koka upp försiktigt.', 'uses':['ägg'],'minutes':5},
                {'text':'Sjud äggen tolv minuter så vitor och gulor blir fasta.', 'uses':['ägg'],'minutes':12,'passive':True},
                {'text':'Häll bort kokvattnet, kyl hastigt med kallt vatten och skala äggen. Kasta skalen och skölj bort skalrester. Kontrollera att vita och gula är fasta och håll äggen varmt över 60 °C till servering.', 'uses':['ägg'],'minutes':5},
            ]
            mark_process(row,len(row['steps']),['ägg'],'peel_after_cooking','Fyra råa hela ägg ersätter angiven kokt gramvikt; skal och färdig vikt är okända, ingen styckvikt antas.')
        row['steps'] += [
            {'text':'Häll hela limebladsinfusionen i en vid panna. Lägg i fläskfärsen och finfördela under uppvärmning. Arbeta in all röd currypasta och det finmortlade citrongräset. Tillsätt ingen olja och häll inte bort fett eller köttsaft.', 'uses':['fläskfärs','röd currypasta','torkade makrutlimeblad','citrongräs'],'minutes':7},
            {'text':'Stek under tät omrörning tills färsen är helt genomlagad och minst 72 °C. Rör ner sockret'+(' och fisksåsen' if row['variant_id']!='simple' else '')+'. Fortsätt på låg till medelhög värme, skrapa bottnen och låt vattnet avdunsta tills små torra färssmulor är täckta av kryddpastan. Behåll allt köttfett; inget spad ska hällas bort. Förläng vid behov, utan att bränna pastan.', 'uses':['fläskfärs','röd currypasta','strösocker']+(['fisksås'] if row['variant_id']!='simple' else []),'minutes':12},
            {'text':'Fördela hela färscurryn med allt varmt ris och grönsakstillbehör över det angivna antalet portioner.'+(' Dela de nykokta äggen och servera dem till.' if row['variant_id']!='simple' else ''),'uses':['fläskfärs','ris','gurka']+(['ägg'] if row['variant_id']!='simple' else []),'minutes':3},
        ]
        for n,s in enumerate(row['steps']):
            s['after']=[n] if n else []
        changes.append('Explicit red-curry dry pork version; new 1 g dried lime-leaf infusion and 40 g whole lemongrass with unknown leaf extraction/trim. Standard/extended use four raw counted shell eggs with unknown peel yield instead of a ready-cooked gram amount. All meat fat retained; rice inspection and resting are separate, process water scales, no fixed serving count.')
    if base.endswith('chivda'):
        rename_ingredient(row, 'risflingor', 'cornflakes')
        rename_ingredient(row, 'jordnötter', 'rostade jordnötter')
        row['primary'] = 'cornflakes'
        row['name'] = 'Cornflakes-chivda – ' + ('enkel' if row['variant_id'] == 'simple' else 'utökad')
        row['equipment'] = ['vid stekpanna', 'mortel', 'fat']
        row['notes'] = 'Uttrycklig majsvariant med 35 g naturella färdigrostade frukost-cornflakes i stället för 35 g risflingor. Ingen ris-/majsidentitet eller makai-poha-form likställs. Rostade osaltade jordnötter används; cornflakes innehåller redan socker och salt. Receptets 3 g socker och 0,5 g salt är egna tillsatser, inte produktens totala innehåll. Förenklad mild kryddning utan curryblad, som i originalutkastet. All olja och kryddbeläggning serveras. Inte provlagad.'
        for c in row['components']:
            c['name'] = 'Krispig majs- och nötblandning'
            for i in c['ingredients']:
                if i['name'] == 'cornflakes':
                    i.update(form='as_sold', label='Naturella färdigrostade cornflakes')
                if i['name'] == 'rostade jordnötter':
                    i['label'] = 'Rostade osaltade jordnötter'
        extended = row['variant_id'] == 'extended'
        row['steps'] = [
            {'text':'Väg färdigrostade cornflakes och rostade osaltade jordnötter. Använd inte rå makai poha, risflingor eller frostade/smaksatta flingor. Mortla strösockret fint. Förbered ett torrt fat.', 'uses':['cornflakes','rostade jordnötter','strösocker'], 'minutes':2},
            {'text':('Värm oljan i en vid panna på medellåg värme. Tillsätt senapsfröna under stänkskydd och låt dem börja knäppa. Sänk värmen och vänd ner jordnötter, kokosflingor och russin. Rör tills kokosen precis får svag färg och russinen mjuknar, utan att bränna dem.' if extended else 'Värm oljan i en vid panna på låg värme. Vänd ner de redan rostade jordnötterna och värm varsamt under omrörning utan att mörkrosta dem.'), 'uses':['rapsolja','rostade jordnötter']+(['senapsfrön','kokosflingor','russin'] if extended else []), 'minutes':4 if extended else 2},
            {'text':'Ta pannan från värmen. Rör ner gurkmeja, finmortlat socker och salt i oljan. Vänd försiktigt ner cornflakes och fördela kryddoljan utan att krossa flingorna. Sätt tillbaka på mycket låg värme och vänd cirka två minuter. Tillsätt ingen vätska och häll inte bort någon olja.', 'uses':['gurkmeja','strösocker','salt','cornflakes','rapsolja'], 'minutes':3},
            {'text':'Bred ut hela blandningen, inklusive kryddor och olja från pannan, på det torra fatet.', 'uses':['cornflakes','rostade jordnötter','rapsolja'], 'minutes':1},
            {'text':'Låt blandningen svalna helt, planera tio minuter.', 'uses':['cornflakes','rostade jordnötter'], 'minutes':10, 'passive':True},
            {'text':'Kontrollera att blandningen svalnat och är krispig. Fördela hela mängden över det angivna antalet mellanmålsportioner och servera.', 'uses':['cornflakes','rostade jordnötter'], 'minutes':1},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit ready-to-eat cornflakes version; retain 35 g as an independently authored dose, not a rice conversion. Use already roasted unsalted peanuts; preserve sweet-salty turmeric coating and extended coconut/raisin/mustard variation. Gentle two-minute coating, no deep frying or discarded oil.')
    if base.endswith('pindi-chole'):
        row['name']+=' – egen kryddblandning och citron'
        row['flavor']=['mörkt te','koriander och spiskummin','citron']
        row['notes']='Granskad Pindi chole med egen kryddblandning och 30 ml citronjuice i kikärterna i stället för 8 g amchur. Färdig cholemasala ersätts av uttryckligen vägda kryddor, inte ett råvarualias. Ingen lika syra eller arom påstås. Teet silas bort och kikärtsvattnet kasseras med okänd extraktion/förlust. Alla kryddor och olja serveras. Inte provlagad.'
        for c in row['components']:
            c['ingredients']=[i for i in c['ingredients'] if i['name'] not in {'cholemasala','amchur'}]
            if c['id']=='kikartor':
                names={i['name'] for i in c['ingredients']}
                additions=[('malen koriander',4,'dry','g'),('garam masala',4,'dry','g'),('paprikapulver',1,'dry','g'),('cayennepeppar',.3,'dry','g'),('gurkmeja',.5,'dry','g'),('citronjuice',30,'as_sold','ml')]
                if 'spiskummin' not in names:
                    additions.append(('spiskummin',2,'dry','g'))
                c['ingredients'].extend({'name':name,'form':form,'quantity':q,'unit':unit,'role':'flavour','label':name} for name,q,form,unit in additions)
        spices=['malen koriander','garam masala','paprikapulver','cayennepeppar','gurkmeja','spiskummin']
        for s in row['steps']:
            s['uses']=[n for n in s['uses'] if n not in {'cholemasala','amchur'}]
            s['text']=s['text'].replace('över fyra portioner','över det angivna antalet portioner')
        row['steps'][1].update(text='Blötlägg kikärtorna i kylskåp cirka åtta timmar.',minutes=480)
        row['steps'][2].update(text='Koka upp 500 ml vatten, tillsätt teet och stäng av värmen.',minutes=3)
        row['steps'][3].update(text='Sjud kikärtorna under lock cirka 90 minuter tills de är helt mjuka. Följ längre koktid på förpackningen vid behov; äldre kikärtor kan kräva längre tid.',minutes=90)
        season=next(s for s in row['steps'] if 'Rör ner cholemasala' in s['text'])
        season['text']='Finhacka ingefäran'+(' och väg färsk eller fryst hackad vitlök' if row['variant_id']!='simple' else '')+'. Värm kikärtskomponentens olja och fräs aromaterna på låg till medelhög värme. Rör ner malen koriander, garam masala, paprikapulver, cayenne, gurkmeja och malen spiskummin, följt direkt av 120 ml vatten så att kryddorna inte bränns. Tillsätt de kokta avrunna kikärtorna samt kikärtskomponentens citronjuice och salt. Sjud under omrörning minst tre minuter så att eventuell fryst vitlök genomhettas, sedan tills kryddorna klär bönorna och nästan ingen fri sås finns kvar. Behåll all olja och kryddbeläggning.'
        season['uses']=list(dict.fromkeys([*season['uses'],*spices,'citronjuice']))
        row['steps'][-1]['uses']=list(dict.fromkeys([*row['steps'][-1]['uses'],*spices,'citronjuice']))
        insert_step(row,3,{'text':'Häll bort blötläggningsvattnet och skölj kikärtorna före kokning.','uses':['kikärtor'],'minutes':2})
        brew=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Koka upp 500'))
        insert_step(row,brew+1,{'text':'Låt teet dra fem minuter under lock.','uses':['svart te'],'minutes':5,'passive':True})
        insert_step(row,brew+2,{'text':'Sila bort alla teblad och kasta dem. Häll hela teinfusionen över de sköljda kikärtorna och tillsätt 1000 ml vatten. Koka upp ordentligt.','uses':['svart te','kikärtor'],'minutes':5})
        cook=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Sjud kikärtorna'))
        row['steps'][cook-1].update(text='Sjud kikärtorna under lock cirka 45 minuter.',minutes=45)
        insert_step(row,cook+1,{'text':'Kontrollera vattennivån och tillsätt vid behov högst 250 ml vatten. Koka upp igen och sänk värmen.','uses':['kikärtor'],'minutes':2})
        insert_step(row,cook+2,{'text':'Sjud ytterligare cirka 45 minuter tills kikärtorna är helt mjuka. Följ längre koktid på förpackningen vid behov.','uses':['kikärtor'],'minutes':45,'passive':True})
        insert_step(row,cook+3,{'text':'Kontrollera att kikärtorna är helt mjuka och går lätt att mosa; förläng kokningen vid behov. Häll av och kasta kokvattnet.','uses':['kikärtor','svart te'],'minutes':3})
        for n,s in enumerate(row['steps']):
            s['after']=[n] if n else []
        for prefix,ingredients,operation in [('Häll bort blötläggningsvattnet',['kikärtor'],'drain_before_cooking'),('Sila bort alla teblad',['svart te'],'remove_after_infusion'),('Kontrollera att kikärtorna',['kikärtor','svart te'],'drain_after_cooking')]:
            index=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith(prefix))
            mark_process(row,index,ingredients,operation,'Vatten eller teblad kasseras i det beskrivna steget. Extraktion och kvarvarande ämnesmängd är okända; inga retentions- eller upptagningsandelar antas.')
        changes.append('Replace ready cholemasala with explicit ground coriander/garam masala/cumin/paprika/cayenne/turmeric doses and amchur with a new 30 ml lemon-juice dose. Preserve tea-darkened dry chickpeas, handmade breads and garlic/cucumber/yoghurt/onion variant differences. Separate soaking/tea brewing/simmer waits from drainage and checks, retain all seasoning/oil, mark unknown tea and chickpea-water losses and scale all process water.')
    if base.endswith('-polsa'):
        rename_ingredient(row,'nöthjärta','högrev')
        rename_ingredient(row,'fläsklever','ungnötslever')
        row['name']+=' – med högrev och ungnötslever'
        row['primary']='högrev och ungnötslever'
        row['flavor']=['kokt nötkött','lever','kryddpeppar']
        row['notes']='Granskad pölsaversion med 500 g högrev i stället för nöthjärta och 250 g hel ungnötslever före putsning i stället för 250 g ätlig fläsklever. Det är nya insatser, inte lika ätlig mängd. Hela kött- och grynmängden serveras; putsning och kasserade kokspad ger okända förluster. Planera kylupptining för frysta produkter. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name']=='ungnötslever':
                    i.update(form='as_sold',label='Ungnötslever i bit, vägd före putsning')
        row['steps'][0].update(text='Väg ungnötslevern före putsning, skär bort grova hinnor och kärl och förvara kallt tills den ska kokas. Skär högreven i grova bitar. Lägg högreven med all dess upptiningssaft i gryta med 1700 ml vatten och hälften av pölsans salt. Koka upp; behåll skummet i spadet.',uses=['högrev','ungnötslever','salt'],minutes=13)
        row['steps'][1].update(text='Sjud högreven under lock på låg värme cirka 60 minuter.',minutes=60)
        row['steps'][2]['text']=row['steps'][2]['text'].replace('Lyft hjärtat','Kontrollera att högreven är mör och lätt kan delas; förläng sjudningen om det behövs. Lyft högreven').replace('Skär levern i jämna bitar','Skär den putsade ungnötslevern i jämna bitar').replace('lägg i det sjudande spadet','lägg med all leverns upptiningssaft i det sjudande spadet')
        row['steps'][3]['text']='Ta upp den genomkokta levern. Mät upp 900 ml vatten från köttkoket till korngrynen, utan att sila bort matbitar; späd med vanligt vatten om det saknas. Kasta återstående köttspad. Koka upp grynen i det uppmätta spadet. Förvara det kokta köttet och levern täckta och varmt över 60 °C tills blandningen är färdig.'
        row['steps'][4].update(text='Sjud korngrynen under lock cirka 40 minuter tills mjuka men med lite textur. Följ längre koktid på förpackningen vid behov.',minutes=40)
        for s in row['steps']:
            s['text']=s['text'].replace('det kokta hjärtat','den kokta högreven')
            s['text']=s['text'].replace('Skala och skär rödbetorna','Skala rödbetorna, väg den råa ätliga mängden och skär dem')
            s['text']=s['text'].replace('Skala potatisen och skär','Skala potatisen, väg den råa ätliga mängden och skär')
            s['text']=s['text'].replace('lite återstående hett kokspad eller 100 ml vatten','högst 100 ml vatten')
            if s['text'].startswith('Stek äggen'):
                s['text']='Knäck äggen, väg den råa ätliga mängden utan skal och stek portionsvis i äggkomponentens smör tills både vita och gula är satta. Servera allt äggsmör.'
        row['steps'][-1]['text']+=' Servera också hela den korta rödbetslagen om sådan ingår och allt smör från lökpannan.'
        insert_step(row,3,{'text':'Kontrollera sjudningen och vätskan. Tillsätt högst 200 ml vatten om det behövs och lägg på locket igen.','uses':['högrev'],'minutes':2})
        insert_step(row,4,{'text':'Sjud högreven ytterligare cirka 60 minuter tills mör.','uses':['högrev'],'minutes':60,'passive':True})
        for prefix,ingredients in [('Sjud rödbetorna',['rödbeta']),('Sjud potatisen',['potatis','salt'])]:
            index=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith(prefix))
            s=row['steps'][index-1]
            if prefix=='Sjud rödbetorna':
                s['text']='Sjud rödbetorna cirka 25 minuter tills helt mjuka.'
            else:
                s['text']='Sjud potatisen cirka 20 minuter tills mjuk.'
            insert_step(row,index+1,{'text':('Kontrollera att rödbetorna är mjuka, häll av och kasta kokvattnet.' if prefix=='Sjud rödbetorna' else 'Kontrollera med sticka att potatisen är mjuk, häll av saltat kokvatten och håll potatisen varm över 60 °C under lock.'),'uses':ingredients,'minutes':2})
        row['steps']=[
            {'text':'Väg högreven och den hela ungnötslevern före eventuell upptining. Lägg i separata täckta kärl i kylskåp vid cirka 4 °C. Behåll varje köttslags vätska till dess egen kokning.','uses':['högrev','ungnötslever'],'minutes':2},
            {'text':'Planera 24 timmars kylupptining för frysta produkter och följ förpackningen tills allt är helt tinat. Redan tinat kött behöver ingen upptining.','uses':['högrev','ungnötslever'],'minutes':1440,'passive':True},
            *row['steps'],
        ]
        for n,s in enumerate(row['steps']):
            s['after']=[n] if n else []
        mark_process(row,3,['ungnötslever'],'trim_before_cooking','Hela leverns inköpsvikt föregår borttagning av grova hinnor och kärl. Putsförlusten är inte uppmätt.')
        for prefix,ingredients in [('Ta upp den genomkokta levern',['högrev','ungnötslever','salt']),('Kontrollera att rödbetorna',['rödbeta']),('Kontrollera med sticka',['potatis','salt'])]:
            index=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith(prefix))
            mark_process(row,index,ingredients,'drain_after_cooking','Del av kokspadet kasseras efter kokning. Salt- och näringsöverföring till kasserad vätska är inte uppmätta; inga retentionsandelar antas.')
        changes.append('Explicit 500 g high-rib beef and 250 g gross young-beef-liver alternative. Keep cooked chopped-meat/barley/onion method and beet/egg/mustard variant differences. Plan shared cold thaw, trim liver with unknown loss, cook all thaw juice, separate halfway inspection and vegetable drainage from passive waits, retain dressing and butter, and mark discarded salted cooking broths unknown.')
    if base.endswith('chiles-en-nogada'):
        rename_ingredient(row,'poblano','paprika')
        row['name']=row['name'].replace('Chiles en nogada – fyllda poblano','Paprika en nogada – fyllda paprikahalvor')+' – milt paprikaalternativ'
        row['flavor']=['valnöt','fruktig färs','granatäpple']
        row['notes']='Granskad mild paprikaversion av nogada, utan påstående om poblanohetta eller traditionell grön färg. Välj paprika enligt korgens produkt; den kan ha annan färg. 700 g avser urkärnade råa halvor före rostning och skalning. Skalningsförlusten är okänd. Fyllningen har frukt och fläsk; all valnötsmjölk, stekfett och granatäppelsaft serveras. Inte provlagad.'
        for c in row['components']:
            c['name']=c['name'].replace('poblano','paprika')
            for i in c['ingredients']:
                if i['name']=='paprika':
                    i.update(quantity=700,label='Paprika, urkärnad rå vikt före rostning')
        row['steps'][0].update(text='Låt valnötterna mjukna i mjölken i ett täckt kärl i kylskåp vid cirka 4 °C i 60 minuter. All mjölk ska användas.',minutes=60,passive=True)
        row['steps'][1].update(text='Sätt ugnen på 240 °C grill. Skölj och halvera paprikan, ta bort kärnhus och stjälk och väg halvorna före rostning. Lägg med skinnet uppåt på plåt. Rosta nära grillelementet under aktiv tillsyn tills skinnet får svarta blåsor; undvik att bränna bort fruktköttet.',minutes=18)
        row['steps'][3]['text']='Dra av löst svartnat skal från paprikahalvorna. Sänk ugnen till 180 °C. Kärna ur äpplet, väg ätlig mängd med skal och tärna.'+(' Kärna även ur päronet, väg ätlig mängd och tärna det samt tomaten.' if row['variant_id']!='simple' else '')+(' Hacka löken, väg färsk eller fryst hackad vitlök och hacka mandeln.' if row['variant_id']=='extended' else '')
        row['steps'][4]['text']+=' Behåll allt stekfett och all kött- och fruktsaft i fyllningen; reducera vid behov under omrörning.'
        row['steps'][5].update(text='Värm de fyllda paprikahalvorna och eventuell fyllning bredvid i formen 12 minuter vid 180 °C.',minutes=12,passive=True)
        row['steps'][6]['text']=row['steps'][6]['text'].replace('Förde','Kontrollera att fyllningen är genomvarm. Förde').replace('de fyllda chilifrukterna mellan fyra tallrikar','paprikahalvorna och all eventuell fyllning bredvid mellan det angivna antalet portioner').replace('granatäppelkärnor','granatäppelkärnor med all tiningssaft')
        insert_step(row,6,{'text':'Fördela all färsblandning i paprikahalvorna i en ugnsform. Lägg eventuell fyllning som inte ryms bredvid halvorna i samma form; hela mängden ska serveras.','uses':['paprika','fläskfärs'],'minutes':4})
        insert_step(row,1,{'text':'Lägg valnötterna och all mjölk i ett täckt kärl i kylskåp vid cirka 4 °C.','uses':['valnötter','mjölk'],'minutes':2})
        peel=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Dra av löst'))
        mark_process(row,peel,['paprika'],'peel_after_cooking','Urkärnad rå paprika vägs före rostning. Svartnat skal dras av efteråt; kvarvarande ätlig massa och näring är inte uppmätta.')
        prepend_thaw(row,'granatäppelkärnor',120,'Behåll all kärnsaft till serveringen. Färska kärnor behöver inte upptining.')
        for n,s in enumerate(row['steps']):
            s['after']=[n] if n else []
        changes.append('Explicit mild bell-pepper halves replace poblano with 700 g raw cored input before roasting; skin loss remains unknown. Retain pork/fruit/walnut/pomegranate identity and variant additions. Cold-thaw pomegranate and serve juice, retain all walnut milk and filling fat, allow excess filling beside peppers, separate handling from waiting and scale sauce water/portion wording.')
    if base.endswith('pad-prik-king-tofu'):
        rename_ingredient(row, 'makrutlimeblad', 'torkade makrutlimeblad')
        row['name'] += ' – med infusion av torkade limeblad'
        row['flavor'] = ['röd curry', 'torkade makrutlimeblad', 'soja']
        row['notes'] = 'Granskad torrbladsvariant: 1 g torkade makrutlimeblad ersätter 4 g färska blad. Ingen färsk-torr-faktor eller lika arom påstås. Bladen sjuds separat och silas bort; all silad vätska kokas in i currypastan, men extraktion är okänd. Tofun pressas med okänd vätskeförlust. Alla stekfetter, bönornas kokvätska och eventuell gurkdressing används. Ingen kokosmjölk. Inte provlagad.'
        row['equipment'] = list(dict.fromkeys([*row['equipment'],'finmaskig sil','liten kastrull med lock']))
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'torkade makrutlimeblad':
                    i.update(quantity=1,form='dry',label='Torkade makrutlimeblad, vägs före infusion')
                if i['name'] == 'tofu':
                    i['label'] = 'Fast naturell tofu, vägd före pressning'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skölj riset i sil. ', '')
        row['steps'][1].update(text='Sjud riset under lock cirka 18 minuter tills kornen är mjuka och vattnet absorberats. Följ längre koktid på förpackningen vid behov.',minutes=18)
        row['steps'][2]['text'] = 'Kontrollera att riset är mjukt och stäng av värmen.'
        insert_step(row,4,{'text':'Låt riset vila fem minuter under lock.','uses':['ris'],'minutes':5,'passive':True})
        prep=next(s for s in row['steps'] if s['text'].startswith('Pressa tofun'))
        prep['text']='Väg tofun före pressning, pressa den lätt och torka ytan; skär i jämna bitar. Väg frysta gröna bönor direkt utan upptining.' + (' Kärna ur paprikan och ansa salladslöken, väg den ätliga mängden och strimla.' if row['variant_id']=='extended' else '')
        prep['uses'].remove('torkade makrutlimeblad')
        sauce=next(s for s in row['steps'] if s['text'].startswith('Sänk värmen. Fräs currypastan'))
        sauce['text']='Sänk värmen. Fräs currypastan med återstående olja kort och tillsätt soja, socker och hela den silade limebladsinfusionen. Rör tills sockret lösts. Vänd ner de frysta bönorna' + (' och paprikan' if row['variant_id']=='extended' else '') + ' och koka under omrörning minst sju minuter eller längre enligt bönförpackningen tills bönorna är genomvarma och mjuka. Låt vätskan nästan koka bort; ingen bönvätska hälls bort.'
        sauce['minutes']=10
        row['steps'][-1]['text']+=' Skrapa ur och servera all kryddpasta och stekolja samt eventuell gurkdressing.'
        row['steps']=[
            {'text':'Väg de torkade limebladen och lägg i en liten kastrull med 100 ml vatten. Koka upp och sänk värmen.','uses':['torkade makrutlimeblad'],'minutes':3},
            {'text':'Sjud limebladen under lock på låg värme i 15 minuter.','uses':['torkade makrutlimeblad'],'minutes':15,'passive':True},
            {'text':'Sila infusionen genom en finmaskig sil. Ta bort alla blad och hårda fragment. Behåll hela den silade vätskan och fyll på med vatten till totalt 100 ml vatten.','uses':['torkade makrutlimeblad'],'minutes':3},
            *row['steps'],
        ]
        for n,s in enumerate(row['steps']):
            s['after']=[n] if n else []
        mark_process(row,3,['torkade makrutlimeblad'],'remove_after_infusion','Torra blad och fragment silas bort efter infusion. Överföring till vattnet och kvarvarande ämnesmängd är inte uppmätta.')
        press=next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Väg tofun'))
        mark_process(row,press,['tofu'],'drain_before_cooking','Tofun vägs före lätt pressning och avtorkning. Förlorad vätskemassa är inte uppmätt.')
        changes.append('Use 1 g separately reviewed dried makrut leaves as a new dose, simmer and strain all fragments before reducing the infusion in curry. No fresh/dry conversion or nutrient extraction assumption. Keep tofu pressing as unknown loss, cook frozen beans without discarding liquid, retain all oil/dressing, scale both process-water amounts and split rice inspection from waiting.')
    if base.endswith('chicken-65-pannstekt'):
        row['name'] += ' – paprika och cayenne, utan curryblad'
        row['flavor'] = ['paprika', 'cayenne', 'yoghurt']
        row['notes'] = 'Uttrycklig Chicken 65-inspirerad pannversion utan curryblad, med ny dos 3 g paprika och 0,3 g cayenne i stället för 3 g kashmirichili. Inte samma arom eller styrka. Yoghurtmarinad och stärkelsehölje behålls; huvudrätten serveras med ris. Upptiningsvätska och kvarvarande stekolja kasseras med okänd förlust. Inte provlagad.'
        for c in row['components']:
            c['ingredients'] = [i for i in c['ingredients'] if i['name'] != 'curryblad']
            for i in c['ingredients']:
                if i['name'] == 'kashmirichilipulver':
                    i.update(name='paprikapulver', quantity=3, label='Paprikapulver')
                if i['name'] == 'kyckling':
                    i['label'] = 'Benfri kyckling, vägd före eventuell upptining'
            if c['id'] == 'c1':
                c['ingredients'].append({'name':'cayennepeppar','form':'dry','quantity':0.3,'unit':'g','role':'flavour','label':'Cayennepeppar'})
        marinade = row['steps'][0]
        marinade['text'] = marinade['text'].replace('chilipulver', 'paprika och cayenne').replace('finriven vitlök', 'hackad färsk eller fryst vitlök')
        marinade['uses'] = ['paprikapulver' if n == 'kashmirichilipulver' else n for n in marinade['uses']] + ['cayennepeppar']
        starch = next(s for s in row['steps'] if s['text'].startswith('Skölj currybladen'))
        starch['text'] = starch['text'].replace('Skölj currybladen och torka dem helt torra. ', '') + ' Skrapa ner all marinad från skålen på kycklingen så att den genomsteks med bitarna.'
        starch['uses'].remove('curryblad')
        fry = next(s for s in row['steps'] if s['text'].startswith('Värm oljan'))
        fry['text'] = fry['text'].replace('i två eller tre omgångar', 'i omgångar utan att tränga bitarna').replace('Lägg färdiga bitar på ett rent fat', 'Låt färdiga bitar rinna av kort på hushållspapper på ett rent fat')
        row['steps'][-1].update(text='Servera de genomstekta kycklingbitarna genast med riset.' + (' Servera hela den kalla gurk- och myntayoghurten separat.' if row['variant_id'] == 'extended' else '') + ' Kvarvarande stekolja och papperets fett kasseras.', uses=['kyckling','ris','rapsolja'], minutes=2)
        for s in row['steps']:
            if 'tärna gurkan fint' in s['text']:
                s['text'] = s['text'].replace('hacka myntan', 'hacka de uppvägda färska myntabladen') + ' Behåll all gurksaft.'
            if s['text'].startswith('Skölj riset'):
                s['text'] = s['text'].replace('Skölj riset. ', '')
            if s['text'].startswith('Sjud riset'):
                s.update(text='Sjud riset svagt cirka 15 minuter eller enligt förpackningens längre anvisning.', minutes=15)
        rice_wait = next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Sjud riset'))
        insert_step(row, rice_wait+1, {'text':'Kontrollera att riset är mjukt och stäng av värmen.','uses':['ris'],'minutes':1})
        insert_step(row, rice_wait+2, {'text':'Låt riset vila fem minuter under lock.','uses':['ris'],'minutes':5,'passive':True})
        row['steps'] = [
            {'text':'Väg kycklingen före eventuell upptining och lägg i täckt kärl i kylskåp vid cirka 4 °C. Redan helt tinad kyckling behöver inte upptining.','uses':['kyckling'],'minutes':1},
            {'text':'Planera 24 timmars kylupptining för fryst kyckling, eller längre enligt förpackningen tills inga iskärnor återstår.','uses':['kyckling'],'minutes':1440,'passive':True},
            {'text':'Kontrollera att kycklingen är helt tinad. Häll bort fri upptiningsvätska och klappa bitarna torra med hushållspapper. Tvätta händer och redskap efter rå kyckling.','uses':['kyckling'],'minutes':3},
            *row['steps'],
        ]
        for n,s in enumerate(row['steps']):
            s['after'] = [n] if n else []
        mark_process(row, 3, ['kyckling'], 'drain_before_cooking', 'Kycklingens inköpsmassa vägs före eventuell upptining; kasserad upptiningsvätska och papperets fukt ger okänd ätlig slutmassa.')
        fry_index = next(n for n,s in enumerate(row['steps'],1) if s['text'].startswith('Värm oljan'))
        mark_process(row, fry_index, ['rapsolja'], 'deep_fry_and_drain', 'Kycklingen pannsteks i uppmätt olja och får rinna av. Upptagen olja är inte uppmätt och kvarvarande olja kasseras.')
        changes.append('Explicit curry-leaf-free pan adaptation with new 3 g paprika and 0.3 g cayenne dose, not a Kashmiri chilli identity or aroma equivalent. Preserve yoghurt/starch, ginger/garlic/lemon and extended rice-flour/cucumber/mint differences. Plan cold thaw; mark unknown drip and frying-oil losses, cook all marinade, use 74 C checks, scalable rice water and portion-neutral batch wording.')
    if base.endswith('pasta-patate-provola'):
        rename_ingredient(row, 'rökt provola', 'mozzarella')
        row['name'] = row['name'].replace('rökt provola', 'avrunnen mozzarella') + ' – utan rökt ost'
        row['family'] = 'Pasta e patate con mozzarella'
        row['flavor'] = ['mozzarella', 'potatis', 'tomat']
        row['notes'] = 'Granskad orökt mozzarellaversion: ny dos 200 g avrunnen mozzarella ersätter 180 g rökt provola, utan samma smak eller vattenhalt. Torr kort pasta och potatis kokar i samma gryta och all stärkelsehaltig vätska serveras. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'mozzarella':
                    i.update(quantity=200, form='preserved_drained', label='Mozzarella, vägd utan fri lag efter avrinning')
                if i['name'] == 'pasta':
                    i.update(requirements=['pack:pasta'], label='Kort pasta, exempelvis penne eller rigatoni')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skala potatisen och skär', 'Skala potatisen, väg den råa ätliga mängden och skär').replace('tärna osten', 'låt mozzarellan rinna av utan att pressa, väg utan fri lag och tärna')
        original = row['steps'][2]
        original.update(text='Tillsätt potatis, salt, peppar och 1000 ml vatten. Koka upp och sänk värmen.', minutes=3, passive=False)
        insert_step(row, 4, {'text':'Sjud under lock cirka 15 minuter tills potatisen är nästan mjuk.','uses':['potatis'],'minutes':15,'passive':True})
        pasta = next(s for s in row['steps'] if 'Lägg ner den torra pastan' in s['text'])
        pasta['text'] = pasta['text'].replace('Lägg ner den torra pastan.', 'Kontrollera att potatisen nästan är mjuk. Lägg ner den torra korta pastan; följ längre koktid på förpackningen vid behov.')
        finish = next(s for s in row['steps'] if 'Vänd ner provolan' in s['text'])
        finish['text'] = finish['text'].replace('provolan', 'den avrunna mozzarellan').replace(' Riv ner basilikan.', '')
        if row['variant_id'] != 'simple':
            pasta['text'] += ' Tillsätt färsk eller fryst hackad basilika minst tre minuter före koktidens slut, eller tidigare enligt förpackningen.'
            pasta['uses'].append('basilika')
            finish['uses'].remove('basilika')
        row['steps'][-1]['text'] += ' Behåll all grytsås och eventuell salladsdressing.'
        for n,s in enumerate(row['steps']):
            s['after'] = [n] if n else []
        changes.append('Visible unsmoked 200 g drained-mozzarella dose replaces 180 g smoked provola. Require short pasta before qualification. Retain potato-starch one-pot method, vegetable differences and salad; boil frozen herbs before cheese incorporation. Count loading/boiling separately from passive simmering; retain all cooking liquid and dressing.')
    if base.endswith('tsouxti-mani'):
        rename_ingredient(row, 'myzithra', 'fetaost')
        row['name'] = row['name'].replace('brynt myzithra', 'brynt smör och smulad feta') + ' – fetaversion'
        row['primary'] = 'fetaost och ägg'
        row['family'] = 'pasta med brynt smör och separat stekt ägg'
        row['flavor'] = ['brynt smör', 'feta', 'ägg']
        row['notes'] = 'Granskad fetaversion: ny dos 100 g feta ersätter 120 g myzithra. Smöret bryns, medan den fuktigare fetan smulas över pastan och inte steks till torra ostkorn. Ingen lika sälta, smak eller konsistens påstås. Äggen steks separat till fast gula. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'fetaost':
                    i.update(quantity=100, label='Fetaost utan fri lag')
        for s in row['steps']:
            s['text'] = s['text'].replace('Riv myzithran fint.', 'Smula den vägda fetan utan fri lag.')
            s['text'] = s['text'].replace('mellan fyra portioner', 'mellan det angivna antalet portioner')
        cook = next(n for n,s in enumerate(row['steps'],1) if 'Koka pastan till' in s['text'])
        row['steps'][cook-1]['text'] = 'Koka pastan cirka nio minuter eller enligt förpackningen tills den är nästan färdig.'
        insert_step(row, cook+1, {'text':'Kontrollera pastan. Spara 80 ml vatten från pastakoket och häll sedan av pastan.','uses':['pasta','salt'],'minutes':2})
        mark_process(row, cook+1, ['pasta','salt'], 'drain_after_cooking', 'Saltat pastavatten hälls delvis bort; en mindre del används vid servering. Stärkelseförlust och saltupptag är inte uppmätta.')
        brown = next(s for s in row['steps'] if 'Smält smöret' in s['text'])
        brown.update(text='Smält smöret med hälften av huvudkomponentens olivolja i en bred panna. Rör på medel-låg värme tills smörets mjölkpartiklar är gyllenbruna och doftar nötigt. Ta omedelbart från värmen innan de blir svarta. Fetan ska inte stekas i detta steg.', uses=['smör','olivolja'])
        toss = next(s for s in row['steps'] if 'Vänd pastan i' in s['text'])
        toss.update(text='Vänd pastan i hela det brynta smöret. Tillsätt lite av det sparade pastavattnet om den klibbar. Smula fetan över pastan; rätten ska inte kokas till ostsås. Håll varmt tills äggen är klara.', uses=['pasta','smör','olivolja','fetaost'])
        row['steps'][-1]['text'] += ' Fördela allt brynt smör och stekfett över portionerna.'
        if row['variant_id'] == 'extended':
            salad = row['steps'][0]
            salad['text'] = salad['text'].replace('och hackad persilja', '')
            salad['uses'].remove('persilja')
            toss['text'] = 'Rör ner fryst hackad persilja och hela det sparade pastavattnet i det brynta smöret. Koka under omrörning minst tre minuter eller längre enligt förpackningen. Vänd sedan ner pastan, smula över fetan och håll varmt utan att koka osten till sås.'
            toss['uses'].append('persilja')
            toss['minutes'] = 6
        for n,s in enumerate(row['steps']):
            s['after'] = [n] if n else []
        changes.append('Visible feta version: 100 g feta replaces 120 g dry myzithra. Brown only the butter; keep feta as a crumbled topping rather than falsely frying wet cheese into dry grains. Retain separately fried whole-yolk eggs and meaningful salads. Mark unknown salted-pasta drainage; extended frozen parsley cooks in retained butter/water. Serving text scales and all pan fat is served.')
    if base.endswith('tod-man-pla'):
        rename_ingredient(row, 'makrutlimeblad', 'citrongräs')
        row['name'] += ' – citrongräsversion utan makrutblad'
        row['flavor'] = ['citrongräs' if f == 'makrut' else f for f in row['flavor']]
        row['notes'] = 'Granskad citrongräsversion: 12 g hel färsk stjälk före ansning ersätter 4 g makrutblad som en ny dos. Hårda delar tas bort och enbart mjukt innanmäte finhackas. Ingen likvärdig arom eller ätlig vikt påstås. Upptiningsförlust och kvarvarande stekolja är okända. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'citrongräs':
                    i.update(quantity=12, form='as_sold', label='Hel färsk citrongrässtjälk, vägd före ansning')
                if i['name'] == 'jordnötter':
                    i.update(name='rostade jordnötter', label='Rostade osaltade jordnötter')
        old = copy.deepcopy(row['steps'])
        for s in old:
            s['uses'] = ['rostade jordnötter' if n == 'jordnötter' else n for n in s['uses']]
            s['text'] = s['text'].replace('rosta och hacka jordnötter', 'hacka de rostade osaltade jordnötterna')
        old[1].update(text='Sjud riset under lock cirka 18 minuter tills vattnet absorberats; följ längre koktid på förpackningen vid behov.', minutes=18)
        prep = next(s for s in old if 'Tina gröna bönor' in s['text'])
        prep.update(text='Väg citrongräset före ansning. Skär bort torr rotände, hårda ytterlager och vedartad topp. Finhacka och mortla det mjuka innanmäte som återstår mycket fint. Lägg gröna bönor direkt från frysen i en liten kastrull med 50 ml vatten. Koka under omrörning minst tre minuter, eller längre enligt förpackningen, tills mjuka. Låt fritt vatten koka in utan att hälla bort det och skär bönorna smått. Håll fisk och mixerskål kalla.', minutes=12)
        mix = next(s for s in old if 'Mixa fisken' in s['text'])
        mix['text'] = mix['text'].replace('Mixa fisken med ägg', 'Knäck och väg rått ägg utan skal. Mixa den kalla fisken med ägg').replace('makrutblad', 'det finhackade mjuka citrongräset')
        form = next(s for s in old if 'Forma sedan sexton' in s['text'])
        form['text'] = form['text'].replace('Forma sedan sexton tunna kakor', 'Forma sedan fyra tunna kakor per portion')
        fry = next(s for s in old if 'Stek i omgångar' in s['text'])
        fry['text'] = fry['text'].replace('minst 70 °C', 'minst 72 °C') + ' Lyft kakorna till galler och låt fri olja rinna av; kvarvarande olja serveras inte.'
        row['steps'] = [
            {'text':'Väg den råa benfria fiskfilén före upptining och lägg täckt i kylskåp. Kontrollera att inga ben finns kvar.','uses':['fisk'],'minutes':2},
            {'text':'Tina fryst fisk helt i kylskåp enligt förpackningen. Planera tolv timmar och förläng om iskärnor återstår.','uses':['fisk'],'minutes':720,'passive':True},
            {'text':'Häll bort fri upptiningsvätska och torka fiskens yta lätt. Håll filén kall; dess vikt efter avrinning är inte förutsatt.','uses':['fisk'],'minutes':2},
            *old[:2],
            {'text':'Kontrollera att riset är mjukt och stäng av värmen.','uses':['ris'],'minutes':1},
            {'text':'Låt riset vila fem minuter under lock.','uses':['ris'],'minutes':5,'passive':True},
            *old[2:],
        ]
        for n,s in enumerate(row['steps']):
            s['after'] = [n] if n else []
        mark_process(row, 3, ['fisk'], 'drain_before_cooking', 'Fri upptiningsvätska från rå benfri fisk hälls bort; kvarvarande ätlig massa och ämnesförlust är okända.')
        prep_index = next(n for n,s in enumerate(row['steps'],1) if 'Väg citrongräset' in s['text'])
        mark_process(row, prep_index, ['citrongräs'], 'trim_before_cooking', 'Hela stjälkens inköpsvikt föregår borttagning av hårda delar. Ingen andel mjukt innanmäte antas.')
        fry_index = next(n for n,s in enumerate(row['steps'],1) if 'Stek i omgångar' in s['text'])
        mark_process(row, fry_index, ['rapsolja'], 'deep_fry_and_drain', 'Kakorna pannsteks i uppmätt olja och får rinna av. Oljeupptag och kvarvarande stekolja är inte uppmätta; inköpt olja är inte konsumerad mängd.')
        changes.append('Explicit 12 g gross whole-lemongrass dose replaces 4 g makrut leaves. Retain springy raw-fish/egg/curry texture and chopped beans. Plan cold thaw, mark unknown drip/trim/frying losses, cook frozen beans with their liquid retained and use roasted unsalted peanuts. Portion-neutral four-cake instruction and separate rice inspection/rest; frozen fish remains cold until mixing.')
    if base.endswith('khao-tom-mat'):
        assert row['variant_id'] == 'simple'
        row['components'][0]['ingredients'] = [i for i in row['components'][0]['ingredients'] if i['name'] != 'bananblad']
        row['name'] += ' – i bakpapperspaket utan bananblad'
        row['flavor'] = ['kokos', 'banan']
        row['equipment'] = ['ångkastrull med insats och lock', 'kastrull', 'sil', 'livsmedelsgodkänt bakplåtspapper', 'livsmedelssnöre']
        row['notes'] = 'Granskad bakpappersversion: bananbladens arom saknas. Papper och snöre är tillagningsutrustning som tas bort, inte livsmedel. Vanlig fast mogen banan används; ingen nam wa-sort påstås. Inte provlagad.'
        row['steps'] = [
            {'text':'Skölj klibbigt ris i sil och lägg i 180 ml vatten. Täck och ställ i kylskåp vid 4 °C.','uses':['klibbigt ris'],'minutes':3},
            {'text':'Blötlägg riset åtta timmar i kylskåp.','uses':['klibbigt ris'],'minutes':480,'passive':True},
            {'text':'Häll bort blötläggningsvattnet och låt riset rinna av i sil.','uses':['klibbigt ris'],'minutes':2},
            {'text':'Värm kokosmjölk, socker och salt i en liten kastrull. Lägg i riset och sjud under tät omrörning cirka tolv minuter tills vätskan absorberats och kornen mjuknat på ytan. Behåll hela kokosblandningen.','uses':['klibbigt ris','kokosmjölk','strösocker','salt'],'minutes':15},
            {'text':'Bred ut riset i en grund skål. Klipp bakplåtspapper till dubbla omslag för två små paket per portion. Skala bananen och väg den angivna ätliga mängden; dela i bitar som ryms i paketen.','uses':['klibbigt ris','banan'],'minutes':5},
            {'text':'Låt riset svalna åtta minuter tills det går att hantera.','uses':['klibbigt ris'],'minutes':8,'passive':True},
            {'text':'Fördela ris och banan i två små paket per portion, med ris runt bananen. Vik in papprets sidor och ändar tätt och bind med livsmedelssnöre. Fyll ångkastrullen med 1000 ml vatten under insatsen, koka upp och lägg paketen i insatsen med plats för ångan.','uses':['klibbigt ris','banan'],'minutes':10},
            {'text':'Ånga paketen under lock över stadig ånga i 25 minuter.','uses':['klibbigt ris','banan'],'minutes':25,'passive':True},
            {'text':'Kontrollera vattennivån försiktigt och fyll vid behov på 300 ml vatten (hett) utan att vattnet når paketen. Lägg tillbaka locket.','uses':['klibbigt ris'],'minutes':1},
            {'text':'Ånga ytterligare 25 minuter.','uses':['klibbigt ris','banan'],'minutes':25,'passive':True},
            {'text':'Öppna ett paket försiktigt: riset ska sakna hård kärna. Förläng ångningen vid behov. Lyft paketen till ett fat.','uses':['klibbigt ris','banan'],'minutes':2},
            {'text':'Låt paketen svalna tio minuter.','uses':['klibbigt ris','banan'],'minutes':10,'passive':True},
            {'text':'Ta bort allt papper och snöre. Servera hela ris- och bananfyllningen, två små paket per portion. Kyl eventuella rester snabbt i små portioner och förvara vid 4 °C.','uses':['klibbigt ris','banan'],'minutes':2},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        mark_process(row, 3, ['klibbigt ris'], 'drain_before_cooking', 'Blötläggningsvattnet hälls bort; eventuell överföring av risets ämnen är inte uppmätt.')
        changes.append('Remove 35 g banana-leaf process wrapping; explicitly use baking paper as equipment, losing leaf aroma. Preserve all food doses and two small parcels per serving. Separate soaking drainage, handling, steam-water inspection, doneness check and serving from passive time; no invented soaking retention.')
    if base.endswith('pasta-ncasciata'):
        rename_ingredient(row, 'caciocavallo', 'mozzarella')
        row['name'] += ' – mozzarellaversion'
        row['flavor'] = ['mozzarella' if f == 'caciocavallo' else f for f in row['flavor']]
        row['notes'] = 'Granskad mozzarellaversion. Ny dos 200 g avrunnen mozzarella ersätter 160 g caciocavallo utan påstående om lika smak, vattenhalt eller utbyte. Ägg vägs råa utan skal och tillagas i vattenbad till fast inlägg. Inte provlagad.'
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'mozzarella':
                    i.update(quantity=200, form='preserved_drained', label='Mozzarella, vägd efter avrinning utan fri lag')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Tärna auberginen och osten.', 'Väg auberginen utan stjälk. Låt mozzarellan rinna av utan att pressa, väg utan fri lag och tärna båda.')
        row['steps'][1].update(text='Sjud vattenbadet med löst täckt äggskål under lock cirka tolv minuter.', passive=True)
        insert_step(row, 3, {'text':'Kontrollera att hela äggmassan är fast och minst 72 °C; förläng annars. Lyft skålen ur vattenbadet och ställ åt sidan tills ägget går att skära.','uses':['ägg'],'minutes':2})
        meat = next(s for s in row['steps'] if 'Stek auberginen' in s['text'])
        meat['text'] += ' Behåll all olja och köttsaft i rätten; använd inget avtorkningspapper.'
        simmer = next(s for s in row['steps'] if 'Rör ner krossade tomater' in s['text'])
        simmer.update(passive=False, text=simmer['text'] + ' Rör regelbundet och skrapa bottnen; detta räknas som aktiv tillsyn.')
        pasta = next(n for n,s in enumerate(row['steps'],1) if 'Koka pastan i' in s['text'])
        mark_process(row, pasta, ['pasta'], 'drain_after_cooking', 'Pastavattnet hälls bort; stärkelseförlust och färdig vikt är inte uppmätta. Saltet tillsätts ragùn, inte pastavattnet.')
        combine = next(s for s in row['steps'] if 'Blanda pasta, ragù' in s['text'])
        combine['text'] = combine['text'].replace('caciocavallo', 'den vägda avrunna mozzarellan').replace('riven basilika', 'färsk eller fryst hackad basilika')
        if row['variant_id'] == 'extended':
            combine['text'] = combine['text'].replace('Blanda parmesan', 'Blanda färdigriven parmesan')
        bake = next(s for s in row['steps'] if 'Gratinera cirka' in s['text'])
        bake['text'] = 'Gratinera vid 200 °C cirka 25 minuter tills pastan är mjuk och gratängen bubblar även i mitten.'
        check = row['steps'].index(bake) + 2
        insert_step(row, check, {'text':'Kontrollera minst 72 °C i centrum och att eventuell fryst basilika varit genomhet minst tre minuter. Förläng vid behov och lyft sedan ut formen.','uses':['nötfärs','ägg','mozzarella'] + (['basilika'] if row['variant_id'] != 'simple' else []),'minutes':2})
        row['steps'][-1]['text'] = 'Låt gratängen vila åtta minuter.'
        row['steps'].append({'text':'Fördela hela gratängen inklusive all sås mellan det angivna antalet portioner.','uses':['pasta','nötfärs','mozzarella'],'minutes':2})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Visible new 200 g drained-mozzarella dose replaces 160 g caciocavallo. Preserve beef, aubergine, firm egg filling and distinct onion/herb/pea/crust variants. Retain all frying fat and sauce, mark unknown pasta drainage, cook frozen herbs, use grated parmesan, separate egg/oven checks and serving from passive periods.')
    if base.endswith('nam-prik-ong'):
        row['flavor'] = ['fisksås' if f == 'räkpasta' else f for f in row['flavor']]
        dip = next(c for c in row['components'] if c['id']=='dipp')
        dip['ingredients'] = [i for i in dip['ingredients'] if i['name']!='räkpasta']
        sauce = next((i for i in dip['ingredients'] if i['name']=='fisksås'), None)
        if sauce is None:
            sauce = {'name':'fisksås','form':'as_sold','quantity':20,'unit':'ml','role':'flavour','label':'Fisksås, ny kulinarisk dos'}
            dip['ingredients'].append(sauce)
        else:
            sauce.update(quantity=30, label='Fisksås, ny kulinarisk dos')
        for step in row['steps']:
            step['uses'] = list(dict.fromkeys('fisksås' if n=='räkpasta' else n for n in step['uses']))
        row['name'] += ' – fisksåsversion utan räkpasta'
        row['notes'] = 'Granskad fisksåsversion: 15 g räkpasta utgår. Enkel använder 20 ml fisksås; övriga använder totalt 30 ml i stället för tidigare 20 ml plus räkpastan. Detta är nya doser, inte likvärdig sälta eller fermenterad smak. Såsen innehåller fortfarande fisk. Inte provlagad.'
        row['steps'][3]['text'] = 'Skala och väg schalottenlöken, dela den och rosta i torr panna tills mjuk med mörka fläckar. Färsk vitlök kan rostas med löken; fryst hackad vitlök läggs direkt i mixern med all sin vätska. Mixa löken, vitlöken och chiliflakes med 100 ml vatten till grov pasta.'
        row['steps'][3]['uses'].remove('fisksås')
        row['steps'][4]['text'] = 'Väg rå ätlig tomat och tärna. Värm oljan och fräs kryddpastan ett par minuter. Tillsätt färsen och finfördela, rör ner tomater och hela fisksåsmängden' + (' samt sockret.' if row['variant_id']!='simple' else '.') + ' Behåll allt fett och köttsaft.'
        old = copy.deepcopy(row['steps'])
        old[1]['text'] = 'Sjud riset under lock cirka 18 minuter tills vattnet absorberats. Följ förpackningens koktid och förläng vid behov.'
        old[1]['minutes'] = 18
        row['steps'] = old[:2] + [
            {'text':'Kontrollera att riset är mjukt, stäng av värmen och lägg på locket.','uses':['ris'],'minutes':1},
            {'text':'Låt riset vila under lock i fem minuter.','uses':['ris'],'minutes':5,'passive':True},
            *old[2:5],
            {'text':'Låt dippen sjuda utan lock på låg värme i tio minuter.','uses':['fläskfärs','tomat'],'minutes':10,'passive':True},
            {'text':'Rör från botten och kontrollera att inget bränner fast. Justera värmen.','uses':['fläskfärs','tomat'],'minutes':1},
            {'text':'Sjud ytterligare tio minuter utan lock.','uses':['fläskfärs','tomat'],'minutes':10,'passive':True},
            {'text':'Rör om och kontrollera minst 72 °C i färsen. Reducera under omrörning tills dippen är tjock nog att ligga kvar på en grönsaksbit; räkna med fem minuter och förläng vid behov. Behåll hela dippen.','uses':['fläskfärs','tomat'],'minutes':5},
            old[-1]]
        row['steps'][-1]['text'] += ' Grönsakerna vägs ansade som rå ätlig mängd. Behåll all eventuell limedressing.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Remove shrimp paste; explicit fish-sauce doses are 20 ml simple / 30 ml standard and extended, not equal taste/salt conversions. Preserve sugar and expanded raw-vegetable differences. Frozen minced garlic goes into the cooked paste. Separate rice heat-off and periodic dip stirring/temperature checks from passive cooking; retain all fat and sauce.')
    if base.endswith('patishapta'):
        rename_ingredient(row, 'jaggery', 'mörkt muscovadosocker')
        row['flavor'] = ['muscovado' if f == 'gur' else f for f in row['flavor']]
        row['side'] = 'kokos-muscovadofyllning'
        row['name'] += ' – med mörkt muscovadosocker'
        row['notes'] = 'Granskad version med mörkt muscovadosocker, inte jaggery. Ny dos 10 g ersätter 12 g jaggery per portion utan påstående om samma sötma eller melassmak. Kokosfyllningen och de tunna ris-vetepannkakorna behålls. Inte provlagad.'
        for c in row['components']:
            c['name'] = c['name'].replace('kokos och gur', 'kokos och muscovado')
            for item in c['ingredients']:
                if item['name']=='mörkt muscovadosocker':
                    item.update(quantity=10,form='dry',label='Mörkt muscovadosocker')
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('Riv ner jaggery', 'Rör ner det uppvägda mörka muscovadosockret').replace('tillsätt kardemumman', 'tillsätt malen kardemumma')
        row['steps'][2]['text'] += ' Behåll hela kokos- och sockerblandningen; koka endast bort överskottsvatten.'
        row['steps'][-1]['text'] = 'Lägg rullarna på tallrikar och låt svalna något. Fördela hela fyllningen och alla pannkakor mellan portionerna; ingen extra sås behövs.'
        changes.append('Visible 10 g dark muscovado dose instead of 12 g jaggery per portion, with no sweetness equivalence. Preserve milk/semolina/cardamom variation and thin rolled rice-wheat crepes. Coconut liquid is reduced and fully retained; serving text follows actual portions.')
    if base.endswith('rajas-con-crema'):
        rename_ingredient(row, 'poblano', 'paprika')
        row['primary'] = 'paprika'
        row['name'] = row['name'].replace('rostade poblano', 'rostad paprika och jalapeño') + ' – med färdiga majstortillas'
        row['flavor'] = ['rostad paprika', 'jalapeño', 'grädde', 'majs']
        row['equipment'] = ['ugn', 'plåt', 'värmetålig skål med lock', 'stekpanna']
        row['notes'] = 'Granskad paprika- och jalapeñoversion, utan poblano. Den angivna paprikamängden vägs urkärnad men med skinn före rostning; skalets förlust är okänd. Jalapeñon är en separat dos på 6 g, inte påstådd likvärdig hetta. Färdiga mjuka majstortillas ersätter degberedningen. Inte provlagad.'
        main = next(c for c in row['components'] if c['id']=='rajas')
        main['name'] = 'Rostade paprikastrimlor i grädde'
        main['ingredients'].append({'name':'jalapeño','form':'raw_edible','quantity':6,'unit':'g','role':'flavour','label':'Naturell hackad fryst jalapeño'})
        for item in main['ingredients']:
            if item['name']=='paprika':
                item['label'] = 'Paprika, rå urkärnad mängd med skinn före rostning'
            if item['name']=='mozzarella':
                item.update(form='preserved_drained', label='Mozzarella, vägd efter avrinning utan fri lag')
        bread = next(c for c in row['components'] if c['id']=='majsbrod')
        bread.update(name='Färdiga mjuka majstortillas', ingredients=[{'name':'majstortillas','form':'as_sold','quantity':400,'unit':'g','role':'side','label':'Färdiga mjuka majstortillas'}])
        row['steps'] = row['steps'][3:]
        row['steps'][0]['text'] = 'Sätt ugnen på 240 °C grill. Dela paprikan, ta bort stjälk och kärnhus och väg den råa ätliga mängden med skinn kvar. Lägg halvorna med skinnet uppåt på plåt. Grilla under uppsikt cirka 18 minuter tills skinnet blåser upp och mörknar fläckvis; fruktköttet ska inte brännas. Flytta vid behov plåten.'
        row['steps'][1]['text'] = 'Låt de rostade paprikahalvorna ånga och svalna under lock i tio minuter.'
        insert_step(row, 2, {'text':'Flytta de rostade paprikahalvorna och all fruktsaft till en värmetålig skål och lägg på lock.','uses':['paprika'],'minutes':1,'after':[1]})
        row['steps'][3]['text'] = 'Dra av löst mörkt skinn, behåll allt paprikakött och all saft och skär i breda strimlor. Skala och väg löken, skiva tunt.' + (' Hacka färsk vitlök eller väg fryst hackad vitlök.' if row['variant_id']!='simple' else '')
        row['steps'][4]['text'] = 'Värm oljan och mjukstek löken. Tillsätt den frysta hackade jalapeñon' + (' och vitlöken' if row['variant_id']!='simple' else '') + ' och fräs en minut. Vänd ner paprikastrimlorna med all saft och den frysta majsen, låt allt bli hett. Häll inte bort någon vätska.'
        row['steps'][4]['uses'].append('jalapeño')
        cream = row['steps'][5]
        cream['text'] = 'Häll i grädden och gräddkomponentens salt. Sjud under omrörning cirka sex minuter tills majsen är genomvarm och såsen omsluter grönsakerna.'
        if row['variant_id']!='simple':
            cream['text'] += ' Väg de kokta svarta bönorna efter avrinning och värm i såsen. Låt mozzarellan rinna av, väg utan fri lag och riv i små bitar. Rör i tills den smält.'
            cream['minutes'] = 12
        if row['variant_id']=='extended':
            salad = next(c for c in row['components'] if c['id']=='tomatsallad')
            coriander = next(i for i in salad['ingredients'] if i['name']=='koriander')
            salad['ingredients'].remove(coriander)
            main['ingredients'].append(coriander)
            cream['text'] += ' Den uppvägda frysta hackade koriandern ska sjuda i gräddsåsen minst tre minuter eller längre enligt förpackningen.'
            cream['uses'].append('koriander')
            row['steps'][6]['text'] = 'Väg rå ätlig tomat, tärna och vänd med limejuicen och salladens salt. Behåll hela dressingen.'
            row['steps'][6]['uses'].remove('koriander')
        last = row['steps'][-1]
        last['text'] = 'Väg den angivna mängden färdiga mjuka majstortillas och värm i torr panna enligt förpackningen tills böjliga. Fördela rajas med hela gräddsåsen mellan portionerna och servera med tortillorna.' + (' Lägg upp tomatsalladen med hela dressingen bredvid.' if row['variant_id']=='extended' else '')
        last['uses'] = ['majstortillas' if n=='masa harina' else n for n in last['uses']]
        last['minutes'] = 6
        for n,step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        mark_process(row, 4, ['paprika'], 'peel_after_cooking', 'Rostad paprika skalas efter att den råa urkärnade mängden vägts. Borttagen skinnmassa och näringsretention är inte uppmätta.')
        changes.append('Visible bell-pepper version with a separate 6 g frozen jalapeno dose, retaining roasting and skin removal with unknown loss. Ready-made 400 g corn tortillas replace 280 g masa plus dough salt, without yield equivalence. Standard/extended mozzarella is explicitly 120 g drained cheese, not as-sold mass. Frozen coriander cooks in the cream instead of raw salad; all sauce and dressing are retained.')
    if base.endswith('spetsofai'):
        rename_ingredient(row, 'grekisk lantkorv', 'färsk salsicciakorv')
        row['primary'] = 'färsk salsicciakorv'
        row['name'] = row['name'].replace('Spetsofai', 'Spetsofai med färsk salsiccia')
        row['notes'] = 'Granskad salsicciaversion med fläsk, fänkål och örter, inte grekisk loukaniko. Korven är rå och behåller sin ätliga svintarm. All olja, steksky och sås används. Inte provlagad.'
        first = row['steps'][0]
        first['text'] = first['text'].replace('Skär korven', 'Väg den råa färska salsicciakorven med sitt ätliga korvskinn kvar. Skär korven').replace('Kärna ur paprika och skär', 'Kärna ur paprikan, väg den ätliga mängden och skär')
        first['text'] += ' Skalad lök och ansad aubergine vägs som rå ätlig mängd när de ingår. Färsk vitlök hackas; fryst hackad vitlök används direkt i den varma pannan.'
        row['steps'][1]['text'] += ' Behåll allt utsmält fett och köttsaft i pannan och återför saften från den undanlagda korven.'
        row['steps'][3]['text'] = 'Sjud försiktigt under lock på glänt cirka 20 minuter.'
        insert_step(row, 5, {'text': 'Rör om och kontrollera att paprikan är mjuk, såsen omsluter korven och korvens mitt håller minst 72 °C. Följ även förpackningens tillagning och fortsätt vid behov tills korven är genomlagad. Behåll hela såsen.', 'uses': ['färsk salsicciakorv', 'paprika'], 'minutes': 2, 'after': [4]})
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('mellan fyra tallrikar', 'mellan portionerna')
        changes.append('Visible raw salsiccia alternative at 550 g, retaining edible casing, all fat and sauce. Separate active temperature check from passive simmering. Preserve aubergine/garlic and feta-cucumber variant differences; raw pork restrictions apply.')
    if base.endswith('pasta-alla-norma'):
        rename_ingredient(row, 'ricotta salata', 'lagrad pecorino')
        row['name'] = row['name'].replace('ricotta salata', 'lagrad pecorino')
        if 'pecorino' not in row['name']:
            row['name'] += ' – med lagrad pecorino'
        row['flavor'] = ['tomat', 'basilika', 'lagrad pecorino']
        row['notes'] = 'Uttrycklig pecorinoversion av auberginepastan. Ny dos 75 g lagrad pecorino vägd före borttagning av hård ytkant ersätter 100 g ricotta salata; ingen smak-, salt- eller utbytesekvivalens antas. Den ursprungliga ricotta salata-versionen bevaras. Inte provlagad.'
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'lagrad pecorino':
                    item.update(quantity=75, label='Lagrad pecorino, vikt före eventuell borttagning av hård kant')
        row['steps'][0]['text'] = 'Ansa auberginen, väg rå ätlig mängd och skär i jämna bitar. Väg den angivna pecorinon före eventuell hård ytkant, skär bort kanten och riv resten. Hacka färsk vitlök eller använd fryst hackad direkt vid tillagningen. Väg färska basilikablad utan grova stjälkar; fryst hackad basilika används direkt i den varma såsen.'
        row['steps'][3]['text'] = 'Sjud såsen utan lock på medellåg värme tills den tjocknat, cirka 15 minuter. Rör om ett par gånger.'
        row['steps'][3]['passive'] = False
        for step in row['steps']:
            step['text'] = step['text'].replace('ricotta salata', 'lagrad pecorino')
            if step['text'].startswith('Vänd aubergine och basilika'):
                step['text'] = step['text'].replace('och låt allt bli varmt.', 'och koka minst tre minuter eller längre enligt örtproduktens anvisning. Behåll all vätska.') + ' Fördela all sås och eventuell sallad med hela dess dressing.'
                step['minutes'] = 6
        mark_process(row, 1, ['lagrad pecorino'], 'trim_before_cooking', 'Pecorinons eventuella hårda ytkant tas bort efter vägning av inköpsmängden; ätligt utbyte är inte uppmätt.')
        drain = next(n for n,s in enumerate(row['steps'],1) if 'häll av' in s['text'])
        mark_process(row, drain, ['pasta', 'salt'], 'drain_after_cooking', 'Saltat pastavatten hälls bort utom den del som används i såsen. Pasta- och saltretention är inte uppmätta.')
        changes.append('New 75 g gross pecorino dose instead of 100 g ricotta salata, explicitly named. Unknown rind loss and salted pasta-water loss remain unmeasured. Stirring is active; basil is heated so frozen selected herbs are supported. Distinct fennel-orange and olive-almond salads retained.')
    if base.endswith('pitarakia-milos'):
        rename_ingredient(row, 'lagrad manoura', 'lagrad pecorino')
        row['primary'] = 'lagrad pecorino'
        row['name'] += ' – med feta och lagrad pecorino'
        row['notes'] = 'Granskad feta- och pecorinoversion, inte manoura från Milos. Ny fyllning av 15 g pecorino före putsning och 15 g feta ersätter 30 g manoura. Ostkant och oljeupptag är inte uppmätta. Inte provlagad.'
        fill = next(c for c in row['components'] if c['id']=='fill')
        next(i for i in fill['ingredients'] if i['name']=='lagrad pecorino').update(quantity=15, label='Lagrad pecorino, vikt före eventuell hård kant')
        fill['ingredients'].append({'name':'fetaost','form':'as_sold','quantity':15,'unit':'g','role':'primary','label':'Fetaost utan fri lag'})
        step = row['steps'][2]
        step['text'] = 'Väg pecorinon före borttagning av eventuell hård kant, skär bort kanten och riv resten. Smula den uppvägda fetaosten. Skala och väg löken, hacka mycket fint. Blanda ost, lök och svartpeppar. Kavla degen tunt mellan bakplåtspapper utan extra mjöl. Forma små rundlar med högst cirka en tesked fyllning i varje, vik till halvmånar och förslut kanterna noga. Använd hela degen och fyllningen.'
        step['uses'].append('fetaost')
        mark_process(row, 3, ['lagrad pecorino'], 'trim_before_cooking', 'Eventuell hård ostkant tas bort efter vägning. Ingen ätlig andel antas.')
        fry = next(n for n,s in enumerate(row['steps'],1) if 'Värm rapsoljan' in s['text'])
        mark_process(row, fry, ['rapsolja'], 'deep_fry_and_drain', 'Frityrbadets oljeupptag och kvarvarande olja är okända. Inköpsoljan är inte serverad konsumtionsmängd.')
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('hela småportionen', 'de färdiga portionerna')
        changes.append('Visible filling of 15 g gross pecorino plus 15 g feta replaces 30 g manoura per portion. Retain thin unyeasted dough, onion and frying; mark unknown rind loss and frying-oil absorption. Avoid fixed four-piece text when servings scale.')
    if base.endswith(('patatato-amorgos', 'tsigariasto-get')):
        rename_ingredient(row, 'getkött', 'lammkött')
        row['primary'] = 'lammkött'
        row['name'] = row['name'].replace('getkött', 'lammkött')
        row['notes'] = 'Granskad version med benfritt lamm i stället för get. Rå ätlig köttmängd anges efter eventuell putsning; ingen benandel eller kokförlust har antagits. Inte provlagad; tider är författaruppskattningar och mörheten avgör faktisk koktid.'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'lammkött':
                    item['label'] = 'Benfritt lammkött för långkok, rå ätlig vikt'
        for step in row['steps']:
            step['text'] = step['text'].replace('getköttet', 'lammköttet')
        first = row['steps'][0]
        first['text'] = first['text'].replace('Putsa lammköttet vid behov och skär', 'Putsa bort grova senor vid behov, väg därefter angiven rå ätlig mängd benfritt lamm och skär')
        if base.endswith('patatato-amorgos'):
            first['text'] = first['text'].replace('Skär lammköttet', 'Väg benfritt lamm efter eventuell putsning. Skär lammköttet').replace('Hacka löken.', 'Skala och väg löken, hacka den.').replace('Tärna morot och selleri grovt.', 'Ansa och väg rå ätlig morot och selleri, tärna grovt.')
            if row['variant_id'] == 'extended':
                rename_ingredient(row, 'rödvin', 'rött matlagningsvin')
                row['name'] += ' – med rött matlagningsvin'
                row['steps'][2]['text'] = row['steps'][2]['text'].replace('rödvinet', 'det röda matlagningsvinet')
                row['steps'][6]['text'] = 'Ta upp lagerbladen. Rör ner den uppvägda frysta hackade persiljan och låt den koka med minst tre minuter eller längre enligt förpackningen.'
                row['steps'][6]['minutes'] = 4
            old = copy.deepcopy(row['steps'])
            row['steps'] = old[:3]
            for turn in range(5):
                row['steps'].append({'text': 'Sjud försiktigt under tätt lock 20 minuter.', 'uses': ['lammkött'], 'minutes': 20, 'passive': True})
                row['steps'].append({'text': 'Rör om från botten och kontrollera att grytan inte kokar torr. Tillsätt vid behov 100 ml vatten. Efter sista omgången ska köttet börja bli mört; fortsätt annars sjuda med regelbundna kontroller innan potatisen tillsätts.', 'uses': ['lammkött'], 'minutes': 1})
            potato = old[4]
            potato['text'] = potato['text'].replace('Skala potatisen och skär', 'Skala potatisen, väg den råa ätliga mängden och skär')
            row['steps'].extend([potato,
                {'text': 'Sjud försiktigt med locket på glänt 15 minuter.', 'uses': ['potatis', 'lammkött'], 'minutes': 15, 'passive': True},
                {'text': 'Vänd försiktigt från botten utan att mosa potatisen. Kontrollera vätskan och tillsätt vid behov 50 ml vatten.', 'uses': ['potatis', 'lammkött'], 'minutes': 1},
                {'text': 'Sjud ytterligare cirka 15 minuter.', 'uses': ['potatis', 'lammkött'], 'minutes': 15, 'passive': True},
                {'text': 'Kontrollera att potatisen är helt mjuk och köttet delar sig med gaffel. Förläng vid behov. Behåll all olja och allt spad som tjocknat av potatisens stärkelse.', 'uses': ['potatis', 'lammkött', 'olivolja'], 'minutes': 2}])
            if row['variant_id'] != 'simple':
                row['steps'].append(old[6])
                mark_process(row, len(row['steps']), ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och tas bort före servering. Kvarvarande näring i såsen och bladens avgivning är inte uppmätta.')
            row['steps'].extend([
                {'text': 'Ta grytan från värmen och lägg på lock.', 'uses': ['potatis', 'lammkött'], 'minutes': 1},
                {'text': 'Låt grytan vila fem minuter av värmen.', 'uses': ['potatis', 'lammkött'], 'minutes': 5, 'passive': True},
                {'text': 'Fördela kött, potatis och hela såsen mellan portionerna.', 'uses': ['potatis', 'lammkött'], 'minutes': 2}])
        else:
            if row['variant_id'] != 'simple':
                rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
                row['name'] += ' – med vitt matlagningsvin'
                row['notes'] += ' Lök, vin, oregano och citron är uttryckliga tillägg till fåingredienstekniken.'
                row['steps'][1]['text'] = row['steps'][1]['text'].replace('Skiva löken och hacka vitlöken.', 'Skala och väg lök och vitlök, skiva löken och hacka vitlöken.').replace('vinet', 'det vita matlagningsvinet')
            index = next(n for n, s in enumerate(row['steps']) if s.get('passive'))
            periods = []
            for turn in range(6):
                periods.extend([
                    {'text': 'Låt köttet tillagas under tätt lock på mycket låg värme i 20 minuter.', 'uses': ['lammkött'], 'minutes': 20, 'passive': True},
                    {'text': 'Vänd köttet och kontrollera bottnen. Sänk värmen om det steker torrt; tillsätt endast vid behov 30 ml vatten så det inte bränner. Köttet ska tillagas i lite eget spad, inte täckas av vatten.', 'uses': ['lammkött'], 'minutes': 1}])
            periods.append({'text': 'Kontrollera att köttet är genomlagat och mycket mört. Förläng tillagningen vid behov med fortsatt tillsyn. Servera allt fett och det koncentrerade spadet.', 'uses': ['lammkött', 'olivolja'], 'minutes': 2})
            row['steps'][index:index + 1] = periods
            row['steps'][-1]['text'] += ' Väg den angivna brödmängden och behåll hela salladens saft om sallad ingår.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit boneless lamb version at the original edible gram dose, with meat named in the title and weighed after trimming. It is not a goat identity alias or a bone/cooking-yield conversion. Preserve the distinct patatato potato-in-tomato method or tsigariasto low-liquid method. Separate periodic checks and serving from passive time; retain all meat fat/gravy. Any wine becomes explicitly named reviewed cooking wine; no claim of complete alcohol evaporation.')
    if base.endswith('rogan-josh'):
        rename_ingredient(row, 'kashmirichilipulver', 'paprikapulver')
        row['name'] += ' – med paprika och cayenne'
        row['flavor'] = ['paprika', 'cayenne', 'fänkålsfrö', 'torkad ingefära']
        row['notes'] = 'Granskad vardagsanpassning av rogan josh med lamm, yoghurt, fänkålsfrö och torkad ingefära, utan tomat. Ny dos 8 g paprikapulver och 0,6 g cayenne ersätter 10 g kashmirichili utan påstående om samma hetta, smak eller färg. Rapsolja används i stället för senapsolja/ghee och ratanjot utelämnas. Inte provlagad; tiderna är uppskattningar.'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'paprikapulver':
                    item.update(quantity=8, label='Malt paprikapulver, inte rökt paprika')
                elif item['name'] == 'lammkött':
                    item.update(label='Benfritt lammkött för gryta, rå ätlig vikt')
                elif item['name'] in {'kardemumma', 'kryddnejlika', 'kanel'}:
                    item['label'] = 'Mald ' + item['name']
            if component['id'] == 'lamm':
                component['ingredients'].append({'name': 'cayennepeppar', 'form': 'dry', 'quantity': 0.6, 'unit': 'g', 'role': 'flavour', 'label': 'Malen cayennepeppar'})
        for step in row['steps']:
            if 'paprikapulver' in step['uses']:
                step['uses'].append('cayennepeppar')
            step['text'] = step['text'].replace('kashmirichili', 'paprikapulver och cayennepeppar')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skär lammköttet', 'Väg benfritt lammkött utan grova senor och skär det')
        row['steps'][0]['text'] += ' De eventuella övriga kryddorna används malda och stannar i såsen.'
        original = copy.deepcopy(row['steps'])
        row['steps'] = original[:2] + [
            {'text': 'Häll i 500 ml vatten och koka upp under omrörning. Sänk till svag sjudning och lägg på lock.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 3},
            {'text': 'Sjud försiktigt under lock 30 minuter.', 'uses': ['lammkött'], 'minutes': 30, 'passive': True},
            {'text': 'Rör i grytan och kontrollera att bottnen inte bränner. Tillsätt vid behov 100 ml vatten.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 1},
            {'text': 'Sjud ytterligare 30 minuter under lock.', 'uses': ['lammkött'], 'minutes': 30, 'passive': True},
            {'text': 'Rör igen och kontrollera vätskan. Tillsätt vid behov 100 ml vatten.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 1},
            {'text': 'Sjud ytterligare cirka 40 minuter under lock.', 'uses': ['lammkött'], 'minutes': 40, 'passive': True},
            {'text': 'Kontrollera att lammet är helt genomlagat och så mört att det delar sig lätt med gaffel. Förläng sjudningen vid behov och kontrollera regelbundet vätskan. Behåll allt fett och all sås.', 'uses': ['lammkött'], 'minutes': 2},
            {**original[3], 'text': original[3]['text'].replace('Skölj riset i sil. ', '')},
            {'text': 'Sjud riset under lock cirka 18 minuter eller längre enligt förpackningen, tills kornen är mjuka och vattnet absorberats.', 'uses': ['ris'], 'minutes': 18, 'passive': True},
            {'text': 'Kontrollera riset och ta från värmen. Om det fortfarande är hårt, tillsätt 50 ml vatten och fortsätt sjuda före vilan.', 'uses': ['ris'], 'minutes': 1},
            {'text': 'Låt riset vila fem minuter under lock.', 'uses': ['ris'], 'minutes': 5, 'passive': True},
            *original[5:]]
        for step in row['steps']:
            if step['text'].startswith('Riv gurkan'):
                step['text'] = 'Riv den uppvägda gurkan grovt och behåll all vätska. Hacka de uppvägda färska myntabladen och blanda gurka, all gurksaft och mynta med raitans yoghurt, citronjuice och salt. Raitan blir lösare än med pressad gurka. Ställ i kylskåp vid 4 °C till servering och servera hela mängden.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New visible paprika/cayenne recipe: 8 g paprika and 0.6 g cayenne replace 10 g Kashmiri chili without sensory equivalence. Keep boneless edible lamb, yoghurt, fennel and dried ginger; no tomato is added. Separate active liquid/softness/rice checks from 100-minute simmering and rice rest. All fat, ground spices and cucumber juice are retained; no invented cooking yield.')
    if base.endswith('frijoles-puercos'):
        rename_ingredient(row, 'mexikansk färsk chorizo', 'färsk chorizokorv')
        row['name'] += ' – med svensk färsk chorizo'
        row['primary'] = 'bönor och färsk chorizokorv'
        row['notes'] = row.get('notes', '').replace('AI-författat receptutkast, inte provlagat och ännu inte import-/produktgranskat av Smako. ', 'Granskad receptanpassning, inte provlagad. ')
        row['notes'] = row.get('notes', '').replace('Rå mexikansk chorizo är nödvändig identitet, inte spansk lufttorkad korv.',
            'Denna granskade version använder uttryckligen svensk rå färsk chorizo med fläsk och nöt; den är inte märkt som mexikansk korv.')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'färsk chorizokorv':
                    item.update(form='as_sold', quantity=35, label='Svensk rå färsk chorizokorv, vägd med fjälster')
        index = next(n for n, s in enumerate(row['steps'], 1) if 'färsk chorizokorv' in s['uses'])
        insert_step(row, index, {'text': 'Väg den råa färska chorizokorven före borttagning av fjälstret. Skär upp fjälstret, skrapa ur all korvfärs och kasta fjälstret. Använd separat skärbräda; tvätta händer och redskap efter rå korv.',
            'uses': ['färsk chorizokorv'], 'minutes': 3, 'after': [index - 1] if index > 1 else []})
        row['steps'][index]['after'] = [index]
        mark_process(row, index, ['färsk chorizokorv'], 'trim_before_cooking',
            'Fjälstret tas bort efter att hela råa korven vägts. Mängden och näringsförlusten är inte uppmätta; ingen ren köttandel antas.')
        row['steps'][index + 1]['text'] += ' Häll inte bort något stekfett; hela korvfärsen och allt fett blandas med bönorna.'
        row['steps'][-1]['text'] += ' Följ även tortillaförpackningens uppvärmningsanvisning.'
        changes.append('Explicit Swedish raw fresh chorizo alternative with pork and beef, not a Mexican identity alias. New gross dose 35 g before casing removal replaces 30 g raw casing-free mince without yield equivalence. Casing loss is unknown; all cooking fat enters the beans. Keep raw handling, 72 C centre check and separate salsa utensils.')
    if base.endswith('sillsallad'):
        rename_ingredient(row, 'inläggningssill', 'ätklar inläggningssill')
        rename_ingredient(row, 'ättiksgurka', 'saltgurka')
        rename_ingredient(row, 'kokta ägg', 'ägg')
        row['primary'] = 'ätklar inläggningssill'
        row['method'] = 'pot'
        row['name'] += ' – med ätklar sill och saltgurka'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'saltgurka':
                    item.update(quantity=80, label='Saltgurka, vägd efter avrinning')
                if item['name'] == 'ätklar inläggningssill':
                    item['label'] = 'Ätklar 5-minuterssill, vägd efter avrinning'
                if item['name'] == 'ägg':
                    item.update(quantity=4, unit='st', form='as_sold', label='Råa hela hönsägg med skal, räknade före kokning')
                if item['name'] == 'dill':
                    item['requirements'] = ['frozen']
        row['steps'] = [
            {'text': 'Skala rödbetorna råa och väg därefter den angivna ätliga mängden. Dela stora betor. Koka upp med 1200 ml vatten i en kastrull.', 'uses': ['rödbeta'], 'minutes': 7},
            {'text': 'Sjud under lock cirka 40 minuter tills rödbetorna är helt mjuka.', 'uses': ['rödbeta'], 'minutes': 40, 'passive': True},
            {'text': 'Kontrollera rödbetorna med sticka, förläng kokningen vid behov. Häll av kokvattnet och skär betorna i mindre bitar på ren skärbräda. Bred ut i en grund skål och ställ i kylskåp.', 'uses': ['rödbeta'], 'minutes': 5},
            {'text': 'Skala potatisen, väg den råa ätliga mängden och dela jämnt. Koka upp med 1200 ml vatten.', 'uses': ['potatis'], 'minutes': 6},
            {'text': 'Sjud cirka 18 minuter tills potatisen är precis mjuk, inte sönderkokt.', 'uses': ['potatis'], 'minutes': 18, 'passive': True},
            {'text': 'Kontrollera potatisen, förläng kokningen vid behov. Häll av, skär i bitar och bred ut i en grund ren skål. Ställ i kylskåp.', 'uses': ['potatis'], 'minutes': 4},
        ]
        mark_process(row, 3, ['rödbeta'], 'drain_after_cooking', 'Rödbetornas kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        mark_process(row, 6, ['potatis'], 'drain_after_cooking', 'Potatisens kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        if row['variant_id'] != 'simple':
            row['steps'].extend([
                {'text': 'Lägg de hela råa äggen i en kastrull med kallt vatten så de täcks. Koka upp.', 'uses': ['ägg'], 'minutes': 5},
                {'text': 'Sjud äggen tolv minuter tills både gula och vita är fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
                {'text': 'Häll av kokvattnet och lägg äggen i kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
                {'text': 'Låt äggen svalna fem minuter i det kalla vattnet.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
                {'text': 'Skala äggen, skölj bort skalrester och dela med rena redskap. Ställ i kylskåp på en ren tallrik.', 'uses': ['ägg'], 'minutes': 4},
            ])
            mark_process(row, 11, ['ägg'], 'peel_after_cooking', 'Fyra råa hela ägg kokas och skalas. Ingen styckvikt, skalandel eller kokt vikt antas.')
        if row['variant_id'] == 'extended':
            row['steps'].append({'text': 'Koka den frysta hackade dillen med 15 ml vatten under omrörning minst tre minuter eller längre enligt förpackningen. Häll hela mängden med vätskan i en liten ren skål och ställ i kylskåp.', 'uses': ['dill'], 'minutes': 4})
        chill = ['rödbeta', 'potatis'] + (['ägg'] if row['variant_id'] != 'simple' else []) + (['dill'] if row['variant_id'] == 'extended' else [])
        row['steps'].extend([
            {'text': 'Kyl alla tillagade ingredienser i de grunda kärlen tills de är högst 8 °C, uppskattningsvis 60 minuter. Kylskåpet bör hålla 4 °C. Förläng vid behov; blanda aldrig varm potatis, rödbeta, ägg eller dill med fisken.', 'uses': chill, 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera att sillen är märkt ätklar 5-minuterssill; rå salt sill som kräver egen behandling får inte användas. Låt sill och saltgurka rinna av utan att skölja. Väg därefter de angivna avrunna mängderna och skär smått. Kärna ur äpplet och skala rödlöken, väg rå ätlig mängd och tärna.', 'uses': ['ätklar inläggningssill', 'saltgurka', 'äpple', 'rödlök'], 'minutes': 10},
        ])
        salad_names = [i['name'] for i in row['components'][0]['ingredients']]
        sauce = 'crème fraiche och peppar' + (' samt senap' if row['variant_id'] != 'simple' else '') + (' och vinäger samt hela den kalla dillblandningen med vätskan' if row['variant_id'] == 'extended' else '')
        row['steps'].extend([
            {'text': 'Rör ihop ' + sauce + '. Vänd varsamt med kall potatis, rödbeta, sill, saltgurka, äpple och rödlök. Tillsätt inget extra salt. Täck skålen och ställ i kylskåp.', 'uses': salad_names, 'minutes': 5},
            {'text': 'Låt salladen stå i kylskåp 30 minuter så smakerna förenas.', 'uses': ['ätklar inläggningssill'], 'minutes': 30, 'passive': True},
            {'text': 'Fördela den kalla sillsalladen i fyra portioner och servera direkt från kylskåp.' + (' Servera de kalla kokta äggen och knäckebrödet till.' if row['variant_id'] != 'simple' else ''), 'uses': ['ätklar inläggningssill'] + (['ägg', 'knäckebröd'] if row['variant_id'] != 'simple' else []), 'minutes': 3},
        ])
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Bind only ready-treated Abba herring at the unchanged 400 g declared drained dose. Explicit salt-pickle alternative: 80 g saltgurka replaces 120 g ättiksgurka, no equivalence. Source comparison quantities are already drained. Weigh beet/potato after raw peeling, separate active draining/cold-chain checks, and retain unknown cooking losses. Standard/extended use four raw shell eggs instead of 180 g cooked eggs, with explicit boiling and peeling. Frozen dill is cooked and chilled with all liquid.')
    if base.endswith('lapskojs'):
        rename_ingredient(row, 'rimmad oxbringa', 'corned beef på burk')
        row['primary'] = 'corned beef på burk'
        row['name'] = row['name'].replace('rimmad oxbringa', 'corned beef på burk')
        row['components'][0]['name'] = 'Färdigkokt nötkött och mjuk lök'
        row['notes'] = 'Granskad konservversion av lapskojs. Inte provlagad; tider är författaruppskattningar. Ny dos 680 g färdigkokt corned beef ersätter 700 g rå rimmad bringa utan påstådd utbytesekvivalens. Hela konservinnehållet används. Standard har snabbsyrad rödbeta för direkt konsumtion, utökad även varm kålsida.'
        for item in row['components'][0]['ingredients']:
            if item['name'] == 'corned beef på burk':
                item.update(quantity=680, label='Färdigkokt corned beef, två hela 340 g-konserver')
        original = copy.deepcopy(row['steps'])
        row['steps'] = []
        if row['variant_id'] != 'simple':
            row['steps'].extend([
                {'text': 'Skala rödbetan, väg rå ätlig mängd och tärna. Koka upp med 700 ml vatten.', 'uses': ['rödbeta'], 'minutes': 6},
                {'text': 'Sjud cirka 25 minuter tills rödbetan är mjuk.', 'uses': ['rödbeta'], 'minutes': 25, 'passive': True},
                {'text': 'Kontrollera rödbetan och förläng vid behov. Häll av kokvattnet och vänd betorna med all vinäger, socker och senap. Ställ åt sidan till serveringen; detta är ett tillbehör för direkt konsumtion, ingen hållbarhetsvaliderad inläggning.', 'uses': ['rödbeta', 'äppelcidervinäger', 'strösocker', 'senap'], 'minutes': 3},
            ])
            mark_process(row, 3, ['rödbeta'], 'drain_after_cooking', 'Rödbetans kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        row['steps'].extend([
            {'text': 'Skala potatisen och löken, väg därefter de råa ätliga mängderna. Dela potatisen och finhacka löken. Koka upp tillsammans i 1600 ml vatten.', 'uses': ['potatis', 'gul lök'], 'minutes': 8},
            {'text': 'Sjud cirka 20 minuter tills potatis och lök är helt mjuka.', 'uses': ['potatis', 'gul lök'], 'minutes': 20, 'passive': True},
            {'text': 'Kontrollera med sticka och förläng kokningen vid behov. Häll av potatis och lök genom ett finmaskigt durkslag så all lök behålls. Lägg tillbaka i kastrullen.', 'uses': ['potatis', 'gul lök'], 'minutes': 2},
        ])
        mark_process(row, len(row['steps']), ['potatis', 'gul lök'], 'drain_after_cooking', 'Potatisens och lökens kokvatten hälls bort. Kvarvarande näring och tillagad portionsvikt är inte uppmätta.')
        if row['variant_id'] == 'extended':
            side = next(s for s in original if s['text'].startswith('Strimla vitkål'))
            side['text'] = 'Ansa vitkål och purjolök, skala moroten och väg rå ätlig mängd. ' + side['text'] + ' Behåll allt smör och all grönsakssaft till serveringen.'
            row['steps'].append(side)
        row['steps'].extend([
            {'text': 'Öppna de två corned beef-konserverna och finfördela hela innehållet inklusive fett och gelé. Värm mjölken med mosets smör. Stöt potatis och lök grovt och arbeta ner hela mjölkblandningen och allt kött. Späd vid behov med 85 ml hett vatten. Tillsätt inget extra salt.', 'uses': ['corned beef på burk', 'gul lök', 'potatis', 'smör', 'mjölk'], 'minutes': 10},
            {'text': 'Värm under ständig omrörning tills hela moset är genomhett, minst fem minuter och längre vid behov. Köttet ska vara finfördelat och inarbetat i moset. Fördela på fyra portioner.' + (' Servera med rödbetorna och all deras dressing.' if row['variant_id'] != 'simple' else '') + (' Servera den varma kålsidan med all smörsky.' if row['variant_id'] == 'extended' else ''), 'uses': [i['name'] for c in row['components'] for i in c['ingredients']], 'minutes': 6},
        ])
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit canned-corned-beef lapskojs: new 680 g whole prepared product (two 340 g cans) replaces 700 g raw cured brisket, not a cooking-yield conversion. Remove the unnecessary 150-minute raw-meat braise. Cook onion with potato, retain all canned fat/jelly and milk/butter. Weigh roots after raw peeling; discarded cooking water has unknown retention. Separate beet draining/dressing and potato inspection from passive simmering.')
    if base.endswith('manchamanteles'):
        rename_ingredient(row, 'matbanan', 'kokbanan med skal')
        row['name'] += ' – med uppvägd hel mogen kokbanan'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'kokbanan med skal':
                    item.update(form='as_sold', quantity=600, label='Mogen gul/svartfläckig kokbanan, inköpt vikt med skal')
                if item['name'] == 'anchochili':
                    item['label'] = 'Mald anchochili'
        row['steps'][0].update(text='Utgå från redan mogen kokbanan med gul till svartfläckig skal och eftergivligt fruktkött. Grön hård kokbanan måste mogna före matlagningen; mognadstid ingår inte i receptets tillagningstid. Rör den uppvägda malda anchochilin med 250 ml hett vatten; ingen hel chili ska rostas eller rensas.', minutes=2)
        row['steps'][1].update(text='Låt den malda chilin dra i vattnet fem minuter; hela blandningen ska användas.', minutes=5)
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('den mjuka chilin', 'den uppblötta malda chilin').replace('det sparade chilivattnet', 'allt chilivatten')
        row['steps'][5].update(text='Sjud kycklingen under lock i elva minuter.', minutes=11)
        insert_step(row, 7, {'text': 'Rör i molesåsen och kontrollera att bottnen inte bränner. Tillsätt vid behov 50 ml vatten.', 'uses': ['kyckling', 'tomat'], 'minutes': 1})
        insert_step(row, 8, {'text': 'Sjud ytterligare elva minuter under lock.', 'uses': ['kyckling'], 'minutes': 11, 'passive': True})
        insert_step(row, 9, {'text': 'Kontrollera minst 74 °C mitt i de tjockaste kycklingbitarna. Fortsätt sjuda om de inte är genomlagade.', 'uses': ['kyckling'], 'minutes': 2})
        fruit_step = row['steps'][9]
        fruit_step['text'] = 'Väg kokbananen med skal till den nya angivna bruttomängden, skala och skiva allt fruktkött. Stek försiktigt i återstående olja tills skivorna är gyllene med mjuk mitt. Använd den uppvägda frysta ananasen i nästa steg; ingen saft ska hällas bort.'
        if row['variant_id'] == 'extended':
            fruit_step['text'] += ' Skala och kärna ur äpplet, väg den råa ätliga mängden och tärna.'
        mark_process(row, 10, ['kokbanan med skal'], 'trim_before_cooking', 'Kokbanan vägs med skal före skalning. Skalets andel och kvarvarande ätliga vikt är inte uppmätta; inget portionsutbyte antas.')
        row['steps'][10]['text'] = row['steps'][10]['text'].replace('ananas', 'fryst ananas med all saft').replace('sjud 6 minuter', 'sjud under omrörning minst tio minuter eller längre enligt förpackningen tills frukten är helt genomhet').replace('matbananen', 'kokbananen')
        row['steps'][10]['text'] += ' Skrapa även ner all stekolja från bananpannan i grytan.'
        row['steps'][10]['minutes'] = 13
        for step in row['steps']:
            if step['text'].startswith('Sjud riset'):
                step['text'] = 'Sjud riset under lock cirka 18 minuter eller längre enligt förpackningen tills det är mjukt och vattnet absorberats.'
            if step['text'].startswith('Ta riset från'):
                step['text'] = 'Låt riset vila under lock fem minuter efter att det tagits från värmen.'
        rice_rest = next(n for n, s in enumerate(row['steps'], 1) if s['text'].startswith('Låt riset vila'))
        insert_step(row, rice_rest, {'text': 'Kontrollera riset och ta det från värmen när det är mjukt. Tillsätt annars 50 ml vatten och fortsätt sjuda före vilan.', 'uses': ['ris'], 'minutes': 1})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New dose 600 g ripe whole plantain weighed with peel replaces 300 g edible flesh; no yield equivalence. Ripeness is a manual precondition, not proved by catalogue or included in cook time. Use the reviewed ground ancho at unchanged 24 g and retain all hydration water. Frozen pineapple cooks in the mole with all juice; all frying oil is retained. Separate simmering inspection and temperature/rice checks from passive time.')
    if base.endswith('arroz-tumbada'):
        rename_ingredient(row, 'råa räkor', 'råa skalade vannameiräkor')
        rename_ingredient(row, 'musslor', 'blåmusselkött utan skal')
        row['name'] += ' – med fryst musselkött utan skal'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'råa skalade vannameiräkor':
                    item.update(form='as_sold', label='Rå skalad vannameiräka, deklarerad produktvikt')
                if item['name'] == 'blåmusselkött utan skal':
                    item.update(quantity=200, label='Fryst blåmusselkött utan skal')
        row['steps'][0]['text'] = 'Använd tinad benfri vit fisk, råa skalade vannameiräkor och musselkött utan skal; inga levande musslor ingår. Behåll all upptiningsvätska och koka den i rätten. Kontrollera fisken efter kvarvarande ben och skär i bitar. Skala löken, väg ätlig mängd och hacka lök och tomat.'
        row['steps'][2].update(text='Sjud riset försiktigt i cirka tolv minuter; det ska fortfarande omges av rikligt med spad.', minutes=12, passive=True)
        insert_step(row, 3, {'text': 'Häll i 1400 ml vatten och all upptiningsvätska. Koka upp ordentligt under omrörning.', 'uses': ['ris', 'fisk', 'råa skalade vannameiräkor', 'blåmusselkött utan skal'], 'minutes': 3})
        row['steps'][4]['text'] = 'Lägg i musselköttet och fisken och sjud försiktigt fem minuter. Tillsätt de råa skalade räkorna och sjud ytterligare tre till fem minuter, eller längre enligt skaldjursförpackningarna. Kontrollera att räkorna är ogenomskinliga i mitten, fisken når minst 63 °C och musselköttet är genomhett. Riset ska vara mjukt men inte sönderkokt. Allt spad behålls.'
        row['notes'] = row.get('notes', '').replace('Musslor har vikt med skal; ätligt utbyte är inte uppskattat.', 'Ny version använder uttryckligen musselkött utan skal, inte levande musslor.')
        row['steps'] = [
            {'text': 'Väg upp råa skalade vannameiräkor, fryst fisk och fryst musselkött i separata täckta kärl. Ställ i kylskåp.', 'uses': ['råa skalade vannameiräkor', 'fisk', 'blåmusselkött utan skal'], 'minutes': 2},
            {'text': 'Tina helt i kylskåp enligt förpackningarna. Planera tolv timmar och förläng vid behov tills inga iskärnor finns kvar. Behåll all vätska för genomkokning i risgrytan.', 'uses': ['råa skalade vannameiräkor', 'fisk', 'blåmusselkött utan skal'], 'minutes': 720, 'passive': True},
            *row['steps']]
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'epazote', 'koriander')
            row['name'] += ' och koriander'
            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] == 'koriander': item.update(quantity=15,label='Fryst hackad koriander')
            row['steps'][2]['text'] += ' Väg färsk eller fryst hackad vitlök och fryst hackad grön jalapeño; all vätska ska med.'+(' Skala och väg moroten, ansa och väg sellerin och finhacka båda.' if row['variant_id']=='extended' else '')
            row['steps'][3]['text'] = 'Värm oljan och mjukstek löken fem minuter. Tillsätt vitlök och fryst hackad jalapeño'+(', morot och selleri' if row['variant_id']=='extended' else '')+'. Fräs under omrörning tre minuter. Vänd ner riset och fräs två minuter; tillsätt alla tomater och salt.'
            row['steps'][3]['minutes'] = 10
            row['steps'][4]['text'] += ' Tillsätt hela den uppvägda frysta koriandern; den kokas med riset och hela örtmängden serveras.'
            row['steps'][4]['uses'].append('koriander')
            row['steps'][6]['uses'] = [n for n in row['steps'][6]['uses'] if n != 'koriander']
            row['notes'] += ' Separat örtversion: 15 g fryst koriander ersätter 5 g epazote utan samma arom; hela örten genomkokas i riset.'
            changes.append('Standard/extended use a new 15 g frozen-coriander dose instead of 5 g epazote, boiled into retained broth. Frozen jalapeno and garlic explicitly cook; extended carrot/celery/lime remain distinct.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit shell-free version: new 200 g frozen mussel meat replaces 600 g live shell-on mussels, not a shell-yield conversion. Raw peeled Miramar shrimp use the unchanged 250 g declared product mass including its added water/salt, not 100 percent pure flesh. Thaw all seafood under refrigeration, boil all thaw liquid and retain all broth. Separate water addition/boiling from passive rice simmer.')
    if base in STAGES[18]:
        rename_ingredient(row, 'fläsklever', 'ungnötslever')
        row['primary'] = 'ungnötslever'
        row['name'] = row['name'].replace('fläsklever', 'ungnötslever')
        if base.endswith('korvkaka'):
            row['name'] += ' – med ungnötslever'
        row['notes'] = row.get('notes', '').replace('fläsklever i stället för kalvlever', 'ungnötslever i stället för kalvlever').replace('Grislever serveras inte rosa', 'Levern serveras genomlagad')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ungnötslever':
                    item.update(form='as_sold', label='Rå ungnötslever, vägd före putsning')
        for step in row['steps']:
            step['text'] = step['text'].replace('fläsklevern', 'ungnötslevern')
        if base.endswith('fegato-veneziana-flasklever'):
            row['steps'][2].update(text='Sjud polentan försiktigt i cirka 25 minuter eller längre enligt förpackningen. Rör regelbundet och skrapa bottnen; tiden räknas som aktiv tillsyn.', passive=False)
            for n, step in enumerate(row['steps'], 1):
                if step['text'].startswith('Putsa'):
                    step['text'] = 'Väg leverbiten före putsning. ' + step['text']
                    mark_process(row, n, ['ungnötslever'], 'trim_before_cooking', 'Grova hinnor och kärl putsas bort från inköpt levervikt; den kvarvarande råa och färdiga vikten är inte uppmätt.')
                if step['text'].startswith('Lägg tillbaka lök'):
                    step['text'] += ' Låt den frysta hackade persiljan koka med minst tre minuter eller längre enligt förpackningen.'
                    step['uses'].append('persilja')
                if step['text'].startswith('Hacka persilja'):
                    step['text'] = step['text'].replace('Hacka persilja och vänd ner med svartpeppar.', 'Vänd ner svartpeppar; persiljan är redan genomkokt i skyn.')
                    step['text'] += ' Servera allt smör, all sky och eventuell salladsdressing.'
            changes.append('Explicit young-beef-liver substitution at 600 g purchased pre-trim mass, not an equivalence to 600 g edible pork liver. Unknown trimming yield; frozen parsley cooks in the gravy and all butter/juice/dressing is served. Polenta stirring counts as active work.')
        else:
            row['steps'][1].update(text='Sjud korngrynen under lock i 17 minuter.', minutes=17)
            insert_step(row, 3, {'text': 'Rör om och kontrollera vattnet. Tillsätt vid behov 100 ml så grynen inte bränner.', 'uses': ['korngryn'], 'minutes': 1})
            insert_step(row, 4, {'text': 'Sjud ytterligare 18 minuter, eller längre tills korngrynen är mjuka. Allt kvarvarande vatten ska gå med i gröten.', 'uses': ['korngryn'], 'minutes': 18, 'passive': True})
            row['steps'][5].update(text='Låt gröten svalna 20 minuter tills den är ljummen och inte börjar tillaga äggen när smeten blandas.', minutes=20)
            insert_step(row, 6, {'text': 'Bred gröten i en vid skål och sätt ugnen på 190 °C över-/undervärme.', 'uses': ['korngryn', 'mjölk'], 'minutes': 2})
            mix = row['steps'][7]
            mix['text'] = mix['text'].replace('Putsa levern', 'Väg ungnötslevern före putsning. Putsa levern').replace('med ägg,', 'med råa ägg knäckta och vägda utan skal,')
            mark_process(row, 8, ['ungnötslever'], 'trim_before_cooking', 'Leverhinnor och kärl avlägsnas från bruttovikten. Kvarvarande ätlig vikt och näringsutbyte är inte uppmätta.')
            row['steps'][8].update(text='Baka kakan mitt i ugnen i cirka 50 minuter.', minutes=50)
            insert_step(row, 9, {'text': 'Klä formen med bakplåtspapper, häll i hela massan och sätt in formen i ugnen.', 'uses': ['ungnötslever', 'korngryn', 'ägg'], 'minutes': 2})
            insert_step(row, 11, {'text': 'Mät minst 75 °C i mitten. Om det är svalare, fortsätt grädda tills temperaturen nåtts. Kakan ska vara genomstannad utan rå levermassa.', 'uses': ['ungnötslever', 'ägg'], 'minutes': 2})
            insert_step(row, 12, {'text': 'Låt kakan stå kvar i ugnen minst tre minuter efter att mitten nått 75 °C.', 'uses': ['ungnötslever', 'ägg'], 'minutes': 3, 'passive': True})
            insert_step(row, 13, {'text': 'Ta ut formen och ställ på värmetåligt underlag.', 'uses': ['ungnötslever'], 'minutes': 1})
            for step in row['steps']:
                if step['text'].startswith('Mosa lingonen'):
                    step['text'] = 'Koka de uppvägda frysta lingonen med sockret minst en minut eller längre enligt förpackningen, under omrörning. Mosa lätt; behåll all bärsaft och servera kompotten ljummen.'
                if step['text'].startswith('Strimla kålen'):
                    step['text'] = 'Ansa kålen och kärna ur äpplet. Väg de råa ätliga mängderna, strimla och vänd med all vinäger. Servera även råkostens saft.'
            changes.append('Explicit young-beef-liver substitution at 400 g purchased pre-trim mass with unknown trimming yield. Keep raw egg weighed without shells. Separate gryn inspection, cooling setup/oven heating, pan loading and centre-temperature checks from passive periods. Frozen lingonberries become a cooked compote; all milk, butter, berry juice and dressing are served.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith(('gulab-jamun', 'phirni')) and row['variant_id'] == 'extended':
        rename_ingredient(row, 'pistagenötter', 'rostade saltade pistaschkärnor')
        row['name'] += ' – med rostade saltade pistaschkärnor'
        for step in row['steps']:
            step['text'] = step['text'].replace('Hacka pistagenötterna', 'Hacka de uppvägda redan skalade, rostade och saltade pistaschkärnorna')
        changes.append('Explicit salted roasted shelled pistachio garnish at the unchanged 10 g dose. This is not an alias for raw unsalted pistachios or nuts weighed with shells. The separate manufacturer kernel page and exact retailer article/65 g package are reviewed.')
    if base.endswith('carne-en-su-jugo'):
        rename_ingredient(row, 'tomatillo', 'salsa verde av tomatillo')
        row['name'] += ' – med färdig tomatillosalsa'
        for component in row['components']:
            component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'salt']
            for item in component['ingredients']:
                if item['name'] == 'salsa verde av tomatillo':
                    item.update(form='as_sold', quantity=250, role='sauce', label='Färdig Salsa Verde av tomatillo, Clemente Jacques')
                elif item['name'] == 'limejuice':
                    item['quantity'] = 20
                elif item['name'] == 'sojasås':
                    item['quantity'] = 5
        for step in row['steps']:
            step['uses'] = [name for name in step['uses'] if name != 'salt']
        row['steps'][0]['text'] = 'Skär nötinnanlår i mycket tunna skivor tvärs fibrerna och därefter i små rutor. Tärna det rimmade fläsket. Skala lök och vitlök, väg den råa ätliga mängden och hacka. Väg upp den färdiga tomatillosalsan; den innehåller redan kryddor, soja, syra och salt.'
        row['steps'][2]['text'] = 'Mixa den uppvägda färdiga tomatillosalsan med gul lök, vitlök, limejuice, svartpeppar och 500 ml vatten. Häll i köttgrytan och koka upp. Tillsätt inget extra salt.'
        if row['variant_id'] != 'simple':
            row['steps'][2]['text'] += ' Mixa även ner den frysta hackade koriandern, chiliflakes och den lilla angivna mängden soja; koriandern genomkokas sedan med grytan.'
        row['steps'][4]['text'] = 'Skölj de redan kokta bönorna, låt rinna av och väg den angivna avrunna mängden. Värm i grytan fem minuter under omrörning. Kontrollera att köttet är mört och genomhettat; förläng kokningen vid behov. Såväl fläsk som färdig salsa och eventuell soja ger sälta; tillsätt inget extra salt.'
        row['steps'][-1]['text'] += ' Servera allt köttspad och allt utsmält fläskfett i grytan.'
        if row['variant_id'] == 'extended':
            row['steps'][5]['text'] = 'Använd de tinade avokadobitarna med all saft. Ansa rädisor och salladslök, väg de råa ätliga mängderna och skiva. Lägg på ett fat med avokadon.'
            prepend_thaw(row, 'avokado', 120, 'Behåll all avokadosaft och servera med grytan.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New prepared-salsa adaptation: 250 g Salsa Verde replaces 400 g raw tomatillo; not an edible-yield conversion. Omit 3 g added salt, reduce lime from 35 to 20 ml and optional soy from 15 to 5 ml because the salsa is already salted/acidified/seasoned. Use 500 ml process water instead of 650. Retain all meat juice/fat, weigh drained beans, cook frozen coriander and explicitly thaw frozen avocado with all juice.')
    if base.endswith('carlota-limon'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'evaporerad mjölk':
                    item.update(quantity=45, unit='g', label='Osötad evaporerad mjölk, vägd i gram')
        row['name'] += ' – med uppvägd osötad evaporerad mjölk'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Vispa kondenserad och evaporerad mjölk', 'Väg den sötade kondenserade mjölken och den osötade evaporerade mjölken separat. Vispa båda')
        row['steps'][2]['text'] = 'Låt portionsglaset stå i kylskåp minst fyra timmar vid cirka 4 °C så kexen mjuknar och krämen sätter sig.'
        insert_step(row, 3, {'text': 'Täck portionsglaset och ställ direkt i kylskåp.', 'uses': ['kondenserad mjölk', 'evaporerad mjölk', 'mariekex'], 'minutes': 1, 'after': [2]})
        row['steps'].append({'text': 'Servera hela den lilla portionen direkt från kylen.', 'uses': ['mariekex'], 'minutes': 1, 'after': [len(row['steps'])]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        if row['variant_id'] == 'extended':
            row['steps'][1]['text'] = row['steps'][1]['text'].replace('små mangotärningar mellan lagren', 'helt tinade mangobitar och all mangosaft mellan lagren')
            prepend_thaw(row, 'mango', 120, 'Behåll alla bitar och all saft till desserten.')
        changes.append('New authored dose 45 g unsweetened evaporated milk replaces 40 ml, not a density conversion. Keep sweetened condensed milk as a separate unchanged input. Frozen mango thaws with all juice; active covering/refrigeration and serving are separated from four-hour chilling.')
    if base.endswith('blodpalt'):
        row['steps'][0].update(text='Mät upp det helt tinade kalla nötblodet i ml och ställ tillbaka det i kylen. Tärna det rimmade fläsket smått. Skala potatisen, väg den angivna råa ätliga mängden och finriv. Pressa ur lös vätska genom en ren handduk till en skål.', minutes=10)
        insert_step(row, 2, {'text': 'Låt potatisvätskan stå orörd två minuter så stärkelsen sjunker.', 'uses': ['potatis'], 'minutes': 2, 'passive': True, 'after': [1]})
        insert_step(row, 3, {'text': 'Häll försiktigt bort den fria potatisvätskan men skrapa tillbaka all sedimenterad stärkelse till potatisen.', 'uses': ['potatis'], 'minutes': 1, 'after': [2]})
        mark_process(row, 3, ['potatis'], 'drain_before_cooking', 'Rå potatis pressas och fri vätska hälls bort medan sedimenterad stärkelse återförs. Kvarhållen vätska/näring har inget uppmätt utbyte.')
        row['steps'][6].update(text='Sjud paltarna försiktigt cirka 45 minuter. De ska ligga fritt i en stor gryta eller två grytor utan att klämmas ihop.', minutes=45, passive=True)
        insert_step(row, 7, {'text': 'Lägg paltarna försiktigt i det sjudande vattnet och lossa dem från botten med hålslev.', 'uses': ['potatis', 'nötblod', 'rimmat fläsk'], 'minutes': 3, 'after': [6]})
        insert_step(row, 9, {'text': 'Kontrollera minst 75 °C mitt i en palt, även i fläskfyllningen. Degens mitt ska sakna rå mjölrand; fortsätt sjuda om det behövs.', 'uses': ['nötblod', 'rimmat fläsk', 'rågmjöl', 'vetemjöl'], 'minutes': 2, 'after': [8]})
        row['steps'][-1]['text'] += ' Allt eventuellt löksmör och all lingonvätska serveras. Kokvattnet används inte.'
        mark_process(row, len(row['steps']), ['potatis', 'nötblod', 'salt'], 'drain_after_cooking', 'Palt lyfts ur saltat kokvatten. Kvarhållen mängd salt och näring är okänd; inget kokutbyte antas.')
        for step in row['steps']:
            if step['text'].startswith('Värm lingonen'):
                step['text'] = step['text'].replace('Värm lingonen', 'Värm de uppvägda frysta lingonen').replace('en minut', 'minst en minut eller längre enligt förpackningen')
            if step['text'].startswith('Strimla kålen'):
                step['text'] = 'Ansa kålen och kärna ur äpplet, väg sedan de råa ätliga mängderna. Strimla och vänd med all vinäger. Servera även saften.'
        row['steps'] = [
            {'text': 'Flytta förpackningen med fryst nötblod till ett läckagesäkert kärl i kylskåpet.', 'uses': ['nötblod'], 'minutes': 1},
            {'text': 'Tina nötblodet helt i kylskåp enligt förpackningen. Planera tolv timmar och förläng vid behov. Håll det kallt och använd inom förpackningens anvisade tid; det ska inte användas rått.', 'uses': ['nötblod'], 'minutes': 720, 'passive': True},
            *row['steps']]
        for process in row['unmeasured_processes']:
            process['step'] += 2
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Retain the authored 250 ml raw food-grade frozen bovine blood without mass/density conversion. Explicit fridge thaw, peeled raw potato weighing, separate starch sedimentation/pouring, palt loading and 75 C centre checks. Both squeezed potato liquid and salted cooking-water losses remain unmeasured; all lingon juice and optional butter are served.')
    if base.endswith('janssons-frestelse'):
        rename_ingredient(row, 'svensk ansjovis med spad', 'svensk ansjovis')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'svensk ansjovis':
                    item.update(quantity=158, form='preserved_drained', label='Svensk ansjovisfilé, avrunnen utan extra spad')
        row['name'] += ' – med avrunnen ansjovis utan extra spad'
        row['steps'][0]['text'] = 'Sätt ugnen på 175 °C över-/undervärme. Skala potatisen och väg den angivna råa ätliga mängden. Skär i cirka 3 mm tunna strimlor utan att skölja bort stärkelsen. Skala och skiva den uppvägda löken. Låt ansjovisfiléerna rinna av och väg 158 g utan fri lag, motsvarande två deklarerade 79 g-mängder; dela grovt. Spadet används inte i denna version.'
        row['steps'][2]['text'] = row['steps'][2]['text'].replace(' samt allt ansjovisspad', '').replace('fisken och spadet är salta', 'fisken är salt')
        row['steps'][3].update(text='Grädda gratängen i nedre delen av ugnen i 60 minuter.', minutes=60)
        insert_step(row, 5, {'text': 'Kontrollera gratängens yta och täck löst med folie om den blivit mörk.', 'uses': ['potatis'], 'minutes': 2, 'after': [4]})
        insert_step(row, 6, {'text': 'Grädda ytterligare 40 minuter. Vätskan ska bindas till en krämig sås.', 'uses': ['potatis', 'grädde'], 'minutes': 40, 'passive': True, 'after': [5]})
        insert_step(row, 7, {'text': 'Kontrollera med sticka att samtliga potatislager är helt mjuka; förläng annars gräddningen. Ta ut formen.', 'uses': ['potatis'], 'minutes': 1, 'after': [6]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
            if step['text'].startswith('Strimla grönkålen'):
                step['text'] = 'Lägg den uppvägda frysta hackade grönkålen direkt i pannan med tillbehörets smör och 60 ml vatten. Genomhetta under omrörning minst tio minuter eller längre enligt förpackningen. Låt vattnet koka in; servera all kål och allt smör.'
            if step['text'].startswith('Skala och riv rödbetan'):
                step['text'] = 'Skala rödbetan och kärna ur äpplet, väg därefter respektive råa ätliga mängd. Riv rödbetan och skär äpplet i tunna stavar. Vänd med all vinäger och servera hela salladen med saften.'
        changes.append('New visible drained-anchovy version: 158 g declared drained sprat replaces 220 g fish-plus-brine. Extra brine is omitted without inventing an equivalence or nutrient yield. Source already declares drained 79 g, so purchasing must not apply another drained fraction. Weigh peeled potato, use frozen kale explicitly, count oven inspection separately and retain all butter/cream/dressing.')
    if base.endswith('gubbrora-ansjovis'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=2, unit='st', form='as_sold', label='Hela råa ägg med skal, räknade före kokning')
                if item['name'] == 'dill':
                    item['requirements'] = ['frozen']
        row['method'] = 'pot'
        row['name'] += ' – med nykokta och kylda ägg'
        herbs = ['dill'] + (['gräslök'] if row['variant_id'] == 'extended' else [])
        prefix = [
            {'text': 'Lägg de hela råa äggen i en kastrull med kallt vatten så de täcks. Koka upp.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter så vitan och gulan blir fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll av kokvattnet och lägg äggen i kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt äggen svalna i det kalla vattnet fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen, skölj bort eventuella skalrester och tärna dem med rena redskap. Lägg på en ren tallrik i kylskåp.', 'uses': ['ägg'], 'minutes': 4},
            {'text': 'Koka de frysta hackade örterna med 15 ml vatten under omrörning minst tre minuter eller längre enligt förpackningen. Häll hela mängden i en ren liten skål och ställ i kylskåp.', 'uses': herbs, 'minutes': 4},
            {'text': 'Låt ägg och örter kallna helt i kylskåp, uppskattningsvis 30 minuter. Förläng tills båda är högst 8 °C innan de blandas med den kalla röran.', 'uses': ['ägg', *herbs], 'minutes': 30, 'passive': True},
        ]
        row['steps'][0].update(text='Låt ansjovisfiléerna rinna av utan att skölja, väg den angivna avrunna mängden och hacka fint.', uses=['svensk ansjovis'], minutes=2)
        row['steps'][1]['text'] = 'Finhacka den skalade uppvägda rödlöken. Rör ihop med crème fraiche och hela den kalla örtblandningen med vätskan.' + (' Rör också i senapen.' if row['variant_id'] == 'extended' else '') + ' Vänd ner de kalla tärnade äggen och ansjovisen. Inget extra salt ingår.'
        row['steps'] = prefix + row['steps']
        mark_process(row, 5, ['ägg'], 'peel_after_cooking', 'Två råa hela ägg kokas och skalas. Ingen rå eller kokt styckvikt eller skalandel antas.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New dose two raw shell eggs replaces 80 g ready-boiled egg; no equivalence is claimed. The hot cooking and subsequent cold chain are explicit, with counted peeling/cooling. Frozen herbs are cooked, cooled and retained with all liquid. Declared drained sprat remains 25 g; no gross-weight or sardell alias.')
    if base.endswith(('pasta-amatriciana', 'pasta-cacio-pepe')):
        rename_ingredient(row, 'pecorino romano', 'lagrad pecorino')
        row['name'] += ' – med lagrad pecorino'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'lagrad pecorino':
                    item.update(quantity=75 if base.endswith('amatriciana') else 150,
                                label='Lagrad pecorino i bit, vägd före ansning')
        insert_step(row, 1, {'text': 'Väg ostbiten före ansning. Skär bort eventuell hård ytkant och finriv all återstående ost. Här används lagrad pecorino av fårmjölk; osten är inte verifierad som Pecorino Romano.',
                            'uses': ['lagrad pecorino'], 'minutes': 5, 'after': []})
        mark_process(row, 1, ['lagrad pecorino'], 'trim_before_cooking', 'Inköpt ostbit vägs före eventuell bortskärning av ytkant. Kvarvarande mängd och dess näring är inte uppmätta.')
        for index, step in enumerate(row['steps'], 1):
            if index == 1:
                continue
            step['text'] = step['text'].replace('Finriv pecorino.', 'Använd den redan finrivna lagrade pecorinon.').replace('Riv pecorinon mycket fint i en rymlig värmetålig skål.', 'Lägg den redan finrivna lagrade pecorinon i en rymlig värmetålig skål.')
            if ('häll' in step['text'].lower() and ('kokvatten' in step['text'] or 'kokvattnet' in step['text'])
                    and ('häll sedan av' in step['text'] or 'hälls av' in step['text'])):
                mark_process(row, index, ['pasta', 'salt'], 'drain_after_cooking', 'En del saltat stärkelsevatten sparas till såsen och resten hälls bort. Saltets och stärkelsens kvarhållna mängd är okänd.')
                step['passive'] = False
            if step['text'].startswith('Tärna guanciale'):
                step['text'] += ' Behåll allt utsmält fett i såsen.'
            if step['text'].startswith('Rör ner chiliflakes'):
                step['passive'] = False
                step['text'] += ' Rör regelbundet under sjudningen.'
            if 'Hacka persilja' in step['text']:
                step.update(text='Väg de redan kokta vita bönorna efter sköljning och avrinning. Koka fryst hackad persilja med 20 ml vatten under omrörning i minst tre minuter eller längre enligt förpackningen. Vänd hela mängden med bönorna, citronjuice och bönkomponentens olivolja och servera ljummet.', minutes=8)
                row['name'] += ' och ljumma persiljebönor'
            step['after'] = [index - 1]
        changes.append('Explicit aged-sheep-cheese alternative, not a Romano identity alias. New gross doses 75 g (amatriciana) / 150 g (cacio e pepe) replace 65 / 140 g, without edible-yield equivalence. Trimmed rind and discarded salted pasta water carry unknown retention. Count grating, draining and regular stirring as active work; frozen parsley is cooked in the visible warm side.')
    if base.endswith('torta-ahogada'):
        rename_ingredient(row, 'surdegsfralla med hård skorpa', 'surdegsfralla')
        row['name'] += ' – med svensk surdegsfralla'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'surdegsfralla':
                    item.update(quantity=320, label='Färdigbakade svenska surdegsfrallor, 4 × 80 g')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Koka upp, skumma och sänk värmen.', 'Koka upp och sänk värmen; skumma inte bort något.')
        row['steps'][1].update(text='Sjud köttet under lock i 55 minuter.', minutes=55, passive=True)
        insert_step(row, 3, {'text': 'Vänd köttbitarna och kontrollera spadet. Tillsätt 100 ml vatten om det behövs så grytan inte kokar torr.', 'uses': ['fläskkarré'], 'minutes': 2, 'after': [2]})
        insert_step(row, 4, {'text': 'Sjud ytterligare 55 minuter under lock. Köttet ska bli helt genomlagat och mycket mört.', 'uses': ['fläskkarré'], 'minutes': 55, 'passive': True, 'after': [3]})
        row['steps'][4]['text'] = 'Kontrollera att köttet är minst 72 °C och faller isär lätt; förläng annars sjudningen. Lyft upp och dra i fibrer. Kokspadet används inte i denna version. Bryn allt kött i köttets rapsolja under omrörning i tio minuter; behåll oljan och köttsaften i fyllningen.'
        row['steps'][4]['minutes'] = 15
        mark_process(row, 5, ['fläskkarré', 'salt'], 'drain_after_cooking', 'Saltat kokspad blir över och serveras inte. Köttets kvarhållna vätska, salt och näring är okända.')
        index = len(row['steps'])
        insert_step(row, index, {'text': 'Sätt ugnen på 200 °C och lägg de färdigbakade surdegsfrallorna på galler. Brödet är en svensk anpassning, inte traditionellt birote. Använd inte rå deg eller ogräddat fryst bakeoffbröd.', 'uses': ['surdegsfralla'], 'minutes': 2, 'after': [index - 1]})
        insert_step(row, index + 1, {'text': 'Låt ugnen bli varm, cirka tio minuter.', 'uses': [], 'minutes': 10, 'passive': True, 'after': [index]})
        insert_step(row, index + 2, {'text': 'Sätt in frallorna i ugnen.', 'uses': ['surdegsfralla'], 'minutes': 1, 'after': [index + 1]})
        insert_step(row, index + 3, {'text': 'Värm frallorna fem minuter tills ytan är frasig; de är redan färdigbakade.', 'uses': ['surdegsfralla'], 'minutes': 5, 'passive': True, 'after': [index + 2]})
        row['steps'][-1]['text'] = 'Ta ut brödet. ' + row['steps'][-1]['text'] + ' Fördela även all eventuell limejuice från löken över fyllningen.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit Swedish baked sourdough roll instead of unverified hard-crust birote. New bread dose 320 g (four declared 80 g rolls) replaces 400 g, no conversion. Discarded salted pork broth has unknown retention. Separate mid-simmer inspection and bread reheating steps; keep frying oil and pickle juice in the served filling.')
    if base.endswith('murgh-musallam'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=4, unit='st', form='as_sold', label='Råa hela hönsägg med skal, räknade före kokning')
                if item['name'] == 'hel kyckling':
                    item.update(quantity=1350, label='Hel rå kyckling, bruttovikt inklusive ben och skinn')
        row['name'] += ' – med hel rå kyckling och nykokta ägg'
        row['steps'][0]['text'] = 'Välj en hel rå kyckling nära ingredienslistans bruttovikt. Butikens vikt är uppskattad; kontrollera faktisk vikt och kostnad. ' + row['steps'][0]['text'] + ' Diska råkycklingredskap och tvätta händerna.'
        row['steps'][0]['minutes'] += 3
        row['steps'][1]['text'] = 'Täck och marinera i kylskåp i två timmar.'
        for step in row['steps']:
            step['text'] = step['text'].replace('de redan kokta äggen', 'de nykokta skalade äggen')
            step['text'] = step['text'].replace('russin och koriander', 'russin och fryst hackad koriander; hela fyllningen ska genomhettas')
        row['steps'][-2:-1] = [
            {'text': 'Ugnstillaga fågeln täckt vid 175 °C i cirka 85 minuter.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 85, 'passive': True},
            {'text': 'Ta försiktigt av locket; skydda händerna mot ånga.', 'uses': ['hel kyckling'], 'minutes': 1},
            {'text': 'Fortsätt ugnstillagningen utan lock cirka 25 minuter för färg.', 'uses': ['hel kyckling'], 'minutes': 25, 'passive': True},
            {'text': 'Mät innerst i låret utan benkontakt och mitt i fyllningen, även eventuell separat fyllningsform. Samtliga ska nå minst 74 °C. Förläng tillagningen om någon mätpunkt är kallare.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 2},
        ]
        row['steps'][-1].update(text='Låt fågeln vila 15 minuter.', minutes=15, passive=True)
        row['steps'].append({'text': 'Ta bort snöret, lyft ur fyllningen och lossa allt ätligt kött och skinn från benen. Kontrollera små ben. Fördela kött, skinn, all fyllning och allt genomkokt spad eller sås mellan portionerna; benen serveras inte.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 10})
        eggs = [
            {'text': 'Lägg det angivna antalet råa hela ägg i en kastrull med 1000 ml vatten och koka upp försiktigt.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter från uppkok tills vita och gula blir helt fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll av det heta vattnet och tillsätt 1000 ml kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt svalna fem minuter så att äggen går att skala.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen och kasta skalen. Kontrollera fasta gulor och vitor; alla kokta ägg används utan antagen gramvikt.', 'uses': ['ägg'], 'minutes': 4},
        ]
        row['steps'][2:2] = eggs
        mark_process(row, 7, ['ägg'], 'peel_after_cooking', 'Ägg köps och doseras som antal före kokning. Skalen avlägsnas och ingen rå eller kokt styckvikt antas.')
        mark_process(row, len(row['steps']), ['hel kyckling'], 'remove_bones_after_cooking', 'Kycklingens inköpta bruttovikt innehåller ben. Allt ätligt kött, skinn och sky serveras; benens andel och tillagat utbyte är okända.')
        changes.append('Visible new dose: 1350 g whole raw chicken replaces 1600 g, and four raw shell eggs replace 120 g ready-cooked egg. Neither is a yield conversion. Whole source package mass stays estimated; bone/shell losses remain unknown. Count cleanup, egg cooking/peeling, lid removal, temperature checks and carving separately from waiting. Both bird and stuffing must reach 74 C.')
    if base.endswith('coda-vaccinara'):
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
            row['name'] += ' – med vitt matlagningsvin'
            row['steps'][2]['text'] = row['steps'][2]['text'].replace('vitt vin', 'vitt matlagningsvin')
        periods = []
        for turn in range(6):
            periods.append({'text': 'Sjud oxsvansen under lock på låg värme i 30 minuter.', 'uses': ['oxsvans med ben'], 'minutes': 30, 'passive': True})
            if turn < 5:
                periods.append({'text': 'Kontrollera vätskan och rör varsamt. Tillsätt vid behov 150 ml vatten så att bottnen inte kokar torr.', 'uses': ['oxsvans med ben'], 'minutes': 1})
        periods[-1]['text'] += ' Efter totalt cirka 180 minuter ska köttet börja lossna från benen; förläng om det fortfarande är segt.'
        row['steps'][3:4] = periods
        for index, step in enumerate(row['steps'], 1):
            if step['text'].startswith('Sjud utan heltäckande'):
                step['passive'] = False
            if step['text'].startswith('Ta upp köttbitarna'):
                mark_process(row, index, ['oxsvans med ben'], 'remove_bones_after_cooking', 'Oxsvans köps med ben som bruttovikt. Ben avlägsnas efter långkok; ingen ätlig andel eller tillagad vikt antas.')
        changes.append('Keep whole source oxtail mass including bones and its estimated variable-weight purchase; do not infer edible yield. Explicit bone removal carries unknown served nutrition. Standard/extended use visibly named cooking wine. Schedule five liquid checks during three hours and count the final regularly stirred reduction as active work.')
    if base.endswith('flasklagg-rotmos'):
        rename_ingredient(row, 'rimmat fläsklägg med ben', 'rimmat fläsklägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'rimmat fläsklägg':
                    item.update(quantity=1500, label='Rå rimmad fläsklägg, bruttovikt före borttagning av eventuella ben och seg svål')
        row['name'] += ' – med rå rimmad lägg'
        row['steps'][0]['text'] = 'Använd rå rimmad fläsklägg, med eller utan ben, nära den angivna vikten före putsning. Kontrollera faktisk vikt och kostnad. ' + row['steps'][0]['text']
        row['steps'][1:2] = [
            {'text': 'Sjud läggen försiktigt under lock i 60 minuter.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera vätskan och vänd läggen. Fyll vid behov på med 300 ml vatten.', 'uses': ['rimmat fläsklägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare 60 minuter.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera och vänd igen; fyll vid behov på med 300 ml vatten.', 'uses': ['rimmat fläsklägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare omkring 60 minuter, tills köttet är mycket mört och lätt delas med gaffel, eller lossnar från ben om ben ingår. Förläng vid behov.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
        ]
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala och tärna kålrot, morot och potatis.', 'Skala kålrot, morot och potatis, väg de råa ätliga mängderna och tärna.')
            step['text'] = step['text'].replace('avlägsna ben och seg svål', 'avlägsna eventuella ben och seg svål')
            if step['text'].startswith('Koka rotfrukterna'):
                step['text'] = 'Koka rotfrukterna mjuka cirka 30 minuter.'
        index = next(n for n, step in enumerate(row['steps'], 1) if step['text'].startswith('Koka rotfrukterna'))
        insert_step(row, index + 1, {'text': 'Häll av rotfrukterna och spara kokvätskan separat till spädning av moset.', 'uses': ['kålrot', 'morot', 'potatis'], 'minutes': 2})
        for index, step in enumerate(row['steps'], 1):
            if 'Ta upp lagerbladen' in step['text']:
                mark_process(row, index, ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och tas upp. Överföring till kokspadet är inte uppmätt.')
            if step['text'].startswith('Mosa rotfrukterna'):
                mark_process(row, index, ['rimmat fläsklägg'], 'remove_bones_after_cooking', 'Eventuella ben och seg svål tas bort från köttet. Förpackningens bruttovikt omvandlas inte till en påhittad ätlig vikt.')
        mark_process(row, len(row['steps']), ['rimmat fläsklägg', 'kålrot', 'morot', 'potatis', 'kryddpeppar'], 'drain_after_cooking', 'Endast kokspad som faktiskt används till moset serveras. Resterande lag och rotfruktsvatten är processrester med okänd salt- och näringsfördelning.')
        changes.append('New culinary dose 1500 g gross raw cured hock replaces 2200 g bone-in hock. Moab makes bone-in and boneless hock; the source label does not establish which, so the recipe explicitly handles either and removes any bones/tough skin. No bone or nutrient yield is inferred. Preserve salted broth use/discard and bay removal as unknown losses; count checks and draining as active work.')
    if base in STAGES[13]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('dal-baati'):
        row['name'] += ' – med röda linser och smör'
        row['steps'][3:4] = [
            {'text': 'Baka brödbollarna i 20 minuter.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 20, 'passive': True},
            {'text': 'Vänd brödbollarna försiktigt på plåten.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 1},
            {'text': 'Baka ytterligare 20 minuter, totalt omkring 40 minuter. Bröden ska ha rostad yta och vara genomgräddade utan rå mjöldeg i mitten; förläng vid behov.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 20, 'passive': True},
        ]
        simmer = next(step for step in row['steps'] if step['text'].startswith('Sjud 25 minuter'))
        simmer.update(passive=False, text='Sjud dalen cirka 25 minuter och rör regelbundet så att den inte fastnar. Linserna ska vara helt mjuka. Tillsätt 150 ml vatten om blandningen blir för fast; all dal och vätska serveras.')
        changes.append('Keep the explicit simple red-lentil and butter adaptation; do not alias chana dal or urad. Count bread turning and regular dal stirring as active work. All butter and dal are retained.')
    if base.endswith('salpicon-de-res'):
        rename_ingredient(row, 'nötkött', 'högrev')
        row['name'] += ' – med långkokt högrev'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('nötköttet', 'den benfria högreven')
        row['steps'][1:2] = [
            {'text': 'Sjud högreven under lock på låg värme i 75 minuter.', 'uses': ['högrev'], 'minutes': 75, 'passive': True},
            {'text': 'Kontrollera vätskan och vänd köttbitarna. Tillsätt vid behov 200 ml vatten så att grytan inte kokar torr.', 'uses': ['högrev'], 'minutes': 1},
            {'text': 'Sjud ytterligare cirka 75 minuter, totalt 150 minuter. Köttet ska gå lätt att dra isär med två gafflar; förläng om det är segt.', 'uses': ['högrev'], 'minutes': 75, 'passive': True},
        ]
        pull = row['steps'][4]
        pull['text'] = pull['text'].replace('Bred ut i ett rent grunt kärl.', 'Bred ut i ett rent grunt kärl; kvarvarande kokspad serveras inte.')
        if row['variant_id'] != 'simple':
            pull['text'] = pull['text'].replace('Bred ut', 'Koka den frysta hackade koriandern med 20 ml vatten i en liten kastrull minst tre minuter eller längre enligt förpackningen. Blanda all koriander och vätska med det varma köttet. Bred ut')
            pull['minutes'] += 4
            pull['uses'].append('koriander')
        mark_process(row, 5, ['högrev', 'salt'], 'drain_after_cooking', 'Köttet lyfts ur saltat kokspad som inte serveras. Saltöverföring, vätskeutbyte och näringsförluster är inte uppmätta.')
        row['steps'][5]['text'] = 'Kyl köttet i vattenbad 15 minuter. Badvattnet ska inte komma i maten.'
        row['steps'][5]['minutes'] = 15
        insert_step(row, 7, {'text': 'Täck kärlet och flytta det till kylskåp vid 4 °C.', 'uses': ['högrev'], 'minutes': 1})
        insert_step(row, 8, {'text': 'Kyl ytterligare cirka 45 minuter tills köttet är högst 8 °C; förläng vid behov. Låt det inte stå på köksbänken.', 'uses': ['högrev'], 'minutes': 45, 'passive': True})
        for step in row['steps']:
            if step['text'].startswith('Skär avokado'):
                step['text'] = step['text'].replace('Skär avokado och rädisa i små bitar.', 'Använd de tinade avokadobitarna med all saft och skär rädisan smått.').replace('och koriander i salladen', 'i salladen; koriandern är redan kokt och kyld med köttet')
            if step['text'].startswith('Koka fryst majs'):
                step['text'] += ' Väg bönorna efter avrinning och kontrollera att majsen är helt kall före blandning.'
                mark_process(row, row['steps'].index(step) + 1, ['majs'], 'drain_after_cooking', 'Majsens kokvatten hälls bort; vätske- och näringsförlusten är inte uppmätt.')
        if row['variant_id'] != 'simple':
            prepend_thaw(row, 'avokado', 120, 'Använd hela mängden och all saft i salladen.')
            for process in row['unmeasured_processes']:
                process['step'] += 2
        changes.append('Specify reviewed boneless chuck for shreddable beef, with a visible title. Keep discarded salted broth under unknown loss; separate simmer inspection and fridge transfer from passive waiting. Frozen coriander cooks before chilling with the beef; frozen avocado thaws with all juice. Extended corn draining is also unmeasured.')
    if base.endswith('inkokt-lax'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] in {'lax', 'dill'}:
                    item['requirements'] = list(dict.fromkeys([*vocabulary[f"{item['name']}|{item['form']}"][1], 'frozen']))
        row['steps'][0]['text'] = 'Använd upptinad benfri och skinnfri lax. Häll all upptiningssaft i lagen och koka upp den ordentligt före fisken. Använd fryst hackad dill direkt i lagen. ' + row['steps'][0]['text']
        row['steps'][1]['text'] = 'Sjud laxen mycket försiktigt cirka tolv minuter. Mitten av den tjockaste biten ska nå minst 63 °C; förläng vid behov. Syra ersätter inte tillagning.'
        insert_step(row, 2, {'text': 'Lägg försiktigt laxen i den heta lagen och sänk värmen.', 'uses': ['lax'], 'minutes': 1})
        transfer = row['steps'][3]
        transfer['text'] = transfer['text'].replace('Byt till nytt kallt badvatten när det blir varmt.', '')
        row['steps'][4:5] = [
            {'text': 'Låt de grunda kärlen kylas i det kalla vattenbadet i 15 minuter.', 'uses': ['lax'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera temperaturen och byt badvattnet mot 4000 ml nytt kallt vatten.', 'uses': ['lax'], 'minutes': 2},
            {'text': 'Låt kylas ytterligare 15 minuter i vattenbadet.', 'uses': ['lax'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera att portionerna inte längre är varma. Täck och flytta till kylskåp vid 4 °C; fortsätt aktiv kylning om de fortfarande är varma.', 'uses': ['lax'], 'minutes': 2},
        ]
        for step in row['steps']:
            if step['text'].startswith('Skala potatisen'):
                step['text'] = step['text'].replace('och skär den', 'och väg den angivna råa ätliga mängden. Skär den')
            if step['text'].startswith('Sjud potatisen'):
                step['text'] = 'Sjud potatisen omkring 20 minuter tills en sticka går lätt igenom.'
        index = next(n for n, step in enumerate(row['steps'], 1) if step['text'].startswith('Hacka såsens dill'))
        insert_step(row, index, {'text': 'Häll av potatisens saltade kokvatten och håll potatisen varm över 60 °C under lock.', 'uses': ['potatis', 'salt'], 'minutes': 2})
        mark_process(row, index, ['potatis', 'salt'], 'drain_after_cooking', 'Saltat potatisvatten hälls bort. Upptag av salt och förlust till vattnet är inte uppmätta.')
        index += 1
        row['steps'][index - 1]['text'] = row['steps'][index - 1]['text'].replace('Hacka såsens dill och rör ihop', 'Rör ihop den helt kalla kokta dillen och all dillvätska')
        insert_step(row, index, {'text': 'Koka såsens frysta hackade dill med 20 ml vatten minst tre minuter eller längre enligt förpackningen. Häll hela mängden i en ren grund skål och ställ i kylskåp.', 'uses': ['dill'], 'minutes': 4})
        insert_step(row, index + 1, {'text': 'Låt dillen och all vätska kallna helt i kylskåp, uppskattningsvis 30 minuter; förläng om den ännu är varm.', 'uses': ['dill'], 'minutes': 30, 'passive': True})
        broth = ['lax', 'gul lök', 'dill', 'ättiksprit 12 procent', 'strösocker', 'salt']
        if row['variant_id'] != 'simple':
            broth += ['morot', 'lagerblad']
            mark_process(row, 4, ['lagerblad'], 'remove_after_infusion', 'Lagerblad plockas bort efter sjudningen; överföringen till lagen är inte uppmätt.')
        mark_process(row, len(row['steps']), broth, 'drain_after_cooking', 'Fisken lyfts ur inläggningslagen före servering. Lagen är processvätska med okänd överföring av salt, socker och övrig näring.')
        prepend_thaw(row, 'lax', 720, 'Koka all upptiningssaft i lagen före fisken.')
        for process in row['unmeasured_processes']:
            process['step'] += 2
        changes.append('Require frozen salmon/dill explicitly, thaw salmon and boil its juice in the discarded poaching liquid. Keep actual discarded sweet-sour brine, bay removal and salted potato water under unknown-loss metadata. Frozen sauce dill cooks and chills before mixing. Active loading, bath-water changes, fridge transfer and draining are separately scheduled.')
    if base in STAGES[12]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('phirni'):
        row['steps'][1]['text'] = 'Blötlägg riset 30 minuter.'
        row['steps'][2]['text'] = 'Häll bort blötläggningsvattnet. ' + row['steps'][2]['text']
        row['steps'][2]['minutes'] += 1
        row['steps'][6]['text'] = 'Låt skålen svalna 15 minuter i det kalla vattenbadet.'
        row['steps'][7]['text'] = 'Kyl cirka 90 minuter tills puddingen är helt kall och har satt sig.'
        insert_step(row, 7, {'text': 'Ställ skålen i ett kallt vattenbad med 500 ml vatten utan att vatten går i puddingen.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        insert_step(row, 9, {'text': 'Flytta skålen till kylskåp; låt den inte stå kvar på köksbänken.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        row['steps'].append({'text': 'Servera hela den kalla portionsskålen.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        changes.append('Preserve raw-ground-rice method and all cooked cream. Count draining, water-bath setup, fridge transfer and serving as active work rather than hiding them inside passive cooling.')
    if base.endswith('hor-mok-pla'):
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('Kontrollera att fisken är benfri.', 'Använd den upptinade benfria fisken och behåll all upptiningssaft i fiskmassan. Knäck ägg och väg den råa mängden utan skal.')
        row['steps'][3:4] = [
            {'text': 'Ställ skålarna stadigt i ånginsatsen och lägg på locket.', 'uses': ['fisk', 'ägg'], 'minutes': 2},
            {'text': 'Ånga under lock i 15 minuter.', 'uses': ['fisk', 'ägg'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera vattnet under insatsen. Fyll vid behov på med 300 ml kokande vatten utan att hälla i maten. Lägg tillbaka locket.', 'uses': [], 'minutes': 1},
            {'text': 'Ånga ytterligare 15 minuter, totalt cirka 30 minuter.', 'uses': ['fisk', 'ägg'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera att krämen stannat och att mitten av samtliga skålar nått minst 72 °C. Förläng ångningen vid behov; servera aldrig rå fisk-äggkräm.', 'uses': ['fisk', 'ägg'], 'minutes': 2},
        ]
        mark_process(row, 3, ['vitkål'], 'drain_after_cooking', 'Kålen ångas och får rinna av före fyllning. Vätske- och näringsförlusten är inte uppmätt.')
        prepend_thaw(row, 'fisk', 720, 'Blanda all upptiningssaft i fiskmassan; hela massan ska genomhettas till minst 72 °C.')
        row['unmeasured_processes'][0]['step'] += 2
        changes.append('Explicit frozen-fish thaw, all juice cooked in the custard, and shell-free raw egg weight. Mark steamed-cabbage draining as unknown loss. Schedule steamer loading, water inspection and final temperature checks as active work.')
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'thaibasilika', 'basilika')
            rename_ingredient(row, 'makrutlimeblad', 'torkade makrutlimeblad')
            rename_ingredient(row, 'färsk chili', 'paprika')
            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] == 'torkade makrutlimeblad':
                        item.update(quantity=1, form='dry', label='Torkade makrutlimeblad, vägs före infusion')
                    if item['name'] == 'basilika':
                        item['label'] = 'Vanlig basilika, ansade blad eller frysta hackade blad'
                    if item['name'] == 'paprika':
                        item.update(quantity=20, label='Röd paprika, ätlig rå vikt efter urkärning')
            row['name'] = 'Hor mok pla – vanlig basilika och torr limebladsinfusion – ' + ('med fisksås' if row['variant_id'] == 'standard' else 'med kokoskräm och limegurka')
            row['flavor'] = ['röd curry', 'kokos', 'vanlig basilika', 'silad limebladsinfusion']
            mixing = row['steps'][4]
            mixing['text'] = mixing['text'].replace('ägg och kokosmjölken från fiskkomponenten', 'ägg och hela den avsvalnade silade kokosmjölken från fiskkomponenten').replace('finstrimlade makrutlimeblad och thaibasilika', 'hackad vanlig basilika; frysta hackade blad tillsätts direkt med all vätska')
            mixing['uses'].remove('torkade makrutlimeblad')
            for step in row['steps']:
                step['text'] = step['text'].replace('Strimla chilin fint', 'Kärna ur röd paprika, väg den ätliga mängden och strimla fint').replace('och lägg på chilin', 'och lägg på paprikastrimlorna')
                step['text'] = step['text'].replace('300 ml kokande vatten', '300 ml vatten (kokande)')
            row['equipment'] = [e.replace('fyra värmetåliga skålar cirka 350 ml', 'värmetåliga portionsskålar cirka 350 ml, en per portion') for e in row['equipment']]
            infusion = [
                {'text': 'Häll hela fiskkomponentens kokosmjölk i en liten kastrull och lägg i de uppvägda torkade limebladen. Värm till svag sjudning under omrörning. Toppens kokosmjölk, om den ingår, hålls separat.', 'uses': ['kokosmjölk', 'torkade makrutlimeblad'], 'minutes': 3},
                {'text': 'Låt dra på mycket låg värme under lock i tio minuter; undvik kraftig kokning.', 'uses': ['kokosmjölk', 'torkade makrutlimeblad'], 'minutes': 10, 'passive': True},
                {'text': 'Sila kokosmjölken genom finmaskig sil till en grund värmetålig skål. Kasta alla blad och hårda fragment; fyll inte på med extra kokosmjölk. Ställ skålen i ett kallt vattenbad med 500 ml vatten utan att vatten kommer i mjölken.', 'uses': ['kokosmjölk', 'torkade makrutlimeblad'], 'minutes': 3},
                {'text': 'Låt den silade kokosmjölken svalna i vattenbadet cirka femton minuter.', 'uses': ['kokosmjölk'], 'minutes': 15, 'passive': True},
                {'text': 'Kontrollera att kokosmjölken har svalnat till högst 25 °C innan råa ägg eller fisk tillsätts; förläng kylningen vid behov. Använd hela den silade mängden i fiskmassan. Fisken stannar i kylskåp tills massan ska blandas.', 'uses': ['kokosmjölk', 'fisk', 'ägg'], 'minutes': 1},
            ]
            for index, step in enumerate(infusion, 3):
                insert_step(row, index, step)
            mark_process(row, 5, ['torkade makrutlimeblad', 'kokosmjölk'], 'remove_after_infusion', 'Blad och hårda fragment silas bort. Extraktion samt kokosmjölk som följer med bladen är okända; inga torr/färsk- eller näringsfaktorer antas.')
            row['notes'] += ' Örtalternativ med vanlig basilika och egen dos 1 g torkade makrutblad i stället för 15 g thaibasilika och 2 g färska blad; vanlig basilika behåller 15 g-dosen. Ingen lika arom påstås. Kokosmjölken vägs/mäts före infusion och okänd silförlust; fyll inte på extra. Utökad får 20 g röd paprika i stället för 5 g färsk chili. Fisk och ägg tillsätts efter aktiv kontroll av kylningen, och hela fiskmassan ångas till minst 72 °C. Inte provlagad.'
            changes.append('Standard/extended only: explicit ordinary-basil version with a new 1 g dried-leaf infusion in the original custard coconut milk. Strain every fragment, record unknown milk/leaf loss and cool before egg/fish mixing. Extended replaces 5 g fresh chili with 20 g edible red pepper garnish; retain separate cooked coconut topping and lime-cucumber side.')
    if base.endswith('kluai-buat-chi'):
        if row['variant_id']=='extended':
            for component in row['components']:
                component['ingredients']=[i for i in component['ingredients'] if i['name']!='pandanblad']
            row['name']='Kluai buat chi – med rostad kokos och sesam, utan pandan'
            row['flavor']=['banan','kokos','sesam','söt-salt']
            row['notes']='Granskad utökad variant utan 2 g pandanblad. Bladets arom utelämnas uttryckligen; ingen annan ingrediens kallas pandan. Samtliga övriga matmängder bevaras. Rosta 8 g kokosflingor och 5 g torra sesamfrön per portion och servera hela toppingen till banan i kokosmjölk. Inte provlagad.'
            row['steps']=[
                row['steps'][0],
                {'text':'Häll kokosmjölk, socker och salt i en liten kastrull med 30 ml vatten. Värm försiktigt till svag sjudning under omrörning; undvik häftig kokning.','uses':['kokosmjölk','strösocker','salt'],'minutes':4},
                row['steps'][3],
                {'text':'Låt banan och kokosmjölk svalna lite före servering.','uses':[],'minutes':3,'passive':True},
                {'text':'Servera alla bananbitar och hela kokosmjölksåsen ljumma med all rostad kokos och sesam ovanpå.','uses':['banan','kokosmjölk','kokosflingor','sesamfrön'],'minutes':1},
            ]
            row['steps'][2]['text']=row['steps'][2]['text'].replace('Dela bananen', 'Skala bananen, väg den angivna ätliga mängden och dela den')
            changes.append('Extended only: omit pandan explicitly, retain original toasted coconut and sesame doses and as-sold seed identity. No leaf infusion, no unknown extraction, all coconut sauce and topping served.')
        else:
            row['steps'][1]['text'] = row['steps'][1]['text'].replace('Dela bananen', 'Skala bananen, väg den angivna ätliga mängden och dela den')
            row['steps'][2].update(text='Låt svalna lite före servering.', passive=True)
            row['steps'].append({'text': 'Servera alla bananbitar och hela kokosmjölksåsen ljumma.', 'uses': ['banan', 'kokosmjölk'], 'minutes': 1})
            changes.append('Weigh peeled edible banana, keep all coconut sauce, and separate passive cooling from serving.')
    if base.endswith('pasticciotto-leccese'):
        row['name'] += ' – mördeg med smör'
        row['steps'][3]['text'] = 'Kyl krämen i kylskåp cirka 35 minuter tills den är helt kall och inte smälter smöret vid fyllning.'
        insert_step(row, 4, {'text': 'Bred krämen i en ren grund skål och täck direkt mot ytan före kylningen.', 'uses': ['mjölk', 'äggula', 'majsstärkelse'], 'minutes': 2})
        row['steps'][-1]['text'] = 'Låt bakverket svalna på galler 20 minuter; fyllningen kan annars bränna.'
        row['steps'].append({'text': 'Lossa försiktigt formen och servera hela bakverket ljummet.', 'uses': ['vetemjöl', 'äggula'], 'minutes': 1})
        insert_step(row, 1, {'text': 'Knäck rena hönsägg och separera gula och vita utan tillsatser. Väg rå äggula utan skal separat till deg och kräm. Oanvänd vita och gula är separata rester; komplettera inköpet om det faktiska utbytet är mindre än uppskattningen.', 'uses': ['äggula'], 'minutes': 3})
        changes.append('Use the existing reviewed egg-separation method with explicitly weighed raw yolks, no fixed yolk count or exact yield. Preserve the authored butter shortcrust adaptation and separate cream transfer/unmoulding from cooling.')
    if base.endswith('sopa-de-lima'):
        mark_process(row, 4, ['rapsolja', 'majstortillas'], 'deep_fry_and_drain', 'Tortillastrimlor steks och lyfts upp på galler; kvarvarande olja serveras inte. Upptagen oljemängd är okänd, medan hela insatsen måste köpas.')
        if row['variant_id'] != 'simple':
            row['name'] += ' – med lime och grapefrukt'
            row['steps'][4]['text'] = row['steps'][4]['text'].replace('Finhacka det helt hinnfria grapefruktköttet', 'Skala grapefrukten och ta bort hinnorna. Väg den angivna ätliga mängden och finhacka den')
            row['steps'][4]['minutes'] += 3
        if row['variant_id'] == 'extended':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Tärna avokadon.', 'Använd de tinade avokadobitarna med all saft.')
            prepend_thaw(row, 'avokado', 120, 'Använd hela mängden i soppan vid servering.')
            row['unmeasured_processes'][0]['step'] += 2
        changes.append('Keep the source-authored real oil input and discarded pan remainder with unknown uptake. Standard/extended visibly name the lime-grapefruit adaptation and weigh peeled flesh; extended frozen avocado is thawed with all juice.')
    if base in STAGES[10]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('bohuslansk-aggost'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=42, unit='g', label='Filmjölk, uppvägd i gram')
                if item['name'] == 'jordgubbar':
                    item['label'] = 'Frysta ansade jordgubbar, hela mängden och saften används'
        row['name'] = row['name'].replace('färska bär', 'tinade bär')
        row['steps'][0]['text'] = 'Knäck ägg och väg den råa mängden utan skal. Väg filmjölken i gram. ' + row['steps'][0]['text']
        row['steps'][0]['minutes'] += 2
        row['steps'][3].update(text='Klä en liten sil eller äggostform med ren silduk över en skål. Lyft över ostmassan med hålslev och varva med sockret. Vasslen är en separat processrest med okänt näringsinnehåll.', minutes=2)
        insert_step(row, 5, {'text': 'Låt rinna av tio minuter tills den värsta hettan gått ur.', 'uses': ['mjölk', 'filmjölk', 'ägg', 'strösocker'], 'minutes': 10, 'passive': True})
        for step in row['steps']:
            step['text'] = step['text'].replace('Skölj och dela jordgubbarna.', 'Dela de tinade jordgubbarna och servera all saft till.')
            step['text'] = step['text'].replace('Vispa den kalla grädden', 'Vispa den kalla vispgrädden')
        mark_process(row, 4, ['mjölk', 'filmjölk', 'ägg', 'strösocker'], 'strain_whey', 'Ostmassan skiljs från vasslen och fortsätter rinna av i kylskåp. Ätligt utbyte och näringsfördelning är inte uppmätta.')
        prepend_thaw(row, 'jordgubbar', 120, 'Servera hela bärmängden och all saft till äggosten.')
        # prepend_steps adjusts dependencies but not the new process metadata.
        row['unmeasured_processes'][0]['step'] += 2
        changes.append('New culinary dose 42 g filmjölk replaces 40 ml without a density conversion. Frozen berries are thawed with all juice and named visibly. Raw egg is weighed shell-free. Whey separation remains explicit and unmeasured; two active transfer minutes are separated from ten passive draining minutes.')
    if base.endswith('shrikhand'):
        mark_process(row, 2, ['yoghurt naturell'], 'strain_whey', 'Yoghurtens vassle silas bort under åtta timmar i kylskåp. Serverad vikt och näringsfördelning är inte uppmätta.')
        if row['variant_id'] == 'extended':
            row['steps'][2].update(text='Värm mjölken försiktigt i en liten kastrull, rör ner saffran och ta från värmen.', minutes=2)
            insert_step(row, 4, {'text': 'Låt saffransmjölken dra och svalna tio minuter.', 'uses': ['mjölk', 'saffran'], 'minutes': 10, 'passive': True})
            for step in row['steps']:
                step['text'] = step['text'].replace('Skär mangon i små bitar', 'Använd de tinade mangobitarna med all saft')
            prepend_thaw(row, 'mango', 120, 'Behåll all saft till krämen.')
            row['unmeasured_processes'][0]['step'] += 2
        changes.append('Keep chilled whey draining without assumed yield or nutrient retention. Extended frozen mango is explicitly thawed with all juice; saffron heating and ten-minute cooling are scheduled separately.')
    if base.endswith('chhena-poda'):
        row['steps'][1]['text'] = 'Låt ostmassan rinna av cirka 15 minuter. Pressa inte torrt; den ska vara fuktig och gå att knåda. Vassle som inte används är en separat processrest.'
        row['steps'][2]['text'] = 'Låt ostmassan svalna tio minuter tills den går att hantera.'
        row['steps'][4]['text'] = 'Låt massan vila 15 minuter så att mannagrynen sväller.'
        row['steps'][6]['text'] = 'Låt kakan svalna i formen 30 minuter.'
        insert_step(row, 2, {'text': 'Klä en sil med ren silduk över en skål och häll försiktigt i ostmassan och vasslen.', 'uses': ['mjölk', 'citronjuice'], 'minutes': 2})
        insert_step(row, 5, {'text': 'Värm ugnen till 185 °C och klä en liten form med bakplåtspapper. Smält det uppmätta smöret försiktigt.', 'uses': ['smör'], 'minutes': 3})
        insert_step(row, 8, {'text': 'Fördela hela massan i formen och jämna till ytan.', 'uses': ['mjölk', 'mannagryn'], 'minutes': 2})
        row['steps'].append({'text': 'Lossa hela den lilla kakan och servera. Förvara inte fuktig färskostkaka i varm ugn efter servering.', 'uses': ['mjölk', 'mannagryn'], 'minutes': 2})
        mark_process(row, 3, ['mjölk', 'citronjuice'], 'strain_whey', 'Mjölk och citron delas i ostmassa och vassle. Bara angiven liten del vassle får återföras; kvarvarande processrest och näringsfördelning är inte uppmätta.')
        changes.append('Keep actual milk curdling and whey separation with unknown yield. Separate active pouring, oven/form preparation, butter melting, filling and unmoulding from passive draining, cooling and baking.')
    if base.endswith('torta-pasqualina'):
        if row['variant_id'] != 'simple':
            for component in row['components']:
                component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'mangold']
                for item in component['ingredients']:
                    if item['name'] == 'spenat':
                        item['quantity'] = 600
            for step in row['steps']:
                step['uses'] = list(dict.fromkeys('spenat' if n == 'mangold' else n for n in step['uses']))
                step['text'] = step['text'].replace(' Skär mangolden och tillsätt den, stjälkar först och blad sist.', '')
            row['name'] += ' – med spenat, mejram och muskot'
            changes.append('Explicit spinach-only pasqualina: 600 g frozen spinach replaces the mixed 400 g spinach/200 g chard proposal, as a new culinary input dose, not a fresh/frozen or drained-yield conversion. Standard retains marjoram/nutmeg and extended retains its tomato-basil side; neither duplicates the simpler variant.')
        inputs = ['spenat']
        mark_process(row, 3, inputs, 'drain_after_cooking', 'Uppvärmda bladgrönsaker pressas ur före fyllningen. Vätskemängd och näringsförlust är inte uppmätta; hela inköpta insatsen bevaras.')
        row['steps'][4]['text'] = 'Låt grönsaksblandningen svalna på ett fat cirka 15 minuter.'
        row['steps'][5]['text'] = 'Värm ugnen till 185 °C. ' + row['steps'][5]['text'].replace('finriven parmesan', 'den färdigrivna parmesanen')
        row['steps'][5]['minutes'] += 1
        if row['variant_id'] == 'extended':
            row['name'] += ' – med ljummen tomat-basilikasallad'
            row['steps'][-1]['text'] = 'Tärna tomaterna. Koka hälften med den frysta hackade basilikan under omrörning minst tre minuter eller längre enligt förpackningen. Blanda med resten av tomaterna, salladens vinäger och olja. Skär pajen i fyra delar och servera hela den ljumma salladen med all saft till.'
            row['steps'][-1]['minutes'] = 9
        if row['variant_id'] != 'simple':
            row['notes'] = row.get('notes', '').replace('AI-författat receptutkast. Inte provlagat och ännu inte import- eller produktgranskat av Smako.', 'Granskad spenatversion, inte provlagad.')
            row['steps'][3]['text'] += ' Bred ut blandningen på ett fat inför avsvalningen.'
            row['steps'][7]['text'] = 'Baka på nedre falsen cirka 45 minuter.'
            insert_step(row, 9, {'text': 'Kontrollera att skalet är gyllene, botten gräddad och ägghålen har stelnad vita och minst 72 °C i mitten. Förläng gräddningen vid behov; ta därefter ut formen.', 'uses': ['ägg', 'vetemjöl', 'spenat'], 'minutes': 2})
            changes.append('Count the oven doneness/temperature check and pan removal as active work before the passive twelve-minute rest.')
        changes.append('Retain real spinach/chard draining as unmeasured loss. Use weighed raw shell-free eggs and already grated parmesan. Separate oven preparation; extended frozen basil cooks in a visibly warm salad.')
    if base.endswith('nicuatole-majspudding'):
        row['steps'][0].update(text='Vispa masa harina med mjölk, socker, vanilj och salt i en liten tjockbottnad kastrull tills inga torra klumpar finns.', minutes=1)
        insert_step(row, 2, {'text': 'Låt blandningen stå fem minuter.', 'uses': ['masa harina', 'mjölk'], 'minutes': 5, 'passive': True})
        row['steps'][3].update(text='Skölj en skål på minst 250 ml med kallt vatten och skaka ur. Packa hela den heta massan i skålen och jämna till.', minutes=2)
        insert_step(row, 5, {'text': 'Låt svalna cirka 15 minuter före kylningen.', 'uses': ['masa harina', 'mjölk'], 'minutes': 15, 'passive': True})
        if row['variant_id'] == 'extended':
            for step in row['steps']:
                step['text'] = step['text'].replace('Tärna den skalade mangon', 'Använd de tinade mangobitarna med all saft')
            prepend_thaw(row, 'mango', 120, 'Behåll hela mängden och all saft till puddingen.')
        changes.append('Keep the explicit masa-harina adaptation with full retained inputs. Use a bowl large enough for all pudding; separate five-minute hydration and fifteen-minute cooling from active work. Extended mango is explicitly frozen and thawed.')
    if base in STAGES[9]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith(('pa-tong-ko', 'bunuelos-de-viento', 'mangalore-buns', 'loukoumades', 'gulab-jamun')):
        if base.endswith('gulab-jamun'):
            row['steps'][5].update(text='Låt bollarna dra i den ljumma sirapen i 30 minuter.', minutes=30)
            insert_step(row, 6, {'text': 'Lyft bollarna med hålslev, låt överskottsoljan rinna av på papper och lägg dem i den ljumma sirapen. Återstående frityrolja serveras inte.', 'uses': ['rapsolja', 'mjölkpulver', 'strösocker'], 'minutes': 2, 'after': [5]})
            row['steps'][6]['after'] = [6]
            insert_step(row, 8, {'text': 'Vänd bollarna försiktigt i sirapen.', 'uses': ['mjölkpulver', 'strösocker'], 'minutes': 1, 'after': [7]})
            insert_step(row, 9, {'text': 'Låt dra ytterligare 30 minuter, totalt 60 minuter.', 'uses': ['mjölkpulver', 'strösocker'], 'minutes': 30, 'passive': True, 'after': [8]})
            for n, step in enumerate(row['steps']):
                step['after'] = [n] if n else []
        if base.endswith('loukoumades'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('fingervarmt, cirka 35 °C', 'tempererat enligt torrjästens förpackningsanvisning')
            row['steps'][2]['text'] = 'Smörj två torra teskedar med några droppar av den uppmätta oljan innan den värms. Värm resten till 170 °C i en stadig kastrull där mängden bildar ett grunt bad. Välj kärl efter portionsmängden och fyll aldrig mer än till en tredjedel. Håll ett torrt lock nära och lämna inte oljan obevakad.'
            row['steps'][3]['text'] = row['steps'][3]['text'].replace('Smörj två torra teskedar med lite av den angivna oljan innan den hettas upp. ', '')
        if base.endswith('mangalore-buns'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('Mosa bananen', 'Skala bananen, väg den angivna ätliga mängden och mosa')
        if base.endswith('bunuelos-de-viento'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('Vispa mjöl, uppvägt ägg', 'Knäck ägg och väg den angivna råa ätliga mängden utan skal; oanvänt ägg är separat rest. Vispa mjöl, uppvägt ägg')
        for step in row['steps']:
            step['text'] = step['text'].replace('mer än halva kastrullen', 'mer än en tredjedel av kastrullen').replace('mer än halvfullt', 'mer än fyllt till en tredjedel')
        draining = [n for n, step in enumerate(row['steps'], 1)
                    if any(term in step['text'] for term in ('rinna av', 'droppa av'))]
        assert draining, f'Missing explicit oil-draining step: {base}'
        index = draining[0]
        mark_process(row, index, ['rapsolja'], 'deep_fry_and_drain', 'Hela uppmätta oljemängden är en inköpt processinsats. Överskottsolja rinner av och serveras inte. Oljans upptag och slutlig näring är okända.')
        changes.append('Keep the original frying quantities and classic method, explicitly mark unknown oil uptake, and do not treat process oil as served food. Preserve fryer temperature, batch/doneness checks and at-most-one-third fill. Active transfer/turning and yeast preparation are clarified where needed.')
    if base.endswith('revithada'):
        row['steps'][1]['text'] = 'Blötlägg kikärtorna 12 timmar i kylskåp. Blötläggningsvattnet hälls bort i nästa aktiva steg.'
        # The two inspections are real work, separately scheduled between
        # passive periods rather than hidden in a six-hour passive step.
        old = row['steps'][3]
        row['steps'][3:4] = [
            {**old, 'text': 'Baka den täckta grytan två timmar vid 150 °C.', 'minutes': 120},
            {'text': 'Kontrollera vätskan och tillsätt 150 ml vatten om kikärtorna annars blir torra. Lägg tillbaka det täta locket.', 'uses': ['kikärtor'], 'minutes': 1},
            {**old, 'text': 'Baka ytterligare två timmar under tätt lock.', 'minutes': 120},
            {'text': 'Kontrollera vätskan igen; tillsätt vid behov 150 ml vatten och lägg tillbaka locket.', 'uses': ['kikärtor'], 'minutes': 1},
            {**old, 'text': 'Baka ytterligare två timmar, totalt omkring sex timmar. Kikärtorna ska vara helt mjuka och kunna mosas lätt; förläng tiden om det behövs.', 'minutes': 120},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        if row['variant_id'] != 'simple':
            mark_process(row, len(row['steps']), ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och plockas sedan bort. Överföring till spadet är inte uppmätt; ingen noll- eller fullretention antas.')
        changes.append('Keep the authored bay leaf and its removal in standard/extended. Explicit unmeasured-process contract makes served nutrition unknown. Count two active liquid inspections during the original six-hour bake.')
    if base.endswith('pasta-alla-genovese'):
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
            row['name'] += ' – med vitt matlagningsvin'
        for step in row['steps']:
            step['text'] = step['text'].replace('Häll i vinet', 'Häll i det vita matlagningsvinet')
            step['text'] = step['text'].replace('riv parmesan över', 'fördela den färdigrivna parmesanen över')
            step['text'] = step['text'].replace('Häll av, hacka persiljan och vänd bönorna', 'Låt fryst hackad persilja koka med bönorna de sista två minuterna. Häll av och vänd bönorna')
        simmer = row['steps'][3]
        periods = []
        for turn in range(6):
            periods.append({**simmer, 'text': 'Sjud på låg värme under lock i 30 minuter.', 'minutes': 30})
            if turn < 5:
                periods.append({'text': 'Rör om och kontrollera att bottnen inte kokar torr. Tillsätt vid behov 50 ml vatten och lägg tillbaka locket.', 'uses': ['högrev', 'gul lök'], 'minutes': 1})
        row['steps'][3:4] = periods
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        for index, step in enumerate(row['steps'], 1):
            if 'Ta upp lagerbladet' in step['text']:
                mark_process(row, index, ['lagerblad'], 'remove_after_infusion', 'Lagerblad plockas bort efter långkok; överföring till såsen är inte uppmätt.')
            if step['text'].startswith('Koka upp 2500 ml vatten'):
                mark_process(row, index, ['pasta', 'salt'], 'drain_after_cooking', 'Saltat pastavatten hälls delvis bort och en mindre del används i såsen. Upptag av salt och förlust till vattnet är okända.')
        changes.append('Keep original salt and bay-leaf procedures with explicit unknown retention. Standard/extended explicitly use 100 ml cooking wine, at the manufacturer-recommended same cooking volume; grated parmesan and cooked frozen parsley. Five active stirring/liquid checks are scheduled between six half-hour simmering periods.')
    if base.endswith('tirokafteri'):
        row['steps'][0]['text'] = 'Värm ugnen till 230 °C över-/undervärme. Kärna ur paprikan, väg angiven rå ätlig mängd med skal och lägg med skalsidan upp i en liten ugnsform.'
        row['steps'][1]['text'] = 'Rosta 20 minuter eller tills skalet fått mörka blåsor.'
        row['steps'][1]['minutes'] = 20
        insert_step(row, 3, {'text': 'Lägg den varma paprikan i en skål och täck.', 'uses': ['paprika'], 'minutes': 1, 'after': [2]})
        insert_step(row, 4, {'text': 'Låt svalna tio minuter så att skalet lossnar.', 'uses': ['paprika'], 'minutes': 10, 'passive': True, 'after': [3]})
        row['steps'][4]['after'] = [4]
        mark_process(row, 5, ['paprika'], 'peel_after_cooking', 'Paprikan vägs rå efter urkärning men före rostning och skalning. Borttaget skal och eventuell vätska är okänt utbyte.')
        changes.append('Preserve roasted-and-peeled pepper method. Raw input is explicitly weighed before roasting/peeling; lost peel and juice are not assigned an invented yield. Active transfer and passive cooling are separate.')
    if base.endswith('melitzanosalata'):
        row['name'] += ' – rostad med skal, sedan skalad'
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'aubergine':
                    item['label'] = 'Aubergine med skal, rå ätlig vikt efter att fästet tagits bort'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skär den redan skalade auberginen i tjocka skivor.', 'Ta bort auberginens fäste, väg angiven rå mängd med skal och dela i längsgående kvartar. Skalet tas bort efter rostningen.')
        row['steps'][2]['text'] = 'Låt grönsakerna rinna av över skålen och svalna 15 minuter. Pressa inte ur fruktköttet. Vätskan serveras inte.'
        insert_step(row, 3, {'text': 'Flytta de rostade grönsakerna till ett durkslag över en skål.', 'uses': ['aubergine'] + (['paprika'] if row['variant_id']=='extended' else []), 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][4]['text'] = row['steps'][4]['text'].replace('Hacka auberginen', 'Dra bort aubergineskalet och hacka fruktköttet')
        row['steps'][4]['minutes'] += 3
        if row['variant_id'] == 'extended':
            row['steps'][4]['text'] = row['steps'][4]['text'].replace('Finhacka rödlök, persilja och rostad paprika', 'Värm fryst hackad persilja med 20 ml vatten i en liten kastrull under omrörning minst två minuter eller längre enligt förpackningen. Behåll hela denna vätska. Finhacka rödlök och rostad paprika')
            row['steps'][4]['text'] += ' Blanda också ner all uppvärmd persilja med vätskan.'
            row['steps'][4]['minutes'] += 3
        mark_process(row, 4, ['aubergine', 'olivolja'] + (['paprika'] if row['variant_id']=='extended' else []), 'drain_after_cooking', 'Vätska från rostade grönsaker med olja rinner av. Ingen kvarhållen andel är uppmätt.')
        mark_process(row, 5, ['aubergine'], 'peel_after_cooking', 'Ny tydlig rå insats med skal före rostning. Skalet tas bort efteråt; 250 g är inte en påstådd motsvarighet till 250 g skalat fruktkött.')
        row['steps'][1].update(text='Rosta grönsakerna i 15 minuter utan att ytan blir svart.', minutes=15)
        insert_step(row, 3, {'text': 'Vänd grönsakerna med tång.', 'uses': ['aubergine'] + (['paprika'] if row['variant_id']=='extended' else []), 'minutes': 1, 'after': [2]})
        insert_step(row, 4, {'text': 'Rosta ytterligare cirka 20 minuter tills auberginen är helt mjuk och brynt men inte svart. Förläng tiden om den fortfarande är fast.', 'uses': ['aubergine'], 'minutes': 20, 'passive': True, 'after': [3]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Visible roast-in-skin version, using the same numerical 250 g as a new gross edible input with skin, not peeled-flesh equivalence. Peel and roast juice are removed after cooking under the unknown-loss contract. No edible yield/density invented.')
    if base.endswith('porterstek'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Krossa enbären lätt', 'Mal enbären mycket fint i kryddkvarn')
            step['text'] = step['text'].replace('Ta bort enbären. ', 'Behåll de finmalda enbären i såsen. ')
            step['text'] = step['text'].replace('Skala potatisen och dela stora exemplar jämnt.', 'Skala potatisen, väg den angivna råa ätliga mängden och dela stora exemplar jämnt.')
            if 'och potatisdelens salt' in step['text']:
                step['text'] = step['text'].replace('och potatisdelens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            if step['text'].startswith('Vispa mjölet'):
                step['text'] = step['text'].replace('Vispa ner i spadet', 'Vispa ner i spadet tillsammans med hela saltmängden från potatiskomponenten')
                step['uses'].append('salt')
            if step['text'].startswith('Koka ner spadet'):
                step['text'] = step['text'].replace('Rör ner grädden', 'Rör ner hela saltmängden från potatiskomponenten och grädden')
                step['uses'].append('salt')
        simmer = row['steps'][1]
        simmer['text'] = simmer['text'].replace('Sjud under tätt lock cirka två timmar. Vänd steken efter en timme.', 'Sjud vidare under tätt lock cirka en timme till, totalt ungefär två timmar.')
        simmer['minutes'] = 60
        insert_step(row, 2, {'text': 'Sjud under tätt lock på låg värme i en timme.', 'uses': ['nötstek'], 'minutes': 60, 'passive': True, 'after': [1]})
        insert_step(row, 3, {'text': 'Vänd steken varsamt vid halvtidskontrollen och lägg på locket igen.', 'uses': ['nötstek'], 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] += ' Fördela hela såsen och all köttsaft från skärbrädan mellan portionerna.'
        if row['variant_id'] != 'simple':
            row['equipment'].append('kryddkvarn')
        changes.append('Use declared concentrated blackcurrant cordial; never the diluted nutrition as concentrate. Grind and retain juniper, retain all sauce and board juices, move unchanged potato salt to sauce, and count the simmering turn as active work.')
    if base.endswith('zuppa-imperiale'):
        rename_ingredient(row, 'grönsaksbuljong', 'grönsaksfond')
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'grönsaksfond':
                    item.update(quantity=35, unit='ml', label='Flytande koncentrerad grönsaksfond')
        row['name'] += ' – med flytande grönsaksfond'
        for step in row['steps']:
            step['text'] = step['text'].replace('Riv parmesanen.', 'Väg upp den färdigrivna parmesanen.')
            step['text'] = step['text'].replace('inte har rå äggsmet i mitten', 'når minst 72 °C i mitten utan rå äggsmet')
            step['text'] = step['text'].replace('buljongpulvret', 'den flytande koncentrerade grönsaksfonden')
            step['text'] = step['text'].replace('Hacka persiljan och rör ner den.', 'Rör ner fryst hackad persilja och låt koka med minst två minuter eller längre enligt förpackningen.')
        changes.append('Visible new dose 35 ml liquid concentrated vegetable stock replaces 12 g powder; the original process water is retained and no equivalence/density is asserted. Use grated parmesan and cook frozen parsley; explicit egg doneness.')
    if base.endswith('pizzoccheri'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'salvia':
                    item.update(form='dry', quantity=1, label='Torkad smulad salvia')
                if c['id'] == 'kok' and item['name'] == 'salt':
                    item['quantity'] = 2
        if row['variant_id'] != 'simple':
            row['name'] += ' – med torkad salvia'
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala potatis och tärna', 'Skala potatisen, väg angiven rå ätlig mängd och tärna')
            if 'med kokkomponentens salt' in step['text']:
                step['text'] = step['text'].replace('med kokkomponentens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            step['text'] = step['text'].replace('tillsammans med salviabladen', 'tillsammans med torkad smulad salvia')
            step['text'] = step['text'].replace('och finriv parmesan', 'och väg upp färdigriven parmesan')
            if step['text'].startswith('Lyft pasta'):
                step['text'] = step['text'].replace('och svartpeppar', ', hela kokkomponentens salt och svartpeppar')
                step['uses'].append('salt')
                step['text'] += ' Skrapa med allt smör och all ost till serveringen.'
            if step['text'].startswith('Skala rödbeta'):
                step['text'] = 'Skala rödbetan och kärna ur äpplet, väg de angivna ätliga mängderna och grovriv. Vänd med äppelcidervinäger och ställ svalt; hela salladen och dressingen serveras separat från pastan.'
        changes.append('Visible dried-sage adaptation: 1 g instead of 5 g fresh leaves, no fresh/dry yield. Replace 6 g discarded cooking-water salt with a new 2 g dose on drained pasta; dough salt unchanged. Ready-grated parmesan, all butter/cheese and salad dressing served.')
    if base.endswith('kai-palo'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=8, unit='st', form='as_sold', label='Hela råa hönsägg med skal, räknade före kokning')
        for step in row['steps']:
            step['text'] = step['text'].replace('hacka koriander grovt', 'väg upp fryst hackad koriander')
            step['text'] = step['text'].replace('tills mycket mört.', 'tills mycket mört och minst 72 °C i mitten.')
            step['text'] = step['text'].replace('Lägg den stekta tofun i grytan.', 'Lägg den stekta tofun i grytan tillsammans med all olja från pannan.')
            if step['text'].startswith('Skala och skiva morot'):
                step['text'] = 'Skala morot och ingefära och väg de råa ätliga mängderna. Dela och skölj pak choi. Koka upp 150 ml vatten med grönsakernas salt och ingefära, lägg i morot och sjud under lock fem minuter. Tillsätt pak choi och sjud ytterligare minst tre minuter tills allt är genomhett och mjukt. Servera med hela grönsaksspadet.'
            step['text'] = step['text'].replace('lite spad och ris', 'hela kryddspadet och ris')
        row['steps'][2:3] = [
            {'text': 'Lägg köttet i kryddspadet och koka upp försiktigt.', 'uses': ['fläskkarré'], 'minutes': 3},
            {'text': 'Sjud under lock på låg värme i 50 minuter.', 'uses': ['fläskkarré'], 'minutes': 50, 'passive': True},
            {'text': 'Rör om och kontrollera vätskan. Tillsätt vid behov 150 ml vatten så att köttet inte kokar torrt.', 'uses': ['fläskkarré'], 'minutes': 1},
            {'text': 'Sjud ytterligare 50 minuter, tills köttet är mycket mört och minst 72 °C i mitten.', 'uses': ['fläskkarré'], 'minutes': 50, 'passive': True},
        ]
        index = next(n for n, step in enumerate(row['steps'], 1) if 'färdigkokta skalade äggen' in step['text'])
        egg_steps = [
            {'text': 'Lägg de räknade hela råa äggen i en separat kastrull med 1000 ml vatten, eller ytterligare 500 ml om det behövs för att täcka. Koka upp försiktigt.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter från uppkok så att både vita och gula blir helt fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll försiktigt bort det heta kokvattnet och kyl äggen med 1000 ml kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt äggen svalna i det kalla vattnet fem minuter så att de går att skala.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen och kassera skalen. Använd samtliga kokta ägg; ingen färdig gramvikt är förutsatt. Kontrollera att både vita och gula är fasta.', 'uses': ['ägg'], 'minutes': 6},
            {'text': 'Lägg ner de nykokta skalade äggen hela i grytan och värm till svag sjudning.', 'uses': ['ägg'], 'minutes': 2},
            {'text': 'Sjud mycket försiktigt i fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Vänd äggen varsamt så att kryddspadet kommer åt runtom.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Vänd äggen försiktigt igen.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Sjud de sista fem minuterna, totalt 15 minuter i kryddspadet.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
        ]
        row['steps'][index - 1:index] = egg_steps
        mark_process(row, index + 4, ['ägg'], 'peel_after_cooking', 'Hela ägg köps som deklarerat antal, kokas och skalas. Skalen serveras inte; ingen styckvikt eller kokt ätlig vikt har antagits.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New explicit dose: eight whole raw shell eggs replace 400 g ready-cooked peeled egg, without a weight equivalence. Count-based source products preserve exact purchase quantities; boiling/peeling has unknown served mass. Ground Five Spice and frozen coriander cook in the retained broth; tofu oil and side liquid are served. Active pot loading, checks, egg cooling/peeling and turning are separately scheduled.')
    candied_doses = {
        'smako-greek-fanouropita': 4,
        'smako-greek-halvas-simigdalenios': 5,
        'smako-greek-portokalopita': 6,
        'smako-italian-budino-riso-toscana': 5,
        'smako-mexican-camotes-poblanos': 4,
        'smako-italian-ricciarelli-siena': 4,
    }
    if base in candied_doses and any(i['name'] == 'apelsinskal' for c in row['components'] for i in c['ingredients']):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'apelsinskal':
                    item.update(name='kanderade apelsinskal', label='Färdigkanderade apelsinskal, mycket finhackade', form='as_sold', quantity=candied_doses[base], unit='g')
                    item.pop('requirements', None)
        for step in row['steps']:
            step['uses'] = ['kanderade apelsinskal' if n == 'apelsinskal' else n for n in step['uses']]
            step['text'] = step['text'].replace('finriv det uppvägda, tvättade apelsinskalet', 'hacka det färdigkanderade apelsinskalet mycket fint')
            step['text'] = step['text'].replace('finrivet apelsinskal', 'mycket finhackat färdigkanderat apelsinskal')
            if base.endswith('portokalopita'):
                step['text'] = step['text'].replace('tillsammans med apelsinskalet', 'tillsammans med mycket finhackat färdigkanderat apelsinskal')
        row['name'] = row['name'].replace('färsk apelsinarom', 'kanderad apelsin') + ' – med kanderat apelsinskal'
        changes.append(f'Visible candied-peel adaptation: {candied_doses[base]} g very finely chopped ready-candied peel replaces raw zest. This is a new culinary dose, not an identity alias, zest yield or sugar equivalence. Other quantities remain unchanged.')
    if base.endswith('fanouropita'):
        row['steps'].append({'text': 'Ta ut den avsvalnade kakan ur formen och dela efter det angivna antalet portioner.', 'uses': [], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('One active minute for unmoulding and portioning after passive cooling.')
    if base.endswith('halvas-simigdalenios'):
        row['steps'][3]['text'] = 'Låt den formade massan svalna 25 minuter.'
        row['steps'][4]['text'] = 'Ställ i kylskåp 60 minuter så att puddingen sätter sig.'
        insert_step(row, 4, {'text': 'Tryck ner hela massan i en liten sköljd silikonform eller portionsskål.', 'uses': ['mannagryn'], 'minutes': 2, 'after': [3]})
        row['steps'][4]['after'] = [4]
        row['steps'].append({'text': 'Stjälp upp den kalla puddingen eller servera direkt ur skålen.', 'uses': ['mannagryn'], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Separate active moulding/unmoulding from the 25-minute cooling and 60-minute refrigeration.')
    if base.endswith('portokalopita'):
        old = row['steps']
        row['steps'] = [
            {'text': 'Sätt ugnen på 100 °C. Riv filodegen i grova remsor och sprid luftigt på en torr plåt.', 'uses': ['filodeg'], 'minutes': 2},
            {**old[0], 'text': 'Torka filoremsorna cirka 18 minuter tills bladen är spröda men inte brynta.'},
            old[1], old[2],
            {'text': 'Klä den lilla formen med bakplåtspapper och häll i hela smeten.', 'uses': ['filodeg', 'ägg'], 'minutes': 2},
            {**old[3], 'text': 'Grädda cirka 28 minuter vid 180 °C tills mitten har stannat, når minst 72 °C och en sticka inte får med sig rå äggsmet.'},
            {'text': 'Stick några hål i kakan och skeda över hela den avsvalnade sirapen.', 'uses': ['apelsinjuice', 'strösocker'], 'minutes': 2},
            {**old[4], 'text': 'Låt kakan svalna 25 minuter.'},
            {**old[5], 'text': 'Kyl ytterligare 60 minuter så att filolagren hinner ta upp sirapen.'},
            {'text': 'Ta ut kakan ur formen och servera hela mängden, inklusive all sirap, fördelad över det angivna antalet portioner.', 'uses': ['filodeg'], 'minutes': 1},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Count active filo tearing, filling the form, syrup application and serving separately from passive oven/cooling time. Explicit egg doneness and all syrup served.')
    if base.endswith('budino-riso-toscana'):
        row['steps'][4]['text'] = 'Låt riskrämen svalna 15 minuter tills den inte längre är het.'
        insert_step(row, 5, {'text': 'Bred ut hela riskrämen i en ren grund skål. Sätt ugnen på 180 °C.', 'uses': ['risottoris'], 'minutes': 1, 'after': [4]})
        row['steps'][5]['after'] = [5]
        row['steps'][-1]['text'] = 'Låt pajen svalna på galler 20 minuter.'
        row['steps'].append({'text': 'Ta den avsvalnade pajen ur formen och servera hela mängden fördelad efter det angivna antalet portioner.', 'uses': [], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Count spreading hot rice cream and unmoulding as active work, preserving the passive cooling times.')
    if base.endswith('camotes-poblanos'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skala och dela sötpotatisen jämnt.', 'Skala sötpotatisen, väg den angivna råa ätliga mängden och dela jämnt.')
        row['steps'][2]['text'] = 'Låt massan svalna 20 minuter tills den går att hantera.'
        insert_step(row, 3, {'text': 'Bred ut hela den heta massan på bakplåtspapper.', 'uses': ['sötpotatis'], 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('liten söt mellanmålsportion', 'söt mellanmålsportion')
        changes.append('Weigh peeled raw sweet potato; separate active spreading from passive cooling. Keep the original explicit refrigerated soft-confection method.')
    if base.endswith('ricciarelli-siena'):
        from admit_expansion_20261101 import prepend_steps
        from app.services.egg_preparation import OPERAND

        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'äggvita':
                    item['requirements'] = sorted(set(vocabulary['äggvita|raw_edible'][1]) | {OPERAND})
        prepend_steps(row, [{'text': 'Knäck rena hönsägg och separera vitan från gulan utan tillsatser. Väg den angivna mängden rå vita utan skal. Inköpets äggutbyte är en populationsuppskattning; komplettera om den vägda mängden är för liten. Oanvänd gula och vita är separata rester. Följ förpackningens hanteringsråd.', 'uses': ['äggvita'], 'minutes': 3, 'after': []}])
        changes.append('Use the existing reviewed egg-separation operand and explicit three active preparation minutes; actual white is weighed, unused yolk is a separate remainder, no exact separation yield is claimed.')
    if base.endswith('isterband-dillpotatis'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala rödbetorna och tärna dem smått.', 'Skala rödbetorna, väg den angivna råa ätliga mängden och tärna smått.')
            if step['text'].startswith('Skala och tärna potatisen.'):
                step['text'] = 'Skala potatisen, väg den angivna råa ätliga mängden och tärna. Koka upp i 1400 ml vatten utan tillsatt salt.'
                step['uses'].remove('salt')
            step['text'] = step['text'].replace('Rör ner resterande salt', 'Rör ner hela den angivna saltmängden')
            if step['text'].startswith('Vänd potatisen och hackad dill'):
                step['text'] = 'Rör ner fryst hackad dill i såsen och sjud under omrörning minst två minuter eller längre enligt förpackningen. Vänd ner potatisen och låt allt bli genomvarmt. Håll på låg värme och rör varsamt så att botten inte bränns.'
                step['minutes'] = 5
            if step['text'].startswith('Skär gurka och äpple'):
                step['text'] = step['text'].replace('Skär gurka och äpple', 'Kärna ur äpplet och väg den ätliga mängden. Skär gurka och äpple')
        row['steps'][-1]['text'] += ' Fördela också allt genomhettat fett från korvpannan över potatisstuvningen.'
        if row['variant_id'] != 'simple':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('avrunna rödbetor', 'rödbetor med hela den sötsyrliga lagen i separata skålar')
            row['steps'][-1]['uses'] += ['ättiksprit 12 procent', 'strösocker']
        changes.append('Salt is retained in the sauce instead of discarded potato water; unchanged dose. Weigh peeled vegetables, cook frozen dill, serve all sausage fat and all sweet-sour beet dressing. No absorption/retention coefficient.')
    if base.endswith('kollyva-veteskal'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('med salt', 'utan tillsatt salt')
        row['steps'][0]['uses'].remove('salt')
        row['steps'][2]['text'] = 'Låt de utbredda kornen svalna 20 minuter och ytan torka.'
        insert_step(row, 3, {'text': 'Häll av överflödigt vatten från de färdigkokta kornen. Bred ut dem i tunt lager på en ren tallrik.', 'uses': ['matvete'], 'minutes': 2, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('kanel, florsocker och nötter', 'kanel, florsocker, hela saltmängden och nötter')
        row['steps'][-1]['uses'].append('salt')
        if row['variant_id'] == 'extended':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Vänd ner granatäppelkärnor', 'Vänd ner helt tinade granatäppelkärnor med all saft')
            prepend_thaw(row, 'granatäppelkärnor', 120, 'Behåll alla kärnor och all saft till veteskålen.')
        changes.append('Keep the declared matvete breakfast adaptation. Salt moves to the retained bowl; two active draining/spreading minutes are explicit. Extended frozen pomegranate is thawed with all juice retained.')
    if base.endswith('panforte'):
        row['name'] = row['name'].replace('Panforte', 'Panforte med färdigkanderat apelsinskal')
        component = row['components'][0]
        component.update(name='Färdigkanderat apelsinskal', ingredients=[{
            'name': 'kanderade apelsinskal', 'form': 'as_sold', 'quantity': 25, 'unit': 'g', 'role': 'flavour', 'label': 'Kanderade hackade apelsinskal'}])
        row['steps'] = row['steps'][2:]
        for step in row['steps']:
            step['uses'] = ['kanderade apelsinskal' if n == 'apelsinskal' else n for n in step['uses'] if n != 'strösocker']
        row['steps'][1]['text'] = 'Värm honungen med 10 ml vatten tills den bubblar. Rör i de färdigkanderade hackade apelsinskalen och därefter nöt-mjölblandningen. Arbeta till en mycket tjock sammanhängande massa; allt ska användas.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        row['steps'].append({'text': 'Servera hela den avsvalnade lilla kakan som en mellanmålsportion.', 'uses': ['kanderade apelsinskal'], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Visible bought-candied-peel version: use 25 g candied peel instead of 12 g raw peel plus 12 g sugar; no peel yield or equivalence is claimed. Remove home candying and use all the new product, honey and 10 ml process water.')
    if base.endswith('bryta-filmjolk'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=285, unit='g')
        row['name'] = row['name'].replace('rårörda lingon', 'kokta sockrade lingon')
        row['steps'][0].update(text='Lägg frysta lingon, allt socker och 20 ml vatten i en liten kastrull. Koka under omrörning minst en minut eller längre enligt förpackningen. Behåll alla bär och all saft.', minutes=5)
        row['steps'][1].update(text='Fördela lingonen tunt i en ren grund skål och låt svalna 20 minuter. Ställ sedan i kylskåp tills helt kalla före servering med filen.', minutes=20)
        for step in row['steps']:
            step['text'] = step['text'].replace('Häll filmjölken', 'Väg filmjölken i gram').replace('de rårörda lingonen', 'de kalla kokta sockrade lingonen')
        changes.append('New culinary dose 285 g filmjölk per portion replaces 280 ml without a density claim. Frozen lingonberries are explicitly boiled with all sugar/juice retained, then cooled; the cooked topping is visibly named.')
    if base.endswith('schiacciata-uva'):
        row['name'] = row['name'].replace('Schiacciata', 'Schiacciata med kärnfria bordsdruvor')
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('Skölj, torka och halvera druvorna.', 'Använd kärnfria bordsdruvor. Plocka av klasstjälkarna, skölj och torka. Väg den angivna ätliga mängden och halvera utan att ta bort skalet; behåll all saft i brödet.')
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace(' Servera yoghurten bredvid.', '')
        row['steps'].append({'text': 'Servera hela den avsvalnade portionen med all fruktsaft från formen.' + (' Servera yoghurten bredvid.' if row['variant_id'] == 'extended' else ''), 'uses': ['vindruvor'] + (['yoghurt naturell'] if row['variant_id'] == 'extended' else []), 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Explicit seedless table-grape adaptation, retaining edible skin/juice. Weigh after removing stems; purchasing uses the separately reviewed 96% population estimate only with estimates enabled. One active serving minute separated from cooling.')
    if base.endswith('enfrijoladas'):
        row['name'] = row['name'].replace('Enfrijoladas', 'Enfrijoladas med färdiga majstortillas')
        component = next(c for c in row['components'] if c['id'] == 'majsbrod')
        component.update(name='Färdiga mjuka majstortillas', ingredients=[{'name': 'majstortillas', 'form': 'as_sold', 'quantity': 400, 'unit': 'g', 'role': 'side', 'label': 'Mjuka majstortillas'}])
        row['steps'] = row['steps'][3:]
        for step in row['steps']:
            step['uses'] = ['majstortillas' if n == 'masa harina' else n for n in step['uses']]
            step['text'] = step['text'].replace('Skiva avokado', 'Använd helt tinade avokadobitar med all saft')
        if row['variant_id'] == 'extended':
            row['steps'][1]['text'] += ' Tillsätt fryst hackad koriander i bönsåsen och låt den koka med hela tiden.'
            row['steps'][1]['uses'].append('koriander')
            row['steps'][2]['text'] = row['steps'][2]['text'].replace('Tärna tomat och rödlök, hacka koriander och blanda', 'Tärna tomat och rödlök och blanda')
            row['steps'][2]['uses'].remove('koriander')
        row['steps'].insert(-1, {'text': 'Värm de färdiga mjuka majstortillorna i torr panna enligt förpackningen tills böjliga och genomvarma. Lägg i ren handduk och använd direkt.', 'uses': ['majstortillas'], 'minutes': 6})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        prepend_thaw(row, 'avokado', 120, 'Använd alla bitar och all saft i avokadotillbehöret.')
        changes.append('Visible ready-made corn-tortilla adaptation: 400 g replaces 280 g masa harina plus 2 g dough salt, with no cooked-yield equivalence. Keep all bean sauce. Frozen avocado is thawed; frozen coriander moves into the boiled sauce.')
    if base.endswith('doi-maach'):
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Skär fisken', 'Använd upptinad benfri fiskfilé, spara all vätska i kylskåp och skär fisken')
        row['steps'][5]['text'] += ' Använd samma panna med allt stekfett kvar. Häll i all upptiningssaft och saft från fiskfatet och koka upp innan yoghurten tillsätts. Eventuell kardemumma och kanel är malda.'
        row['steps'][5]['uses'].append('fisk')
        row['steps'][5]['minutes'] += 2
        if row['variant_id'] == 'extended':
            row['steps'][7]['text'] = 'Dela blomkålen i små buketter och väg upp den frysta hackade gröna jalapeñon. Lägg i en kastrull med 100 ml vatten och sjud under lock åtta minuter. Tillsätt ärtor och fryst hackad koriander och värm ytterligare minst tre minuter, eller längre enligt förpackningen, tills allt är genomhett och grönsakerna mjuka. Servera grönsakerna med all kvarvarande vätska bredvid fisken.'
        row['steps'][-1]['text'] += ' Fördela hela yoghurtsåsen och allt stekfett mellan portionerna.'
        prepend_thaw(row, 'fisk', 720, 'All upptiningssaft kokas med löken före yoghurten.')
        changes.append('Explicit frozen-fish thaw and cooking of all juice; retain frying fat, ground spices and side liquid. Frozen jalapeno/coriander are cooked in the extended side.')
    if base.endswith('pescado-zarandeado'):
        row['steps'][0]['text'] = 'Sätt ugnen på 220 °C. Väg upp mald Ancho Style-chili; ingen stjälk eller kärna ska tas bort och pulvret ska inte blötläggas eller rinna av.'
        row['steps'][1]['text'] = 'Låt ugnen bli helt varm, cirka 15 minuter.'
        row['steps'][1]['uses'] = []
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('den avrunna chilin', 'hela mängden mald chili').replace('samt 50 ml vatten', 'samt 50 ml vatten och all upptiningssaft från fisken')
        row['steps'][2]['uses'].append('fisk')
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Ingen rå fisk har ännu varit i kontakt med pastan.', 'Koka pastan under omrörning hela tiden; upptiningssaften ingår och ska genomhettas.')
        row['steps'][4]['text'] = row['steps'][4]['text'].replace('Kontrollera fiskfilén', 'Kontrollera den helt upptinade benfria fiskfilén')
        if row['variant_id'] == 'extended':
            row['steps'][2]['text'] += ' Tillsätt den frysta hackade koriandern i pastan så att den kokas med hela mängden.'
            row['steps'][2]['uses'].append('koriander')
            row['steps'][7]['text'] = 'Strimla kålen och krama lätt med sin limejuice. Vänd ner de helt tinade avokadobitarna med all avokadosaft. Koriandern ingår i den varma adobopastan.'
            row['steps'][7]['uses'].remove('koriander')
        row['steps'][-1]['text'] += ' Servera också all genomhettad sky och olja från formen samt hela lökdressingen om lök ingår.'
        if row['variant_id'] == 'extended':
            prepend_thaw(row, 'avokado', 120, 'Använd alla bitar och all avokadosaft i kålsalladen.')
        prepend_thaw(row, 'fisk', 720, 'All upptiningssaft kokas i adobopastan före ugnsbakningen.')
        changes.append('Retain the authored edible chili dose as explicitly ground Ancho Style; remove discarded soaking water. Thaw fish, cook all juice and retain oven drippings. Extended avocado is thawed and frozen coriander cooks in the paste.')
    if base.endswith('tacos-de-canasta'):
        row['steps'][0]['text'] = 'Skala potatisen, väg den angivna råa ätliga mängden och dela. Koka upp med 1000 ml vatten utan tillsatt salt. Väg upp den malda Ancho Style-chilin separat till chilioljan.'
        row['steps'][0]['uses'].remove('salt')
        row['steps'][1]['text'] = 'Sjud potatisen cirka 18 minuter tills den är helt mjuk. Häll av potatisen noga. Chilipulvret ska inte blötläggas.'
        row['steps'][1]['uses'] = ['potatis']
        for step in row['steps']:
            if step['text'].startswith('Strimla moroten'):
                step['text'] = step['text'].replace('Strimla moroten tunt och skiva jalapeñon.', 'Skala moroten, väg den ätliga mängden och strimla tunt. Väg upp fryst hackad jalapeño och tillsätt direkt i lagen med all vätska.')
            if step['text'].startswith('Hacka löken'):
                step['text'] = step['text'].replace('resten av saltet', 'hälften av fyllningarnas salt').replace('Mosa potatisen med andra delen.', 'Mosa potatisen med andra delen och återstående hälft av fyllningarnas salt.')
                step['text'] = 'Skölj de kokta bönorna och väg efter avrinning. ' + step['text']
            if step['text'].startswith('Mixa den mjuka anchochilin'):
                step['text'] = step['text'].replace('Mixa den mjuka anchochilin', 'Mixa hela mängden mald Ancho Style-chili')
            if step['text'].startswith('Finhacka tomat och koriander'):
                step['text'] = 'Tärna tomaten. Koka hälften av tomaten med den frysta hackade koriandern under omrörning minst tre minuter eller längre enligt förpackningen. Vänd med resten av tomaten, salsans limejuice och salt. Behåll all saft; detta är en ljummen tomatsalsa.'
                step['minutes'] = 9
        row['steps'][-1]['text'] += ' Skrapa ur all kvarvarande chiliolja från bakpapperet och fördela över tacosen.'
        changes.append('Ground ancho needs no soaking or discard. Salt is added after potato draining, with original dose preserved. Frozen jalapeno cooks in the served pickle liquid; coriander cooks in a visibly warm salsa. All chili oil is served.')
    if base.endswith('chilorio'):
        row['steps'][2].update(text='Väg upp mald Ancho Style-chili. Mixa hela mängden med vitlök, vinäger, oregano och 100 ml vatten till en tjock pasta.' + (' Tillsätt också spiskummin.' if row['variant_id'] != 'simple' else ''), minutes=5, passive=False)
        row['steps'][2]['uses'] = ['anchochili', 'vitlök', 'äppelcidervinäger', 'oregano'] + (['spiskummin'] if row['variant_id'] != 'simple' else [])
        row['steps'][3].update(text='Lyft köttet till ett fat och dra isär det med två gafflar. Behåll allt kokspad, fett och eventuell lök i grytan. Koka utan lock och rör regelbundet cirka 30 minuter tills spadet reducerats till en tjock bottensky; inget spad ska hällas bort. Tiden kan bli längre i en smal gryta.', minutes=35, passive=False, uses=['fläskkarré'] + (['gul lök', 'apelsinjuice'] if row['variant_id'] != 'simple' else []))
        row['steps'][4]['text'] = 'Häll rapsoljan i den breda grytan med den reducerade skyn. Lägg tillbaka allt kött och eventuell saft från fatet. Stek under omrörning tills kanterna får lite färg och rör sedan ner hela chilipastan.'
        row['steps'][5]['text'] = 'Stek och rör på medelvärme tills chilipastan klär köttet och rätten är ganska torr, cirka tio minuter. Om den fastnar, tillsätt 50 ml vatten och låt koka in. Servera hela mängden inklusive allt fett.'
        if row['variant_id'] == 'extended':
            row['steps'][6]['text'] = 'Väg de redan kokta svarta bönorna efter avrinning. Värm med fryst hackad koriander och 30 ml vatten i en liten kastrull minst tre minuter eller längre enligt förpackningen. Koka in allt fritt vatten. Skiva de ansade rädisorna och vänd med bönorna och limejuicen.'
            row['steps'][6]['minutes'] = 9
        changes.append('Ground ancho replaces whole-chili hydration at the same authored edible dose. All pork broth/fat is reduced and served, adding explicit 35 active minutes for pulling/reduction. Frozen coriander and bean liquid are cooked into the side.')
    if base.endswith('spaghetti-aglio-olio'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'pasta':
                    item['requirements'] = ['pack:spaghetti']
                if item['name'] == 'salt' and component['id'] == 'c1':
                    item['quantity'] = 3
        for step in row['steps']:
            if 'med pastakomponentens salt' in step['text']:
                step['text'] = step['text'].replace('med pastakomponentens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            if step['text'].startswith('Häll försiktigt 100 ml'):
                step['text'] = step['text'].replace('Lägg i pastan', 'Rör ner pastakomponentens salt. Lägg i spaghettin')
                step['uses'].append('salt')
                step['text'] += ' Servera all sås och hela tillbehörens dressing om tillbehör ingår.'
        changes.append('Require spaghetti. Replace the proposed 8 g salt in discarded cooking water with a new culinary dose of 3 g in the retained sauce; no salt-absorption coefficient is invented.')
    if base.endswith('horiatiki'):
        row['steps'][0]['text'] += ' Låt oliverna rinna av och väg utan fri lag; även kapris vägs efter avrinning om den ingår.' if row['variant_id'] == 'extended' else ' Låt oliverna rinna av och väg utan fri lag.'
        row['steps'][0]['uses'].append('oliver')
        changes.append('Explicit drained olive weight; all salad dressing is served.')
    if base.endswith('gnocchi-di-susine'):
        row['steps'][0]['text'] = 'Skala potatisen, väg den angivna ätliga råa mängden och skär jämnt. Koka upp i 500 ml vatten utan tillsatt salt.'
        row['steps'][2]['text'] = 'Låt den pressade potatisen ånga av och svalna 15 minuter; en blöt massa behöver längre avångning, inte obegränsat extra mjöl.'
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Dela plommonköttet', 'Kärna ur plommonen, väg den ätliga mängden och dela plommonköttet')
        insert_step(row, 3, {'text': 'Pressa den avrunna potatisen och bred ut tunt på ett fat.', 'uses': ['potatis'], 'minutes': 2, 'after': [2]})
        row['steps'][3]['after'] = [3]
        changes.append('Weigh peeled raw potato and pitted plum; separate two active pressing minutes from fifteen passive cooling minutes.')
    if base.endswith('semla'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Vispa den kalla grädden', 'Vispa den kalla vispgrädden')
        changes.append('Explicit whipping cream, already restricted to reviewed Vispgrädde products by the unchanged intake requirement.')
    if base.endswith('chana-madra'):
        row['steps'][2]['text'] += ' Använd malda kryddor, inklusive malen kardemumma och eventuell malen nejlika; inga hela kapslar eller kryddor ska plockas bort.'
        changes.append('Explicit ground spices retained in the sauce; no assumed extraction from removed pods.')
    if base.endswith('khichu'):
        row['name'] = row['name'].replace('kumminhetta', 'spiskumminhetta')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Hacka chilin fint.', 'Väg upp fryst hackad grön jalapeño och tillsätt direkt utan att tina eller hälla bort vätska.')
        if row['variant_id'] == 'extended':
            for c in row['components']:
                for item in c['ingredients']:
                    if item['name'] == 'jordnötter':
                        item['name'] = 'rostade jordnötter'
            for step in row['steps']:
                step['uses'] = ['rostade jordnötter' if n == 'jordnötter' else n for n in step['uses']]
                step['text'] = step['text'].replace('Hacka jordnötterna', 'Hacka de rostade osaltade jordnötterna')
        changes.append('Use reviewed frozen chopped green jalapeno in the boiled dough; roasted unsalted peanuts explicitly retain the reviewed form.')
    if base.endswith('stompa'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=47, unit='g')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Rör i filmjölken', 'Väg filmjölken i gram och rör i den')
        changes.append('New culinary gram recipe: 47 g filmjölk per portion replaces the proposed 45 ml. This is a new dose, not a density conversion or a claim of equal amounts.')
    row['version'] = '1.0.1'
    row['notes'] = row.get('notes', '') + ' Innehållsgranskad 2026-11-01 med angiven produktform och mängdenhet; inte provlagad. Mängdändringar redovisas i granskningsrapporten.'
    return changes


def amount_changes(before, after):
    def rows(recipe):
        return {(c['id'], i['name'], i['form']): (i['quantity'], i.get('unit')) for c in recipe['components'] for i in c['ingredients']}
    old, new = rows(before), rows(after)
    return [{'component': k[0], 'ingredient': k[1], 'form': k[2], 'before': old.get(k), 'after': new.get(k)}
            for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)]


def build(stage):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f'standardized-stage{stage}.json'
    if (REPORT / f'import-stage{stage}.json').exists():
        raise ValueError('Stage is already issued and immutable; create a new stage/version instead')
    vocabulary = library_vocabulary(current_recipes())
    authors, native, records = [], [], []
    for path in sorted(SOURCE.glob('*/source/paket/*.json')):
        doc = json.loads(path.read_bytes())
        for original in doc['recipes']:
            if original['base_id'] not in STAGES[stage]:
                continue
            selected = SELECTED_VARIANTS.get(stage, {}).get(original['base_id'])
            if selected is not None and original['variant_id'] not in selected:
                continue
            row = copy.deepcopy(original)
            changes = correct(row, vocabulary)
            pack, _ = standardize({**doc, 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-01')
            authors.append(row)
            native.extend(pack['recipes'])
            records.append({'source_id': ':'.join(original[k] for k in ('base_id', 'version', 'variant_id')),
                'source_file': path.relative_to(SOURCE).as_posix(), 'source_sha256': sha(path.read_bytes()),
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'content_review': STAGES[stage][row['base_id']], 'changes': changes,
                'amount_changes': amount_changes(original, row), 'cooking_test': 'not_cooked'})
    assert {r['base_id'] for r in authors} == STAGES[stage].keys()
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': native})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    check_process_water(checked['recipes'])
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    target.write_bytes(raw)
    (OUTPUT / f'authoring-stage{stage}.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1', 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': authors}))
    (REPORT / f'recipe-review-stage{stage}.json').write_bytes(encoded({'reviewed_bases': len(STAGES[stage]), 'reviewed_variants': len(records), 'pack_sha256': sha(raw), 'recipes': records}))
    print({'stage': stage, 'bases': len(STAGES[stage]), 'variants': len(records), 'pack': str(target)})


def admit(stage, qualification=None):
    target = OUTPUT / f'standardized-stage{stage}.json'
    raw = target.read_bytes()
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    expected = {identity(r) for r in checked['recipes']}
    review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
    assert review['pack_sha256'] == sha(raw)
    assert {r['runtime_id']: r['content_sha256'] for r in review['recipes']} == {
        identity(r): r.design.content_sha256 for r in checked['recipes']}
    if qualification:
        probe = json.loads(qualification.read_bytes())
        results = probe['modes']['estimated']['recipes']
        assert probe['pack_sha256'] == sha(raw) and not probe['input_only']
        assert len(results) == len(expected) and {r['id'] for r in results} == expected
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in results)
        imported = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        assert imported['pack_sha256'] == sha(raw)
        imported.update(qualification_sha256=sha(qualification.read_bytes()), basket_status='verified_estimated')
        (REPORT / f'import-stage{stage}.json').write_bytes(encoded(imported))
        (REPORT / f'qualification-stage{stage}.json').write_bytes(qualification.read_bytes())
        print({'stage': stage, 'qualified': len(expected)})
        return
    diff = pack_diff(checked)
    assert {r['status'] for r in diff} <= {'unchanged', 'new_recipe', 'new_variant'}, diff
    pending = {r['id'] for r in diff if r['status'] in {'new_recipe', 'new_variant'}}
    if not pending:
        print({'stage': stage, 'already_imported': True})
        return
    assert pending == expected, 'The reviewed stage must be imported atomically'
    before = (ROOT / 'library-manifest.json').read_bytes()
    result = import_pack(target, accepted_ids=pending)
    after = (ROOT / 'library-manifest.json').read_bytes()
    assert import_pack(target, accepted_ids=pending)['published_file'] == result['published_file']
    assert (ROOT / 'library-manifest.json').read_bytes() == after
    (REPORT / f'import-stage{stage}.json').write_bytes(encoded({'before_manifest_sha256': sha(before), 'after_manifest_sha256': sha(after),
        'pack_sha256': sha(raw), 'basket_status': 'pending_local_qualification', 'idempotent_reimport': True, 'result': result}))
    print({'stage': stage, 'imported': len(pending)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, choices=STAGES, required=True)
    parser.add_argument('--qualifying-report', type=Path)
    parser.add_argument('--import-reviewed', action='store_true')
    args = parser.parse_args()
    if args.qualifying_report:
        admit(args.stage, args.qualifying_report)
    elif args.import_reviewed:
        admit(args.stage)
    else:
        build(args.stage)
