# Siirtoinventaario: Freight Planner + FleetFlow → uusi TMS

> **Historiallinen analyysi 14.11.2026.** Osa käsitteistä (esim. `order_legs`, `stops`, `movements`) ja agenttinimistä on korvattu. Voimassa olevat päätökset: [suunnitelma.md](../suunnitelma.md), luku 2.

Tarkastaja: fp-auditor · Päivämäärä: 14.11.2026
Lähteet: Freight Planner `main` `1128d19` (`/home/claude/fp`), FleetFlow `main` `f9a04f0` (`/home/claude/fleetflow-planner`), PR #6:n dokumentti (`git -C /home/claude/ff show FETCH_HEAD:docs/order-routing-trip-principles.md`), suunnitelma `/home/claude/fp/docs/tms-yhdistamissuunnitelma.md`.

> **Huom:** suunnitelma muuttui tarkastuksen aikana. Ensimmäisessä luennassa D3 oli vielä "pohjana Freight Plannerin repo", ja D9–D12 puuttuivat. Raportti perustuu uusimpaan versioon: D3 = uusi sovellus (hyväksytty), D11 = React + TypeScript + Vite (hyväksytty), D12 = FastAPI + Pydantic + SQLAlchemy + PostgreSQL (ehdotus). Rivinumerot viittaavat siihen versioon.

---

## Tiivistelmä

- **Siirrettävä ydin on pieni mutta arvokas.** Sellaisenaan siirtyvät puhtaat Python-moduulit `money.py`, lisähintamoottorin valinta- ja laskentafunktiot (`surcharges.py`), asiakashinnaston postinumerologiikka (`customer_pricing.py`), palvelukoodisto ja FleetFlow'n `jobPlanning.js`. Niiden mukana siirtyy noin 120 testiä.
- **Freight Plannerin `app.py`:n (2 557 riviä) liiketoimintasäännöt siirtyvät vain muokattuina.** Säännöt ovat Flask-reiteissä, ja ne on sidottu `orders.trip_id`-malliin. Jos D12 (FastAPI) hyväksytään, Flaskin reittikoodia ei siirry lainkaan.
- **FleetFlow'n arvo on lähes kokonaan UI-mallissa ja toimialueperiaatteissa.** Plan Checkin logiikka on `App.jsx`:ssä, testaamatonta ja osin virheellistä, eikä sitä pidä siirtää sellaisenaan.
- **Testit tänään:** Freight Planner backend 311/311 läpi ja FleetFlow 7/7 läpi. Freight Plannerin frontendissä ei ole yhtään oikeaa testiä.
- **Kaksi kriittistä havaintoa suunnitelmasta.** (1) Uuden sovelluksen päätös (D3/D11/D12) ei ole vielä päivittynyt lukuihin 2 (R1), 3 ja 5. (2) Luku 2B merkitsee perälaudan ja pressun soveltuvuuslogiikan toteutetuiksi (✅), mutta koodissa niitä ei ole.
- **Karkea arvio:** siirto säästää noin 50–70 tuntia uudelleenkirjoitukseen verrattuna. Suurin hyöty tulee valmiista testitapauksista ja säännöistä, ei UI-koodista.

---

## 1. Siirretään sellaisenaan

Puhdas logiikka, testattu, eikä riippuvuutta vanhaan tietomalliin. Testien fixturet pitää silti vaihtaa, koska nykyiset ajavat vanhan Alembic-skeeman (`ensure_surcharge_rates` → `upgrade_connection`, `surcharges.py:80-83`).

| Kohde | Tiedosto | Testit | Huomio |
|---|---|---|---|
| Rahamuunnokset ja pyöristys: `to_decimal`, `quantize`, `round_money`, `to_minor`/`from_minor`, `to_cents`/`from_cents`, `to_e4`/`from_e4`, `total`, `percent_of`, `parse_field` | `fp/backend/money.py:59-193` | `test_money.py`: noin 36 kerättyä logiikkatestiä (42 yhteensä; noin 6 on API-testejä) | Ainoa riippuvuus on `decimal`. Jos PostgreSQL ja `NUMERIC` valitaan, `*_cents`/`*_e4`-muunnokset voivat jäädä tarpeettomiksi, mutta `round_money` ja `percent_of` säilyvät (ks. päätös P4) |
| Lisähinnan valinta ja laskenta: `derive_trade_type`, `_normalize_context`, `_is_valid_on`, `_matches`, `specificity`, `select_rate`, `compute_amount`, `round_amount` | `fp/backend/surcharges.py:243-389` | `test_surcharges.py`: noin 45 kerättyä moottoritestiä (esim. `test_select_rate_pure`, `test_most_specific_wins`, `test_min_amount_applies`, `test_rate_selected_by_date` ×6) | `select_rate(rates, context)` ja `compute_amount` ovat puhtaita. Säännöt: tarkin osuma voittaa (maa 8 > tuote 4 > operaattori 2 > suunta 1) ja ROUND_HALF_UP |
| Postinumeroalueen osuma ja normalisointi: `normalize_zip`, `_zip_match_len`, `_valid_on`, `find_rate_card`-funktion pisteytyssilmukka | `fp/backend/customer_pricing.py:191-278` | `test_customer_pricing.py`: `TestRateCardZipLookup` (7), `TestRateCardCountryLookup` (13), `TestRateCardValidity` (4), `TestBillingRule` (7) = 31 | Pisteytys (osumien määrä → alueen pituus → `valid_from` → id) kannattaa erottaa omaksi funktiokseen. SQL-haku on luokassa 2 |
| Palvelukoodisto `SERVICES` ja oletus-`cost_type` | `fp/backend/services.py:11-50` | `test_services_table_contains_spec_codes`, `test_default_cost_types`, `test_services_have_valid_category_and_active` | Pelkkää dataa. `LEGACY_CODE_MAP` ja migraatio kuuluvat luokkaan 4 |
| Jobin alku- ja loppuaika: `getJobStartTime`, `getJobEndTime` | `fleetflow-planner/src/jobPlanning.js:1-25` | Epäsuorasti `jobPlanning.test.js:55-62` | D11:n mukaan tarvitaan TypeScript-tyypit (Job-rajapinta) |
| Sijaintiaukot: `getTruckLocationGaps` | `fleetflow-planner/src/jobPlanning.js:37-71` | `jobPlanning.test.js:45-88` (4 testiä) | Puhdas ja numeerinen aikajärjestys. Logiikka siirtyy suunnitelman mukaan backendiin (`planning`), joten se kannattaa kirjoittaa Pythoniksi testitapauksineen. Testitapaukset siirtyvät sellaisenaan |

---

## 2. Siirretään muokattuna

| Kohde | Tiedosto | Testit | Purettava sidos |
|---|---|---|---|
| `calculate_surcharge`, `fetch_rates` | `surcharges.py:391-426` | Moottoritestit + `test_api_created_rate_used_in_calculation` | Suora SQL `surcharge_rates`-tauluun → repository/SQLAlchemy |
| `find_rate_card`, `get_billing_rule` | `customer_pricing.py:237-308` | Ks. luokka 1 (31 testiä) | SQL-haku ja `rate_card_as_dict` vanhoihin sarakkeisiin. **Testattu, mutta ei käytössä:** kumpaakaan ei kutsuta `app.py`:stä (vain CRUD) |
| Syötteen validointi: `validate_surcharge_payload`, `validate_rate_card_payload`, `validate_billing_rule_payload`, `_parse_bool`, `_zip_prefix` | `surcharges.py:429-500`, `customer_pricing.py:313-421` | `test_api_create_validation` ×14, `TestRateCardApi`, `TestBillingRuleApi` (yhteensä noin 57 API-testiä) | Virhelista + dict → Pydantic-mallit (D12). Säännöt säilyvät: pakollinen `cost_type`, `pass_through` vain säännöissä ja postinumeroalueen maaetuliite pois |
| Voimassaolojen päällekkäisyys (409): `find_overlap`, `find_rate_card_overlap`, `find_billing_rule_overlap`, `_validity_overlap_sql` | `surcharges.py:501-520`, `customer_pricing.py:424-463` | `test_api_*overlap*`, `test_api_adjacent_periods_allowed` | SQLite-SQL → ORM tai PostgreSQL:n `daterange` + EXCLUDE-rajoite |
| Rahasarakkeiden kartta: `MONEY_COLUMNS`, `column(s)`, `row_from_db`, `values_to_db` | `money.py:28-56, 151-181` | `test_money.py`: API-muototestit | Taulujen ja sarakkeiden nimet ovat vanhasta skeemasta |
| Automaatti 120 → 200 (polttoainelisä) | `app.py:1262-1282` | `test_costs.py`: 3 testiä | Flaskin `request` → domain-palvelu. Kohdistuu tripiin, ja uudessa mallissa kohde voi olla order tai leg (R2/R3) |
| Automaatti vahvistus → 400-rivit (päivät × leasing/vuokra) | `app.py:772-808` | `test_trailer_rental_added_on_confirmation`, `test_trailer_rental_not_duplicated`, `test_no_legacy_trailer_code` | Status-merkkijono ja `trips.trailer_id` → trailerivaraus (`resource_reservations`) |
| Automaatit 800 (odotusaika) ja `delivered_at` (FEC) | `app.py:1783-1833` | **Ei testejä** | Arvattava trip-ID. Lisäksi virheitä, ks. ristiriita T1. Kirjoitetaan uudelleen `handling_events`-tauluun, ja vain sääntö säilyy |
| Kapasiteetin tarkistus (paino, LDM, tilavuus) | `app.py:206-215, 1160-1177` + `TRAILER_SPECS` `app.py:55-112` | **Ei testejä** | `orders.trip_id`-summa → summa tripin legeistä (R1). Float ja `round` |
| LDM ja tilavuus: `calculate_loading_meters`, `calculate_volume` | `app.py:163-172` | **Ei testejä** | Puhdas, mutta float. `stackable`-kenttää ei huomioida |
| Lukitus `is_locked` (Laskutettu) | `app.py:202-203` + noin 10 kutsua | Ei suoria testejä | R3: laskutus kohdistuu Orderiin, joten lukitussääntö muuttuu |
| Reittiosuma `get_route_match` (sama postialue / naapurimaa) | `app.py:855-898` | **Ei testejä** | Puhdas funktio, mutta siinä on kuollutta koodia (S1). `NEIGHBORS` on toimialuedataa |
| Maarajoitusmoottori `check_restrictions` + apufunktiot `_in_season`, `_times_overlap` | `fp/backend/restriction_engine.py:1-169` | **Ei yksikkötestejä** (vain taulun olemassaolo `test_alembic.py`, `test_db_path.py`) | Hakee säännöt itse kannasta (`:81-84`) → säännöt parametriksi. `min_weight_t` NULL kaatuu (`:95, :114`). Suunnitelman kerros 1 käyttää tätä, joten testit kirjoitetaan ennen siirtoa |
| Dashboard-aggregaatiot | `app.py:1358-1432, 1653-1747` | `test_dashboard.py` (7, mukana issue #20:n regressio) | SQL `trips`/`costs`. Testi-idea (summat eivät kerrannu) säilyy |
| ID-generaattorit | `app.py:175-199` | `test_id_gen.py` (8) | `MAX(id)+1` → sekvenssi. Kolme kopiota (S8) |
| Demodata | `fp/backend/init_db.py:17-505` | `test_demo_data.py` (21: "Demo"-nimet, katteet 8–20 %, spot, 400-rivit) | Uusi skeema. Testien säännöt siirtyvät |
| `db_config.get_db_path`, testikannan vartija | `db_config.py`, `tests/conftest.py:59-66` | `test_db_path.py` (osa) | Ympäristömuuttuja → asetukset. Vartija-idea siirtyy |
| `assignTruckToJob` | `jobPlanning.js:28-35` | `jobPlanning.test.js:16-43` | Nollaa `driverHoursToday`-kentän (`:33`), ja testi lukitsee tämän (`:29-30`). Uudessa mallissa ajoaika lasketaan `duty_events`-tauluista eikä kenttää nollata (T6) |
| Aikataulun päällekkäisyys ja puskuri `getTruckScheduleFeasibility` | `App.jsx:517-597` | **Ei testejä** | Komponenttitiedostossa. 45 min kovakoodattu. `parseTimeToMinutes` palauttaa virheellisestä ajasta 0 (T5). Siirtyy Pythoniin (`planning`) |
| Plan Check `handleCheckPlan` | `App.jsx:787-910` | Vain savutesti `App.test.jsx` | React-tila ja `setState`. Virheet T5–T6. **Vain tulosrakenne** (truck → jobs → status/issues) kannattaa ottaa mallina kerrokselle 1 |
| Etäisyys `calculateDistanceKm` (haversine) ja kaupunkikoordinaatit | `App.jsx:12-28, 470-482` | **Ei testejä** | Pieni puhdas funktio. 72 km/h kovakoodattu kahdessa paikassa. Siirtyy `locations`-tauluun ja Pythoniin |
| FleetFlow'n demodata `initialDailyJobs`, `demoJobDetailsById` | `App.jsx:30-466` | — | Siirretään seediin vasta, kun sisäinen ristiriita on korjattu (T7) |

---

## 3. Käytetään vain mallina tai referenssinä

| Kohde | Tiedosto | Testit | Huomio |
|---|---|---|---|
| Freight Plannerin näkymät: TripDetail, TripForm, TripList, OrderForm, OrderList, AddToTripModal (kapasiteettipalkit 70/90, reittiosuma ✅⚠️❌), Dashboard, CostsDashboard, CustomerList/Form, DriverPage (FEC-mobiili), Login | `fp/frontend/src/components/*.js` (noin 7 000 riviä) | Ei testejä (`App.test.js` on tyhjä) | JavaScriptiä ja inline-CSS:ää, joten D10/D11 estävät suoran siirron. Kenttäjaot, välilehdet ja työnkulku ovat hyvä malli |
| Hallintanäkymät: HallintaKalusto (huolto/katsastus, `DueBadge`), HallintaHinnoittelu, HallintaAsetukset, CountryRestrictionsPage | `fp/frontend/src/components/*.jsx` | — | Sama kuin yllä |
| Toast-järjestelmä | `context/ToastContext.js`, `hooks/useToast.js`, `components/ToastContainer.js` | — | Pieni ja toimiva. Voidaan kirjoittaa TypeScriptiksi ja tokeneille noin tunnissa |
| CostCalculatorin kaava (myyntihinta = kulut / (1 − kate)) | `CostCalculator.js:131-145` | — | Kaava on oikea. Hinnat on kovakoodattu (T4), joten ne eivät siirry |
| FleetFlow'n näkymät: Board, Job Workspace (7 alavälilehteä), Fleet Timeline, Plan Check -paneeli, Route & Risk | `fleetflow-planner/src/App.jsx:1606-3276` | `App.test.jsx` (1 skenaario) | Yksi 3 276 rivin komponentti, joten se pilkotaan uudelleen. Skenaariotesti on hyvä E2E-malli |
| Teemat classic / light / dark | `fleetflow-planner/src/App.css` (4 237 riviä) | — | D9-tokenien lähde (`--bg-main` ja muut) |
| Toimialuedata: `TRAILER_SPECS`, `PALLET_TYPES`, `INCOTERMS`, `STATUSES`, `NEIGHBORS`, `SERVICES` | `app.py:55-140, 875-893` | — | Seediksi tai vakioiksi uuteen malliin |
| Säännöt ja määrittelyt: pricing-engine-spec, PR #6:n periaatteet, Freight Plannerin soveltuvuustaulukko v9 | `fp/docs/pricing-engine-spec.md`, `ff` PR #6, `FREIGHT_PLANNER_KONTEKSTI.txt:1005-1045` | — | v9 on uudempi kuin `:912-940` (S2) |
| Tarkistusraportin malli | `fleetflow-planner/docs/FF-002C-validation.md` | — | Hyvä pohja PR-kohtaisille tarkistuksille |
| CI-työnkulku ja testikannan vartija | `fp/.github/workflows/tests.yml`, `tests/conftest.py` | — | Uuteen repoon lisätään myös frontendin testiajo |

---

## 4. Ei siirretä

| Kohde | Tiedosto | Testit | Perustelu |
|---|---|---|---|
| Alembic-revisiot 0001–0003 | `fp/backend/migrations/versions/` | `test_alembic.py` (16) | D3: uusi skeema, ei yhteensopivuutta. Uusi repo alkaa omasta baselinesta. 0003:n Decimal-muunnoksen idea on dokumentoitu `CLAUDE.md`:ssä |
| Yhteensopivuuskääreet `migrate_*.py` (6 kpl) | `fp/backend/migrate_*.py` | — | Vanhan kannan päivitystä varten |
| Vanhojen koodien yhdistäminen `LEGACY_CODE_MAP`, `merge_legacy_codes` | `services.py:52-107` | Noin 5 testiä `test_services.py`:ssä | 401/831 ovat vain vanhassa datassa |
| `fuel_rates`-siirto ja yhteensopivuuskerros: `migrate_fuel_rates`, `multiplier_to_rate`, `fuel_row_as_legacy`, `/api/fuel-rates` | `surcharges.py:142-240`, `app.py:1540-1651`, `init_db.py:262-272` | `test_fuel_migration.py` (40) | Polttoainelisä on jo `surcharge_rates`-mallissa |
| FuelRateManager-näkymä | `FuelRateManager.js` | — | Korvautuu lisähintojen hallinnalla |
| `db_migrate.py` (`_BorrowedConnection`, SQLite-transaktiot) | `fp/backend/db_migrate.py` | Osa `test_alembic.py`:stä | SQLite-spesifinen. D12/PostgreSQL käyttää tavallista Alembic-ympäristöä |
| Kovakoodattu kirjautuminen | `app.py:220-227`, `App.js:155-167` | — | Vaihe 1 tekee oikean autentikoinnin |
| `MoneyJSONProvider` | `app.py:27-42` | — | Flask-spesifinen. Pydanticilla Decimalin serialisointi tehdään eri tavalla |
| `FERRY_ROUTES`-vakio, `STATUS_FLOW` (ei käytössä) | `app.py:118-123, 134-140` | — | Kolmas lauttahintalähde (T4). Kuollutta koodia |
| Päällekkäiset näkymät CarrierList ja TrailerList (reitit `/carriers`, `/trailers`) | `App.js:190-196` | — | Korvautuvat Hallinta-näkymillä (S5) |
| Tyhjä frontend-testi | `fp/frontend/src/App.test.js` | — | Ei tarkista mitään |
| FleetFlow'n `MapView.jsx` | `src/MapView.jsx` | — | Ei käytössä missään (ei importtia) |
| FleetFlow'n keksityt varahaut: `getDemoTripDetailsForJob`, `getDemoOrdersForJob`, `getDemoNodesForJob`, `getDemoAssignmentCheckForJob` | `App.jsx:1122-1319` | — | Keksivät dataa (`adr = id.endsWith("003")`, `adrCapable = truck !== "TR-102"`). Käyttöliittymän rakenne kuuluu luokkaan 3 |
| Event login tekstiluokittelu säännöllisellä lausekkeella | `App.jsx:1640` | — | Tila päätellään tekstistä. Korvataan rakenteisella tasolla |
| Satunnaiset tiedostot | `fleetflow-planner/dev-server.err` (tyhjä), `fp/.claude/settings.local.json` | — | Eivät kuulu repoon |

---

## 5. Ristiriidat ja päällekkäiset toteutukset

Jokainen kohta on tarkistettu lukemalla koodi.

### Kriittinen

**K1. Suunnitelma ei ole päivittynyt D3/D11/D12:n jälkeen.**
`tms-yhdistamissuunnitelma.md`:
- rivi 62 (R1): "`orders.trip_id` siirretään migraatiossa ensimmäiseksi legiksi". Tämä on ristiriidassa D3:n (rivi 30) "ei siirretä yhteensopivasti" kanssa.
- Luku 3: "Frontend (Vite + React, JS)" ja "Backend (Flask, blueprintit)" ovat ristiriidassa D11:n (TypeScript) ja D12:n (FastAPI) kanssa. "SQLite → PostgreSQL" ei koske uutta sovellusta, joka voi aloittaa suoraan PostgreSQL:llä.
- Vaihe 1: "`app.py` … jaetaan blueprinteihin" (rivi 211) ja "Frontend siirretään Viteen".
- Vaihe 2: "migraatio `orders.trip_id`:stä" ja "API pysyy taaksepäin yhteensopivana" (rivi 217).
- Vaihe 3: "demodata siirretään `seed_demo_data()`:han" (Freight Plannerin funktio).
- Vaihe 0: "Toni hyväksyy … D3–D7", vaikka D3 on jo hyväksytty.

Ilman korjausta agentit toteuttavat vanhan suunnitelman mukaisia tehtäviä.

**K2. Luku 2B merkitsee toteutetuksi logiikkaa, jota koodissa ei ole.**
- Rivi 92, Perälauta: "✅ terminaaliflow, terminaalivalinta, kuittaus". Sarakkeet `trips.tail_lift_unloading` ja `unloading_terminal_id` ovat vain skeemassa (`0001_baseline.py:63-64, 331-332`). `update_trip` (`app.py:706-716`) ei kirjoita niitä, eikä frontend käytä niitä missään (grep: ei osumia `frontend/src`:ssä).
- Rivi 94, Pressukuljetukset: "✅ … pitkien tavaroiden esto". Pitkien tavaroiden (> 2,5 m) estoa ei ole: `AddToTripModal.js` ei tarkista trailerityyppiä, ja `add_order_to_trip` (`app.py:1138-1185`) tarkistaa vain kapasiteetin.

Molemmat ovat vain dokumentaatiossa (`FREIGHT_PLANNER_KONTEKSTI.txt:1005-1045`), joten ne on toteutettava uutena eikä siirrettävä. Tämä vaikuttaa työmääräarvioon.

### Tärkeä

**T1. FEC-odotusaika (800) on virheellinen eikä sitä ole testattu** (`app.py:1783-1833`).
- `now` on UTC-aikaa (`datetime.utcnow()`, `:1793`), mutta sitä verrataan paikalliseen `loading_time_end`-aikaan (`:1812`). Suomen ajassa viive aliarvioidaan 2–3 tuntia.
- Kaikki virheet niellään (`except Exception: pass`, `:1822`).
- Lukitusta ei tarkisteta, joten Laskutettu-keikalle voi syntyä 800-rivi.
- Summa lasketaan floatilla: `round(delay_h * 45, 2)` (`:1819`). `test_no_float_in_money_code` ei huomaa tätä, koska se tarkistaa vain `money.py`:n, `surcharges.py`:n ja `customer_pricing.py`:n (`test_money.py:90`).
- 45 €/h on kovakoodattu, ja koodin kommentti myöntää laskennan keskeneräiseksi (`:1820-1821`).

**T2. Statusketjua ei valvota.**
- `update_trip_status` hyväksyy minkä tahansa statuksen `STATUSES`-listasta (`app.py:766-770`), myös hypyn suoraan Laskutettu-tilaan. Näin ohitetaan `confirm_invoice`-funktion Toimitettu-vaatimus (`:824`).
- `STATUS_FLOW` (`:134-140`) on määritelty, mutta sitä ei käytetä.
- Siirtymiä ei ole testattu, lukuun ottamatta 400-automaattia.

**T3. Hinnoittelumoottori on testattu, mutta sitä ei ole kytketty käyttöön.** `find_rate_card`, `get_billing_rule` ja `derive_trade_type` ovat käytössä vain testeissä. Ainoa `calculate_surcharge`-kutsu on polttoainelisä (`app.py:1267`). Siirto onnistuu, mutta kytkentä (vaihe 6) on kokonaan tekemättä.

**T4. Hinnoilla on rinnakkaisia lähteitä.**
- **Lautta, kolme lähdettä:**
  - `app.py:118-123` `FERRY_ROUTES` (TripForm hakee: `TripForm.js:54` → `/api/ferry-routes`)
  - `CostCalculator.js:3-9`
  - `ferry_rates`-taulu (`init_db.py:171-181`, HallintaHinnoittelu)
- **Km-hinnat:** `CostCalculator.js:11-15` (1,45 / 1,28 €/km) ja `km_rates` (`init_db.py:164-169`: 1,85 / 2,20 €/km). Laskin ei käytä APIa.

**T5. FleetFlow'n aikakäsittely on kahdella eri tavalla.**
- `parseTimeToMinutes` (`App.jsx:490-494`) palauttaa virheellisestä ajasta 0. `jobPlanning.js:47-51` palauttaa NaN ja suodattaa ajan pois.
- Plan Check ja Fleet-näkymä järjestävät ajat merkkijonoina `localeCompare`-funktiolla (`App.jsx:796, 1363, 1375`), mutta `getTruckLocationGaps` järjestää numeerisesti. "9:00" järjestyy merkkijonona "10:00":n jälkeen.
- Demodatassa kaikki ajat ovat muotoa `HH:MM`, joten virhe on piilevä.

**T6. FleetFlow'n ajoaikalogiikka on neljässä paikassa, ja siinä on toimialuevirheitä.**
- Kopiot: `handleCheckPlan` (`App.jsx:833-843`), `plan` (`:942-959`), `selectedJobPreview` (`:994-999`) ja `eventLog` (`:1030-1036`). 72 km/h on kovakoodattu kohdissa `:820` ja `:939`. 45 minuutin puskuri on kohdissa `:560`, `:580` ja `:812`.
- 4,5 h tulkitaan päivän kumulatiiviseksi ajoksi eikä yhtäjaksoiseksi ajoksi edellisen tauon jälkeen.
- 9 h:n raja ei huomioi 10 h:n pidennystä.
- Joustava aikaikkuna merkitsee jobin tilaan "Break required" (`:838-840`).
- `driverHoursToday` on staattinen kenttä, jonka `assignTruckToJob` nollaa (`jobPlanning.js:33`).

Suunnitelma (luku 4) toteaa oikein, että kerros 1 on rakennettava alusta.

**T7. FleetFlow'n demodata on sisäisesti ristiriitainen.** JOB-001 on `Kotka → Hanko Port` klo 06:30–09:00 (`App.jsx:36-39`), mutta sen yksityiskohdissa orderit kulkevat `Demo Terminal North → Demo DC East` klo 07:30–13:00 (`App.jsx:207-240`). Trip & Orders -välilehti näyttää siis eri reitin kuin job. Ristiriita korjataan ennen seediin siirtoa.

**T8. Maarajoitusmoottorilla ei ole yksikkötestejä.** Suunnitelman kerros 1 nojaa siihen (luku 4). `rule["min_weight_t"]` on NULL-kelpoinen (`0001_baseline.py:210`, oletus 3,5), ja NULL kaataa vertailun (`restriction_engine.py:95, 114`). Muuttujat `day_start` ja `day_end` (`:131-132`) ovat käyttämättä.

**T9. Trailerityypillä on kaksi lähdettä.** `trips.trailer_type` ja `trailers.trailer_type` palautetaan rinnakkain (`app.py:566, 588`, nimellä `trailer_type_name`). Kapasiteetti käyttää tripin kenttää (`:1161`), joten tyypit voivat erota toisistaan.

**T10. Freight Plannerin frontend-testit puuttuvat ja CI ajaa vain backendin.**
- `frontend/src/App.test.js` sisältää vain tyhjän funktion.
- `tests.yml` ajaa vain backendin.
- Paikallisesti testit ajettiin Python 3.13:lla, jota CI-matriisi (3.11, 3.15) ei sisällä.

### Siivous

- **S1.** `get_route_match`: irrallinen `...` (`app.py:862`) ja `delete_trip`-funktiosta kopioitu kuollut koodi `return`-lauseen jälkeen (`:900-905`).
- **S2. Freight Plannerin dokumentaatio vs. koodi:**
  - "React 18" (`CLAUDE.md:4`, `README.md:21, 151`, `FREIGHT_PLANNER_KONTEKSTI.txt:13`), mutta `frontend/package.json:10` on `react ^19.2.5`. **Projektien välillä ei ole React-ristiriitaa:** molemmat käyttävät React 19:ää (FleetFlow ^19.2.5, asennettuna 19.2.6). Ristiriita on vain Freight Plannerin dokumentaatiossa.
  - `CLAUDE.md:120` "~2100 riviä", vaikka `app.py` on 2 557 riviä.
  - `KONTEKSTI.txt:281` mainitsee "Toast.js", mutta tiedosto on `ToastContainer.js`.
  - Perälaudasta on kaksi versiota: `KONTEKSTI.txt:912-940` (esto) ja `:1005-1045` (v9, ei estoa).
  - "TULOSSA"-merkinnät on jätetty toteutettuihin kohtiin: `ferry_rates` (`:219`), `settings` (`:223`) ja `check-restrictions`/maintenance (`:381-384`). Toteutukset ovat `app.py:2011, 2037-2105, 2247-2300, 2531`.
- **S3. FleetFlow'n dokumentaatio vs. koodi:** `FLEETFLOW_MASTER_CONTEXT.md` päättyy vaiheeseen 8.1C.2 eikä mainitse FF-002A–D:tä, Vitestiä tai `jobPlanning.js`:ää. `README.md`:n teknologialuettelo (rivit 126-133) ei mainitse testejä.
- **S4. FleetFlow'n sisäiset päällekkäisyydet:**
  - Päivän laskurit lasketaan kolmesti: `DailyCapacity` (`App.jsx:625-633`), `capacitySummary` (`:720-735`) ja `boardOverview` (`:1380-1422`). `boardOverview` tulkitsee tyhjän truck-kentän eri tavalla kuin kaksi muuta.
  - `trucks` (`:1358`) ja `fleetTruckSequences` (`:1369`) muodostavat saman ryhmittelyn.
  - `fleetTrucks` (`:1354`) luodaan joka renderöinnillä uudelleen, joten sitä käyttävät `useMemo`-laskennat ajetaan joka kerta.
- **S5. Freight Plannerin frontendin päällekkäisyydet:**
  - `/carriers`- ja `/trailers`-listat (`App.js:190-196`) puuttuvat sivupalkista. Kuljetusyhtiöt näkyvät HallintaKaluston kautta (CarrierList upotettuna). Trailerit ja vetäjät ovat lisäksi HallintaKaluston omissa välilehdissä, jotka hakevat datan uudelleen (`HallintaKalusto.jsx:69-86, 277-292`).
  - `/fuel` ja `/restrictions` ovat sekä omia reittejä että upotettuina HallintaHinnoitteluun (`:3-4, 362`).
  - `STATUS_COLORS` on neljänä kopiona eri väreillä: `Dashboard.js:4-9` vs. `TripDetail.js:6-10`, `CostsDashboard.js:4-9` ja `AddToTripModal.js:25`.
  - API-osoite on kovakoodattu noin 71 kertaa 22 tiedostossa. Lisäksi neljässä tiedostossa on oma paikallinen `const API`.
- **S6. Kate lasketaan neljässä paikassa:** `app.py:625-630`, `:1414-1415` (2 desimaalia), `:1692-1693` (1 desimaali) ja `TripDetail.js:951-954` (float frontendissä).
- **S7.** Kolme lähes identtistä ID-generaattoria (`app.py:175-199`). `order_reference` ja `order_id` käyttävät samaa laskuria.
- **S8.** Voimassaolon tarkistus on kahdesti: `surcharges._is_valid_on` (`:307`) ja `customer_pricing._valid_on` (`:229`).
- **S9.** `fuel_rates`-taulua seedataan yhä (`init_db.py:262-272`), vaikka se vain migroidaan heti `surcharge_rates`-tauluun.
- **S10.** Repoihin kuulumattomat tiedostot: `fleetflow-planner/dev-server.err` ja `fp/.claude/settings.local.json`.

---

## 6. Testitulokset (ajettu 14.11.2026)

| Projekti | Komento | Tulos | Ympäristö |
|---|---|---|---|
| Freight Planner backend | `cd /home/claude/fp/backend && pip install -q -r requirements.txt --break-system-packages && python -m pytest tests/ -q` | **311 passed** 8,11 sekunnissa, 0 epäonnistunutta | Python 3.13.18 (ei CI-matriisissa 3.11/3.15) |
| FleetFlow | `cd /home/claude/fleetflow-planner && npm test` (`vitest run`) | **7 passed**, 2 testitiedostoa, 2,49 s | Vitest 5.1.0, jsdom |
| Freight Planner frontend | Ei ajettu | — | `node_modules` puuttuu, ja ainoa testi (`App.test.js`) ei tarkista mitään |

Freight Plannerin kerätyt testit tiedostoittain: alembic 16, costs 6, customer_pricing 66, dashboard 7, db_path 12, demo_data 21, fuel_migration 40, id_gen 8, money 42, services 14 ja surcharges 79.

Mitä testeille tapahtuu siirrossa (karkea jako):
- **Logiikkatestit siirtyvät, fixture vaihtuu:** noin 112 Freight Plannerin testiä (rahalaskenta noin 36, lisähintamoottori noin 45, asiakashinnaston haku 31) ja FleetFlow'n `jobPlanning.test.js`:n 6 testiä
- **API-testit kirjoitetaan uudelleen samoin tapauksin:** noin 105 (CRUD, 409, validointi, kulut, dashboard, ID:t, demodata)
- **Ei siirry:** noin 75 (alembic 16, fuel 40, db_path noin 12, palvelukoodiston vanhat migraatiot noin 5)

Testaamattomat mutta siirtymässä olevat kohteet: FEC, statussiirtymät, kapasiteetti, LDM, reittiosuma, maarajoitukset ja FleetFlow'n Plan Check.

---

## 7. Säästääkö siirto työtä? (karkea arvio)

| Kategoria | Siirtotyö | Uudelleenkirjoitus testeineen | Nettosäästö | Peruste |
|---|---|---|---|---|
| 1. Sellaisenaan | 6–10 h (fixturet, TypeScript-tyypit, nimet) | 35–50 h | **noin 30–40 h** | Valmiit reunatapaukset (pyöristys, tarkin osuma, postinumeroalue, voimassaolon rajat) ovat suurin yksittäinen säästö |
| 2. Muokattuna | 40–60 h | 60–90 h | **noin 20–30 h** | Säännöt ja testitapaukset säilyvät, mutta koodi muuttuu. T1:n ja T6:n virheet on korjattava, ei kopioitava |
| 3. Malli | 0 h koodia | — | **noin 15–30 h suunnittelua** | UI kirjoitetaan uudelleen joka tapauksessa (TypeScript + tokenit, noin 80–120 h), mutta rakenne ja toimialuetaulukot ovat valmiina |
| 4. Ei siirretä | 0 h | 0 h | 0 h | Noin 75 testiä ja noin 1 000 riviä vanhan skeeman koodia jää pois |

**Yhteensä noin 50–70 h säästöä eli merkittävästi, mutta ei suurinta osaa työstä.** Uuden sovelluksen isoimmat kokonaisuudet ovat Plan Check, uusi tietomalli, autentikointi ja UI, ja ne ovat käytännössä uutta työtä.

---

## 8. Päätökset, joita Tonin pitää tehdä

1. **P1. Päivitetäänkö suunnitelma D3/D11/D12:n mukaiseksi ennen vaihetta 0 (K1)?** Muutettavat kohdat: R1, luku 3, vaiheet 1–3 ja vaiheen 0 D3-maininta.
2. **P2. Hyväksytäänkö D12 (FastAPI)?** Päätös ratkaisee, siirtyykö Flask-koodia lainkaan. FastAPI:lla luokan 2 validointi muuttuu Pydantic-malleiksi.
3. **P3. Korjataanko luku 2B (K2)?** Perälauta ja pressu ⚠️-tilaan, sekä työmäärä uutena toteutuksena.
4. **P4. Rahamuoto PostgreSQL:ssä:** säilyykö INTEGER `*_cents`/`*_e4`, vai siirrytäänkö `NUMERIC`-tyyppiin? INTEGER-perustelu (`CLAUDE.md`: SQLitessä ei ole desimaalityyppiä) ei päde PostgreSQL:ään. Päätös vaikuttaa `money.py`:n laajuuteen.
5. **P5. Siirretäänkö FleetFlow'n ajoaikalogiikkaa lainkaan, vai aloitetaanko `feasibility.py` puhtaalta pöydältä säädöstekstin pohjalta (T6)?** Suositus: puhdas pöytä, ja FleetFlow'sta otetaan vain tulosrakenne ja UI.
6. **P6. FEC-odotusajan sääntö (T1):** aikavyöhyke, porrastus (30 min karenssi, €/h), lukitus ja kohdistus (order vai trip).
7. **P7. Statusketju (T2):** sallitaanko vain `STATUS_FLOW`-mukaiset siirtymät, ja tehdäänkö Orderille, Tripille ja Jobille erilliset ketjut (R3)?
8. **P8. Kovakoodatut hinnat (T4):** yksi lähde (kanta) laskimelle, lauttareiteille ja km-hinnoille.
9. **P9. Kirjoitetaanko maarajoitusmoottorille testit vanhaan repoon ennen siirtoa (T8), jotta käyttäytyminen lukitaan?**
10. **P10. FleetFlow'n demodatan korjaus (T7) ja se, mitkä FleetFlow'n jobit siirtyvät uuteen seediin.**
