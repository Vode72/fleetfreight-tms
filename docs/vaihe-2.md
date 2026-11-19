# Vaihe 2: tietomalli

Tila: **käynnissä** (2A, tietomalli v1 ja 2B-1 valmiit; seuraavaksi 2B-2) · Päivitetty 18.11.2026

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

### 2B-2 Kalusto · tulossa
- `trucks` (vetäjä / kuorma-auto), `dollies` (D61), `load_units` (traileri, kiinteä kori; D60), `compartments`, `reefer_units` ja `reefer_evaporators` (D47, D76)
- Kaluston kelpoisuudet omassa taulussaan (`equipment_qualifications`, D70) voimassaolojaksoina (D67)
- Arkistointi (D72): `archived_at` rekistereihin (myös 2B-1:n taulut) ja `driver_qualifications` CASCADE → RESTRICT, uutena revisiona; samassa revisiossa oman kuljetusliikkeen linkki oman yrityksen asiakasriviin (D73)
- Demodata: kalusto kuljetusliikkeittäin, thermo-kuormatilat lohkoineen, junakelpoiset kuormatilat (D63), HCT-yhdistelmä dollyineen
- **Valmis kun:** kuormatila voidaan kuvata trailerina tai kiinteänä korina, ja kelpoisuuksien historia säilyy

### 2B-3 Asetustaulut · tulossa
- `customs_areas` (D48), `adr_rules`-rakenne (sisältö tarkistetaan lähteistä ennen vaihetta 5, luku 3C), `pallet_types`,
  `road_restrictions`, `ltl_linehauls`, `line_operators`, `line_routes`, `line_departures` (lautta ja juna, D62, D63),
  `routing_preferences` (D64)
- Satamien säilytysasetukset (D83): ilmaiset päivät (oletus 3) ja päivämaksu `*_cents` satamakohtaisesti uudella revisiolla; demossa keksityt summat
- Demodata: lauttayhteydet D62:n mukaan molempiin suuntiin, junayhteys Rostock ja Travemünde ↔ Verona, reititysehdotukset D64:n mukaan
- **Valmis kun:** demon linjavuorot ja reititysehdotukset ovat kannassa, ja versioidut taulut tukevat voimassaoloa

### 2C Kuorma ja keikka · tulossa
- Kuorma: `orders` (tyypit D54, kuormatyyppi D37, tavaralaji D56, Earliest/Latest ja aikatyyppi noudolle ja toimitukselle D80: `domain/time_types.py` valmis), `order_lines`, `dangerous_goods`, `temperature_requirements`
- Keikka: `jobs`, `trips`, `nodes`, `legs` ja `leg_trips` (D55), `order_nodes`, `line_bookings`, `handling_events`, `deviations`, `seals`
- Resurssit ja ajoaika: `duty_events`, `resource_reservations`, `trailer_positions`
- Kylmä, tulli ja dokumentit: `sensors`, `trip_compartment_settings`, `temperature_readings`, `temperature_alarms`,
  `customs_declarations`, `customs_items` (D58), `customs_events`, `documents`
- Kulut ja lavasaldot: `service_codes`, `costs`, `cost_allocations`, `invoices`, `invoice_lines`, `pallet_ledger` (D59)
- Toteumatauluissa vain lisäys, `source` ja `reversal_of_id` (sääntö 9)
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

2A → tietomalli v1 → 2B-1 → 2B-2 → 2B-3 → 2C. Tilakoneet voidaan tehdä 2C:n rinnalla, tilatokenit milloin tahansa.

## Vaiheen 2 valmis-kriteerit
- `alembic upgrade head` tyhjään kantaan luo kaikki luvun 3 taulut, ja CI on vihreä
- Tilakoneet ja domain-enumien synkronointitestit menevät läpi
- Demodata siemennetään idempotentisti, ja D65:n skenaarion lähtötiedot ovat olemassa
- ff-auditor tarkistaa koko tietomallin ennen vaihetta 3
