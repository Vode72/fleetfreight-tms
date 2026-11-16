# Paperitestit: yhdistetyn TMS:n tietomalli

> **Historiallinen analyysi 14.11.2026.** Osa käsitteistä (esim. `order_legs`, `stops`, `movements`) ja agenttinimistä on korvattu. Voimassa olevat päätökset: [suunnitelma.md](../suunnitelma.md), luku 2.

Laatija: `fp-logistiikka` (logiikkakatselmointi, ei koodia) · 14.11.2026
Kohde: `fp/docs/tms-yhdistamissuunnitelma.md` luvut 2, 2B ja 3
Vertailupohja: FleetFlow `docs/order-routing-trip-principles.md` (FETCH_HEAD), Freight Plannerin `FREIGHT_PLANNER_KONTEKSTI.txt` ja `CLAUDE.md`, FleetFlow'n `FLEETFLOW_MASTER_CONTEXT.md`

> **Suositus ei ole päätös.** Kaikki tämän raportin suositukset ovat ehdotuksia. Toni päättää, ja vasta sen jälkeen päätösrekisteri (luku 2) päivitetään.
>
> Kaikki tunnisteet, yritykset, rekisterinumerot ja vuorot ovat fiktiivisiä demoarvoja.

---

## 0. Tiivistelmä

Ehdotettu malli (orders → order_legs → trips, jobit erikseen) kestää kaikki viisi skenaariota **pääpiirteissään**. Order ID säilyy, Cross Dock ja Remain LU erottuvat, ja Trip voi jatkua tyhjän trailerin palautukseen. Paperitesteissä löytyi kuitenkin kuusi rakenteellista aukkoa. Ne kannattaa korjata ennen ensimmäistä Alembic-revisiota, koska jälkikäteen jokainen niistä on migraatio:

1. **Pysähdykset puuttuvat taulukosta.** FleetFlow'n Node/Stop-käsite (satamaan jättö, satamasta nouto, trailerin vaihto, pysäköinti, sähköön kytkentä) ei ole luvun 3 tauluissa. `handling_events` kuvaa kuorman tapahtumia ja `jobs` ajoja, mutta "traileri jätetty Vuosaaren satamaan klo 14.10" ei kuulu kumpaankaan.
2. **Lauttaosuudella ei ole kuljettajaa.** Saattamaton traileri liikkuu lautalla ilman Jobia. Jos siirtymät ovat vain Jobin osia (R5-ehdotus), merimatka jää mallin ulkopuolelle. Siirtymä tarvitsee oman taulun, jossa `job_id` on vapaaehtoinen ja kulkumuotona on tie tai lautta.
3. **Job ei mahdu yhden Tripin sisään.** Kun kuljettajat vaihtavat trailereita puolivälissä (skenaario 3) tai kuljettaja jättää trailerin ja ottaa toisen tilalle (skenaario 4), yksi Job koskee kahta Tripiä. `jobs.trip_id` ei siis voi olla yksittäinen viiteavain.
4. **Ajoaika kuuluu kuljettajalle, ei Jobille.** EU 561/2006 laskee ajot kuljettajakohtaisesti yli Jobien, päivien ja viikkojen. `duty_events` on sidottava kuljettajaan, ja Job viittaa niihin vain välillisesti.
5. **Alihankkijan kuljettajaa ei aina tiedetä.** Mantereen vetäjä Lübeckissä on tyypillisesti alihankkija, eikä liikenteenohjaaja näe kuljettajan tunteja. `jobs.driver_id` on voitava jättää tyhjäksi, ja silloin Plan Check on rajattu.
6. **Tripin perälauta- ja ADR-tiedot ovat väärällä tasolla.** FP:n `trips.tail_lift_unloading` ja `unloading_terminal_id` ovat keikkatason kenttiä, mutta perälautapurku koskee yksittäistä orderia. Uudessa mallissa se on oma order leg (terminaali → vastaanottaja), ja tripin ADR- ja lämpötilaliput johdetaan ordereista.

Tiivistetyt suositukset (perustelut luvussa 2):

| # | Suositus lyhyesti |
|---|---|
| R1 | `order_legs` kuten ehdotettu. Legin raja on **jokainen gateway, jossa orderille annetaan ohje** (UNLOAD/LOAD/REMAIN). Yksi leg kuuluu yhteen Tripiin. Trip = yhden lastitilan (trailerin) kuormattu kierros |
| R2 | Kulu kirjataan tasolle, jolla se syntyy. Jakoavain määritellään palvelukoodikohtaisesti: oletus LDM, aiheuttajakohtaiset kulut suoraan orderille ja kiinteät per lähetys tasan. Jako lasketaan funktiolla ja jäädytetään orderin laskutuksessa |
| R3 | Order, Trip ja Job saavat kukin oman tilaketjun. Myynti laskutetaan orderilta. Ostot kohdistuvat Tripiin tai Jobiin. "Laskutettu" lukitsee orderin myyntirivit, ei Tripiä |
| R4 | Job = yksi ajoneuvo + yksi kuljettaja, ja vaihto luo uuden Jobin (hyväksy). Lisäksi: Job ↔ Trip on N:M siirtymien kautta, kuljettaja voi olla tyhjä alihankkijalla ja kaksimiehitys rajataan v1:n ulkopuolelle |
| R5 | Order Leg ja siirtymä erotetaan (hyväksy). Siirtymä on oma taulu `movements`, jossa `job_id` on vapaaehtoinen. Kuormatulla siirtymällä on täsmälleen yksi Trip. Legin ja siirtymän yhteys johdetaan Tripin ja pysähdysten kautta, ei erillisellä liitostaululla |

---

## 1. Skenaariot

### Merkinnät

- **Ehdotettu malli** = luvun 3 taulut. Lisäksi näytetään erikseen kaksi apurakennetta, joita paperitesti tarvitsi: `stops` ja `movements` (merkitty **[uusi]**). Ilman niitä ontumiskohdat on kirjattu.
- Siirtymän ajotyypit: `SOLO` (vetoauto ilman traileria), `EMPTY_TRAILER`, `LOADED_TRAILER`. Ajon tarkoitus (esim. `RETURN_TO_BASE`) on oma kenttänsä.
- Tapahtumat: `IOP` (kuorma vastaanotettu lastauspaikalla), `IOD` (kuorma luovutettu), `POD` (toimitustodiste), `UNLOAD`, `LOAD`, `REMAIN`.
- Kulukoodit ovat FP:n demokoodistosta (`services.py`).
- ✅ = malli toimii · ⚠️ = toimii kiertotiellä tai vaatii tarkennuksen · ❌ = ontuu, korjaus tarvitaan

---

### Skenaario 1: Jyväskylä–Vantaa–Lübeck (vienti, saattamaton traileri)

**Tilanne.** Demo Paper Oy lastaa Jyväskylässä 13,6 LDM:n kuorman (`DEMO-ORDER-A`, 22 000 kg) vastaanottajalle Demo Papier GmbH, Lübeck. Kotimaan vetäjä ajaa Jyväskylä → Vantaan terminaali. Mantereen osuus: Vantaa → Vuosaaren satama → lautta Vuosaari–Travemünde saattamattomana → mantereen alihankkija hakee trailerin Travemündestä ja toimittaa sen Lübeckiin.

Kaksi varianttia:
- **1a Cross Dock:** kuorma puretaan Vantaalla kotimaan trailerista (`DEMO-TR-FI1`) ja lastataan mantereen traileriin (`DEMO-TR-EU1`) yhdessä kahden muun orderin kanssa.
- **1b Remain LU:** kuorma jää traileriin `DEMO-TR-EU1`, joka käy Vantaalla vain konsolidointia varten (sinne lastataan lisäksi `DEMO-ORDER-X`). Sen jälkeen traileri viedään satamaan.

#### 1a Cross Dock: syntyvät rivit

| Taulu | Rivi | Keskeiset kentät | Arvio |
|---|---|---|---|
| orders | DEMO-ORDER-A | lastaus Jyväskylä, purku Lübeck, 13,6 LDM / 22 000 kg, maksaja lähettäjä (DAP) | ✅ |
| order_legs | DEMO-LEG-A1 | seq 1, Jyväskylä (asiakas) → Vantaa (terminaali), trip DEMO-TRP-1, lopussa UNLOAD | ✅ |
| order_legs | DEMO-LEG-A2 | seq 2, Vantaa → Lübeck (asiakas), trip DEMO-TRP-2, alussa LOAD | ⚠️ ks. huomio A |
| trips | DEMO-TRP-1 | traileri DEMO-TR-FI1, kotimaa, orderit A + kaksi muuta JKL-alueen orderia | ✅ |
| trips | DEMO-TRP-2 | traileri DEMO-TR-EU1, vienti, lautta, orderit A + X + Y | ✅ |
| stops **[uusi]** | S1–S8 | JKL lastaus · Vantaa purku · Vantaa lastaus · Vuosaari gate-in · Travemünde gate-out · Lübeck purku · tyhjän trailerin jättöpaikka | ❌ ei taulua luvussa 3 |
| jobs | DEMO-JOB-1 | kotimaan vetäjä DEMO-TRK-NRF1, kuljettaja DEMO-DRV-01 | ✅ |
| jobs | DEMO-JOB-2 | shunttaus Vantaa → Vuosaari, terminaalin vetäjä, DEMO-DRV-05 | ✅ |
| jobs | DEMO-JOB-3 | alihankkija Demo Trans GmbH, vetäjä tiedossa, **kuljettaja tuntematon** | ❌ R4: `driver_id` pakollinen? |
| movements **[uusi]** | M1 | JOB-1, `EMPTY_TRAILER` varikko → JKL (jos traileri on varikolla), trip TRP-1 | ⚠️ ks. huomio C |
| movements | M2 | JOB-1, `LOADED_TRAILER` JKL → Vantaa, trip TRP-1 | ✅ |
| movements | M3 | JOB-2, `LOADED_TRAILER` Vantaa → Vuosaari, trip TRP-2 | ✅ |
| movements | M4 | **ei jobia**, kulkumuoto FERRY, Vuosaari → Travemünde, trip TRP-2, ferry_booking FB-1 | ❌ R5-ehdotuksessa siirtymä on aina Jobin osa |
| movements | M5 | JOB-3, `SOLO` alihankkijan varikko → Travemünde | ✅ |
| movements | M6 | JOB-3, `LOADED_TRAILER` Travemünde → Lübeck, trip TRP-2 | ✅ |
| movements | M7 | JOB-3 tai myöhempi job, `EMPTY_TRAILER` Lübeck → paluukuorman lastauspaikka tai satama, trip TRP-2, tarkoitus `REPOSITION` | ⚠️ ks. huomio D |
| handling_events | 6 kpl orderille A | IOP (JKL), UNLOAD (Vantaa), LOAD (Vantaa), IOD (Lübeck), POD (Lübeck). Jokaisella suunniteltu, ennustettu ja toteutunut aika | ✅ |
| handling_events | trailerin tapahtumat | gate-in Vuosaari, laivaan lastattu, purettu laivasta, vapautettu, gate-out Travemünde | ❌ eivät ole kuorman tapahtumia, ks. huomio B |
| ferry_sailings | FS-1 | Demo Ferries, Vuosaari → Travemünde, lähtö, saapuminen, **saattamattoman cut-off** | ⚠️ cut-off ≠ saattaen ajavan check-in |
| ferry_bookings | FB-1 | sailing FS-1, traileri TR-EU1, saattamaton, pituus, paino, ADR ei, varausnumero, tila | ⚠️ tilaketju puuttuu, ks. luku 3 |
| resource_reservations | 5 kpl | TRK-NRF1 (JOB-1), TR-FI1 (TRP-1), terminaalivetäjä (JOB-2), TR-EU1 (TRP-2: Vantaa → paluu), alihankkijan vetäjä (JOB-3, informatiivinen) | ✅ |
| trailer_positions | 6+ riviä | TR-FI1: JKL → Vantaa (tyhjä). TR-EU1: Vantaa → Vuosaari → merellä → Travemünde → Lübeck → … | ✅ "merellä"-tila tarvitaan |
| duty_events | DRV-01, DRV-05 | ajo, lastaus (muu työ), tauko | ✅ vain omille kuljettajille |
| costs | TRP-1 | 210 kotimaan ajo kuormattu, 400 trailervuokra | ✅ |
| costs | TRP-2 / leg A2 | 700 käsittely Vantaa (cross dock), 212 shunttaus, 500 lautta, 510 satamamaksu, 520 BAF, 530 ETS, 540 MARPOL, 220 mantereen ajo (alihankkija), 300 Saksan tiemaksu, 221 tyhjä siirto | ⚠️ jakoperuste R2 |
| costs | order A, myynti | 120 FREIGHT (asiakashinnasto FI→DE FTL), 200 polttoainelisä, 230 liikkuvuuspaketti, 530 ETS-myynti, 540 MARPOL-myynti | ✅ myynti orderille, ei legille |

**Huomiot**

- **A. Legin raja ja lautta.** A2 kattaa sekä shunttauksen, lautan että mantereen toimituksen. Se on oikein, jos legin raja on gateway (Vantaa) eikä satama. Jos legiksi tehtäisiin jokainen satama, yhdelle vientiorderille syntyisi 4 legiä ilman kaupallista hyötyä, eikä Gateway Instructions kattaisi satamaa. Suositus R1:ssä: satama ei ole legin raja, ellei kuormaa siellä käsitellä.
- **B. Trailerin ja kuorman tapahtumat ovat eri asioita.** Satamaan jättö (gate-in) ja satamasta nouto (gate-out) koskevat traileria, eivät orderia. Jos ne kirjataan `handling_events`-tauluun orderikohtaisesti, 33 lavapaikan LTL-trailerissa syntyy 12 kopiota samasta gate-in-ajasta. Ratkaisu: `stops` (suunniteltu ja toteutunut aika) trailer- ja Trip-tasolla. `handling_events` jää kuormatasolle.
- **C. Lastauspaikalle tuotu tyhjä traileri.** Kuuluuko M1 Tripiin TRP-1? Suositus: kyllä. Tyhjän trailerin vienti lastaukseen on Tripin alku, ja kulu 211 (kotimaan tyhjä ajo) kohdistuu Tripille. Muuten tyhjät kilometrit jäävät kaikkien Tripien ulkopuolelle eikä KPI näe niitä.
- **D. Tripin loppu.** TRP-2 päättyy vasta, kun TR-EU1 on joko tyhjänä paluukuorman lastauspaikalla tai jätetty satamaan. Malli tukee tätä (Trip jatkuu palautukseen), mutta tilaketju on ratkaisematta (R3).
- **E. Aikavyöhyke.** Lastaus on Suomen ajassa ja toimitus Saksan ajassa. Aikaleimat kannattaa tallentaa UTC:nä ja `locations`-riville IANA-aikavyöhyke. Muuten IOP–IOD-kuljetusaika on tunnin väärin. Puuttuu luvusta 2B.
- **F. Paino maittain.** 22 000 kg kuorma on Saksassa normaalin 40 t:n kokonaispainon rajoissa. Jos Suomessa lastataan raskaammin (Suomen mitoitus sallii huomattavasti suuremmat yhdistelmät), mantereen osuus voi ylittyä. Nykyinen `restriction_engine` tarkistaa kohdemaan; uudessa mallissa tarkistus pitää ajaa **legin ja siirtymän maille**. En ole varma, sovelletaanko yhdistettyjen kuljetusten 44 t:n poikkeusta ro-ro-lauttaan liittyvään kuljetukseen Saksassa. Se on varmistettava ennen kuin sitä käytetään sääntönä.

#### 1b Remain LU: erot variantista 1a

| Taulu | Rivi | Muutos Cross Dockiin nähden | Arvio |
|---|---|---|---|
| order_legs | A1, A2 | **Molemmat samalla tripillä TRP-2**. A1:n lopussa REMAIN | ✅ |
| trips | TRP-2 | traileri TR-EU1 alusta loppuun: JKL lastaus → Vantaa → satama → Lübeck | ✅ |
| trips | TRP-1 | ei synny | ✅ |
| handling_events | order A | IOP, (REMAIN suunniteltuna ohjeena) | ⚠️ ks. alla |
| handling_events | DEMO-ORDER-X | IOP (Vantaa), LOAD (Vantaa) | ✅ |
| stops | Vantaa | trailerin saapuminen ja lähtö, myös vaikka order A:ta ei käsitellä | ❌ ilman `stops`-taulua Vantaan käynnistä ei jää jälkeä |
| movements | M2 | JOB-1 vie TR-EU1:n JKL → Vantaa. **Kotimaan vetäjä vetää mantereen traileria** | ✅ |
| resource_reservations | TR-EU1 | varattu jo JKL-lastauksesta alkaen, joten mantereen trailerin pool-päivät kasvavat | ✅ näkyy oikein |
| costs | 400 trailervuokra | mantereen traileri sidottu pidempään | ✅ |

**Huomiot**

- **REMAIN-tapahtuma.** Periaatteen mukaan REMAIN ei ole toteutunut UNLOAD/LOAD-käsittely. Se on silti **ohje** (Gateway Instructions) ja sen toteutuminen on tarkistettava: lastasiko terminaali vahingossa A:n ulos? Suositus: REMAIN on suunniteltu käsittelytieto `order_legs`-rivillä, ja toteutuneeksi kirjataan vain poikkeama. Ei omaa handling_event-riviä jokaisesta REMAINista.
- **Lastausjärjestys.** Remain LU toimii vain, jos order A on lastattu niin, että Vantaalla lisättävä X mahtuu ja A:n ei tarvitse liikkua. Tämä on käytännössä tärkeä ja malli ei tiedä sitä. V1:ssä riittää varoitus ("REMAIN + LOAD samaan traileriin: tarkista lastausjärjestys").
- **Trailerin kelpoisuus.** Remain LU edellyttää, että JKL:ssä lastataan traileri, joka kelpaa saattamattomana lautalle (kiinnityspisteet, mantereen kelpoisuus, rekisteröinti). Kaluston soveltuvuustarkistukseen tarvitaan ominaisuus "kelpaa saattamattomana ro-ro-lautalle". Puuttuu `qualifications`-listasta.

**Skenaario 1: yhteenveto.** Order–leg–trip-rakenne toimii kummassakin variantissa. Mallista puuttuvat pysähdykset, lauttasiirtymä ilman kuljettajaa ja tuntematon alihankkijakuljettaja.

---

### Skenaario 2: Vuosaari–Vantaa–Oulu (tuonti, osittainen purku, tyhjän palautus)

**Tilanne.** Saattamaton mantereen traileri `DEMO-TR-EU2` saapuu Travemündestä Vuosaareen. Siinä on neljä orderia:

| Order | Vastaanottaja | Ohje Vantaalla |
|---|---|---|
| DEMO-ORDER-B | Oulu, Demo Kauppa | REMAIN |
| DEMO-ORDER-C | Vantaa, paikallisjakelu | UNLOAD |
| DEMO-ORDER-D | Oulu, Demo Rauta | REMAIN |
| DEMO-ORDER-E | Tampere (jatkuu toisella keikalla) | UNLOAD |

Vantaalla vapautuneeseen tilaan lastataan lisäksi `DEMO-ORDER-F` (Vantaa → Oulu, kotimaa). Oulun toimitusten jälkeen tyhjä traileri palautetaan Vuosaareen vientiä varten. Paluukuormaa ei löydy.

#### Syntyvät rivit

| Taulu | Rivi | Keskeiset kentät | Arvio |
|---|---|---|---|
| orders | B, C, D, E | lastauspaikka Saksassa, purku Suomessa | ✅ |
| orders | F | Vantaa → Oulu | ✅ |
| order_legs | B0, C0, D0, E0 | seq 1: lastauspaikka DE → Vantaa, trip TRP-20 (sisältää mantereen noudon, lautan ja shunttauksen) | ⚠️ ks. huomio A |
| order_legs | B1, D1 | seq 2: Vantaa → Oulu, trip TRP-20 (REMAIN) | ✅ |
| order_legs | C1 | seq 2: Vantaa → vastaanottaja, jakelutrippi TRP-22 | ✅ |
| order_legs | E1 | seq 2: Vantaa → Tampere, trip TRP-23 | ✅ |
| order_legs | F1 | seq 1: Vantaa → Oulu, trip TRP-20, alussa LOAD | ✅ |
| trips | TRP-20 | TR-EU2, tuonti + kotimaan lisäkuorma + tyhjä palautus | ⚠️ tyyppi "tuonti" ei kuvaa F:ää |
| stops | 9 kpl | DE lastaukset · Travemünde gate-in · Vuosaari gate-out · Vantaa saapuminen ja lähtö · Oulu purku 1 · Oulu purku 2 · Vuosaari gate-in (tyhjä) | ❌ ei taulua |
| jobs | JOB-20 | shunttaus Vuosaari → Vantaa, DRV-05 | ✅ |
| jobs | JOB-21 | linja Vantaa → Oulu, DRV-02, TRK-PHK1 | ✅ |
| jobs | JOB-22 | tyhjän palautus Oulu → Vuosaari | ⚠️ ks. huomio D |
| movements | M20–M24 | FERRY (ei jobia), LOADED Vuosaari → Vantaa, LOADED Vantaa → Oulu (2 purkupaikkaa), EMPTY_TRAILER Oulu → Vuosaari (tarkoitus `REPOSITION`) | ⚠️ FERRY ilman jobia |
| handling_events | B, D | IOD ja POD Oulussa | ✅ |
| handling_events | C, E | UNLOAD Vantaa | ✅ |
| handling_events | F | IOP (= LOAD) Vantaa | ⚠️ ks. huomio B |
| ferry_bookings | FB-20 | saattamaton tuonti, vapautus (release) ja nouto | ⚠️ release-tila puuttuu |
| trailer_positions | TR-EU2 | merellä → Vuosaari (odottaa noutoa, ilmainen säilytysaika) → Vantaa → Oulu → tyhjä → Vuosaari | ✅ |
| resource_reservations | TR-EU2 | koko TRP-20 | ✅ |
| costs | TRP-20 | 500/510/520/530/540 lauttakulut, 212 shunttaus, 700 käsittely Vantaa, 210 linja Vantaa–Oulu, **211 tyhjä Oulu–Vuosaari** | ⚠️ R2: kenelle tyhjä paluu? |
| costs | orderit | myynti: B, D, E (tuonti DE → FI), F (kotimaa) | ✅ |

**Huomiot**

- **A. Tuontiorderin alku.** Orderin lastauspaikka on Saksassa, eikä IOP tapahdu Vuosaaressa. FleetFlow'n esimerkki alkaa Vuosaaresta, koska suunnittelijan työ alkaa sieltä. Malli ei saa olettaa, että ensimmäinen leg alkaa Suomesta. Jos mantereen nouto on toisen yksikön vastuulla, ensimmäinen leg voi olla "ulkoinen" (ei omaa Tripiä, IOP saadaan agentilta). V1:ssä riittää, että legillä voi olla `trip_id = NULL` ja tila "ulkoinen / toinen toimisto".
- **B. Osittainen käsittely.** Tässä skenaariossa jokainen order käsitellään kokonaan (UNLOAD tai REMAIN). Oikeassa elämässä yksi order jakautuu joskus: 20 lavasta 6 puretaan Vantaalla ja 14 jatkaa. Malli ei tue tätä ilman määrää käsittelyriveillä. Suositus v1:een: **osittainen käsittely = orderin jako kahdeksi orderiksi**, jotka viittaavat alkuperäiseen (`parent_order_id`), ja jakorivi kirjataan. Osittainen määrä legillä on huomattavasti monimutkaisempi eikä tuo v1:ssä vastaavaa hyötyä.
- **C. F:n IOP ja LOAD.** Kun order lastataan terminaalissa ensimmäistä kertaa, sama hetki on sekä IOP (kuorma vastaanotettu kuljetukseen) että LOAD. Suositus: kirjataan molemmat. IOP voi olla aiemmin, jos asiakas toi tavaran terminaaliin edellisenä päivänä. Tämä erottaa kuljetusajan terminaalissa seisomisesta.
- **D. Tyhjän palautus ja Job.** Jos DRV-02 ajaa Oulusta tyhjänä takaisin, JOB-21 ja palautus voivat olla samaa Jobia (sama kuljettaja ja auto). Erillinen JOB-22 tarvitaan vain, jos palautuksen tekee joku muu. Malli tukee molempia.
- **E. Tyhjän palautuksen kulu.** 211 tyhjä ajo Oulu–Vuosaari on Tripin kulu. Jos se jaetaan Tripin ordereille LDM:n mukaan, F (kotimaan lisäkuorma, joka maksaa kotimaan hintaa) saa osuuden palautuksesta, vaikka se ei aiheuttanut sitä. Tämä on R2:n ydinkysymys, ks. luku 2.
- **F. Tripin "tyyppi".** TRP-20 on samanaikaisesti tuontia ja kotimaata. `transport_type` kannattaa siirtää orderille tai johtaa ordereista. Tripin tyyppi on silloin vain näyttöä varten (esim. "tuonti + kotimaa").
- **G. Toimitus ≠ Tripin loppu.** B ja D toimitetaan Oulussa, ja ne on voitava laskuttaa heti. FP:n nykyinen malli ("Toimitettu" ja "Laskutettu" lukitsee tripin) estäisi palautuksen kulun 211 lisäämisen laskutuksen jälkeen. Tämä vahvistaa R3:n tarpeen.

**Skenaario 2: yhteenveto.** Gateway-logiikka toimii hyvin. Ongelmat ovat osittainen käsittely, orderin alku ulkomailla, tyhjän palautuksen kulujen jako ja Tripin lukitus.

---

### Skenaario 3: kuljettajan vaihto kesken päivän (ajoaika täyttyy), sama traileri

**Tilanne.** Trip `DEMO-TRP-30`: traileri `DEMO-TR-FI3`, linja Vantaa → Oulu. Kuljettaja DRV-03 on ajanut aamulla jakelua, ja hänen päivittäistä ajoaikaansa on jäljellä noin 3 h. Vantaa–Oulu vaatii selvästi enemmän.

Kolme käytännön vaihtoehtoa:

- **3a Kuljettajanvaihto samassa autossa.** DRV-04 tulee Jyväskylässä autoon, ja DRV-03 jää Jyväskylään (tai palaa kyydillä).
- **3b Trailerin vaihto eri autoon.** DRV-03 jättää TR-FI3:n Jyväskylän vaihtopaikalle ja DRV-04 hakee sen omalla autollaan.
- **3c Vastakkain ajo (yleinen kotimaan linjoilla).** DRV-03 ajaa Vantaa → Jyväskylä trailerilla TR-FI3. DRV-04 ajaa Oulu → Jyväskylä trailerilla TR-FI4 (eri Trip TRP-31, etelään). Kuljettajat vaihtavat trailerit, ja kumpikin ajaa takaisin kotiterminaaliinsa.

#### Syntyvät rivit (3a ja 3c, joissa erot näkyvät)

| Taulu | 3a: rivit | 3c: rivit | Arvio |
|---|---|---|---|
| trips | TRP-30 | TRP-30 (TR-FI3, pohjoiseen), TRP-31 (TR-FI4, etelään) | ✅ |
| jobs | JOB-30 (DRV-03, TRK-01), JOB-31 (DRV-04, **sama** TRK-01) | JOB-30 (DRV-03, TRK-01), JOB-32 (DRV-04, TRK-02) | ✅ R4: vaihto = uusi Job |
| movements | M30 JOB-30 LOADED Vantaa → JKL, trip 30 · M31 JOB-31 LOADED JKL → Oulu, trip 30 | M30 JOB-30 LOADED Vantaa → JKL, trip 30 · **M32 JOB-30 LOADED JKL → Vantaa, trip 31** · M33 JOB-32 LOADED Oulu → JKL, trip 31 · **M34 JOB-32 LOADED JKL → Oulu, trip 30** | ❌ jos `jobs.trip_id` on yksittäinen: JOB-30 koskee kahta tripiä |
| stops | JKL: kuljettajanvaihto (ei trailerin liikettä) | JKL: trailerinvaihto, molemmat trailerit irti ja kiinni | ❌ ei taulua |
| resource_reservations | TRK-01 koko päivän kahdelle Jobille, TR-FI3 koko Tripille | TRK-01, TRK-02, TR-FI3, TR-FI4 | ✅ |
| duty_events | DRV-03: jakelu + ajo Vantaa → JKL. DRV-04: matka vaihtopaikalle (ks. huomio B), ajo JKL → Oulu | DRV-03: ajo ennen vaihtoa ja sen jälkeen. DRV-04 samoin | ⚠️ sidottava kuljettajaan |
| handling_events | ei uusia: kuorma ei liiku trailerissa | ei uusia | ✅ oikein, vaihto ei ole käsittely |
| order_legs | ei muutoksia | ei muutoksia | ✅ oikein, kuljettajan vaihto ei ole reititysmuutos |
| costs | ostokulu jakautuu kahdelle Jobille (jos eri alihankkijat) | molempien Jobien kulut kahdelle Tripille: M32 kuuluu TRP-31:lle | ⚠️ kulu siirtymätasolla, ks. R5 |

**Huomiot**

- **A. Job ↔ Trip on N:M.** Vastakkain ajossa yhden kuljettajan Job kattaa kahden eri Tripin siirtymiä. Tämä on kotimaan linjaliikenteessä arkea, ei poikkeus. Siksi siirtymä viittaa Tripiin ja Jobiin, eikä Job viittaa suoraan yhteen Tripiin.
- **B. Ajoaika lasketaan kuljettajalle.** DRV-03:n aamun jakelu (eri Job) ja iltapäivän linja-ajo lasketaan yhteen samaan päivittäiseen ajoaikaan. 561/2006: päivittäinen ajoaika enintään 9 h, kahdesti viikossa 10 h. Tauko viimeistään 4,5 h ajon jälkeen, 45 min (voidaan jakaa 15 + 30 min). Nämä ovat FP:n kontekstissa ja vastaavat käsitystäni asetuksesta. Ne on silti tarkistettava säädöstekstistä ennen `feasibility.py`:tä, kuten suunnitelma jo edellyttää. Laskenta vaatii `duty_events.driver_id`:n, ja Jobin raja ei saa nollata laskuria.
- **C. Matka vaihtopaikalle.** Jos DRV-04 matkustaa Jyväskylään muulla kuin ohjaamallaan ajoneuvolla, matka-aika kuuluu asetuksen mukaan pääsääntöisesti muuhun työhön tai lepoon tietyin ehdoin. En ole varma tarkasta tulkinnasta (561/2006 art. 9 ja sen tulkinnat). Mallissa tarvitaan duty-tyyppi "matkustus vaihtopaikalle", ja sen luokittelu jätetään säännöksi, joka varmistetaan.
- **D. Muut rajat.** Päivittäinen ajoaika ei ole ainoa raja. Työaikadirektiivi 2002/15/EY rajoittaa viikkotyöaikaa (keskiarvo ja enimmäismäärä) sekä yötyötä. Vuorokausilepo (11 h, lyhennettynä 9 h rajoitetusti) ratkaisee, milloin DRV-03 voi aloittaa seuraavana päivänä. Plan Checkin pitää siis katsoa myös seuraavaa päivää eikä vain tätä Jobia.
- **E. Kaksimiehitys.** Vaihtoehto ajoajan riittämättömyyteen on kaksimiehitys, jossa molemmat kuljettajat ovat autossa koko ajan. Silloin Job = 1 auto + 2 kuljettajaa, ja lepoajan säännöt poikkeavat yksinajosta. R4-ehdotus ei kata tätä. Suositus: rajataan v1:n ulkopuolelle ja kirjataan tunnetuksi rajoitukseksi.
- **F. Valvonta vs. suunnittelu.** Toteutuneet ajoajat tulevat oikeasti ajopiirturilta. Demossa ne ovat simuloituja tai syötettyjä. Malliin tarvitaan `duty_events.source` (suunniteltu / ilmoitettu / ajopiirturi), jotta suunniteltua ja toteutunutta ei sekoiteta (FF-periaate).

**Skenaario 3: yhteenveto.** R4-ehdotus (vaihto = uusi Job) toimii. `jobs.trip_id`-yksittäisviite ei toimi. Aikalaskenta on sidottava kuljettajaan.

---

### Skenaario 4: Hanko–Tampere–Vantaa, paluu ja jatkolastaus purun aikana

**Tilanne.** Saattamaton tuontitraileri `DEMO-TR-EU4` (order `DEMO-ORDER-G`, koko kuorma) saapuu Hankoon. Kuljettaja DRV-06 (TRK-06) hakee sen ja vie Tampereelle, Demo Machinery Finland Oy:lle. Asiakkaan purku kestää noin 3 h. Kaksi varianttia:

- **4a Live-purku + jatkolastaus samaan traileriin.** DRV-06 odottaa purun. Sama asiakas lastaa heti perään vientikuorman (`DEMO-ORDER-H`, Tampere → Belgia) samaan TR-EU4:ään, ja DRV-06 vie sen Vantaan terminaaliin. Sieltä se jatkaa satamaan.
- **4b Drop & hook.** DRV-06 jättää TR-EU4:n purettavaksi, kytkee asiakkaan valmiiksi lastaaman trailerin `DEMO-TR-EU5` (order H) ja ajaa heti Vantaalle. TR-EU4 puretaan ja lastataan ilman kuljettajaa, ja toinen kuljettaja hakee sen myöhemmin.

#### Syntyvät rivit

| Taulu | 4a live | 4b drop & hook | Arvio |
|---|---|---|---|
| trips | TRP-40 (G, tuonti, TR-EU4). **TRP-41 (H, vienti, TR-EU4)** | TRP-40 (G, TR-EU4), TRP-41 (H, TR-EU5) | ⚠️ ks. huomio A |
| order_legs | G1 Hanko → Tampere (trip 40) · H1 Tampere → Vantaa (trip 41) · H2 Vantaa → Belgia | samat, mutta H1 trip 41 = TR-EU5 | ✅ |
| jobs | JOB-40 DRV-06: Hanko → Tampere, odotus, Tampere → Vantaa | JOB-40 DRV-06: Hanko → Tampere, vaihto, Tampere → Vantaa | ✅ |
| movements | M40 LOADED Hanko → Tampere (trip 40) · M41 LOADED Tampere → Vantaa (trip 41) | M40 sama · M41 LOADED Tampere → Vantaa **TR-EU5** (trip 41) · TR-EU4 myöhemmin toisella jobilla | ✅ jos siirtymä viittaa tripiin |
| stops | Tampere: saapuminen, purku alkaa ja päättyy, lastaus alkaa ja päättyy, lähtö | Tampere: TR-EU4 irti (drop), TR-EU5 kiinni (hook) | ❌ ei taulua |
| handling_events | G: UNLOAD → IOD, POD. H: IOP, LOAD | G: IOD vasta, kun asiakas ilmoittaa purun valmiiksi (ilman kuljettajaa). H: IOP jo ennen hakua | ⚠️ ks. huomio C |
| duty_events | DRV-06: purun ajan muuta työtä tai valmiusaikaa (ks. huomio D) | DRV-06: lyhyt kytkentä (muu työ) | ⚠️ |
| resource_reservations | TR-EU4 jatkuu TRP-40 → TRP-41 ilman väliä | TR-EU4 asiakkaalla, "varattu: purku/lastaus" | ✅ |
| trailer_positions | TR-EU4: Hanko → Tampere (lastattu → tyhjä → lastattu) → Vantaa | TR-EU4: Tampere asiakkaalla. TR-EU5: Tampere → Vantaa | ✅ |
| ferry_bookings | FB-40 tuonti: Hangon release, gate-out | sama | ⚠️ release-tila |
| costs | TRP-40: lauttakulut, 212 haku Hangosta, 800 odotusaika jos purku myöhästyy. TRP-41: 210 Tampere–Vantaa | TRP-41: ei odotusaikaa. TR-EU4:n seisontapäivät asiakkaalla (830 ylikäyttö?) | ⚠️ ks. huomio E |

**Huomiot**

- **A. Sama traileri, eri Trip.** Kun tyhjäksi purettu traileri lastataan uudelleen uudella kaupallisella kuormalla, kyse on uudesta Tripistä (vienti), vaikka traileri ja kuljettaja ovat samat. Muuten tuontikuorman Trip "jatkuu palautukseen" ja samaan Tripiin tulee vientiorder, jolloin tuonnin ja viennin kate sekoittuvat. Suositus R1:ssä: **Trip päättyy, kun traileri tyhjenee ja seuraava tapahtuma on uusi lastaus. Jos se lähtee tyhjänä, Trip jatkuu palautukseen.** Peräkkäiset Tripit samalla trailerilla voi ryhmitellä valinnaisella RoundTripillä (FF-periaate).
- **B. Saman tripin tyhjä vaihe 0 km.** Variantissa 4a TRP-40:llä ei ole tyhjää siirtymää lainkaan. Tämä on hyvä tapaus: KPI näyttää 0 tyhjää km:ä, mikä vastaa todellisuutta.
- **C. Tapahtuma ilman kuljettajaa.** Variantissa 4b purku tapahtuu, kun kuljettajaa ei ole paikalla, eikä FEC-kuittaus toimi (FP:n FEC-linkki on Trip-kohtainen ja kuljettajan käytössä). IOD:n lähteenä on asiakkaan ilmoitus tai terminaalin kuittaus. `handling_events.source` (FEC / terminaali / asiakas / manuaali) tarvitaan. Tämä vaikuttaa FP:n automaattiin "FEC delivery_completed → delivered_at".
- **D. Odotus purun aikana.** Variantissa 4a DRV-06 odottaa noin 3 h. Ajo- ja lepoaika-asetuksen kannalta odotus ei ole lepoa. Työaikadirektiivin mukaan ennalta tiedossa oleva odotus voi olla valmiusaikaa, ja muuten se on työaikaa. Yksityiskohdat (mm. milloin odotus "tiedetään etukäteen") on varmistettava, enkä anna niistä tarkkoja ehtoja. Mallissa: duty-tyyppi `AVAILABILITY` erikseen tyypistä `OTHER_WORK`, ja suunnittelija valitsee.
- **E. Seisonta ja ylikäyttö.** Variantissa 4b TR-EU4 seisoo asiakkaalla. Kenen laskuun? FP:ssä on koodi 830 (trailerin ylikäyttö) ja 400 trailervuokra FEC-päivien mukaan (#7). Uudessa mallissa seisontapäivät lasketaan `trailer_positions`-historiasta. Laskentasääntö (vapaa-aika tunneissa, laskutettava asiakkaalta) puuttuu.
- **F. Hangon release.** Saattamattoman tuontitrailerin voi hakea satamasta vasta, kun lauttayhtiö on vapauttanut sen (rahti maksettu, mahdollinen tulli selvitetty, noutotunnus). Malli tarvitsee `ferry_bookings`-tilan "vapautettu" ja noutotunnuksen, ja Plan Check varoittaa, jos Job on suunniteltu ennen vapautusta.

**Skenaario 4: yhteenveto.** Malli kestää molemmat variantit, kun Tripin päättymissääntö on selvä ja tapahtumalla voi olla muu lähde kuin kuljettaja. Drop & hook (live vs. drop -käsittely) on lisättävä orderin tai pysähdyksen ominaisuudeksi.

---

### Skenaario 5: ADR + thermo + perälauta samalla tripillä eri ordereilla

**Tilanne.** Trip `DEMO-TRP-50`, traileri `DEMO-TR-FI5` (Umpikaappi, kylmäkone), Vantaa → Tampere, kolme orderia:

| Order | Tavara | Vaatimus |
|---|---|---|
| DEMO-ORDER-J | maali, ADR luokka 3, UN-numerollinen, pakkausryhmä II, 600 kg pakattuna | ADR |
| DEMO-ORDER-K | elintarvike (maitotuotteet) | +2…+6 °C |
| DEMO-ORDER-L | kodinkoneet yksityiselle vastaanottajalle, ei lastauslaituria | perälauta purussa |

#### Syntyvät rivit

| Taulu | Rivi | Keskeiset kentät | Arvio |
|---|---|---|---|
| orders | J, K, L | J: adr = true. K: min +2, max +6, seuranta. L: tail_lift = true | ✅ |
| dangerous_goods | DG-1 (order J) | UN-nro, luokka 3, PG II, määrä, pakkaustyyppi, tunnelikoodi | ✅ |
| order_legs | J1, K1 | Vantaa → Tampere (vastaanottaja), trip 50 | ✅ |
| order_legs | L1 | Vantaa → **Tampereen terminaali**, trip 50, lopussa UNLOAD | ✅ korvaa FP:n `trips.tail_lift_unloading`-lipun |
| order_legs | L2 | Tampereen terminaali → vastaanottaja, jakelutrippi TRP-51, ajoneuvovaatimus perälauta | ✅ |
| trips | TRP-50 | adr, temperature_controlled **johdettuina** ordereista. Tripin oma lämpötila-asetus +2…+6 °C | ⚠️ ks. huomio C |
| trips | TRP-51 | kuorma-auto, jossa perälauta | ✅ |
| qualifications | DRV-07: ADR-ajolupa voimassa · TR-FI5: kylmäkone, huolto voimassa · jakeluauto: perälauta | ✅ |
| jobs | JOB-50 (DRV-07), JOB-51 (jakelu) | ✅ |
| handling_events | J, K: IOD Tampere. L: UNLOAD terminaali, LOAD jakeluautoon, IOD vastaanottaja | ✅ |
| costs | myynti: J 600 ADR-lisä, K 610 lämpötilalisä, L 700 käsittely + jakelun hinta | ✅ suoraan orderille |
| costs | kulut: TRP-50 210 ajo, 400 trailervuokra. TRP-51 jakelu. 700 terminaalikäsittely (L) | ⚠️ 700 on L:n aiheuttama, ei jaeta LDM:llä |

#### Yhteensopivuustarkistukset

| Tarkistus | Tulos tässä tapauksessa | Mallin valmius |
|---|---|---|
| ADR: kuljettajan pätevyys | Tarvitaanko täysi ADR vai riittääkö vapautus, ratkaisee ADR 1.1.3.6 -laskenta (kuljetusluokka × määrä, raja 1 000 pistettä). Kuljetusluokat ja kertoimet otetaan ADR:n taulukosta A, ei muistista | ❌ 1.1.3.6-laskenta puuttuu 2B-taulukosta |
| ADR: yhteenlastaus muiden ADR-aineiden kanssa | Ei muita ADR-aineita, joten ok | ⚠️ `dangerous_goods`-rivillä tarvitaan varoituslipukkeet, koska yhteenlastauskiellot katsotaan niistä (ADR 7.5.2) |
| ADR + elintarvike | ADR 7.5.4 erottaa myrkylliset (6.1), tartuntavaaralliset (6.2) ja vastaavasti merkityt aineet elintarvikkeista. Luokan 3 maali ei kuulu tähän ADR:n perusteella. **Moni asiakas ja elintarvikealan laatujärjestelmä kieltää silti kaikki vaaralliset aineet samassa tilassa elintarvikkeiden kanssa.** | ❌ tarvitaan yrityksen oma sääntö ("ADR + elintarvike = esto / varoitus") ADR:n sääntöjen lisäksi |
| ADR: ajoneuvo | Kappaletavarana kuljetettavalle ADR:lle ei käsitykseni mukaan tarvita ajoneuvon ADR-hyväksyntätodistusta (se koskee mm. säiliöitä). Varusteet ja oranssikilvet tarvitaan. Varmistettava | ⚠️ kaluston ADR-varustus `qualifications`-tauluun |
| ADR: tunnelit | Tripin tunnelirajoituskoodi on sen orderin koodi, joka on tiukin. Tällä reitillä ei tunneleita, mutta mantereella merkitsee | ✅ kenttä on `dangerous_goods`-taulussa, johdettava Tripille |
| ADR: lautta | Jos sama yhdistelmä menisi lautalle, lauttayhtiölle tehdään vaarallisten aineiden ilmoitus, ja matkustaja-aluksilla on rajoituksia. Ei tässä skenaariossa | ✅ 2B mainitsee IMDG-ilmoituksen |
| Lämpötila | Kaikilla saman tilan ordereilla on oltava yhteinen lämpötilaväli. J (maali) voi vaatia "suojattava pakkaselta", jolloin minimi on esim. +5 °C. Leikkaus +5…+6 °C on kapea mutta mahdollinen | ⚠️ tarvitaan leikkauslaskenta, ja orderin "ei lämpötilavaatimusta" ≠ "kestää minkä tahansa lämpötilan" |
| Lohkot / 2-koneinen | Jos K ja J vaativat eri lämpötiloja, tarvitaan 2-koneinen traileri ja lohko kullekin orderille. FP:ssä `required_compartment` on jo orderilla | ⚠️ lohko pitää kiinnittää legiin tai Tripin lohkoon, ei vain orderiin |
| Perälauta | FP:n linjaus (puoliperävaunuissa ei perälautaa, purku terminaalin kautta) toimii, ja uusi malli ilmaisee sen L1/L2-legeillä | ✅ parempi kuin nykyinen Trip-lippu |
| Lastausjärjestys | L puretaan ensin terminaalissa (UNLOAD), J ja K jatkavat. L on lastattava viimeisenä | ⚠️ vain varoitus v1:ssä |

**Huomiot**

- **A. Tripin liput johdetaan.** FP:ssä `trips.adr`, `trips.tail_lift` ja `trips.temperature_controlled` ovat erillisiä kenttiä. Kun sama Trip sisältää eri vaatimuksia, kentät joko johdetaan ordereista (kysely tai välimuisti) tai ne ovat ristiriidassa. Suositus: johdetaan, ei tallenneta. Tripillä tallennetaan vain trailerin **asetus** (lämpötila), joka on suunnittelijan päätös.
- **B. Perälautaflow siirtyy legeille.** `trips.tail_lift_unloading` ja `unloading_terminal_id` migroidaan L1/L2-legeiksi. Tarkistus "kaikki tail_lift-orderit kuitattu ennen vahvistusta" muuttuu muotoon "perälauta-orderilla on terminaalileg ja jakeluleg, jonka ajoneuvossa on perälauta".
- **C. Thermo tarkistetaan kalustoa vasten.** FleetFlow'n oletus "kaikki demokuljettajat osaavat thermon, ja tarkistus tehdään trailerityyppiä vasten" on käytännössä järkevä. ADR ja GDP tarkistetaan kuljettajan, auton ja yhtiön yhdistelmää vasten. Suositus: säilytetään tämä jako.

**Skenaario 5: yhteenveto.** Order- ja leg-taso toimii yhteensopivuudessa hyvin, kunhan Tripin liput johdetaan. Puuttuvat: ADR 1.1.3.6 -laskenta, varoituslipukkeet yhteenlastausta varten, yrityksen oma ADR + elintarvike -sääntö ja lämpötilavälien leikkaus.

---

### Skenaarioiden yhteenveto

| Löydös | S1 | S2 | S3 | S4 | S5 | Vakavuus |
|---|---|---|---|---|---|---|
| `stops`-taulu (pysähdykset trailer- ja Trip-tasolla) puuttuu | ❌ | ❌ | ❌ | ❌ | | **Korjattava ennen vaihetta 2** |
| Siirtymä ilman Jobia (lautta) | ❌ | ❌ | | ⚠️ | | **Korjattava ennen vaihetta 2** |
| Job ↔ Trip N:M | | | ❌ | ⚠️ | | **Korjattava ennen vaihetta 2** |
| `duty_events` kuljettajalle, ei Jobille | | | ❌ | ⚠️ | | **Korjattava ennen vaihetta 2** |
| Alihankkijan kuljettaja tuntematon | ❌ | | | | | Korjattava ennen vaihetta 2 (nullable) |
| Tripin päättymissääntö (tyhjenee → uusi lastaus = uusi Trip) | ⚠️ | ⚠️ | | ❌ | | Päätettävä R1/R3 |
| Tyhjän palautuksen kulujen jako | | ❌ | | | | Päätettävä R2 |
| Osittainen käsittely | | ⚠️ | | | | V1: orderin jako |
| Tapahtuman lähde (FEC / terminaali / asiakas) | | | | ❌ | | Kenttä, halpa |
| Lautan varauksen tilat (cut-off, release) | ⚠️ | ⚠️ | | ⚠️ | | V1: perustilat |
| Aikavyöhykkeet | ⚠️ | ⚠️ | | | | V1: UTC + `locations.timezone` |
| Tripin liput johdetaan ordereista | | ⚠️ | | | ⚠️ | V1 |
| ADR 1.1.3.6, varoituslipukkeet, ADR + elintarvike | | | | | ❌ | V1: tietokentät. Laskenta vaiheessa 4 |

---

## 2. Suositukset R1–R5

> **Muistutus: suositus ≠ päätös.** Toni päättää jokaisesta erikseen. Kustannus = mitä suositus maksaa toteutuksessa ja monimutkaisuudessa.

### R1: Orderin ja Tripin suhde

**Suositus.** Hyväksytään `order_legs` ehdotetussa muodossa ja täsmennetään neljä sääntöä:

1. **Legin raja = gateway, jossa orderille annetaan ohje** (UNLOAD / LOAD / REMAIN) tai jossa order vaihtaa Tripiä. Satama tai lautta ei ole legin raja, ellei kuormaa siellä käsitellä. Kuljettajan tai vetäjän vaihto ei ole legin raja.
2. **Yksi leg kuuluu yhteen Tripiin** (`trip_id`, voi olla NULL, kun leg on suunnittelematta tai ulkoinen). Jos leg pitäisi jakaa kahdelle Tripille, se on kaksi legiä.
3. **Trip = yhden lastitilan (trailerin tai kuorma-auton kopin) kuormattu kierros**: ensimmäisestä lastauksesta siihen, kun lastitila on tyhjä ja joko lastataan uudelleen (→ uusi Trip) tai palautettu (→ Trip päättyy). Remain LU = sama traileri = sama Trip. Cross Dock = eri traileri = eri Trip.
4. **Gateway Instructions johdetaan legeistä**: ohjelistan rivit ovat legit, joiden `to_location` on kyseinen gateway. Suunniteltu ohje tallennetaan legille, ja järjestelmä tarkistaa sen johdonmukaisuuden (sama Trip seuraavalla legillä ⇒ REMAIN on looginen; eri Trip ⇒ UNLOAD + LOAD).

Lisäksi: legien on muodostettava ketju (legin n `to_location` = legin n+1 `from_location`). Toteutuneita tapahtumia sisältävää legiä ei poisteta reitityksen muuttuessa (FF-periaate). Routingin versiointi jätetään v1:ssä yhteen aktiiviseen reititykseen ja muutoshistoriaan (audit trail).

**Perustelu.** Paperitesteissä tämä sääntö antoi jokaisessa skenaariossa yksiselitteisen vastauksen siihen, montako legiä ja Tripiä syntyy. Sääntö "Trip = trailerin kierros" vastaa sitä, miten liikenteenohjaaja käytännössä ajattelee keikkaa. Se myös erottaa tuonnin ja viennin katteen (S4). FP:n nykyinen `trips.trailer_id` tukee sitä jo.

**Mitä se maksaa.**
- Migraatio: `orders.trip_id` → yksi leg (lastauspaikka → purkupaikka). Kunnes frontend on siirretty, `orders.trip_id` voidaan tarjota näkymänä tai API-kenttänä ("ensimmäisen legin trip").
- Jokainen Tripiin liittyvä kysely (kapasiteetti, AddToTripModal, dashboard) kulkee legien kautta. Kapasiteetti lasketaan **legin aikavälillä**: Tripin LDM-käyttöaste voi vaihdella gatewayn jälkeen (S2: C ja E pois, F sisään).
- Trailerin vaihto poikkeustilanteessa (rikkoutuminen) = Tripin päättäminen ja uusi Trip, jossa UNLOAD/LOAD. Hieman raskas, mutta poikkeamat jäävät näkyviin, mikä on hyvä asia.
- Kuorma-autojakelu (ei traileria) vaatii, että "lastitila" voi olla myös auto. Pieni lisäys.

### R2: Kulujen jakoperuste

**Suositus.**

1. **Kulu kirjataan sille tasolle, jolla se syntyy:** Trip (lautta, linja-ajo, tyhjä palautus), siirtymä tai Job (alihankkijan ajo, shunttaus), leg (terminaalikäsittely), order (ADR-lisä, odotusaika asiakkaan vuoksi, perälautajakelu). `costs`-rivillä on täsmälleen yksi kohde.
2. **Jakoavain määritellään palvelukoodikohtaisesti** (taulu tai kenttä `services`-rivillä):
   - `LDM` (oletus): rahti, lautta, tiemaksut, trailervuokra
   - `DIRECT`: aiheuttajakohtainen kulu menee vain aiheuttavalle orderille (600, 610, 800, 810, perälauta-jakelu)
   - `EQUAL`: kiinteä per lähetys -maksu (esim. hallinnointi)
   - `WEIGHT`: valinnainen, esim. painoperusteiset satamamaksut
   - LDM:n ja painon yhdistelmä (rahdituspaino) vasta myöhemmin, koska muuntokerroin on yrityskohtainen sopimusasia. En anna sille vakioarvoa.
3. **Jako lasketaan, ei tallenneta erikseen**, kunnes order laskutetaan. Silloin orderin osuus **jäädytetään** (`cost_allocations`-rivit jakoperusteineen), jotta laskutetun orderin kate ei muutu, kun Tripille tulee myöhemmin kuluja.
4. **Pyöristys:** jaetut osuudet pyöristetään sentteihin `money.round_money()`-funktiolla ja jäännös annetaan suurimmalle osuudelle (largest remainder). Osuuksien summa = kulu, ja tähän tehdään testi (vrt. FP:n #20-testi).
5. **Tyhjän palautuksen kulu** (S2): oletuksena Tripin kuormatuille ordereille LDM:n mukaan. Asetuksen kautta se voidaan kohdistaa trailer poolin yleiskuluksi, jos yritys haluaa nähdä palautukset erikseen. Tämä on liiketoimintapäätös, ei tekninen kysymys, ks. avoimet kysymykset.

**Perustelu.** Tasan jako (FP nyt) vääristää LTL-katetta. Kahden lavan order saa saman lauttakulun kuin 12 lavan order. LDM on Suomen–mantereen trailerliikenteessä luonteva oletus, koska lautta hinnoittelee trailerin metreinä ja kapasiteetti loppuu tyypillisesti lattiametreistä. Aiheuttajakohtaisten kulujen jakaminen LDM:llä taas rankaisee ordereita, joilla ei ole mitään tekemistä kulun kanssa.

**Mitä se maksaa.**
- Uusi kenttä `services.allocation_basis` (tai erillinen taulu) + jakofunktio + testit
- Uusi taulu `cost_allocations` jäädytystä varten
- Raportointi monimutkaistuu: Tripin kate ≠ sen orderien katteiden summa, jos osa kuluista on poolin yleiskuluja. Dashboardiin tarvitaan selite
- FP:n TripDetail ("lauttakulu per order tasan") muuttuu

### R3: Elinkaari ja laskutuksen kohdistus

**Suositus.** Kolme erillistä tilaketjua ja selkeä lukitussääntö:

| Kohde | Tilat (ehdotus) | Mikä siirtää |
|---|---|---|
| Order | Avoin → Reititetty → Suunniteltu → Kuljetuksessa → Toimitettu → Laskutettu (+ Peruttu) | Reititetty: legit olemassa. Suunniteltu: kaikilla legeillä Trip. Kuljetuksessa: IOP. Toimitettu: viimeisen legin IOD. Laskutettu: lasku |
| Trip | Suunniteltu → Vahvistettu → Käynnissä → Kuormat toimitettu → Suljettu (+ Peruttu) | Kuormat toimitettu: kaikkien legien IOD tai UNLOAD tehty. Suljettu: traileri palautettu tai uusi Trip alkanut, ja ostokulut tarkistettu |
| Job | Avoin → Osoitettu → Vahvistettu → Käynnissä → Valmis (+ Peruttu) | Vahvistettu: kuljettaja tai alihankkija kuitannut |

- **Myynti laskutetaan orderilta.** Laskutettavuuden ehto v1:ssä: order Toimitettu. POD-vaatimus asiakaskohtaisena asetuksena myöhemmin.
- **Ostot kohdistuvat Tripiin, legiin tai Jobiin** (R2).
- **Lukitus:** "Laskutettu" lukitsee **orderin myyntirivit ja jäädytetyt kustannusosuudet**, ei Tripiä. Trip lukittuu, kun se on Suljettu. Myöhemmin tuleva ostolasku tai korjaus Suljetulle Tripille tehdään vastakirjauksena (`reversal_of_id`, FP #7 on jo suunniteltu).
- **FP:n automaattien siirto:** 400-rivit Tripin vahvistuksessa säilyvät Tripillä. `delivered_at` ja OTD siirtyvät orderin IOD-tapahtumaan. Odotusaika 800 syntyy pysähdyksen tai käsittelytapahtuman perusteella ja kohdistuu orderille (DIRECT).

**Perustelu.** S2 ja S4 osoittivat, että orderin toimitus ja Tripin loppu ovat eri hetkiä. Jos laskutus lukitsee Tripin, joko laskutus viivästyy palautukseen asti (huono kassavirralle) tai palautuksen kulu jää kirjaamatta (huono katteelle). Erillinen Job-ketju on tarpeen, koska alihankkijan kuittaus on eri asia kuin Tripin vahvistus.

**Mitä se maksaa.**
- Statusmigraatio: nykyinen `trips.status` jaetaan. Kuvaus: Suunniteltu/Vahvistettu/Käynnissä → sama Tripillä. Toimitettu → Trip "Kuormat toimitettu" + orderit Toimitettu. Laskutettu → orderit Laskutettu + Trip Suljettu
- `confirm-invoice`-endpoint muuttuu orderikohtaiseksi
- Kolme tilakonetta tarkoittaa kolme testisarjaa ja enemmän käyttöliittymän tilanäyttöä. Tämä on suurin yksittäinen kustannus R1–R5:ssä, mutta ilman sitä S2 ja S4 eivät toimi

### R4: Jobin kuljettajarajaus

**Suositus.** Hyväksytään ehdotus "Job = yhden ajoneuvon ja yhden kuljettajan työ, ja vaihto luo uuden Jobin" seuraavin täsmennyksin:

1. **Job ↔ Trip on N:M siirtymien kautta.** Jobilla ei ole yksittäistä `trip_id`:tä (S3 vastakkain ajo, S4 drop & hook).
2. **`jobs.driver_id` saa olla tyhjä**, kun työ on annettu alihankkijalle, joka nimeää kuljettajan itse (S1 mantereen osuus). Silloin Plan Check ilmoittaa "ajoaikatarkistus alihankkijan vastuulla" eikä anna väärää vihreää.
3. **Ajo- ja työaika sidotaan kuljettajaan** (`duty_events.driver_id`), ei Jobiin. Toteutettavuus lasketaan kuljettajan aikajanalta yli Jobien ja päivien (viikko ja kaksi viikkoa).
4. **Kuljettajan päivä (vuoro) ≠ Job.** Yhdessä vuorossa voi olla useita Jobeja (aamun jakelu + iltapäivän linja). Vuoroa ei tarvitse olla omana tauluna v1:ssä. Se voidaan johtaa duty_events-tapahtumista.
5. **Kaksimiehitys rajataan v1:n ulkopuolelle** ja kirjataan tunnetuksi rajoitukseksi. Myöhemmin `job_crew`-taulu (Job, kuljettaja, rooli).

**Perustelu.** Yksi kuljettaja per Job pitää toteutettavuusmoottorin yksinkertaisena ja vastaa sitä, miten Suomen kotimaan ja vientiliikenteen jako tehdään. Täsmennykset 1–3 eivät ole valinnaisia. Ilman niitä S1 ja S3 eivät mallinnu oikein.

**Mitä se maksaa.**
- Jobin tiedot kootaan siirtymistä (reitti, Tripit), joten kyselyt ovat raskaampia kuin suora `trip_id`
- Plan Check tarvitsee "osittainen tarkistus" -tuloksen alihankkijajobeille
- Kaksimiehityksen lisääminen myöhemmin on yksi migraatio (`driver_id` → `job_crew`). Hallittava, koska Alembic on käytössä

### R5: Order Leg vs. fyysinen siirtymä

**Suositus.** Hyväksytään jako (Order Leg = kaupallinen reititys, siirtymä = fyysinen ajo) seuraavin täsmennyksin:

1. **Siirtymä on oma taulu `movements`**: `job_id` (NULL lautalla tai ulkoisella siirrolla), `trip_id` (pakollinen kuormatulla ja Tripin tyhjällä siirtymällä, NULL SOLO-ajolla), `trailer_id`, `from_stop`, `to_stop`, ajotyyppi (SOLO / EMPTY_TRAILER / LOADED_TRAILER), kulkumuoto (ROAD / FERRY), tarkoitus (esim. RETURN_TO_BASE, REPOSITION), suunniteltu ja toteutunut km sekä aika.
2. **Pysähdykset (`stops`) ovat oma taulu** (FleetFlow'n Node/Stop): sijainti, tyyppi (lastaus, purku, gateway, gate-in, gate-out, trailerin irti tai kiinni, kuljettajanvaihto, korjaamo, pysäköinti, sähköön kytkentä), live vai drop, aikaikkuna, suunniteltu, ennustettu ja toteutunut saapumis- ja lähtöaika.
3. **Legin ja siirtymän yhteys johdetaan** Tripin ja pysähdysten kautta (leg on Tripillä, Tripin siirtymät kulkevat legin `from`–`to`-välin). Erillistä liitostaulua ei tehdä. Näin ajotiedolla on yksi lähde (FF-periaate: ei kahta päällekkäistä ajotietolähdettä).
4. **Kilometrit ja ajoaika lasketaan vain siirtymistä** (ehdotuksen mukaisesti). Legin "km" on johdettu tieto, ja kaksoislaskenta estyy (FF-periaate RETURN_TO_BASE).
5. **Lautta on siirtymä, ja `ferry_bookings` viittaa siihen.** Saattaen ajettavassa lauttamatkassa siirtymällä on Job ja kuljettajalle syntyy duty-tapahtuma (lepo tietyin ehdoin, ks. avoimet kysymykset). Saattamattomassa siirtymässä ei ole Jobia.

**Perustelu.** Ehdotuksen muotoilu "fyysinen siirtymä on Jobin osa" kaatuu saattamattomaan lauttaan, joka on Suomen–mantereen liikenteen päätuote (S1, S2, S4). Pysähdykset ovat se paikka, johon trailerin tapahtumat (satama, vaihto, drop) kuuluvat. Ilman niitä ne valuvat joko `handling_events`-tauluun (kopioituna jokaiselle orderille) tai vapaaseen tekstiin.

**Mitä se maksaa.**
- Kaksi lisätaulua (`stops`, `movements`) vaiheen 2 Alembic-revisioihin. Luvun 3 taulukkoa on päivitettävä.
- Johdettu leg–siirtymä-yhteys vaatii huolellisen kyselyn ja testit (mm. Remain LU, jossa yksi siirtymä palvelee kahta saman orderin legiä peräkkäin).
- FleetFlow'n demodatan Node-tyypit ovat jo valmiina listana, joten käsitteellistä työtä ei tarvita.

### Sivuhuomiot R6 ja R7

- **R6 (`drivers`):** ehdotus on hyvä. Lisää `drivers.home_location_id` (kotiinpaluu ja viikkolepo) ja `drivers.employment_type` (oma / alihankkijan nimetty). Kortit ja pätevyydet voimassaoloineen `qualifications`-tauluun, kuten ehdotettu.
- **R7 (Gateway Instructions):** sama dokumentti, ja R1:n sääntö 4 tekee siitä legeistä johdetun. Versiointi, jakelu ja kuittaus ovat FF:ssä avoimia. V1:ssä riittää versionumero ja "muuttunut lähetyksen jälkeen" -varoitus.

---

## 3. Puuttuvat toimialuekäsitteet (luku 2B)

Arvio: **V1** = kuuluu ensimmäiseen yhdistettyyn versioon (vaiheet 2–6) · **V1-kenttä** = vain tietokenttä tai lippu v1:ssä, logiikka myöhemmin · **Myöh.** = myöhempi vaihe · **Ei** = ei portfolio-TMS:n laajuudessa

| Käsite | Mitä se on | Miksi merkitsee | Arvio |
|---|---|---|---|
| **Pysähdykset (Stops / Nodes)** | Trailerin ja Tripin fyysiset tapahtumapaikat | S1–S4: ilman niitä satama, vaihto ja drop eivät mallinnu | **V1** (taulu, ks. R5) |
| **Saattamattoman trailerin satamakäsittely** | Cut-off (eri kuin check-in), gate-in ja gate-out, release (vapautus) ja noutotunnus, satamassa seisonta ja ilmainen säilytysaika, trailerin kuntotarkastus satamassa | S1, S2, S4. Toimituksen ajoitus riippuu vapautuksesta | **V1**: varauksen tilat (varattu → gate-in → laivassa → purettu → vapautettu → noudettu) + cut-off. **Myöh.**: säilytysmaksut ja vauriodokumentit |
| **Lauttavarauksen poikkeamat** | Varaus myöhästyy, odotuslista, uudelleenvaraus, no-show-maksu | Yleinen, vaikuttaa kuluihin ja toimitusaikaan | **Myöh.** (V1: tila "myöhästynyt" + manuaalinen uudelleenvaraus) |
| **Tullaus** | Vienti- ja tuonti-ilmoitukset EU:n ulkopuolelle (FP:n demossa CH- ja NO-vastaanottajia), MRN-numero, poistumisvahvistus | Kuorma ei voi lähteä tai sitä ei voi luovuttaa ilman tulliselvitystä. Koskee jo nykyistä demodataa | **V1-kenttä**: `customs_required`, tulliasiakirjan viite, varoitus. Tulli-integraatio **Ei** |
| **T1-passitus** | Tullivalvonnassa oleva kuljetus, takaus, määräaika, lähtö- ja määrätoimipaikka | Ilman passituksen päättämistä syntyy tullivelka. Liittyy EU:n ulkopuolisiin reitteihin | **Myöh.**: V1:ssä vain asiakirjatyyppi tullauskentässä |
| **Lavanvaihto / lavasaldo** | EUR-lavojen vaihto lastaus- ja purkupaikoilla, lavakuitti, saldo asiakkaittain ja kuljetusliikkeittäin | Arkipäivää kotimaassa ja EU:ssa. Riitoja ilman kirjanpitoa | **V1-kenttä**: orderilla `pallet_exchange` + vaihdetut määrät käsittelytapahtumassa. **Myöh.**: saldokirjanpito |
| **Poikkeamat ja reklamaatiot** | Vaurio, vajaus, myöhästyminen, CMR-huomautus, korvausvaatimus | FP:n backlogissa "Poikkeamanhallinta". CMR:n vastuunrajoitus (8,33 SDR/kg bruttopainosta) on tunnettu, mutta korvauskäsittely on oma prosessinsa | **V1**: `deviations`-taulu (tyyppi, order, leg tai pysähdys, kuvaus, kuva). **Myöh.**: reklamaatioprosessi ja korvauslaskenta |
| **Sinetit** | Sinettinumero lastauksessa, tarkistus purussa | Saattamaton traileri on lähes aina sinetöity. Rikkoutunut sinetti on reklamaatioperuste | **V1-kenttä** (käsittelytapahtumalla), halpa |
| **Live vs. drop -käsittely** | Kuljettaja odottaa lastauksen ja purun, tai jättää trailerin | S4: vaikuttaa kuljettajan aikaan, trailerin varaukseen ja odotusaikakuluun | **V1** (pysähdyksen kenttä) |
| **Aikavyöhykkeet** | FI ja DE eri aikavyöhykkeillä, kesäaika | S1: IOP–IOD-aika väärin ilman | **V1**: UTC kannassa + `locations.timezone` |
| **Tapahtuman lähde** | FEC, terminaali, asiakas, manuaali, ajopiirturi | S4: purku ilman kuljettajaa. Suunniteltu ja toteutunut erotetaan (FF-periaate) | **V1-kenttä** |
| **Orderin jako (osittainen käsittely)** | Yksi order jaetaan kahdeksi, ja viittaus alkuperäiseen säilyy | S2. FF:n avoin kohta | **V1**: `parent_order_id` + jakotoiminto |
| **ADR 1.1.3.6 -vapautuslaskenta** | Kuljetusluokka × määrä, 1 000 pisteen raja | Ratkaisee, tarvitaanko ADR-ajolupa ja täydet varusteet | **V1-kenttä** (kuljetusluokka `dangerous_goods`-riville). Laskenta vaiheessa 4 |
| **ADR-varoituslipukkeet ja yhteenlastaus** | Lipukkeet aineittain, yhteenlastauskieltotaulukko | S5. Luokka ei yksin riitä | **V1-kenttä**. Tarkistus vaiheessa 4 |
| **Yrityksen omat kuormaussäännöt** | Esim. ADR + elintarvike kielletty samassa tilassa, ei kemikaaleja ruoan kanssa | S5. Tiukempi kuin ADR | **Myöh.** (sääntötaulu). V1: kovakoodattu varoitus |
| **Lämpötilavälien leikkaus** | Saman tilan ordereiden yhteinen lämpötilaväli | S5 | **V1** (logiikka, ei taulua) |
| **Ro-ro-kelpoisuus** | Traileri kelpaa saattamattomana lautalle (kiinnityspisteet ym.) | S1b Remain LU | **V1-kenttä** (`qualifications`) |
| **Lastausjärjestys** | Mikä lastataan viimeisenä, jotta sen saa ensin ulos | S1b, S5 | **Myöh.** (V1: varoitus) |
| **Alihankinnan ostohinnasto** | Kuljetusliikkeiden sopimushinnat (km, reitti, kiinteä) | Kulut syötetään nyt käsin. Ehdotusmoottori (kerros 2) tarvitsee ostohinnan | **Myöh.** (vaihe 6) |
| **Ostolaskujen täsmäytys** | Alihankkijan lasku vs. kirjattu kulu | R3: Tripin sulkeminen | **Myöh.** |
| **Kabotaasi** | Ulkomaisen liikenteenharjoittajan kotimaan kuljetukset Suomessa. Rajoitukset kuljetusten määrästä ja ajanjaksosta | Jos mantereen alihankkija ajaa Vuosaari–Oulu (S2), rajoitukset koskevat | **Myöh.**: varoitus. Tarkat luvut on varmistettava liikkuvuuspaketin säädöksistä, enkä esitä niitä tässä |
| **Kuljettajien lähettäminen** | Posting-ilmoitukset kansainvälisessä liikenteessä | Hallinnollinen, ei suunnittelua | **Ei** |
| **Kuljettajan kotiinpaluu ja viikkolepopaikka** | Liikkuvuuspaketin kotiinpaluuvelvoite, säännöllinen viikkolepo ei ohjaamossa | Mantereella ajavat omat kuljettajat | **Myöh.** (vaihe 4). Tarkat aikarajat varmistettava |
| **Kuljettajan saatavuus** | Vuorolista, loma, vapaapäivät | Ehdotusmoottori ei voi ehdottaa lomalla olevaa | **V1** (yksinkertainen poissaolotaulu tai `resource_reservations`-tyyppi) |
| **Ajopiirturidata** | Toteutuneet ajo- ja lepoajat | Toteutunut vs. suunniteltu | **Ei** integraatiota. V1: `duty_events.source` |
| **Kuormansidonta** | Sidontavälineet, EN 12195-1 | Turvallisuus ja vastuu. Ei suunnitteluydin | **Ei** v1 (vapaa teksti ohjeissa) |
| **Asiakkaan ajanvaraus (slot booking)** | Purkuaika varattava jakelukeskuksesta | Orderilla on jo `time_slot_*` ja `pre_advise` | ✅ olemassa, tarkista vain, että siirtyy legeille |
| **e-CMR** | Sähköinen rahtikirja | Dokumenttimoduuli | **Myöh.** |
| **Orderin peruutus ja muutos** | Peruutus suunnittelun jälkeen, peruutusmaksu, muutoshistoria | Elinkaari (R3) | **V1**: tila Peruttu + audit trail. Maksu **Myöh.** |

Suositus D8:n hengessä: lisätään kaikki yllä olevat lukuun 2B (mitään ei pudoteta), mutta merkitään v1-rajaus näkyvästi, jotta "kaikki mukaan" ei tarkoita "kaikki heti".

---

## 4. Avoimet kysymykset Tonille

Nämä vaativat liikenteenohjaajan päätöksen tai kokemuksen, eikä niitä voi ratkaista dokumenteista:

1. **Tripin raja (R1):** Hyväksytkö säännön "Trip = yhden trailerin kuormattu kierros; tyhjenee ja lastataan uudelleen → uusi Trip"? Vai haluatko, että esim. tuonti + heti perään vienti samalla trailerilla on yksi Trip (S4a)?
2. **Legin raja (R1):** Riittääkö gateway (terminaali) legin rajaksi, vai haluatko sataman omaksi legikseen esim. siksi, että satamaosuus laskutetaan joskus erikseen?
3. **Tyhjän palautuksen kulu (R2):** Kuuluuko se Tripin ordereille (LDM:n mukaan) vai trailer poolin yleiskuluihin? Miten se on tehty työpaikoillasi?
4. **Jakoperuste (R2):** Onko LDM oikea oletus myös lautalle, vai käytetäänkö käytännössä rahdituspainoa (LDM/paino-muunnosta)? Jos käytetään, mikä muuntokerroin demoon? (Sopimuskohtainen arvo, en arvaa sitä.)
5. **Laskutuksen ehto (R3):** Laskutetaanko order IOD:n jälkeen vai vasta POD:n saavuttua? Onko se asiakaskohtaista?
6. **Alihankkijan kuljettaja (R4):** Riittääkö demossa "kuljettaja ei tiedossa, tarkistus alihankkijan vastuulla"? Vai halutaanko alihankkijalta ilmoitettu kuljettaja ja tunnit?
7. **Kaksimiehitys (R4):** Voidaanko se rajata v1:n ulkopuolelle?
8. **Osittainen käsittely:** Riittääkö v1:ssä orderin jako kahdeksi orderiksi (S2)? Kuinka usein tämä on oikeasti tapahtunut työssäsi?
9. **Lauttamatka kuljettajan lepona:** Saattaen ajettavat lautat (esim. kuljettaja mukana Travemündeen) vaikuttavat lepoaikoihin. 561/2006 sallii lauttamatkan aikaisen levon tietyin ehdoin (mm. makuupaikka tai hytti), ja ehtoja on muutettu liikkuvuuspaketissa. Tarkat ehdot on luettava säädöksestä ennen toteutusta. Ovatko saattaen ajettavat lautat demon laajuudessa vai vain saattamattomat?
10. **ADR + elintarvike:** Onko yrityskohtainen esto (S5) demossa esto 🔴 vai varoitus 🟠?
11. **Perälauta:** Pysyykö FP:n linjaus "puoliperävaunussa ei koskaan perälautaa, aina terminaalin kautta"? Vai pitääkö varautua perälautatraileriin tai suoraan jakeluun kuorma-autolla?
12. **Tullaus:** FP:n demossa on CH- ja NO-vastaanottajia. Riittääkö v1:ssä lippu + asiakirjaviite + varoitus?
13. **Satamakäsittely:** Mitkä saattamattoman trailerin tilat ovat sinun kokemuksesi mukaan suunnittelijalle oikeasti tärkeitä (cut-off, release, noutotunnus, säilytysaika)? Puuttuuko listasta jotain?
14. **Luvun 3 taulukko:** Hyväksytkö, että `stops` ja `movements` lisätään vaiheen 2 tietomalliin ennen ensimmäistä Alembic-revisiota?

---

## Liite: säädöksiin liittyvät varaumat

Tässä raportissa mainitut säädösviittaukset ovat yleistason kuvauksia, eivät toteutuksen määrittelyjä. Ennen `feasibility.py`:tä (vaihe 4) jokainen raja luetaan voimassa olevasta säädöstekstistä:

| Aihe | Mitä tässä raportissa oletetaan | Varmuus |
|---|---|---|
| 561/2006 päivittäinen ajoaika 9 h (2×/vko 10 h), tauko 45 min 4,5 h:n jälkeen (15 + 30), vuorokausilepo 11 h (lyhennetty 9 h rajoitetusti) | Vastaa FP:n kontekstia ja käsitystäni | Hyvä, mutta tarkistettava |
| 561/2006 viikko- ja kahden viikon ajoaika | Mainitaan, lukuja ei käytetä raportissa | Tarkistettava |
| Lauttamatkan aikainen lepo (art. 9) ja liikkuvuuspaketin muutokset | Ehdot olemassa, yksityiskohdat ei varmoja | **Epävarma** |
| Matkustus vaihtopaikalle | Luokittelu riippuu tilanteesta | **Epävarma** |
| 2002/15/EY valmiusaika vs. työaika odotuksessa | Ennalta tiedossa oleva odotus voi olla valmiusaikaa | Kohtalainen, tarkistettava myös kansallinen laki |
| ADR 1.1.3.6 (1 000 pistettä), 7.5.2 yhteenlastaus, 7.5.4 elintarvikkeet | Rakenne oikein, kertoimet ja taulukot luettava ADR:stä | Hyvä rakenteen osalta |
| ADR-hyväksyntätodistus ei koske kappaletavaraa | Käsitykseni mukaan näin | Tarkistettava |
| Painorajat DE 40 t, yhdistetyn kuljetuksen 44 t ro-ro-yhteydessä | 44 t:n soveltuvuus ro-ro-kuljetukseen epävarma | **Epävarma** |
| Kabotaasin ja kotiinpaluun aikarajat | Ei esitetty lukuja | Tarkistettava |
| CMR 8,33 SDR/kg | Tunnettu vastuunrajoitus | Hyvä |
