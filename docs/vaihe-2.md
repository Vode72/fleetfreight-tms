# Vaihe 2: tietomalli

Tila: **käynnissä** (2A, tietomalli v1, 2B-1, 2B-2 ja 2B-3a valmiit; seuraavaksi 2B-3b) · Päivitetty 21.11.2026

Tavoite: koko tietomalli v1 (`suunnitelma.md` luku 3) Alembic-revisioina, tilakoneet testeineen ja
yhdistetty demodata, jonka päälle vaiheen 4 läpimenevä polku rakennetaan. Taulut luodaan luvun 3
järjestyksessä, ja viittaus osoittaa aina aiemmin luotuun tauluun. Vaiheessa ei vielä tehdä näkymiä
eikä Plan Check -sääntöjä (vaiheet 4 ja 5).

## Yhteiset käytännöt

| Asia | Käytäntö |
|---|---|
| Skeema | Jokainen muutos uutena Alembic-revisiona; valmiita revisioita ei muokata (sääntö 2) |
| Sallitut arvot | `VARCHAR` + `CHECK`, arvot domain-moduulin enumista; synkronointitesti pitää enumin ja kannan samana |
| Voimassaolot | `DATE`, molemmat päät mukaan lukien; jokainen jakso omana rivinään, ei päällekkäisiä jaksoja (D67) |
| Raha | `*_cents` ja `*_e4` (D28) |
| Demodata | `scripts/seed_demo_data.py`, idempotentti, vain kehityskäynnistyksellä, ei migraatioissa (säännöt 2 ja 5, D68) |
| Domain | puhtaat moduulit `backend/domain/`-kansiossa, ei FastAPI- eikä tietokantariippuvuutta (sääntö 6) |

## Alavaiheet

Jokainen on oma haaransa ja PR:nsä. ff-reviewer katselmoi jokaisen, eikä mitään yhdistetä automaattisesti.

### 2A Käyttäjän asetukset (D49) · valmis, PR #13
- Teema ja kieli `users`-tauluun uudella revisiolla, tallennus-endpoint, `/auth/me` palauttaa valinnat
- Selain muistaa valinnan välimuistina kirjautumissivua varten

### Tietomalli v1 · valmis, PR #14
- Luvun 3 tietomalli hyväksytty 17.11.2026 (D52–D61), täydennetty 18.11.2026 (D62–D69, ylempi paikka)

### 2B-1 Osapuolet ja paikat · valmis, PR #15
- Taulut: `customers` (asiakas / oma yritys, lavanvaihto sovittu D59), `locations` (tyypit, ylempi paikka,
  postinumero ja kaupunki D68, aikavyöhyke, aukioloajat), `carriers`, `drivers`, kuljettajien pätevyydet voimassaolojaksoina (D67)
- Demodata: oma yritys, terminaaliverkosto (D31–D33), satamat (D62), junaterminaalit (D63), tullitoimipaikat (D48),
  asiakkaat toimipaikkoineen, kuljetusliikkeet, kuljettajat ja pätevyydet
- GDP-koulutuksen oletusvoimassaolo asetuksena (D69)

### 2B-2 Kalusto · valmis, PR #17 ja #18
- `trucks` (vetäjä / kuorma-auto), `dollies` (D61), `load_units` (traileri, kiinteä kori; D60), `compartments`, `reefer_units` ja `reefer_evaporators` (D47, D76)
- Kaluston kelpoisuudet omassa taulussaan (`equipment_qualifications`, D70) voimassaolojaksoina (D67)
- Arkistointi (D72): `archived_at` rekistereihin (myös 2B-1:n taulut) ja `driver_qualifications` CASCADE → RESTRICT, uutena revisiona; samassa revisiossa oman kuljetusliikkeen linkki oman yrityksen asiakasriviin (D73)
- Demodata: kalusto kuljetusliikkeittäin, thermo-kuormatilat lohkoineen, junakelpoiset kuormatilat (D63), HCT-yhdistelmä dollyineen
- **Valmis kun:** kuormatila voidaan kuvata trailerina tai kiinteänä korina, ja kelpoisuuksien historia säilyy

### 2B-3 Asetustaulut (laajennettu D84) · tulossa

Neljä PR:ää järjestyksessä a → b → c → d, kukin oma revisionsa, demodatansa ja testinsä. Demomaat: FI, SE, EE, LV, LT, PL, DE, NL, BE, DK, FR, ES ja IT.
**Säädösten ja viranomaisten raja-arvot** (painot, mitat, nopeudet, ajokiellot, pyhät, tiemaksut) haetaan virallisista lähteistä ennen kirjausta, ja jokaisella rivillä on lähdelinkki ja tarkistuspäivä. Mitään ei kirjoiteta muistista. Plan Check -tarkistukset tehdään vaiheessa 5.

#### 2B-3a Maat ja rajoitukset · osa 1 tehty (rakenne ja ajokiellot), osa 2a tehty (vetoauto, maiden yleissäännöt), osa 2b-1 tehty (Espanja, DGT), osa 2b-2 tehty (Baskimaa, Katalonia), osa 2b-3 tehty (tiemaksut), osa 2c tehty (painot, pituudet, HCT ja ADR-tunnelit; D89) · valmis
- **Osa 1, PR (2B-3a-1):** taulut `countries`, `country_rules`, `public_holidays`, `road_restrictions`, `road_restriction_windows` (revisio 2cb43f9f78c1), `domain/restrictions.py`, viitedatan lataaja `scripts.seed_reference_data` (JSON-tiedostot `backend/reference_data/`, ajetaan myös tuotannossa). Data: 13 maata; pyhät 2026–2027 DE (§ 30(4) StVO), FR (L3133-1) ja PL (asetuksen luettelo); ajokiellot DE (sunnuntai ja pyhät, kesälauantait FerReiseV), FR (viikonloppu ja pyhät, 2026 lisälauantait, Auvergne-Rhône-Alpes talvi), PL (pyhät, pyhien aatot 2026–2027, kesä 2026, yli 12 t) ja IT (vuoden 2026 kalenteri, 79 päivää)
- `public_holidays` sisältää ne pyhät, joihin maan liikennesäännöt viittaavat (esim. Saksassa vain § 30(4) StVO:n luettelo), ei kaikkia yleisiä vapaapäiviä
- **Osa 2a, PR (2B-3a-2):** kenttä `road_restrictions.solo_tractor` (D85: exempt, conditional, not_exempt; vain ajokielloille; revisio 9bb6eb8d032e): DE vapautettu, PL ei, IT ehdollinen, FR ei kirjattu. `country_rules` 13 maalle: kuorma-auton nopeusrajoitukset ajoneuvoluokkineen (D87: painoraja ja peruste ajoneuvo/yhdistelmä; revisio 47da3484520e; Your Europe, tarkistettu 19.11.2026; Suomi Finlexistä, VNa 1257/1992 3 § muutettuna 1310/2018: 80/80, Your Europen 60 km/h yli 7,5 t ei perustu säädökseen), raskaan kaluston talvirengaskausi Ruotsille (Transportstyrelsen 10.11.–10.4.; henkilöautosivujen kausia ei kirjata kausikenttiin, koska ne eivät kerro koskevatko raskasta kalustoa), lähetetyn työntekijän ilmoitus IMI-portaaliin (koskee kabotaasia ja cross-tradea, ei kahdenvälistä kuljetusta, kauttakulkua eikä omaa maata) ja kabotaasi (3 kuljetusta 7 päivässä, 4 päivän tauko). Maissa, joissa raja riippuu painosta, kirjataan yhdistelmän (yli 7,5 t tai yli 12 t) arvo ja muut arvot huomautukseen. Arvot, joille virallista lähdettä ei ole tarkistettu, jäävät tyhjiksi (NULL = ei kirjattu): painot, pituudet, HCT ja tiemaksujärjestelmä kaikille maille sekä Alankomaiden nopeudet. Siksi `toll_system` saa olla tyhjä (revisio c3888037643f). Lataaja täydentää myöhemmin tyhjät arvot, mutta ei koskaan korvaa kirjattuja.
- **Osa 2b-1, PR (2B-3a-3):** Espanjan tieosuuskohtaiset ajokiellot DGT:n päätöksestä BOE-A-2026-1255, liite II (DGT:n PDF, tarkistettu 20.11.2026): 557 riviä → 125 rajoitusta (tieosuus ja suunta) ja 594 aikaikkunaa, yli 7 500 kg ajoneuvo tai yhdistelmä. Toistuvat jaksot viikonpäiväikkunoina kausineen (jatkuvat vuoden 2027 päätöksen voimaantuloon asti), päiväkohtaiset kiellot päivämääräikkunoina. Toistuvien jaksojen pyhät BOE-A-2025-21667:n mukaan (15.8. kaikkialla, 28.7. Kantabriassa A-8:lla). Valencian moottoripyörä-GP:n päivät siirretty 27.–29.11. (BOE-A-2026-13892). Vapautukset B.1.2 ja N-230:n perjantaipoikkeus huomautuksessa. Ei koske Kataloniaa eikä Baskimaata (omat viranomaiset ja päätökset). Rivit on poimittu PDF:n taulukoista ohjelmallisesti, ja jokaisen rivin tie, PK-arvot, kellonajat ja otsikon viikonpäivät tarkistetaan; testit tekevät pistokokeita lähteeseen.
- **Osa 2b-2, PR (2B-3a-4):** Baskimaan ajokiellot päätöksestä BOE-A-2026-2625, liite II (tarkistettu 20.11.2026): 30 rajoitusta (alue ES-PV) ja 407 päivämääräikkunaa, yli 7 500 kg. Kesäjakso 6.6.–6.9.2026 puretaan päiviksi (koko alueen pyhät 25.7. ja 15.8. BOE-A-2025-21667:n mukaan). Rajat ylittävän liikenteen ryhmä (AP-8, N-I, A-15, AP-1 ja muut Irunin suunnan tiet; aattona klo 22 – päivänä klo 22) on omina rajoituksinaan, koska se koskee vain rajat ylittäviä kuljetuksia. Voimaan 17.2.2026 (kahdeksas arkipäivä julkaisusta 5.2.).
- **Osa 2b-2 jatkuu, Katalonia:** päätös ISP/300/2026 (BOE-A-2026-6095) ja muutos ISP/1933/2026 (BOE-A-2026-16758; liitteen A alaviitteet muutetussa muodossa, alkuperäisiä ei tarkistettu), alue ES-CT, voimaan 19.2.2026: 35 rajoitusta ja 196 aikaikkunaa (ennen voimaantuloa olevia päiviä ei kirjata). Liite A (kierretty taulukko, luettu sanojen sijainneista): 21 verkko-osuutta M 10–14, T 17–22, D 10–22; A-2:n suuntamerkinnät (L, B) ja alaviitteiden osuudet (AP-7 PK 84–149, 84,5–210, 265–344; C-35 PK 28–32) omina rajoituksinaan; matriisin C-32-sarake molemmille C-32-osuuksille. Kesä- ja talvijaksojen pyhät Katalonian kalenterista (24.6., 15.8., 11.9.; 6.1., 8.12., 25.12., 26.12.). Kohta 7 (Aranin tiet: N-230 suunnittain, C-28 molempiin suuntiin, koska päätös ei kerro sen ajorataa), kohta 8 (yli 26 t pysyvä kielto N-II La Jonquera–Fornells, N-240, N-340 kahdella osuudella) ja kohta 9 (C-153 Olot). ATP-pilaantuvat vapautettu Kataloniassa vain liitteen B 3 b reiteillä; euromodulaariyhdistelmien rajoitukset ja kauttakulun moottoritiepakko vain huomautuksessa.
- **Kelirikko ja siltojen painorajat (Tonin päätös 21.11.2026):** ei käsin syötettyjä rivejä; haetaan myöhemmin integraationa Väyläviraston ja Fintrafficin rajapinnoista (Digiroad, Digitraffic).
- **Osa 2b-3, PR (2B-3a-5):** tiemaksujärjestelmä kaikille 13 maalle virallisista lähteistä (tarkistettu 20.11.2026; lähde maan rivin huomautuksessa): ei maksuja FI; aikaperusteinen SE, EE, LV ja LT (vinjetit 31.12.2026 asti); matkaperusteinen PL, DE, BE, DK (1.1.2025 alkaen), FR, ES, IT, NL (1.7.2026 alkaen) ja LT (1.1.2027 alkaen, Via Toll). Muutos kesken jakson on uusi rivi (D67): NL 1.1.–30.6.2026 ja 1.7.2026–, LT 2026 ja 2027–. Lataaja sulkee avoimen jakson, kun tiedosto antaa sille päättymispäivän.
- **Osa 2c, PR (2B-3a-6, D89):** `country_rules`: puoliperävaunuyhdistelmän (5 akselia) paino ja pituus kotimaan liikenteessä ja `hct_allowed`-lippu 13 maalle kansallisista säädösteksteistä (tarkistettu 21.11.2026; lähde ja muut akselimäärät sekä täysperävaunuyhdistelmä maan rivin huomautuksessa). Paino: FI 44 t, LV, LT, PL ja DE 40 t, NL 50 t (yläraja, myös vetoakseli- ja moottoritehoehto), BE, FR, ES ja IT 44 t; ei kirjattu SE (paino bruttopainotaulukosta kantavuusluokan ja akselivälin mukaan), EE (akselikohtaista lukua ei tarkistettu) ja DK (puoliperävaunuyhdistelmään sovelletaan yhdistelmien painoja, 5 akselia 47 t tai 44 t; tulkinta vahvistamatta). Pituus: 16,50 m, paitsi FI 23,00 m, SE 24,0 m ja DK 17,88 m. EU:n kansainvälinen raja (40 t, 16,50 m) kerran: `domain/eu_limits.py` (SWD(2023) 445) ja `strictest()`. HCT sallittu FI, SE, DE, NL, BE (vain Flanderi), DK ja ES; muut NULL. HCT-verkot `road_restrictions`-riveinä (tyyppi `hct_route`, rajat huomautuksessa): SE (34,5 m nimetyillä teillä, BK4 74 t), DE (Lang-Lkw Positivnetz), NL (LZV), BE-VLG (LZV), DK (modulvogntog, BEK 1491/2025) ja ES (euromodulaarinen). Suomessa 34,5 m ja 76 t ovat yleisen tieverkon rajoja, joten verkkoriviä ei ole. ADR-tunneliesimerkit Alankomaista Staatscourantista: Heinenoordtunnel A29 (C), Beneluxtunnel (C), Stadsbaantunnel Utrecht (E). Italian teksti luettu toisen käden julkaisusta (virallinen Normattiva), Belgian painot alueellisia (Flanderi uudistamassa).
- **Valmis kun:** demomaiden yleissäännöt, pyhät, keskeiset ajokiellot ja puoliperävaunuyhdistelmän painorajat (D89) ovat kannassa lähteineen; arvo, jolle virallista lähdettä ei tarkistettu, on NULL ja syy maan rivin huomautuksessa ✓

#### 2B-3b Paikat
- Turvaparkit: `parking_details` paikoille (tyyppi parking): sertifiointitaso alan yleisten standardien mukaan, paikkamäärä, varauspakko, yöhinta `*_cents`, sähkö thermotrailerille, palvelut, aukiolo
- Rajanylityspaikat: uusi paikkatyyppi *border_crossing* ja lisätiedot: maat, EU:n ulkoraja, linkki tullitoimipaikkaan (D48), aukioloajat, raskas liikenne sallittu, tila (auki / kiinni), arvioitu odotusaika
- Lastaus- ja purkupaikan ominaisuudet: laituri / maataso, sivulastaus, trukki, perälautavaatimus, ajoneuvon enimmäispituus (HCT), ajanvarauspakko (D82)
- Satamien säilytysasetukset (D83): ilmaiset päivät (oletus 3) ja päivämaksu `*_cents`; demossa keksityt summat
- Pesupaikat ja pesutodistus (European Cleaning Document) elintarvike- ja kemikaalikuljetuksiin (D56)
- **Valmis kun:** demon turvaparkit, rajanylitykset ja satamat asetuksineen ovat kannassa

#### 2B-3c Linjat ja reititys
- `line_operators`, `line_routes`, `line_departures` (lautta ja juna, D62, D63) ja aluskohtaiset ADR-rajoitukset (kaikki alukset eivät ota kaikkia luokkia)
- `routing_preferences` (D64), `ltl_linehauls`, `customs_areas` (D48), `adr_rules`-rakenne (sisältö lähteistä ennen vaihetta 5, luku 3C)
- Demodata: lauttayhteydet D62:n mukaan molempiin suuntiin, junayhteys Rostock ja Travemünde ↔ Verona, reititysehdotukset D64:n mukaan
- **Valmis kun:** demon linjavuorot ja reititysehdotukset ovat kannassa, ja versioidut taulut tukevat voimassaoloa

#### 2B-3d Kustannusasetukset (rakenne; laskenta vaiheessa 6)
- Tiemaksut maittain akselimäärän, päästöluokan ja CO2-luokan mukaan; kalustoon päästö- ja CO2-luokka uudella revisiolla
- Polttoainelisän indeksi, valuutat ja kurssit (SEK, PLN, DKK, NOK), `pallet_types`
- **Valmis kun:** tiemaksun, polttoainelisän ja valuuttamuunnoksen lähtötiedot ovat kannassa

### 2C Kuorma ja keikka · tulossa
- Kuorma: `orders` (tyypit D54, kuormatyyppi D37, tavaralaji D56, Earliest/Latest ja aikatyyppi noudolle ja toimitukselle D80: `domain/time_types.py` valmis), `order_lines`, `dangerous_goods`, `temperature_requirements`
- Keikka: `jobs`, `round_trips` (D86), `trips`, `nodes`, `legs` ja `leg_trips` (D55), `order_nodes`, `line_bookings`, `handling_events`, `deviations`, `seals`
- Resurssit ja ajoaika: `duty_events`, `resource_reservations`, `trailer_positions`
- Kylmä, tulli ja dokumentit: `sensors`, `trip_compartment_settings`, `temperature_readings`, `temperature_alarms`,
  `customs_declarations`, `customs_items` (D58), `customs_events`, `documents`
- Kulut ja lavasaldot: `service_codes`, `costs`, `cost_allocations`, `invoices`, `invoice_lines`, `pallet_ledger` (D59)
- Toteumatauluissa vain lisäys, `source` ja `reversal_of_id` (sääntö 9)
- Poikkeusluvat (D85): `exemption_permits` (maa, rajoitus tai rajoitustyyppi, ajoneuvo tai trippi, lupanumero, voimassaolojakso D67, liitedokumentti)
- Noden aikaikkuna = varattu aika ja ajanvarausnumero (D82)
- **Avoimet ennen 2C:tä (ff-logistiikka 19.11.2026, D80):** orderin ajan muutoshistoria täsmällisyys-KPI:tä varten; aukioloajat viikonpäivittäin ja poikkeuspäivät `locations`-tauluun; jaetussa orderissa (D22) ajat molempiin osiin
- **Valmis kun:** D65:n skenaario (Jyväskylä–Vantaa–Lübeck) voidaan kirjata kantaan riveinä, ja liput täsmäävät alirivien kanssa

### Tilakoneet (R3, D50, D53) · tulossa
- Order-, Trip- ja Job-ketjut puhtaina domain-moduuleina; Trip alkaa tilasta Luonnos (D53)
- Peruttu kaikissa ketjuissa D50:n ehdoin; kielletty siirtymä palauttaa 409:n
- **Valmis kun:** jokainen sallittu ja kielletty siirtymä on testattu

### Tilatokenit (D51) · tulossa
- Tilat väriryhmiksi CSS-muuttujina molempiin teemoihin, Trip Luonnos ryhmään Avoin (D53)
- Teeman esikatselu väriryhmien mukaan

### Demodata · jatkuu alavaiheittain
- Molempien projektien demodata yhdistettynä, "Demo"-säännöt (sääntö 5, D68), FleetFlow'n ristiriitainen JOB-001-data korjattuna

## Järjestys

2A → tietomalli v1 → 2B-1 → 2B-2 → 2B-3a → 2B-3b → 2B-3c → 2B-3d → 2C. Tilakoneet voidaan tehdä 2C:n rinnalla, tilatokenit milloin tahansa.

## Vaiheen 2 valmis-kriteerit
- `alembic upgrade head` tyhjään kantaan luo kaikki luvun 3 taulut, ja CI on vihreä
- Tilakoneet ja domain-enumien synkronointitestit menevät läpi
- Demodata siemennetään idempotentisti, ja D65:n skenaarion lähtötiedot ovat olemassa
- ff-auditor tarkistaa koko tietomallin ennen vaihetta 3
