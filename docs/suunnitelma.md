# FleetFreight TMS: Freight Planner + FleetFlow → yhdistetty TMS

Päivitetty: 14.11.2026 (v2: uusi sovellus, siirtoinventaario ja paperitestit) · Tila: luonnos, odottaa Tonin hyväksyntää
Lähteet: Freight Planner `main` (`1128d19`), FleetFlow `main` (`f9a04f0`),
FleetFlow PR #6 (draft) ja issuet #7–#12.

---

## 1. Tavoite

Yksi toimiva, tuotantotasoinen TMS, jossa yhdistyvät:

- **kuormasuunnittelu** (Freight Planner): mitä kuljetetaan, millä keikalla, mihin hintaan ja millä katteella
- **resurssisuunnittelu** (FleetFlow): kuka ajaa, milloin ja missä järjestyksessä, ja ehtiikö kuljettaja ajo-, työ- ja lepoaikojen puitteissa

Järjestelmä pysyy portfolioprojektina: julkinen repo, vain fiktiivinen demodata ja live-demo.
Periaate: **järjestelmä laskee, tarkistaa ja ehdottaa; liikenteenohjaaja päättää.**

---

## 2. Päätösrekisteri

Tilat: **Hyväksytty** · **Ehdotus** (odottaa Tonin päätöstä) · **Oletus** (käytetään, kunnes Toni päättää toisin) · **Avoin** (vaatii selvityksen)
Ehdotusta ei merkitä hyväksytyksi ilman Tonin päätöstä. Korvattu päätös säilyy historiassa.

| # | Päätös | Tila | Lähde |
|---|---|---|---|
| D1 | FleetFlow ja Freight Planner yhdistetään yhdeksi TMS:ksi | Hyväksytty 14.11.2026 | Toni, chat |
| D2 | Tavoite on tuotantotasoinen TMS kuljetusten optimoinnilla, ja se säilyy portfolioprojektina | Hyväksytty 14.11.2026 | Toni, chat |
| D3 | **Uusi sovellus** (uusi repo), johon siirretään molempien toimivat ja testatut osat. Vanhaa rakennetta ei siirretä yhteensopivasti, koska data on demodataa. Vanhat repot arkistoidaan linkin kanssa. *(Korvaa 14.11. luonnoksen "pohjana Freight Plannerin repo".)* | Hyväksytty 14.11.2026 | Toni, chat |
| D4 | Moduulijako: kuormasuunnittelu omistaa Orderin, Order Routingin, Tripin, kulut, hinnoittelun ja dokumentit. Resurssisuunnittelu omistaa Jobin, kuljettajan päivän, aikalaskennan ja toteutettavuuden | Hyväksytty 14.11.2026 | luku 3 |
| D5 | Yksi sääntötiedosto: `CLAUDE.md` on päälähde, ja `AGENTS.md` (Codex) viittaa siihen | Hyväksytty 14.11.2026 | luku 6 |
| D6 | Frontend siirretään Create React Appista Viteen. Kieli pysyy JavaScriptinä, TypeScript ei ole päätetty | Korvattu → D11 | FF #11 |
| D7 | FleetFlow'n koodikehitys jäädytetään FF-002E:tä lukuun ottamatta. GitHub Pages -demo säilyy, kunnes yhdistetty demo on julkaistu | Ehdotus | luku 5 |
| D8 | Kaikki kummankin projektin toimialuekäsitteet tulevat mukaan (luku 2B). Mitään ei pudoteta, ja päällekkäiset toteutukset yhdistetään | Hyväksytty 14.11.2026 | Toni, chat |
| D9 | Kaksi vaihdettavaa teemaa koko sovellukseen: **Business Light** (beige-harmaa vaalea teema, sininen aksentti) ja **Control Dark** (Freight Plannerin tumma, oranssi aksentti). Valinta tallentuu käyttäjälle | Hyväksytty 14.11.2026 | Toni, chat |
| D10 | Tyylit toteutetaan CSS-muuttujina (design tokenit), ei inline-väreinä. Freight Plannerin "inline CSS kaikkialla" -sääntö ei siirry uuteen sovellukseen, koska teemanvaihto vaatii muuttujat | Hyväksytty 14.11.2026 | D9 |
| D11 | Uuden sovelluksen perusta: React + TypeScript + Vite frontendissä, Python backendissä. Korvaa D6:n "kieli pysyy JavaScriptinä" | Hyväksytty 14.11.2026 | Toni, chat |
| D12 | Backend FastAPI + Pydantic + SQLAlchemy + Alembic, tietokanta PostgreSQL (Docker). TypeScript-tyypit generoidaan backendin OpenAPI-kuvauksesta (`openapi-typescript`). Testit pytest + Vitest | Hyväksytty 14.11.2026 | D11 |
| D13 | **Node–Leg-malli (Tonin TMS-käytäntö):** legit ovat aina kahden peräkkäisen Noden välissä. Node on jokainen fyysinen tai suunnittelun piste: terminaali, korjaamo, katsastus, pesupaikka, lastauspaikka (asiakas), purkupaikka (vastaanottaja), satama lähtö, satama saapuminen. **Kun traileri ja vetäjä liitetään keikalle, niiden lähtöpaikoista tulee omat Nodet.** Korvaa R1:n ja R5:n aiemmat ehdotukset (gateway-raja, erillinen Order Leg) | Hyväksytty 14.11.2026 | Toni, chat |
| D14 | Trip = trailerin kuormattu kierros. Remain LU = sama Trip, Cross Dock = eri Trip | Hyväksytty 14.11.2026 | Toni, chat |
| D15 | Tyhjän trailerin palautuksen kulu jaetaan keikan ordereille LDM:n mukaan | Hyväksytty 14.11.2026 | Toni, chat |
| D16 | Order on laskutettavissa toimituksen (IOD) jälkeen | Hyväksytty 14.11.2026 | Toni, chat |
| D17 | Keikan alun siirtymät (vetäjä trailerille, tyhjä traileri lastaukseen) kuuluvat samaan Tripiin. Niillä on oma veloitus ajotyypin mukaan: **vetäjä ilman traileria (SOLO / empty truck)** ja **veto tyhjällä trailerilla (EMPTY_TRAILER)** omilla hinnoillaan. Vastaa Freight Plannerin palvelukoodeja 210/220 kuormattu, 211/221 tyhjä, 212/222 vetoyksikkö | Hyväksytty 14.11.2026 | Toni, chat |
| D18 | **Vetäjänvaihto Nodessa:** missä tahansa Nodessa vetäjän 1 toiminta voidaan katkaista ja liittää vetäjä 2. Vetäjän 1 Job päättyy ja vetäjän 2 Job alkaa, Trip jatkuu (sama traileri). Ostokulut kohdistuvat legeittäin kunkin vetäjän kuljetusyhtiölle | Hyväksytty 14.11.2026 | Toni, chat |
| D19 | Jaettavien kulujen oletusjakoperuste on LDM, ja palvelukoodikohtainen poikkeus on mahdollinen | Oletus (Toni ei vastannut 14.11.) | paperitestit R2 |
| D20 | Alihankkijan keikalla kuljettaja voi olla tyhjä. Plan Check näyttää "ajoaikatarkistus alihankkijan vastuulla" | Oletus (Toni ei vastannut 14.11.) | paperitestit R4 |
| D21 | Kaksimiehitys ei ole ensimmäisessä versiossa (yksi kuljettaja per Job) | Oletus (Toni ei vastannut 14.11.) | paperitestit R4 |
| D22 | Osittainen käsittely: order jaetaan kahdeksi, ja molemmat osat viittaavat alkuperäiseen Order ID:hen | Hyväksytty 14.11.2026 | Toni, chat |
| D23 | Ensimmäisessä versiossa ovat sekä saattamattomat että saattaen ajettavat lautat. Lauttamatkan aikainen lepo huomioidaan ajoaikalaskennassa (ehdot luetaan 561/2006:sta ennen toteutusta) | Hyväksytty 14.11.2026 | Toni, chat |
| D24 | ADR ja elintarvike samalla trailerilla on esto, jota liikenteenohjaaja ei voi ohittaa | Hyväksytty 14.11.2026 | Toni, chat |
| D25 | Perälauta: puoliperävaunussa ei ole perälautaa, joten purku tehdään aina terminaalin kautta (terminaaliflow) | Hyväksytty 14.11.2026 | Toni, chat |
| D26 | Tullaus ensimmäisessä versiossa: tullattava-lippu orderilla, asiakirjaviite ja Plan Check -varoitus puuttuvasta tullauksesta. Tulliasiakirjat ja T1 myöhemmin | Hyväksytty 14.11.2026 | Toni, chat |
| D27 | Saattamattoman trailerin satamakäsittely: cut-off-aika, vapautus (release), noutotunnus / PIN, säilytysaika ja satamamaksut sekä **sähköön kytkentä satamassa (kyllä / ei)** thermotrailereille | Hyväksytty 14.11.2026 | Toni, chat |
| D28 | Raha tallennetaan PostgreSQL:ssä kokonaislukuina (`*_cents` ×100, `*_e4` ×10 000), laskenta `Decimal`. Freight Plannerin `money.py` ja sen testit siirtyvät muuttamatta | Hyväksytty 14.11.2026 | Toni, chat |
| D29 | Uuden projektin nimi on **FleetFreight TMS** (repo `fleetfreight-tms`) | Hyväksytty 14.11.2026 | Toni, chat |
| D30 | Live-seuranta demossa: simuloidut sijainnit legien suunnitelluista ajoista ja FEC-kuittauksista, välitetään FastAPI-WebSocketilla Leaflet-karttaan. Ei oikeaa GPS-dataa | Ehdotus | chat 14.11. |
| D31 | Demodatan kotimaan terminaaliverkosto, viisi terminaalia: **pääkaupunkiseutu (Demo Terminal Central), Turku, Tampere, Kuopio ja Oulu**. Väli noin 150–300 km, joten terminaalin alue on päiväajon päässä edestakaisin. Jyväskylän seutu hoidetaan Tampereelta tai Kuopiosta. Nimet keksittyjä (Demo Terminal + kaupunki), koordinaatit kaupungin yleiseen keskipisteeseen | Hyväksytty 14.11.2026 | Toni, chat |
| D32 | **Kaikissa terminaaleissa on lastauslaiturit**, joten perästä purku onnistuu kaikkialla (perälautaorderien terminaaliflow D25 toimii jokaisessa terminaalissa) | Hyväksytty 14.11.2026 | Toni, chat |
| D33 | **Lämpötilasäädelty käsittely kolmessa terminaalissa: Central, Tampere ja Oulu** (kylmätila ja kylmäkoneiden sähköpistokkeet). Thermo-orderin Cross Dock sallitaan vain näissä, muissa terminaaleissa vain Remain LU | Hyväksytty 14.11.2026 | Toni, chat |
| D34 | Käyttöliittymä on **kaksikielinen (englanti ja suomi), vaihdettavissa** asetuksista. Kaikki tekstit käännöstiedostoissa alusta asti, ei kovakoodattuja tekstejä komponenteissa. Oletuskieli englanti | Hyväksytty 14.11.2026 (oletuskieli: Oletus) | Toni, chat |
| D35 | Reititys: **`react-router`** (uusin vakaa, 8.x) | Oletus (Toni ei ole erikseen päättänyt) | PR 1C |
| D36 | **Pressukuljetus on perustapaus**, ei pätevyys. Trailerityyppi kertoo perusominaisuudet (sivulastaus: pressu, mega, sivuaukeava; ei umpikaappi). Erityisominaisuudet ovat yksinkertaisia valintoja trailerilla ja vaatimuksia orderilla: **XL-sertifioitu (EN 12642 XL), kelakouru, TIR-tullivaijeri, ylhäältä lastaus**. Ei erillistä pressulogiikkaa eikä uusia tauluja | Hyväksytty 15.11.2026 | Toni, chat |
| D37 | **Kolme kuormatyyppiä: FTL (täysi kuorma), PTL (osakuorma) ja LTL (kappaletavara)**, ja niille omat riippuvuudet ja toiminnot (luku 3B) | Hyväksytty 15.11.2026 (yksityiskohdat luvussa 3B: Ehdotus) | Toni, chat |
| D38 | **Kuormatyyppi on kaupallinen tuote, reitti on operatiivinen toteutus.** Kuormatyyppi määrää hinnoittelun, Nodet näyttävät todellisen reitin. Poikkeama (esim. LTL suoraan ilman terminaalia) antaa Plan Check -varoituksen, ei estoa | Hyväksytty 15.11.2026 | Toni, chat |
| D39 | **Kuormatila voi olla traileri tai kuorma-auton oma kuormatila** (nouto- ja jakeluautot, usein perälauta). Mallinnetaan vaiheessa 2. Trip = kuormatilan kuormattu kierros, ja ajotyyppeihin lisätään kuorma-auton kuormattu ajo | Hyväksytty 15.11.2026 | Toni, chat |
| D40 | **Demodatan rajat ja kertoimet (Euroopan malli):** LTL enintään 2,4 LDM tai 2 500 kg, PTL siitä 10 LDM tai 15 000 kg asti, yli → järjestelmä ehdottaa FTL-hintaa. Rahdituspaino: 1 LDM = 1 850 kg, 1 m³ = 333 kg, lavapaikka = 740 kg. Kaikki asetuksina ja asiakashinnastossa ylikirjoitettavina | Hyväksytty 15.11.2026 | Toni, chat |
| D41 | **Ensimmäiseen versioon kaikki:** vähimmäisveloitus ja osakuorman hintakatto (= FTL-hinta), purkujärjestys (LIFO multi-dropissa) ja lastauslista kuljettajalle, ADR-pisteet kuljetusyksikölle ja luokkien yhteenkuormauskiellot (Plan Check, vaihe 5), sekä **lavanvaihto ja lavasaldot** (lavatyyppi ja vaihdetut lavat lastaus- ja purkutapahtumiin vaiheessa 2, saldot asiakkaittain ja laskutus vaiheessa 6) | Hyväksytty 15.11.2026 | Toni, chat |
| D42 | **Lähtöpöytä ja Tripit-sivu.** Lähtöpöydällä kootaan Trip: vapaat orderit, kuormatila, vetäjät ja kuljettajat, lautat ja muut Nodet yhdistetään Node–Leg-ketjuksi, ja Plan Check ajetaan ennen vahvistusta. Tripit-sivulla kaikki tripit tiloittain (KPI:t, haku, täyttö, lautta, Plan Check, kate). Layout: Design-kangas 16.11.2026 | Hyväksytty 16.11.2026 | Toni, chat |
| D43 | **Tripin tietosivu välilehdillä:** Yleiset, Node–Leg, Orderit, Vaaralliset aineet, Lämpötila, Dokumentit, Kulut ja kate. ADR- ja lämpötilatiedot eivät ole erillisiä sivuja vaan tripin välilehtiä. Näiden kahden välilehden sisältö määräytyy D44:n, D46:n ja D47:n mukaan | Hyväksytty 16.11.2026 | Toni, chat |
| D44 | **Vaaralliset aineet ja lämpötilavaatimus kirjataan orderille, Trip johtaa ne.** Orderin luonnissa on ADR-täppä, josta avautuu ADR-välisivu DG-riveille: UN-numero, kuljetusnimi, luokka, pakkausryhmä, määrä ja yksikkö, kuljetuskategoria, rajoitettu määrä -lippu. Thermo vastaavasti: min, max, esijäähdytys, GDP. Tripillä ei ole käsin asetettavaa täppää: kun tripillä on yksikin ADR-order, tripin otsikossa, Tripit-listassa ja lähtöpöydällä näkyy ADR-merkki, ja tiukin lämpötila johdetaan kyydissä olevista ordereista | Hyväksytty 16.11.2026 | Toni, chat |
| D45 | **ADR-avustin tripille, periaate:** avustin on päätöstuki, ei päätä. Se laskee ja näyttää tripin DG-tilanteen (pisteet, vapautus, merkinnät, pakolliset varusteet ja asiakirjat) ja valitsee sovellettavan säännöstön **legeittäin**. Kertoimet, rajat ja säännöt ovat versioitu sääntötaulukko ADR-painoksen mukaan. Vastuu luokittelusta lähettäjällä, tarkistus turvallisuusneuvonantajalla | Hyväksytty 16.11.2026 | Toni, chat |
| D46 | **ADR-avustimen säännöt (tarkistettu lähteistä 16.11.2026, ks. luku 3C):** pisteet kuljetusyksikölle 1.1.3.6.4:n mukaan ja "mitä jos" -laskelma uudelle orderille; alle rajan luku 5.3 (oranssit kilvet ja suuret varoituslipukkeet), 5.4.3 (kirjalliset turvallisuusohjeet), osa 8 poikkeuksin ja osa 9 eivät koske, mutta kuljetusasiakirja ja jäljelle jäävät osan 8 vaatimukset säilyvät; yli rajan oranssit kilvet, kappaletavarassa suuret varoituslipukkeet lisäksi luokille 1 ja 7; legin säännöstö ROAD = ADR, Itämeren ro-ro-lautta = Itämeren MoU, muu merilegi = IMDG; **merilegillä 1.1.3.6-vapautusta ei käytetä** (A1); DG-ilmoitus varustamolle ennen cut-offia. Sääntötaulukossa ADR 2025 ja ADR 2027 erikseen | Hyväksytty 16.11.2026 (MoU §10 -merkinnät tarkistetaan ennen vaihetta 5) | Toni, chat |
| D47 | **Lämpötila-välilehti ja -valvonta:** kuormatilan lohkot ja asetusarvot (tiukin orderivaatimus), kylmäkone ja ATP-luokka voimassaoloineen, anturit kalibrointipäivineen, esijäähdytyksen kuittaus, käyrä sallitulla alueella ja Node-merkinnöillä, hälytykset ja kuljettajan kuittaus syineen, satamasähkö (D27), CSV ja PDF-raportti tallennetusta datasta (ei muokattavissa jälkikäteen). Demossa anturidata simuloidaan (D30). Lisäksi Lämpötilavalvonta-näkymä käynnissä oleville thermo-tripeille | Hyväksytty 16.11.2026 | Toni, chat |

### FleetFlow'sta siirtyvät hyväksytyt periaatteet (PR #6, 14.11.2026)

- Order → Order Routing → Order Leg → Trip. Sama Order ID usealla legillä, ja jokaisella legillä on oma leg-id
- Cross Dock ei luo uutta Orderia. UNLOAD ja LOAD ovat erillisiä tapahtumia. Remain LU jää traileriin
- Routing voidaan tehdä ennen terminaaliin saapumista. Gateway Instructions kertoo UNLOAD/LOAD/REMAIN
- IOP, IOD ja POD ovat erillisiä. IOP–IOD on kuorman kuljetusaika
- Tripillä on oma elinkaari, ja se voi jatkua tyhjän trailerin palautukseen. RoundTrip on valinnainen
- Toteutuneita tapahtumia ei poisteta uudelleensuunnittelussa
- SOLO, EMPTY_TRAILER ja LOADED_TRAILER ovat ajotyyppejä. RETURN_TO_BASE on tarkoitus, ei ajotyyppi
- Toteutettavuus menee tyhjien kilometrien minimoinnin edelle

### Freight Plannerista säilyvät päätökset

- Alembic on skeeman ainoa lähde. Raha on kannassa INTEGER (`*_cents`, `*_e4`) ja laskennassa Decimal
- Palvelukoodisto: koodi kertoo palvelun, `cost_type` kertoo suunnan. Lisähintojen tarkin osuma voittaa
- Automaatit: 120 → 200, vahvistus → 400-rivit, odotusaika → 800, toimitus → `delivered_at`

### Ristiriidat, jotka on ratkaistava ennen toteutusta

| # | Ristiriita | Freight Planner nyt | FleetFlow | Ehdotus |
|---|---|---|---|---|
| R1 | Orderin ja Tripin suhde | `orders.trip_id`: yksi order, yksi trip | Sama order usealla legillä ja tripillä | **Ratkaistu: D13 + D14.** Order kulkee Node–Leg-ketjussa lastaus-Nodesta purku-Nodeen. Orderin reititys = ne legit, joilla se on kyydissä (johdettu tieto, ei erillistä Order Leg -taulua). Cross Dockissa order siirtyy terminaali-Nodessa toiseen Tripiin |
| R2 | Kulujen jako ordereille | Lauttakulu jaetaan tasan | LDM / paino / tavaramäärä | Kulu kirjataan sinne, missä se syntyy. Jakoperuste palvelukoodin mukaan, oletus LDM. Aiheuttajan kulut suoraan orderille. Jako jäädytetään laskutuksessa (`cost_allocations`). Tyhjä palautus: **LDM keikan ordereille (D15)** |
| R3 | Elinkaari ja laskutus | Trip-statusketju, Laskutettu lukitsee tripin | Trip jatkuu toimituksen jälkeen | Kolme tilaketjua: **Order** Avoin → Reititetty → Suunniteltu → Kuljetuksessa → Toimitettu → Laskutettu. **Trip** Suunniteltu → Vahvistettu → Käynnissä → Kuormat toimitettu → Suljettu. **Job** Avoin → Osoitettu → Vahvistettu → Käynnissä → Valmis. Myynti laskutetaan orderilta. Laskutus lukitsee orderin, ei Tripiä. Korjaukset vastakirjauksina. **Ehdotus** |
| R4 | Jobin kuljettajarajaus | Ei Job-käsitettä | Yksi kuljettaja vai useampi? (FF #8) | **Ratkaistu: D18, D20, D21.** Job = yksi vetäjä ja kuljettaja. Vaihto Nodessa luo uuden Jobin, Trip jatkuu. Job ja Trip ovat N:M legien kautta. Ajo- ja työaika lasketaan kuljettajalle yli Jobien ja päivien |
| R5 | Fyysinen Leg vs. Order Leg | Ei kumpaakaan | Molemmat käsitteinä, suhde avoin | **Ratkaistu: D13.** Yksi Leg-käsite: fyysinen siirtymä kahden Noden välillä (ajotyyppi SOLO / EMPTY_TRAILER / LOADED_TRAILER, kulkumuoto ROAD / FERRY). Job vapaaehtoinen (saattamaton traileri lautalla). Kilometrit ja ajoaika lasketaan vain legeistä |
| R6 | Kuljettajat | Ei kuljettajia, vain vetäjät ja kuljetusyhtiöt | Kuljettaja on keskiössä | Uusi `drivers`-taulu: kuljetusyhtiö, kotipaikka (kotiinpaluu ja viikkolepo), työsuhde (oma / alihankkijan nimetty). Pätevyydet `qualifications`-tauluun |
| R7 | Gateway Instructions | Suunniteltu "Gateway Instruction List" | "Gateway Instructions PDF" | Sama dokumentti, johdetaan legeistä. V1:ssä versionumero ja "muuttunut lähetyksen jälkeen" -varoitus |

### Avoimet kysymykset (selvitettävä ennen toteutusta)

- **A1 (D46): ratkaistu 16.11.2026.** Itämeren MoU:n §3(2) luettelee ne ADR:n 1.1.3-vapautukset, joiden ansiosta IMDG:tä ei sovelleta laivalla, eikä 1.1.3.6 ole luettelossa. Merilegillä pistevapautus ei siis päde: DG-tiedot (UN-numerot ja luokat) annetaan varustamolle aina. Kuljetusyksikön merkinnät merilegillä (MoU §10) tarkistetaan koko MoU-tekstistä ennen vaihetta 5, koska käytettävissä oli vain ote.

Perustelut ja skenaarioittaiset rivit: `analyysi/paperitestit.md`. Avoimet kysymykset Tonille: saman raportin luku 4 (14 kysymystä).

---

## 2B. Toimialueen kattavuus: kaikki mukaan

Periaate: **kaikki kummankin projektin toimialuekäsitteet tulevat mukaan yhdistettyyn järjestelmään.** Mitään ei pudoteta. Päällekkäiset toteutukset yhdistetään yhdeksi.

Tila: ✅ toteutettu koodissa · 📄 suunniteltu tai dokumentoitu · ⚠️ osittain (pelkkä lippu tai demo) · — puuttuu

| Käsite | Freight Planner | FleetFlow | Yhdistetyssä | Moduuli |
|---|---|---|---|---|
| **Trailer pool** | ⚠️ trailerilista, leasing- ja vuokrahinnat, katsastus ja huolto | ⚠️ trailerit jobeilla | Pool: trailerin sijainti, tila (vapaa / varattu / lastattu / tyhjä / huollossa), seisontapäivät ja siirtohistoria | resurssi |
| **Asiakkaat** | ✅ rekisteri, tyyppi, asiakashinnasto, lisäsäännöt | ⚠️ demonimet jobeilla | FP:n rekisteri + toimipaikat (`locations`) | kuorma |
| **Kuljetusliikkeet** | ✅ kuljetusyhtiöt | ⚠️ carrier jobilla | FP:n rekisteri + kuljettajat | resurssi |
| **Vetäjät** | ✅ vetäjät kuljetusyhtiöittäin | ✅ truck-keskeinen suunnittelu (Fleet Timeline) | FP:n rekisteri + varaukset ja päivän työjono | resurssi |
| **Kuljettajat** | — | ✅ kuljettaja jobilla, ajotunnit | Uusi rekisteri: pätevyydet (ADR, GDP), aikalaskenta | resurssi |
| **Tripit** | ✅ statusketju, kapasiteetti, kulut, FEC | ✅ Trip-ketju | Yksi Trip, oma elinkaari (R3) | kuorma |
| **Orderit** | ✅ täysi tilausrakenne, kopiointi | ✅ orderit tripillä | FP:n rakenne + pysyvä Order ID usealla legillä | kuorma |
| **Nodet ja legit** | — | 📄 Node/Stop + Order Leg + fyysinen Leg (PR #6) | Node–Leg-ketju (D13) | kuorma / resurssi |
| **Order Routing** | — | 📄 Cross Dock, Remain LU, ennakkoreititys | Reititys legeiksi, UNLOAD / LOAD / REMAIN | kuorma |
| **Lauttayhtiöt** | ⚠️ reitit ja hinnat (`ferry_rates`), operaattori lisähinnoissa (BAF, ETS, MARPOL) | — | Lauttayhtiö-rekisteri, reitit, vuorot (lähtö, saapuminen, check-in), varaukset, saattamaton traileri vs. vetäjän kanssa | kuorma |
| **ADR** | ⚠️ lippu orderilla ja tripillä, 600 ADR-lisä | ⚠️ ADR-vaatimus ja -tarkistus | Vaaralliset aineet ordeririveittäin (UN-nro, luokka, pakkausryhmä, määrä), kuljettajan ADR-pätevyys, yhteenlastaus, tunnelirajoitukset, lautan IMDG-ilmoitus | molemmat |
| **GDP** | — | ⚠️ vaatimus, kaluston kelpoisuus, dokumenttipaketti | GDP-vaatimus orderilla, GDP-kelpoinen kalusto ja kuljettaja, lämpötilaloki ja dokumentit | molemmat |
| **Perälauta** | ⚠️ vaatimus orderilla; terminaaliflow vain dokumentoitu (sarakkeet kannassa, ei koodia) | ⚠️ tail lift -vaatimus | FP:n flow + vaatimus kaluston soveltuvuustarkistukseen | molemmat |
| **Thermokuljetukset** | ✅ min/max-lämpötila, seuranta, lohko, 2-koneinen, kylmäkonehuolto | ⚠️ lämpötilavaatimus | FP:n malli + lämpötilan yhteensopivuus samalla kuormalla | molemmat |
| **Pressukuljetukset** | ⚠️ trailerityypit ja speksit; pitkien tavaroiden esto vain dokumentoitu | — | FP:n soveltuvuustaulukko (lastaus sivulta, pitkät tavarat) | molemmat |
| **Terminaalit** | ✅ 16 demoterminaalia, CRUD | ⚠️ nodet | Osa `locations`-taulua (tyyppi: terminaali / satama / asiakas / varikko) | yhteinen |
| **Maarajoitukset** | ✅ ajokiellot, painorajat, reittitarkistin | — | Syötteenä toteutettavuustarkistukseen | resurssi |
| **Ajo-, työ- ja lepoajat** | 📄 suunniteltu laskuri | ⚠️ 4,5 h -tarkistus | Toteutettavuusmoottori (luku 4) | resurssi |
| **Kartta ja reitit** | 📄 #13 OpenRouteService | ✅ Leaflet, Route & Risk | Leaflet-näkymä + reitityspalvelu | resurssi |
| **Kulut, hinnoittelu, kate** | ✅ palvelukoodisto, lisähinnat, asiakashinnasto, km-hinnat | 📄 kustannusten jako | FP:n moottori + jakoperuste (R2) | kuorma |
| **FEC-kuittaukset** | ✅ kuljettajan mobiilisivu, odotusaika-automaatti | 📄 simuloitu FEC | FP:n sivu + salainen token + kuittaukset `handling_events`-tauluun | molemmat |
| **Dokumentit** | 📄 Transport Order, CMR, lasku, Credit Note | 📄 Gateway Instructions PDF | Yksi dokumenttimoduuli (R7) | kuorma |
| **Dashboard ja KPI** | ✅ dashboard, Costs Dashboard | ✅ Board, päivän yhteenveto | Kuorma- ja liikennenäkymä erikseen, yhteiset KPI:t | molemmat |
| **Hallinta ja asetukset** | ✅ kalusto, hinnoittelu, asetukset | ✅ teemat | FP:n hallinta + FF:n teemat | yhteinen |

Jos lista ei ole kattava, puuttuva käsite lisätään tähän ennen vaiheen 2 tietomallia.

---

## 3. Tavoitearkkitehtuuri

```
Frontend (React + TypeScript + Vite)
├── Kuormasuunnittelu   Orderit · Routing · Keikat · Asiakkaat · Kulut · Dashboard
├── Liikennesuunnittelu Board · Job Workspace · Fleet Timeline · Route & Risk   ← FleetFlow
├── Hallinta            Kalusto · Trailer pool · Kuljettajat · Lautat · Hinnoittelu · Asetukset
└── Kuljettaja (FEC)    mobiili, salainen kertakäyttölinkki
API-tyypit generoidaan backendin OpenAPI-kuvauksesta (openapi-typescript)

Backend (FastAPI + Pydantic + SQLAlchemy, moduuleittain)
├── auth          käyttäjät, roolit, tokenit
├── orders        orderit, order routing, legit, käsittelytapahtumat, ADR- ja GDP-tiedot
├── trips         keikat, pysähdykset, siirtymät, kapasiteetti legin aikavälillä
├── pricing       kulut, jakoperusteet, lisähinnat, asiakashinnasto, kate   ← FP:n moduulit
├── resources     kuljettajat, vetäjät, trailer pool, pätevyydet, varaukset
├── ferries       lauttayhtiöt, vuorot, varaukset, satamakäsittely
├── planning      jobit, duty-tapahtumat, toteutettavuus, ehdotukset   ← FleetFlow'n ydin
├── documents     Transport Order, CMR, Gateway Instructions, lasku, Credit Note
└── reporting     KPI:t, Power BI -endpointit
Domain-logiikka on puhtaita Python-moduuleja ilman riippuvuutta web-kehykseen,
jotta ne voidaan testata erikseen.

Tietokanta: PostgreSQL (Docker), Alembic-migraatiot alusta asti
```

### Teemat (D9, D10)

Kaikki komponentit käyttävät vain muuttujia. Värit ovat nykyisten sovellusten käytetyimmät arvot (FleetFlow `App.css`, Freight Planner komponenttien inline-värit).

| Token | Business Light | Control Dark (Freight Planner) |
|---|---|---|
| `--bg-main` | `#f3efe7` | `#0f172a` |
| `--panel-bg` | `#fbf8f1` | `#1e293b` |
| `--panel-header` | `#e6ded2` | `#334155` |
| `--border` | `#c9bfb0` | `#334155` |
| `--text-main` | `#1f2933` | `#f1f5f9` |
| `--text-muted` | `#6b7280` | `#94a3b8` |
| `--accent` | `#0a6ed1` | `#f97316` |

Lisäksi yhteiset semanttiset tokenit molempiin teemoihin: tilavärit (Suunniteltu, Vahvistettu, Käynnissä, Toimitettu, Laskutettu, Peruttu), kapasiteettipalkit (vihreä / oranssi / punainen), rajoitusten vakavuus (red / orange / yellow) sekä ADR-, GDP- ja thermo-merkit. Näin värikoodaus toimii samoin kummassakin teemassa.

Johdetut tokenit (molemmissa teemoissa): `--text-muted-strong`, `--accent-text`, `--accent-contrast` (teksti aksenttivärin päällä), `--border-strong`, `--surface-hover` ja `--surface-selected`.

Sääntö (WCAG AA, 4.5:1 tekstille): perusarvot `--text-muted` ja `--accent` kelpaavat tekstinä vain pinnoilla, joilla ne läpäisevät AA:n (`--panel-bg`, Control Darkissa myös `--bg-main`). Muilla pinnoilla (esim. `--panel-header`) käytetään johdettuja `--text-muted-strong` ja `--accent-text`. Kontrastitesti valvoo tätä.

Tiiviys pysyy samana molemmissa: business-UI, paljon tietoa yhdellä ruudulla.

### Tietomallin luonnos (paperitestattu 14.11.2026, lopullinen muoto ratkaistaan R1–R6:n jälkeen)

| Taulu | Moduuli | Sisältö |
|---|---|---|
| orders | kuorma | asiakastilaus, **kuormatyyppi FTL/PTL/LTL (D37)**, osapuolet, tavara, rahdituspaino, aikaikkunat, vaatimukset (ADR, lämpötila, perälauta, XL, kelakouru, TIR, ylhäältä lastaus) |
| order_nodes | kuorma | orderin käsittely Nodessa: LOAD / UNLOAD / REMAIN, suunniteltu ja toteutunut. Orderin reititys johdetaan tästä ja legeistä |
| trips | kuorma | operatiivinen kuljetuskokonaisuus: traileri, lautta, statusketju |
| locations | yhteinen | asiakkaat, terminaalit ja satamat koordinaatteineen. Terminaaleilla: lastauslaiturit (D32), kylmätila ja lämpötila-alue sekä kylmäkonepistokkeiden määrä (D33) |
| handling_events | kuorma | IOP, IOD, POD, UNLOAD, LOAD: suunniteltu ja toteutunut aika, lavatyyppi ja vaihdetut / vaihtamatta jääneet lavat (D41) |
| drivers | resurssi | kuljettaja, kuljetusyhtiö, kortit, ADR-pätevyys |
| nodes | kuorma / resurssi | keikan pisteet järjestyksessä: sijainti, tyyppi (vetäjän lähtö, trailerin nouto, terminaali, lastaus, purku, satama lähtö / saapuminen, korjaamo, katsastus, pesu, kuljettajanvaihto), live / drop, aikaikkuna, suunniteltu / ennustettu / toteutunut aika |
| legs | kuorma / resurssi | siirtymä kahden peräkkäisen Noden välillä: Job (vapaaehtoinen), Trip, vetäjä, traileri, ajotyyppi (SOLO / EMPTY_TRAILER / LOADED_TRAILER), kulkumuoto (ROAD / FERRY), tarkoitus (esim. RETURN_TO_BASE), km ja aika |
| jobs | resurssi | yhden ajoneuvon ja kuljettajan työyksikkö. Kuljettaja voi olla tyhjä alihankkijan työssä. Ei omaa `trip_id`:tä |
| duty_events | resurssi | ajo, muu työ, tauko, lepo, valmiusaika (pohja aikalaskennalle) |
| resource_reservations | resurssi | vetäjän ja trailerin varaukset aikaväleineen, historia säilyy |
| costs | kuorma | kulu- ja myyntirivit, linkki tripiin, orderiin, legiin tai jobiin |
| cost_allocations | kuorma | kulujen jako ordereille jakoperusteen mukaan, jäädytetään laskutuksessa |
| trailer_positions | resurssi | trailer poolin sijainti- ja tilahistoria (seisontapäivät, siirrot) |
| ferry_operators, ferry_sailings, ferry_bookings | kuorma | lauttayhtiöt, vuorot ja varaukset (nykyinen `ferry_rates` liitetään reitteihin). Varauksella: saattaen / saattamaton, cut-off, release, noutotunnus, ilmainen säilytysaika ja maksut, sähköön kytkentä (D27) |
| dangerous_goods | kuorma | ADR-rivit orderilla: UN-nro, luokka, pakkausryhmä, määrä, tunnelikoodi |
| qualifications | resurssi | kuljettajan ja kaluston pätevyydet ja kelpoisuudet: ADR, GDP, thermo, perälauta, voimassaolo |

---

## 3B. Kuormatyypit (D37)

Kuormatyyppi on orderin pakollinen tieto. Se ohjaa reititystä, kapasiteettia, hinnoittelua, kulujen jakoa ja Plan Checkiä.
Rajat ja kertoimet ovat asetuksia, eivät koodiin kirjoitettuja lukuja. Demossa käytetään keksittyjä arvoja.

| | **FTL** täysi kuorma | **PTL** osakuorma | **LTL** kappaletavara |
|---|---|---|---|
| **Kuvaus** | Koko traileri yhdelle tilaajalle | Osa trailerista, suora kuljetus | Yksittäiset lavat ja kollit, konsolidoitu terminaalin kautta |
| **Tyypillinen koko** | koko kuormatila, kapasiteetti trailerin tiedoista (ei vakio 13,6 LDM) | LTL- ja FTL-rajan välissä *(LDM- ja painoraja asetuksissa)* | pienet lähetykset *(LDM- ja painoraja asetuksissa)* |
| **Reititys (Node–Leg)** | Suoraan, ei UNLOAD/LOAD-käsittelyä terminaalissa. Terminaali-Node sallittu REMAIN-käyntinä (vetäjänvaihto, yöpysäköinti, satama) | Yleensä suoraan, voi jakaa trailerin muiden PTL- ja LTL-osuuksien kanssa (multi-drop) | **Oletuksena terminaalin kautta**: nouto → terminaali → runkokuljetus → terminaali → jakelu |
| **Trailerin jakaminen** | Ei. Kuormatila on varattu orderille kokonaan | Kyllä, PTL- ja LTL-osuuksien kanssa kapasiteetin rajoissa | Kyllä, konsolidoidaan terminaalissa |
| **Kapasiteetin laskenta** | Koko kuormatila varataan | LDM / lavapaikat ja paino **legeittäin** (huippukuorma jokaisella legillä) | LDM, paino ja tilavuus legeittäin. Hinnoitteluun **rahdituspaino** |
| **Hinnoittelu** | Hinta per kuljetus (asiakashinnasto: reitti + FTL) | Hinta LDM:n tai lavapaikkojen mukaan | Hinta rahdituspainon mukaan (kg-portaat tai €/100 kg) |
| **Rahdituspaino** | ei käytetä | valinnainen | suurin seuraavista: todellinen paino, LDM × kerroin, m³ × kerroin *(kertoimet asetuksissa)* |
| **Kulujen jako (R2, D19)** | Kaikki keikan kulut orderille | LDM:n mukaan | LDM:n tai rahdituspainon mukaan. Terminaalikäsittely aiheuttajalle |
| **Dokumentit** | Rahtikirja per lähetys: CMR kansainvälisessä, kotimaan rahtikirja kotimaassa *(valinta lähtö- ja määrämaan mukaan, lakiperuste tarkistetaan)* | sama | sama, lisäksi terminaaliohjeet (Gateway Instructions) ja runkokuljetuksen kuormaluettelo |
| **Plan Check** | Varoittaa, jos samaan kuormatilaan yritetään toista orderia | Varoittaa ylikapasiteetista legeittäin ja purkujärjestyksestä | Varoittaa (ei estä), jos reitti ei kulje terminaalin kautta. Varoittaa konsolidoinnin cut-offista |
| **Tyypilliset lisät** | Odotusaika, polttoainelisä, ADR, thermo, lauttalisät (BAF, ETS), peruutusmaksu | samat + lisäpysähdys multi-dropissa | samat + terminaalikäsittely, jakelulisä, perälauta (terminaaliflow D25) |

**Riippuvuudet muihin päätöksiin:**
- **Thermo (D33):** LTL-thermo konsolidoidaan vain kylmäterminaalissa (Central, Tampere, Oulu)
- **ADR (D24):** ADR + elintarvike -esto koskee myös konsolidoitua LTL-trailer-kuormaa, ei vain yksittäistä orderia
- **Perälauta (D25):** perälautaorder kulkee aina terminaalin kautta kuormatyypistä riippumatta. PTL ja FTL eivät silloin voi mennä suoraan
- **Kulujen jako legeittäin:** jaettava kulu kohdistetaan vain niille ordereille, jotka ovat kyydissä kyseisellä legillä (LTL on Cross Dockin jälkeen eri Tripillä, D14)
- **Lautat:** LTL kulkee lautalla runkokuljetuksen trailerissa, ja lauttakulu jaetaan trailerin ordereille (D19)

**Muut kuormatyyppeihin liittyvät tiedot (ff-logistiikka 15.11.2026):**
- **Pinottavuus** ordeririveillä: pinoamaton lava varaa lattiapinnan, mikä vaikuttaa LDM:ään ja hintaan
- **LDM-kaava:** pituus × leveys / 2,4 m. EUR-lava (1,2 × 0,8 m) = 0,4 LDM, FIN-lava (1,2 × 1,0 m) = 0,5 LDM
- **LTL-verkon aikataulut:** runkolinjojen lähdöt, terminaalien cut-off-ajat ja toimitusaikalupaus
- **Kollitason tiedot:** kollimäärä ja poikkeamat (vaurio, puuttuva kolli) käsittelytapahtumiin
- **Rahdinmaksaja:** lähettäjä tai vastaanottaja
- **LTL-thermo** Turun ja Kuopion alueilla jaetaan kylmäterminaalista (Central, Tampere, Oulu), ja Plan Check huomaa sen
- Demoarvot: D40. Laajuus: D41

---

## 3C. ADR-avustimen lähteet ja tarkistus (D46)

Tarkistettu 16.11.2026. Ennen vaihetta 5 sääntötaulukko tarkistetaan vielä virallisesta ADR-tekstistä (UNECE), koska osa alla olevasta on luettu otteista tai viranomaisten tiivistelmistä.

| Sääntö | Sisältö | Lähde |
|---|---|---|
| 1.1.3.6.2 | Rajan alla ei sovelleta: luku 1.10 (paitsi luokan 1 suuren vaaran aineet), luku 5.3, 5.4.3, valtaosa luvusta 7.2, CV1, osa 8 (poikkeuksin), osa 9 | BAM DGG-Info, ADR 2025 |
| 1.1.3.6.3 | Kategoria 0: määrä 0, eli vapautusta ei voi käyttää. Kategoriat 1–3 rajoin, kategoria 4 rajaton | ADR 2025 (BAM, UNECE) |
| 1.1.3.6.4 | Summa ≤ 1 000: kat. 1 × 50, kat. 1 taulukon huomautus a × 20, kat. 2 × 3, kat. 3 × 1, kat. 4 ei lasketa | BAM DGG-Info, ADR 2025 |
| ADR 2027 | Voimaan 1.1.2027: huomautus a ja kerroin 20 poistuvat. Siirtymäsäännös 1.6.1.61: vanhaa saa käyttää tietyille UN-numeroille 31.12.2030 asti | ASTRA, ADR 2027 -muutokset |
| 5.3.1.5 | Kappaletavarassa suuret varoituslipukkeet ajoneuvoon vain luokat 1 ja 7 | HSE (UK), CDG |
| 1.1.4.2.1 | IMDG-merkityt yksiköt hyväksytään kuljetusketjussa, jossa on merikuljetus, kun 5.3.2:n oranssit kilvet ovat kunnossa | ADR (EU-virallinen julkaisu), HSE |
| MoU §1 | Kaikki ro-ro-alukset Itämerellä, Pohjanlahdella, Suomenlahdella ja Skagen–Lysekil-linjaan asti | MoU 2022 (Tallinna), Transportstyrelsen |
| MoU §3(2) | Laivalla sallitut ADR 1.1.3 -vapautukset luetellaan, 1.1.3.6 ei ole mukana | MoU 2022 (Tallinna) |

Vastuu: lähettäjä luokittelee, turvallisuusneuvonantaja tarkistaa. Avustin laskee ja varoittaa, ei hyväksy.

---

## 4. Optimointi: FleetFlow'n alkuperäinen ydin

Optimointi rakennetaan kolmessa kerroksessa. Jokainen kerros on käyttökelpoinen sellaisenaan:

### Kerros 1: toteutettavuustarkistus (Plan Check)
Puhdas Python-moduuli `planning/feasibility.py`, joka on kattavasti testattu ja deterministinen.
Annetaan kuljettajan päivän Jobit, ja moduuli palauttaa: ehtiikö, missä raja ylittyy ja aikaisimman mahdollisen ajan.

Tarkistettavat säännöt (rajat varmistetaan säädöstekstistä ennen toteutusta):
- **EU 561/2006, ajo- ja lepoajat:** päivittäinen ja viikoittainen ajoaika, kahden viikon ajoaika, tauko 4,5 tunnin ajon jälkeen (myös jaettuna), vuorokausilepo (myös lyhennetty) ja viikkolepo
- **Työaikadirektiivi 2002/15/EY:** viikkotyöaika ja sen keskiarvo, tauot työajan pituuden mukaan, yötyön rajoitus
- Aikaikkunat, lastaus- ja purkuajat, lautan lähtö ja check-in
- Maarajoitukset (nykyinen `restriction_engine.py`)
- Kaluston soveltuvuus (perävaunutyyppi, ADR, lämpötila, pitkät tavarat)

Nykytila: FleetFlow'n ajoaikalogiikka on hajallaan neljässä paikassa ja vertaa aikoja merkkijonoina. Siitä siirretään vain Plan Checkin tulosrakenne mallina. Freight Plannerin maarajoitusmoottori siirretään muokattuna, ja sille kirjoitetaan testit ennen siirtoa. Kerros rakennetaan käytännössä alusta, ja aikalaskenta tehdään kuljettajan aikajanalta yli Jobien ja päivien (R4).

### Kerros 2: ehdotukset (heuristiikka)
Avoimelle Jobille järjestelmä etsii kuljettajat, joiden päivään se mahtuu toteutettavasti, ja järjestää ne tyhjien kilometrien ja jäljelle jäävän pelivaran mukaan.
Liikenteenohjaaja hyväksyy tai hylkää ehdotuksen, eikä järjestelmä muuta suunnitelmaa itse.

### Kerros 3: optimointi (myöhemmin)
Koko päivän ajoneuvoreititysongelma aikaikkunoilla (VRPTW), esimerkiksi Google OR-Toolsilla. Tuloksena on ehdotus, ja kerros 1 tarkistaa sen.

Etäisyydet ja ajoajat: ensin linnuntie kertoimella, myöhemmin OpenRouteService tai OSRM (Freight Planner #13).

---

## 5. Vaiheistus

Jokainen vaihe koostuu pienistä tehtävistä, ja jokainen tehtävä tehdään omassa haarassa ja PR:ssä testeineen. Automaattista yhdistämistä ei käytetä.

Lähtökohta on uusi repo (D3). Vanhoja rakenteita ei siirretä yhteensopivasti. Siirrettävät osat ja niiden luokittelu: `analyysi/siirtoinventaario.md` (säästö noin 50–70 h uudelleenkirjoitukseen verrattuna).

### Vaihe 0: päätökset ja vanhojen projektien sulkeminen
- [x] Toni vastasi paperitestien kysymyksiin 14.11.2026 (D13–D27; D19–D21 oletuksina)
- [x] D4, D5, D10, D12 ja D28 hyväksytty 14.11.2026
- [x] Nimi: FleetFreight TMS (D29)
- [ ] Repo `fleetfreight-tms` luodaan
- [ ] FleetFlow: FF-002E (#10) ja PR #6:n korjaus (Job-rajaus avoimeksi, ChatGPT-linkki pois), sitten koodi jäädytetään (D7)
- [ ] Freight Planner: KONTEKSTI-tiedostoon merkitään, mitä on oikeasti toteutettu (esim. perälaudan flow ja pitkien tavaroiden esto ovat vain dokumentoituja)

### Vaihe 1: runko
- [ ] Repo, Docker Compose (PostgreSQL), FastAPI-runko, Vite + React + TypeScript -runko, CI (pytest, Vitest, lint, typecheck)
- [ ] Teemat CSS-muuttujina (D9, D10) ja sovelluksen layout (sivupalkki ja välilehdet)
- [ ] Autentikointi ja roolit alusta asti
- [ ] `CLAUDE.md` + `AGENTS.md` (D5) ja agenttien ohjeet uudelle pinolle
- [ ] OpenAPI → TypeScript-tyyppien generointi

### Vaihe 2: tietomalli
- [ ] Alembic-revisiot: `locations`, `customers`, `carriers`, `drivers`, `trucks`, `trailers`, `qualifications`
- [ ] Alembic-revisiot: `orders`, `dangerous_goods`, `trips`, `nodes`, `legs`, `order_nodes`, `handling_events`
- [ ] Alembic-revisiot: `jobs`, `duty_events`, `resource_reservations`, `trailer_positions`, ferry-taulut, `costs`, `cost_allocations`
- [ ] Orderin DG-rivit ja lämpötilavaatimus (D44) sekä kuormatilan lohkot, kylmäkone, ATP ja anturit (D47), kun D44 ja D47 on hyväksytty
- [ ] Kolmen tilaketjun tilakoneet testeineen (R3)
- [ ] Demodata: molempien projektien demodata yhdistettynä, "Demo"-säännöt, FleetFlow'n ristiriitainen JOB-001-data korjattuna

### Vaihe 3: siirrettävät moduulit
- [ ] Sellaisenaan: `money.py`, lisähintamoottori (`select_rate`, `compute_amount`, `derive_trade_type`), asiakashinnaston postinumerologiikka, palvelukoodisto. Noin 120 testiä mukana
- [ ] Muokattuina: automaatit (120 → 200, 400-rivit, 800), maarajoitusmoottori (testit ensin), kapasiteetti, validoinnit ja 409-tarkistukset
- [ ] Yksi hintalähde lautoille ja kilometreille (nyt kolme ja kaksi)
- [ ] FEC-odotusaika uudelleen: aikavyöhykkeet oikein, virheet näkyviin, lukitus tarkistetaan, raha `Decimal`

### Vaihe 4: läpimenevä polku (ensimmäinen demottava versio)
- [ ] Order → Trip → Nodet ja legit → Job kuljettajalle → yksinkertainen Plan Check
- [ ] Näkymät: Orderit, Lähtöpöytä, Tripit, tripin tietosivu (D42, D43; DG- ja lämpötilavälilehdet täyttyvät D44, D46 ja D47 hyväksynnän jälkeen), Routing, Board ja Job Workspace
- [ ] Skenaario Jyväskylä–Vantaa–Lübeck toimii demossa alusta loppuun

### Vaihe 5: toteutettavuus (kerros 1)
- [ ] `feasibility.py` sääntö kerrallaan: 561/2006 (myös lauttalepo, D23), 2002/15/EY, aikaikkunat, lautat, maarajoitukset, kaluston ja kuljettajan soveltuvuus (ADR, GDP, thermo, pitkät tavarat, perälauta)
- [ ] ADR-avustin (D45, D46) ja lämpötilasäännöt (D47) Plan Checkiin (D46, D47 ja A1 ratkaistava ensin)
- [ ] Fleet Timeline ja Route & Risk

### Vaihe 6: kaupallinen puoli
- [ ] Hinnoittelumoottori ja kulujen jako (R2), kate orderille ja Tripille
- [ ] Dokumentit: Transport Order, CMR, Gateway Instructions, lasku, Credit Note
- [ ] Lavasaldot asiakkaittain ja vaihtamatta jääneiden lavojen laskutus (D41)
- [ ] Trailer pool -näkymä, lautat ja satamakäsittely, raportit ja Power BI -endpointit

### Vaihe 6B: live-seuranta (D30)
- [ ] Simuloidut sijainnit legeistä ja FEC-kuittauksista, WebSocket, ETA-ennuste ja myöhästymisvaroitus Route & Risk -näkymään
- [ ] Simuloitu lämpötiladata, hälytykset ja Lämpötilavalvonta-näkymä, lämpötilaraportti PDF (D47)

### Vaihe 7: ehdotukset (kerros 2)
- [ ] Jobin sijoitusehdotukset ja hyväksyntä
- [ ] Siirtymäajojen ehdotukset (SOLO / EMPTY_TRAILER)

### Vaihe 8: tuotantovalmius
- [ ] Julkinen live-demo, joka nollautuu yöllä
- [ ] Audit trail, lokitus, virheseuranta
- [ ] Vanhat repot arkistoidaan, ja niiden README ohjaa uuteen

### Vaihe 9: optimointi (kerros 3)
- [ ] VRPTW-ratkaisija ehdotuksena

**Miksi tässä järjestyksessä:** tietomalli ja autentikointi tehdään ennen ominaisuuksia, koska muuten ne joudutaan kirjoittamaan uudelleen. Vaihe 4 tuottaa mahdollisimman aikaisin demottavan version, jossa koko ketju toimii ohuena. Sen jälkeen jokainen vaihe syventää sitä. Näin projekti ei jää keskeneräiseksi kokoelmaksi irrallisia osia.

---

## 6. Työtapa

- Ensin suunnitelma, sitten Tonin hyväksyntä, sitten koodi
- Oma haara per tehtävä. PR, testit ja katselmointi ennen yhdistämistä
- Claude Code -agentit (ohjeet päivitetään uudelle pinolle vaiheessa 1): logistiikka (logiikka ennen koodia), backend, frontend, reviewer (jokainen PR) ja auditor (vaiheiden välissä)
- Codexia käytettäessä `AGENTS.md` viittaa samaan `CLAUDE.md`:hen, joten säännöt ovat samat molemmille
- Päätösrekisteri (luku 2) päivitetään aina, kun päätös syntyy tai muuttuu
