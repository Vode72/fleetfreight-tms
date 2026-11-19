# FleetFreight TMS: Freight Planner + FleetFlow → yhdistetty TMS

Päivitetty 18.11.2026 · D1–D74 · tilat luvussa 2 (osa päätöksistä Ehdotus tai Oletus)
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

Tilat: **Hyväksytty** · **Ehdotus** (odottaa Tonin päätöstä) · **Oletus** (käytetään, kunnes Toni päättää toisin) · **Avoin** (vaatii selvityksen) · **Korvattu** (merkintä "Korvattu → Dxx", korvaava päätös kertoo voimassa olevan linjan)
Ehdotusta ei merkitä hyväksytyksi ilman Tonin päätöstä. Korvattu päätös säilyy historiassa.

| # | Päätös | Tila | Lähde |
|---|---|---|---|
| D1 | FleetFlow ja Freight Planner yhdistetään yhdeksi TMS:ksi | Hyväksytty 14.11.2026 | Toni, chat |
| D2 | Tavoite on tuotantotasoinen TMS kuljetusten optimoinnilla, ja se säilyy portfolioprojektina | Hyväksytty 14.11.2026 | Toni, chat |
| D3 | **Uusi sovellus** (uusi repo), johon siirretään molempien toimivat ja testatut osat. Vanhaa rakennetta ei siirretä yhteensopivasti, koska data on demodataa. Vanhat repot jäädytetään ja jäävät GitHubiin portfolioon (D7) linkin kanssa. *(Korvaa 14.11. luonnoksen "pohjana Freight Plannerin repo".)* | Hyväksytty 14.11.2026 | Toni, chat |
| D4 | Moduulijako: kuormasuunnittelu omistaa Orderin, Order Routingin, Tripin, kulut, hinnoittelun ja dokumentit. Resurssisuunnittelu omistaa Jobin, kuljettajan päivän, aikalaskennan ja toteutettavuuden | Hyväksytty 14.11.2026 | luku 3 |
| D5 | Yksi sääntötiedosto: `CLAUDE.md` on päälähde, ja `AGENTS.md` (Codex) viittaa siihen | Hyväksytty 14.11.2026 | luku 6 |
| D6 | Frontend siirretään Create React Appista Viteen. Kieli pysyy JavaScriptinä, TypeScript ei ole päätetty | Korvattu → D11 | FF #11 |
| D7 | FleetFlow'n ja Freight Plannerin koodikehitys jäädytetään 18.11.2026 (tarkennettu: FF-002E jäi tekemättä, sisältö siirtyi FleetFreightin päätöksiin). FleetFlow'n draft-PR #6 suljetaan. Repot jäävät GitHubiin portfolioon, ja README:hen lisätään linkki FleetFreight TMS:ään. GitHub Pages -demo säilyy, kunnes yhdistetty demo on julkaistu | Hyväksytty 18.11.2026 | Toni, chat |
| D8 | Kaikki kummankin projektin toimialuekäsitteet tulevat mukaan (luku 2B). Mitään ei pudoteta, ja päällekkäiset toteutukset yhdistetään | Hyväksytty 14.11.2026 | Toni, chat |
| D9 | Kaksi vaihdettavaa teemaa koko sovellukseen: **Business Light** (beige-harmaa vaalea teema, sininen aksentti) ja **Control Dark** (Freight Plannerin tumma, oranssi aksentti). Valinta tallentuu käyttäjälle (tarkennus: D49) | Hyväksytty 14.11.2026 | Toni, chat |
| D10 | Tyylit toteutetaan CSS-muuttujina (design tokenit), ei inline-väreinä. Freight Plannerin "inline CSS kaikkialla" -sääntö ei siirry uuteen sovellukseen, koska teemanvaihto vaatii muuttujat | Hyväksytty 14.11.2026 | D9 |
| D11 | Uuden sovelluksen perusta: React + TypeScript + Vite frontendissä, Python backendissä. Korvaa D6:n "kieli pysyy JavaScriptinä" | Hyväksytty 14.11.2026 | Toni, chat |
| D12 | Backend FastAPI + Pydantic + SQLAlchemy + Alembic, tietokanta PostgreSQL (Docker). TypeScript-tyypit generoidaan backendin OpenAPI-kuvauksesta (`openapi-typescript`). Testit pytest + Vitest | Hyväksytty 14.11.2026 | D11 |
| D13 | **Node–Leg-malli (Tonin TMS-käytäntö):** legit ovat aina kahden peräkkäisen Noden välissä. Node on jokainen fyysinen tai suunnittelun piste: terminaali, korjaamo, katsastus, pesupaikka, lastauspaikka (asiakas), purkupaikka (vastaanottaja), satama lähtö, satama saapuminen. **Kun traileri ja vetäjä liitetään keikalle, niiden lähtöpaikoista tulee omat Nodet.** Korvaa R1:n ja R5:n aiemmat ehdotukset (gateway-raja, erillinen Order Leg) | Hyväksytty 14.11.2026 | Toni, chat |
| D14 | Trip = trailerin kuormattu kierros (tarkennettu: D54, kaikki ajot muodostavat tripin; D55). Remain LU = sama Trip, Cross Dock = eri Trip | Hyväksytty 14.11.2026 | Toni, chat |
| D15 | Tyhjän trailerin palautuksen kulu jaetaan keikan ordereille LDM:n mukaan | Hyväksytty 14.11.2026 | Toni, chat |
| D16 | Order on laskutettavissa toimituksen (IOD) jälkeen | Hyväksytty 14.11.2026 | Toni, chat |
| D17 | Keikan alun siirtymät (vetäjä trailerille, tyhjä traileri lastaukseen) kuuluvat samaan Tripiin. Niillä on oma veloitus ajotyypin mukaan: **vetäjä ilman traileria (SOLO / empty truck)** ja **veto tyhjällä trailerilla (EMPTY_TRAILER)** omilla hinnoillaan. Vastaa Freight Plannerin palvelukoodeja 210/220 kuormattu, 211/221 tyhjä, 212/222 vetoyksikkö | Hyväksytty 14.11.2026 | Toni, chat |
| D18 | **Vetäjänvaihto Nodessa** (tarkennettu: D78, kuljettajan vaihto ei muodosta uutta Jobia): missä tahansa Nodessa vetäjän 1 toiminta voidaan katkaista ja liittää vetäjä 2. Vetäjän 1 Job päättyy ja vetäjän 2 Job alkaa, Trip jatkuu (sama traileri). Ostokulut kohdistuvat legeittäin kunkin vetäjän kuljetusyhtiölle | Hyväksytty 14.11.2026 | Toni, chat |
| D19 | Jaettavien kulujen oletusjakoperuste on LDM, ja palvelukoodikohtainen poikkeus on mahdollinen | Hyväksytty 18.11.2026 | Toni, chat (paperitestit R2) |
| D20 | Alihankkijan keikalla kuljettaja voi olla tyhjä. Plan Check näyttää "ajoaikatarkistus alihankkijan vastuulla" | Hyväksytty 18.11.2026 | Toni, chat (paperitestit R4) |
| D21 | Kaksimiehitys ei ole ensimmäisessä versiossa (yksi kuljettaja per Job) | Oletus (Toni ei vastannut 14.11.) | paperitestit R4 |
| D22 | Osittainen käsittely: order jaetaan kahdeksi, ja molemmat osat viittaavat alkuperäiseen Order ID:hen | Hyväksytty 14.11.2026 | Toni, chat |
| D23 | Ensimmäisessä versiossa ovat sekä saattamattomat että saattaen ajettavat lautat. Lauttamatkan aikainen lepo huomioidaan ajoaikalaskennassa (ehdot luetaan 561/2006:sta ennen toteutusta) | Hyväksytty 14.11.2026 | Toni, chat |
| D24 | ADR ja elintarvike samalla trailerilla on esto, jota liikenteenohjaaja ei voi ohittaa (tarkennettu: D56) | Hyväksytty 14.11.2026 | Toni, chat |
| D25 | Perälauta: puoliperävaunussa ei ole perälautaa, joten purku tehdään aina terminaalin kautta (terminaaliflow) | Hyväksytty 14.11.2026 | Toni, chat |
| D26 | Tullaus ensimmäisessä versiossa: tullattava-lippu orderilla, asiakirjaviite ja Plan Check -varoitus puuttuvasta tullauksesta. Tulliasiakirjat ja T1 myöhemmin. *(Korvattu: D48, 16.11.2026.)* | Korvattu → D48 | Toni, chat |
| D27 | Saattamattoman trailerin satamakäsittely: cut-off-aika, vapautus (release), noutotunnus / PIN, säilytysaika ja satamamaksut sekä **sähköön kytkentä satamassa (kyllä / ei)** thermotrailereille | Hyväksytty 14.11.2026 | Toni, chat |
| D28 | Raha tallennetaan PostgreSQL:ssä kokonaislukuina (`*_cents` ×100, `*_e4` ×10 000), laskenta `Decimal`. Freight Plannerin `money.py` ja sen testit siirtyvät muuttamatta | Hyväksytty 14.11.2026 | Toni, chat |
| D29 | Uuden projektin nimi on **FleetFreight TMS** (repo `fleetfreight-tms`) | Hyväksytty 14.11.2026 | Toni, chat |
| D30 | Live-seuranta demossa: simuloidut sijainnit legien suunnitelluista ajoista ja FEC-kuittauksista, välitetään FastAPI-WebSocketilla Leaflet-karttaan. Ei oikeaa GPS-dataa | Hyväksytty 18.11.2026 | Toni, chat |
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
| D41 | **Ensimmäiseen versioon kaikki:** vähimmäisveloitus ja osakuorman hintakatto (= FTL-hinta), purkujärjestys (LIFO multi-dropissa) ja lastauslista kuljettajalle, ADR-pisteet kuljetusyksikölle ja luokkien yhteenkuormauskiellot (Plan Check, vaihe 5), sekä **lavanvaihto ja lavasaldot** (toteutus: D59; lavatyyppi ja vaihdetut lavat lastaus- ja purkutapahtumiin vaiheessa 2, saldot asiakkaittain ja laskutus vaiheessa 6) | Hyväksytty 15.11.2026 | Toni, chat |
| D42 | **Lähtöpöytä ja Tripit-sivu** (näkymän nimi Tripsuunnittelu, D74). Lähtöpöydällä kootaan Trip: vapaat orderit, kuormatila, vetäjät ja kuljettajat, lautat ja muut Nodet yhdistetään Node–Leg-ketjuksi, ja Plan Check ajetaan ennen vahvistusta. Tripit-sivulla kaikki tripit tiloittain (KPI:t, haku, täyttö, lautta, Plan Check, kate). Layout: Design-kangas 16.11.2026 | Hyväksytty 16.11.2026 | Toni, chat |
| D43 | **Tripin tietosivu välilehdillä:** Yleiset, Node–Leg, Orderit, Vaaralliset aineet, Lämpötila, Tulli (lisätty 16.11.2026, D48), Dokumentit, Kulut ja kate. ADR- ja lämpötilatiedot eivät ole erillisiä sivuja vaan tripin välilehtiä. Näiden kahden välilehden sisältö määräytyy D44:n, D46:n ja D47:n mukaan | Hyväksytty 16.11.2026 | Toni, chat |
| D44 | **Vaaralliset aineet ja lämpötilavaatimus kirjataan orderille, Trip johtaa ne.** Orderin luonnissa on ADR-täppä, josta avautuu ADR-välisivu DG-riveille: UN-numero, kuljetusnimi, luokka, pakkausryhmä, määrä ja yksikkö, kuljetuskategoria, rajoitettu määrä -lippu. Thermo vastaavasti: min, max, esijäähdytys, GDP. Tripillä ei ole käsin asetettavaa täppää: kun tripillä on yksikin ADR-order, tripin otsikossa, Tripit-listassa ja tripsuunnittelussa näkyy ADR-merkki, ja tiukin lämpötila johdetaan kyydissä olevista ordereista | Hyväksytty 16.11.2026 | Toni, chat |
| D45 | **ADR-avustin tripille, periaate:** avustin on päätöstuki, ei päätä. Se laskee ja näyttää tripin DG-tilanteen (pisteet, vapautus, merkinnät, pakolliset varusteet ja asiakirjat) ja valitsee sovellettavan säännöstön **legeittäin**. Kertoimet, rajat ja säännöt ovat versioitu sääntötaulukko ADR-painoksen mukaan. Vastuu luokittelusta lähettäjällä, tarkistus turvallisuusneuvonantajalla | Hyväksytty 16.11.2026 | Toni, chat |
| D46 | **ADR-avustimen säännöt (tarkistettu lähteistä 16.11.2026, ks. luku 3C):** pisteet kuljetusyksikölle 1.1.3.6.4:n mukaan ja "mitä jos" -laskelma uudelle orderille; alle rajan luku 5.3 (oranssit kilvet ja suuret varoituslipukkeet), 5.4.3 (kirjalliset turvallisuusohjeet), osa 8 poikkeuksin ja osa 9 eivät koske, mutta kuljetusasiakirja ja jäljelle jäävät osan 8 vaatimukset säilyvät; yli rajan oranssit kilvet, kappaletavarassa suuret varoituslipukkeet lisäksi luokille 1 ja 7; legin säännöstö ROAD = ADR, Itämeren ro-ro-lautta = Itämeren MoU, muu merilegi = IMDG; **merilegillä 1.1.3.6-vapautusta ei käytetä** (A1); DG-ilmoitus varustamolle ennen cut-offia. Sääntötaulukossa ADR 2025 ja ADR 2027 erikseen | Hyväksytty 16.11.2026 (MoU §10 -merkinnät tarkistetaan ennen vaihetta 5) | Toni, chat |
| D47 | **Lämpötila-välilehti ja -valvonta:** kuormatilan lohkot ja asetusarvot (tiukin orderivaatimus), kylmäkone ja ATP-luokka voimassaoloineen, anturit kalibrointipäivineen, esijäähdytyksen kuittaus, käyrä sallitulla alueella ja Node-merkinnöillä, hälytykset ja kuljettajan kuittaus syineen, satamasähkö (D27), CSV ja PDF-raportti tallennetusta datasta (ei muokattavissa jälkikäteen). Demossa anturidata simuloidaan (D30). Lisäksi Lämpötilavalvonta-näkymä käynnissä oleville thermo-tripeille | Hyväksytty 16.11.2026 | Toni, chat |
| D48 | **Tullaus v1:ssä täytenä, ADR:n mallilla (korvaa D26):** orderilla Tullattava-täppä, josta avautuu tullin välisivu: menettely (vienti, tuonti, passitus T1 / T2 / T-, TIR, ATA), MRN, edellinen asiakirja, lähtö-, kauttakulku- ja määrätullitoimipaikka, ilmoittaja (asiakas tai tulliasiamies), vakuus, Incoterms ja sinetin numero. TIR-vaijeri pysyy D36:n mukaisesti orderin vaatimuksena ja trailerin ominaisuutena, eikä sitä kirjata tullisivulle uudelleen. Tripillä johdettu TULLI-merkki ja Tulli-välilehti. Tullin vaiheet tapahtumina Nodeissa (vienti hyväksytty, passitus avattu, saapunut määrätoimipaikkaan, passitus päätetty, tullattu); toteutuneita tullitapahtumia ei poisteta, korjaukset vastakirjauksina (sääntö 9). Plan Check tunnistaa reitin Nodeista tulli- ja verorajan ylitykset versioidun alue- ja maataulukon perusteella (EU:n tullialueen ulkopuoliset maat, yhteisen passituksen maat, veroalueen ulkopuoliset alueet kuten Ahvenanmaa) ja varoittaa puuttuvasta tullattava-tiedosta, MRN:stä tai vakuudesta, tullitoimipaikan aukioloajasta ja cut-offista. **T1 mukana heti:** passituksen tiedot tavarariveineen ja PDF-yhteenveto, joka on selvästi merkitty demoksi eikä jäljittele virallista saateasiakirjaa. Ei oikeaa sähköistä ilmoittamista (NCTS); MRN:t, tullitoimipaikat ja vakuudet ovat keksittyjä ("Demo"-nimet, ei oikeita koodeja tai MRN-muotoa). Säännöt ja maat tarkistetaan lähteistä ennen toteutusta (luku 3D) | Hyväksytty 16.11.2026 | Toni, chat |
| D49 | **Teema- ja kielivalinta tallennetaan käyttäjälle tietokantaan** (`users`-taulun kentät uudella Alembic-revisiolla, tallennus-endpoint, `/auth/me` palauttaa valinnat). Selain muistaa valinnan välimuistina kirjautumissivua varten. Toteutus vaiheen 2 alussa. Tarkentaa D9:ää | Hyväksytty 16.11.2026 | Toni, chat |
| D50 | **R3:n kolme tilaketjua hyväksytään, ja jokaiseen lisätään päätetila Peruttu** (tarkennettu: D53). Peruttu on sallittu vain ennen toteutuksen alkua, tilasiirtyminä: **Order** tiloista Avoin, Reititetty ja Suunniteltu (ei Kuljetuksessa tai myöhemmin); peruttu order irrotetaan tripiltä, ja tripin täyttö ja Plan Check lasketaan uudelleen. **Trip** tiloista Suunniteltu ja Vahvistettu, kun mikään sen legi ei ole toteutunut eikä mikään sen Job ole Käynnissä tällä tripillä (alun siirtymät D17 mukaan lukien); orderit palaavat tilaan Avoin ja näkyvät vapaina tripsuunnittelussa (D42). **Job** tiloista Avoin, Osoitettu ja Vahvistettu; legit jäävät ilman Jobia uutta osoitusta varten. Toteutuksen alettua tilalle tulee poikkeama ja korjaus vastakirjauksena (sääntö 9). Peruutusmaksun laskutus: avoin kysymys A2 | Hyväksytty 16.11.2026 | Toni, chat |
| D51 | **Tilavärit yhteisinä väriryhminä**, joihin kunkin ketjun tilat kuvataan: Avoin (Order Avoin ja Reititetty, Job Avoin), Suunniteltu (Order ja Trip Suunniteltu, Job Osoitettu), Vahvistettu (Trip ja Job), Käynnissä (Order Kuljetuksessa, Trip ja Job Käynnissä), Valmis (Order Toimitettu, Trip Kuormat toimitettu, Job Valmis), Lukittu (Order Laskutettu, Trip Suljettu), Peruttu (kaikki). Poikkeama (esim. myöhästyminen) on oma merkki tilan päällä, ei tila. Sama väri tarkoittaa samaa joka näkymässä ja kummassakin teemassa | Hyväksytty 16.11.2026 | Toni, chat |
| D52 | **Luonnostrippi (K1):** trippi syntyy tilaan Luonnos heti, kun ensimmäinen order liitetään siihen. Reitti tallentuu suoraan tripin Node–Leg-ketjuun, ja kuormatila voi olla tyhjä, kunnes trippi suunnitellaan | Hyväksytty 17.11.2026 | Toni, chat |
| D53 | Trip-tilaketjun alkuun tila **Luonnos**: Luonnos → Suunniteltu → Vahvistettu → Käynnissä → Kuormat toimitettu → Suljettu (+ Peruttu, myös Luonnoksesta). Väriryhmä Avoin (D51) | Hyväksytty 17.11.2026 | Toni, chat |
| D54 | **Kaikki ajot muodostavat tripin (K2, tarkentaa D14):** jokainen trippi koostuu orderista, Nodeista ja legeistä. Orderilla on tyyppi: tavara, tyhjä kuormatila (esim. tyhjän kärryn lähetys), huolto, pesu, katsastus, siirto. Maksaja voi olla asiakas (laskutetaan normaalisti) tai oma yritys (sisäinen order: sisäinen laskutus, kulut kalustolle). Pesu, jonka edellinen kuorma aiheutti, laskutetaan aiheuttajalta: pesuorder viittaa aiheuttaneeseen orderiin; järjestelmä ehdottaa, liikenteenohjaaja päättää. Täyttöaste ja kuormatyyppitilastot lasketaan vain tavaraordereista | Hyväksytty 17.11.2026 | Toni, chat |
| D55 | **Kuorma-auto + täysperävaunu v1:ssä (K3):** legi on vetoyksikön fyysinen siirtymä, ja sama legi voi kuulua usealle tripille (auton kuormatila ja perävaunu), joten km ja ajoaika lasketaan kerran. Tripit seuraavat kuormatilaa, Jobit vetäjää, ja ne kohtaavat Nodeissa: esim. yhdistelmä lautalla, perävaunu irrotetaan sataman parkkiin (Job irtoaa tripiltä, trippi jatkuu), vetäjä kytkee toisen kärryn (uusi trippi), toinen vetäjä noutaa jätetyn kärryn ja sama trippi jatkuu | Hyväksytty 17.11.2026 | Toni, chat |
| D56 | **ADR + elintarvike (K4, tarkentaa D24):** esto legeittäin samanaikaisesti kyydissä oleville ordereille. Jos kuormatilassa on aiemmin ollut ADR-tavaraa, Plan Check varoittaa ja ehdottaa pesu-Nodea; kirjattu vuoto on esto. Tavaralaji kirjataan orderille | Hyväksytty 17.11.2026 | Toni, chat |
| D57 | **Tripin kiinteät kulut (K5)** (esim. trailerin vuokra, tyhjä palautus) jaetaan ordereille LDM:n mukaan; legikohtaiset kulut vain legillä kyydissä oleville. Palvelukoodikohtainen poikkeus sallittu (D19) | Hyväksytty 17.11.2026 | Toni, chat |
| D58 | **Passitus (K6):** yksi passitusilmoitus voi kattaa useita ordereita, tavararivit ordereittain. Myös yksi ilmoitus per order on mahdollinen | Hyväksytty 17.11.2026 | Toni, chat |
| D59 | **Lavanvaihto (K7, toteuttaa D41):** asiakaskohtainen asetus "lavanvaihto sovittu", oletuksena pois päältä. Kun päällä, purussa ja lastauksessa kirjataan vaihdetut lavat, ja saldot pidetään kaikille vastapuolille (asiakas, kuljetusliike, paikka). Vajeiden laskutus vaiheessa 6. Yleinen alan käytäntö: lavanvaihto on sopimuskohtainen | Hyväksytty 17.11.2026 | Toni, chat |
| D60 | **Kuormatilarekisteri:** kuormatila on oma yksikkönsä (`load_units`), jonka tyyppi v1:ssä on **traileri** tai **kuorma-auton kiinteä kori** (D39). Trippi seuraa kuormatilaa (D55). Vaihtokori (irrotettava kuormatila) ja merikontti myöhemmin (juna: muutettu D63:lla); vaihtokori lisätään uutena tyyppinä samaan tauluun | Hyväksytty 17.11.2026 | Toni, chat |
| D61 | **HCT ja dolly v1:ssä:** dolly on kalustoa ilman kuormatilaa ja kytketään legille. Plan Check laskee yhdistelmän pituuden ja kokonaismassan ja tarkistaa, onko reitti sallittu yhdistelmälle. Raja-arvot ja sallitut reitit tarkistetaan lähteistä ennen vaihetta 5; demossa ne ovat asetuksia | Hyväksytty 17.11.2026 | Toni, chat |
| D62 | **Lauttayhteydet demossa (todenmukaiset reitit, keksityt varustamot):** reitit, satamat ja vuorovälit julkisten tietojen pohjalta, varustamot Demo-nimin (sääntö 5 pysyy). Jokainen yhteys molempiin suuntiin omina reitteinään ja vuoroinaan; kiertävien linjojen paluu voi kulkea eri satamien kautta. Yhteydet: Vuosaari–Travemünde päivittäin (saattaen ja saattamatta), Vuosaari–Tallinna päivittäin (varmistetaan ennen toteutusta), Kotka–Lübeck ja Kotka–Hanko–Antwerpen (saattamaton), Kotka–Antwerpen viikoittain, Hanko–Gdynia 6/vko, Hanko–Rostock 4/vko, Oulu–Travemünde–Antwerpen viikoittain, Naantali–Långnäs–Kapellskär 2/pv. Uudet demosatamat Naantali, Långnäs (Ahvenanmaa, veroraja) ja Kapellskär; Norjaan Ruotsin kautta | Hyväksytty 18.11.2026 | Toni, chat |
| D63 | **Juna v1:ssä (muuttaa D60:n rajausta):** kulkumuoto RAIL ROAD- ja FERRY-legien rinnalle. Juna toimii kuten saattamaton lautta: kuormatila kulkee ilman vetäjää ja Jobia. Junaterminaalit paikkoina, rautatieoperaattori keksitty (Demo Rail). Ensimmäinen yhteys Rostock ja Travemünde ↔ Demo Rail Terminal Verona (nimi tarkennettu 18.11.2026) molempiin suuntiin. Plan Check tarkistaa kuormatilan junakelpoisuuden | Hyväksytty 18.11.2026 | Toni, chat |
| D64 | **Reititysehdotus kohdemaan mukaan (asetustaulukko):** Italia → Rostock ja juna Veronaan; Belgia, Ranska, Espanja, Alankomaat → Antwerpen; Saksa, Itävalta, Sveitsi → Travemünde tai Lübeck; Puola → Gdynia; Baltia → Tallinna; Norja → Kapellskär ja maantie Svinesundin kautta. Järjestelmä ehdottaa orderin luonnissa, liikenteenohjaaja päättää (sääntö 8). V1 maatasolla; tarkempi alue (esim. postinumero) myöhemmin, tarkempi sääntö voittaa. Yleinen alan reitityslogiikka | Hyväksytty 18.11.2026 | Toni, chat |
| D65 | **Vaiheen 4 pääskenaario Jyväskylä–Vantaa–Lübeck, alku edellisen kuorman purusta:** sama vetäjä ja traileri ovat purkaneet edellisen tripin Jyväskylän seudulla; uusi trippi alkaa purkupaikalta tyhjänä siirtona (EMPTY_TRAILER, D17) lastaukseen Jyväskylässä → Demo Terminal Central (Vantaa) → Vuosaari → lautta → purku Lübeckissä. Näyttää tripien ketjuuntumisen samalle kalustolle ja kuljettajan ajoajan yli tripien. Lisäskenaariot myöhemmin: tyhjä traileri poolista terminaalista ja drop-and-hook (SOLO) | Hyväksytty 18.11.2026 | Toni, chat |
| D66 | **Terminaalin kylmätila v1:ssä yhtenä lämpötila-alueena:** Plan Check tarkistaa, onko terminaalissa kylmätila ja osuuko orderin lämpötila alueelle; muuten varoitus. Erilliset vyöhykkeet (pakaste, kylmä, GDP +15…+25 °C, GDP-kartoitus) myöhemmin omana tauluna | Hyväksytty 18.11.2026 | Toni, chat |
| D67 | **Pätevyyksien historia säilyy:** jokaisesta voimassaolojaksosta oma rivi (voimassa alkaen ja asti). Uusiminen luo uuden rivin, vanha jää historiaan. "Voimassa nyt" ja "voimassa ajopäivänä" haetaan jaksoista. Koskee kuljettajien pätevyyksiä ja kaluston kelpoisuuksia | Hyväksytty 18.11.2026 | Toni, chat |
| D68 | **Postinumero ja kaupunki omiksi kentiksi paikoille:** demossa oikea postinumero ja kaupunki, katuosoite keksitty (esim. "Demo Street 1, 33100 Tampere"). Postinumero on julkista aluetietoa eikä yksilöi ketään, kun katuosoite on keksitty; tarkentaa sääntöä 5 (ei oikeita osoitteita) tältä osin. Käyttö: asiakashinnasto (vaihe 3), CMR (vaihe 6), tarkempi reititysehdotus (D64) | Hyväksytty 18.11.2026 | Toni, chat |
| D69 | **GDP-koulutuksen oletusvoimassaolo on asetus** (oletus 12 kk). Voimassaolo voidaan aina kirjata käsin todistuksen mukaan. Käyttöliittymässä ja dokumentaatiossa merkitään, että kyse on yrityksen käytännöstä eikä säädöksestä | Hyväksytty 18.11.2026 | Toni, chat |
| D70 | **Pätevyydet ja kelpoisuudet erillisissä tauluissa:** kuljettajan pätevyydet (`driver_qualifications`: ADR-ajolupa ja laajuudet, ajokortti, ammattipätevyys, kuljettajakortti, GDP) ja kaluston kelpoisuudet (oma taulu vaiheessa 2B-2: esim. ADR-hyväksyntä, ATP, GDP-kartoitus, perälauta). Molemmissa voimassaolot jaksoina (D67) | Hyväksytty 18.11.2026 | Toni, chat |
| D71 | **Node on fyysinen pysähdys, joka voi kuulua usealle tripille (tarkentaa D13 ja D55):** Node ei omista trippiä. Tripin Node–Leg-ketju muodostuu sen legeistä (`leg_trips`). Yhdistelmässä tripit jakavat samat Nodet ja legit, joten pysähdys, ajat ja kuittaukset kirjataan kerran. Yhden tripin ajossa ei muutosta | Hyväksytty 18.11.2026 | Toni, chat |
| D72 | **Rekisteririvit arkistoidaan, ei poisteta:** asiakkailla, paikoilla, kuljetusliikkeillä, kuljettajilla ja kalustolla tila aktiivinen / arkistoitu (`archived_at`). Arkistoitu ei näy valintalistoissa, mutta historia, vanhat tripit ja raportit säilyvät. Fyysinen poisto estetään (RESTRICT), jos riviin viitataan; admin voi poistaa vain rivin, jolla ei ole viittauksia. Toteutetaan uudella revisiolla ennen ensimmäistä rekisteri-API:a (koskee myös `driver_qualifications`: CASCADE → RESTRICT) | Hyväksytty 18.11.2026 | Toni, chat |
| D73 | **Oma yritys yhtenä tietona:** oman kuljetusliikkeen rivi (`carriers`, type own) viittaa oman yrityksen asiakasriviin (`customers`, own_company), ja nimi ja tunnus luetaan sieltä. Tietokanta varmistaa linkin ja sen, että kumpaakin on enintään yksi. Toteutetaan samassa revisiossa kuin D72 | Hyväksytty 18.11.2026 | Toni, chat |
| D74 | **Käyttöliittymän termistö on alan arkikieltä, sama kuin dokumentaatiossa:** suomeksi Tripit, Orderit, Tripsuunnittelu, Board; englanniksi Trips, Orders, Trip planner, Board. Tripsuunnittelu (D42:n tripsuunnittelu) on tripin kokoamisnäkymä, Board päivän ajojen seuranta. Yksi sanasto koko järjestelmässä | Hyväksytty 18.11.2026 | Toni, chat |
| D75 | **Kuormatilan mallikoodi ja tekniset ominaisuudet erikseen (hybridiluokittelu, FleetFlow-projektin suunnitelma FF-003A 12.11.2026):** mallikoodit thermo – kaikissa yksi kylmäkone keulassa – FB (Thermo Box, umpikori, yksi sisäyksikkö ja yksi lämpötilavyöhyke), FD (Thermo Double, kaksi sisäyksikköä ja kaksi vyöhykettä väliseinällä erotettuna), FS (Thermo Side, sivusta avattava, muuten kuten FB; tarkennettu 18.11.2026) – Tonin keksimiä; pressu CS, MEGA, COIL – yleisiä. Lisävarusteet erillisinä tietoina (esim. MEGA + kelakouru, ei MEGA_COIL-mallia). Yhteensopivuus ratkaistaan todellisista ominaisuuksista, ei mallikoodista | Hyväksytty 18.11.2026 | Toni, FleetFlow-suunnitelma FF-003A ja chat |
| D76 | **Kylmäkone, sisäyksiköt ja lämpötilavyöhykkeet (tarkennettu 18.11.2026):** kuormatilalla yksi kylmäkone keulassa; koneella voimanlähde ja kylmäkonehuolto (kelpoisuusjakso, D67). Koneella sisäyksiköt (höyrystimet), joista kukin palvelee yhtä lohkoa: FB ja FS yksi sisäyksikkö ja yksi vyöhyke, FD kaksi sisäyksikköä (keula ja perä) ja kaksi vyöhykettä (lohkoa), esim. keula −18 °C ja perä +10 °C. Lohkon lämpötila-alue kertoo, mihin se pystyy; kuorman asetusarvo kirjataan orderille tai kuormalle; vain FD:llä on väliseinä, ja jokaisella FD:llä on se. Väliseinä ylhäällä FD lastataan yhtenä tilana; tämä on tripin tila, ei rekisterin. Lohkojen itsenäinen säädettävyys trailerikohtainen. **Väliseinä:** laskeutuu katosta, paksuus n. 50 mm, siirtyy yhden EUR-lavarivin (2 lavaa) askelin, vähintään 4 EUR-lavaa etu- ja takaosastoon, valinnaisesti takaosaston enimmäisosuus lavariveistä (jotkin kylmäkoneet rajoittavat takavyöhykkeen esim. 1/3:aan tilasta; tyhjä = ei rajaa; vain väliseinälliselle); väliseinä kuluttaa kuormatilaa vain paksuutensa verran (ei noin 2 LDM), ja osastojen kapasiteetti lasketaan todellisista mitoista: 13,6 m:n tilaan mahtuu väliseinä alhaalla 32 EUR-lavaa, kumpaankin osastoon vähintään 4. Väliseinän paikka valitaan kuormalle (4 + 28, 6 + 26 … 28 + 4 EUR-lavaa), joten FD:n lohkoilla ei ole rekisterissä kiinteitä lavamääriä. Arvot trailerikohtaisia | Hyväksytty 18.11.2026 | Toni, FleetFlow-suunnitelma FF-003A ja chat |
| D77 | **Plan Checkin neljä tasoa:** OK (vaatimukset täyttyvät), RISK (riski edellyttää käsittelyä), OPEN (tieto tai vahvistus puuttuu), BLOCKED (kriittinen vaatimus ei täyty). Kriittinen puute tai ristiriita estää vahvistuksen; liikenteenohjaaja näkee perustelut ja korjausehdotukset. **Toimintalogiikka (tarkennettu 18.11.2026, FleetFlow-suunnitelma Plan Checkin tiloista):** jokainen tarkistus tuottaa oman tuloksensa (tila, perustelu, korjausehdotus), ja kaikki tulokset tallennetaan, vaikka näkymä näyttää yhden kokonaistilan. Tarkistuksella on tieto, onko se pakollinen; v1:ssä pakollisuus on kiinteä tarkistustyypin mukaan (esim. lämpötilakyky, ADR, ajo- ja lepoajat, kantavuus ja päällekkäiset varaukset pakollisia; ETA ei), myöhemmin pääkäyttäjän asetus samoin oletuksin. Kokonaistila: BLOCKED, jos yksikin esto; muuten OPEN, jos pakollinen tieto puuttuu; muuten RISK, jos käsiteltäviä riskejä; muuten OK. Ei-pakolliset OPEN-tulokset näytetään erillisinä huomioina. RISK kuitataan perustelulla (kuittaaja, aika ja perustelu tallennetaan); kuittaus sidotaan tarkistuksen syötteisiin ja raukeaa, kun ne muuttuvat (esim. ajat, reitti tai kalusto), mutta ei tarkistukseen liittymättömästä muutoksesta; pakollisia turvallisuus- ja kuljetusvaatimuksia ei voi kuitata. Plan Check ajetaan uudelleen aina suunnitelman muuttuessa. Kuormatila ja käyttökelpoisuus erillisiä: tyhjä ≠ puhdas tai soveltuva (tila: puhdistettava, soveltuu, käyttökelvoton; toteutus vaiheessa 2C) | Hyväksytty 18.11.2026 | Toni, FleetFlow-suunnitelma FF-003A ja chat |
| D78 | **Job = vetoauto (tarkentaa D18):** vetoauton vaihto muodostaa uuden Jobin, kuljettajan vaihto ei. Kuljettajat ovat Jobin sisällä aikajaksoina (`job_drivers`), ja vaihto kirjataan tapahtumaksi Nodessa. Ajo- ja työaika lasketaan kuljettajakohtaisesti. Rakenne sallii kaksimiehityksen myöhemmin (D21: ei v1:ssä). Lähde: FleetFlow-liite A, kohdat 12 ja 36 | Hyväksytty 18.11.2026 | Toni, chat |
| D79 | **Kuorman lämpötilaluokka näytetään merkkeinä Thermo ja Pressu** (en: Thermo, Curtainsider). FleetFlow-suunnitelman lyhenteitä TK ja PK ei käytetä. Tieto johdetaan orderin lämpötilavaatimuksesta (D44, D36); ei sekoitu kuormatyyppeihin FTL, PTL ja LTL | Hyväksytty 18.11.2026 | Toni, chat |
| D80 | **Aikatyypit FIX, Termin, ETA ja Sovittava** (FleetFlow-liite A, kohta 34). Aikatyyppi ja aika kirjataan orderille erikseen lastaukselle ja purulle: päivä (FIX ja ETA) omassa sarakkeessaan ja Terminin kellonajat kahdella sarakkeella, alku ja loppu. Noden suunniteltu aika lasketaan, ja Plan Check (D77) vertaa sitä orderin aikaan. **FIX:** asiakas on maksanut toimituksesta tiettynä päivänä, esim. FIX 20.11.; ehdoton molempiin suuntiin: aikaisempi päivä BLOCKED (ei pureta etuajassa, esim. varasto täynnä tai purku suoraan toiseen kärryyn) ja myöhempi päivä BLOCKED; ei marginaalia, kellonaika tarkistetaan paikan aukioloaikoja vastaan erikseen. **Termin:** sovittu päivä ja kellonaika tai aikaikkuna, esim. 20.11. klo 14–16; ikkunan lopun jälkeen BLOCKED, alle marginaalin ennen loppua RISK, ennen ikkunan alkua OK (auto odottaa, odotusaika näytetään); Termin ilman loppua on viimeinen sallittu saapumisaika. **ETA:** asiakkaalle ilmoitettu arvioitu toimituspäivä, ei sitova; myöhempi päivä vain RISK. **Sovittava:** aika sovitaan erikseen; ei-pakollinen OPEN, joten trip voidaan suunnitella ja vahvistaa ja aika täydennetään myöhemmin. Päiviä verrataan paikan paikallisena päivänä. Marginaali on asetus, oletus 30 min. **Tärkeysjärjestys** (sitovin ensin), jota käytetään ristiriidoissa, järjestämisessä ja optimoinnissa: 1. FIX, 2. Termin, 3. ETA, 4. Sovittava. Tarkennettu 19.11.2026: FIX on päivä eikä kellonaika; ETA on päivä; aikainen saapuminen Terminiin OK. Toteutus: `domain/time_types.py` | Hyväksytty 19.11.2026 | Toni, chat |
| D81 | **Mobiili ja tabletti: responsiivinen web ja PWA.** Sama React-sovellus toimii tietokoneella, tabletilla ja puhelimella; ei erillistä sovelluskauppasovellusta v1:ssä. Taitekohdat: tabletti ≤ 1024 px (sivupalkki oletuksena kuvakkeina), puhelin ≤ 640 px (valikko laatikkona, teema, kieli ja uloskirjautuminen valikossa, kosketuskohteet vähintään 44 px). PWA-manifesti, jolla sovelluksen voi lisätä aloitusnäytölle. **Laitteet roolin mukaan:** liikenteenohjaajan raskaat näkymät (Board, Tripsuunnittelu) tietokoneelle ja tabletille; puhelimella tripin tiedot, tilat, Plan Check -huomiot, kuittaukset ja hyväksynnät; kuljettajan FEC-sivu puhelimelle. Jokainen uusi näkymä testataan puhelimen ja tabletin leveydellä. Natiivikuori (esim. Capacitor) vasta, jos tarvitaan push-ilmoituksia, kameraa tai offline-tilaa | Hyväksytty 19.11.2026 | Toni, chat |

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
| R2 | Kulujen jako ordereille | Lauttakulu jaetaan tasan | LDM / paino / tavaramäärä | **Osin ratkaistu: D15, D19, D57.** Kulu kirjataan sinne, missä se syntyy. Jakoperuste palvelukoodin mukaan, oletus LDM. Aiheuttajan kulut suoraan orderille. Jako jäädytetään laskutuksessa (`cost_allocations`). Tyhjä palautus: **LDM keikan ordereille (D15)** |
| R3 | Elinkaari ja laskutus | Trip-statusketju, Laskutettu lukitsee tripin | Trip jatkuu toimituksen jälkeen | **Ratkaistu: D50 (hyväksytty 16.11.2026).** Kolme tilaketjua: **Order** Avoin → Reititetty → Suunniteltu → Kuljetuksessa → Toimitettu → Laskutettu. **Trip** (Luonnos, D53) → Suunniteltu → Vahvistettu → Käynnissä → Kuormat toimitettu → Suljettu. **Job** Avoin → Osoitettu → Vahvistettu → Käynnissä → Valmis. Myynti laskutetaan orderilta. Laskutus lukitsee orderin, ei Tripiä. Korjaukset vastakirjauksina, kaikissa ketjuissa lisäksi päätetila Peruttu |
| R4 | Jobin kuljettajarajaus | Ei Job-käsitettä | Yksi kuljettaja vai useampi? (FF #8) | **Ratkaistu: D18, D20, D21.** Job = yksi vetäjä ja kuljettaja. Vaihto Nodessa luo uuden Jobin, Trip jatkuu. Job ja Trip ovat N:M legien kautta. Ajo- ja työaika lasketaan kuljettajalle yli Jobien ja päivien |
| R5 | Fyysinen Leg vs. Order Leg | Ei kumpaakaan | Molemmat käsitteinä, suhde avoin | **Ratkaistu: D13.** Yksi Leg-käsite: fyysinen siirtymä kahden Noden välillä (ajotyyppi SOLO / EMPTY_TRAILER / LOADED_TRAILER, kulkumuoto ROAD / FERRY). Job vapaaehtoinen (saattamaton traileri lautalla). Kilometrit ja ajoaika lasketaan vain legeistä |
| R6 | Kuljettajat | Ei kuljettajia, vain vetäjät ja kuljetusyhtiöt | Kuljettaja on keskiössä | **Osin ratkaistu: toteutettu 2B-1:ssä** (kuljettajat ja heidän pätevyytensä). Uusi `drivers`-taulu: kuljetusyhtiö, kotipaikka (kotiinpaluu ja viikkolepo), työsuhde (oma / alihankkijan nimetty). Pätevyydet `driver_qualifications`- ja `equipment_qualifications`-tauluihin (D70) |
| R7 | Gateway Instructions | Suunniteltu "Gateway Instruction List" | "Gateway Instructions PDF" | **Osin ratkaistu: vaiheen 6 dokumenttimoduuli.** Sama dokumentti, johdetaan legeistä. V1:ssä versionumero ja "muuttunut lähetyksen jälkeen" -varoitus |

### Avoimet kysymykset (selvitettävä ennen toteutusta)

- **A1 (D46): ratkaistu 16.11.2026.** Itämeren MoU:n §3(2) luettelee ne ADR:n 1.1.3-vapautukset, joiden ansiosta IMDG:tä ei sovelleta laivalla, eikä 1.1.3.6 ole luettelossa. Merilegillä pistevapautus ei siis päde: DG-tiedot (UN-numerot ja luokat) annetaan varustamolle aina. Kuljetusyksikön merkinnät merilegillä (MoU §10) tarkistetaan koko MoU-tekstistä ennen vaihetta 5, koska käytettävissä oli vain ote.
- **A2 (D50):** miten perutun orderin peruutusmaksu laskutetaan, kun Peruttu on päätetila eikä siitä ole siirtymää tilaan Laskutettu? Vaihtoehdot: maksu erillisenä myyntirivinä (`costs`), jonka laskutus merkitään riville orderin tilan pysyessä Peruttuna, tai sallittu siirtymä Peruttu → Laskutettu. Ratkaistaan ennen vaiheen 2 tilakoneita.

Perustelut ja skenaarioittaiset rivit: `analyysi/paperitestit.md`. Tonille esitetyt kysymykset: saman raportin luku 4 (14 kysymystä), vastattu 14.11.2026 (D13–D27).

---

## 2B. Toimialueen kattavuus: kaikki mukaan

Periaate: **kaikki kummankin projektin toimialuekäsitteet tulevat mukaan yhdistettyyn järjestelmään.** Mitään ei pudoteta. Päällekkäiset toteutukset yhdistetään yhdeksi.

Tila: ✅ toteutettu koodissa · 📄 suunniteltu tai dokumentoitu · ⚠️ osittain (pelkkä lippu tai demo) · — puuttuu

| Käsite | Freight Planner | FleetFlow | Yhdistetyssä | Moduuli |
|---|---|---|---|---|
| **Kuormatilat** (ent. trailer pool) | ⚠️ trailerilista, leasing- ja vuokrahinnat, katsastus ja huolto | ⚠️ trailerit jobeilla | Kuormatilarekisteri (`load_units`: traileri tai kuorma-auton kiinteä kori, D60); trailer pool: sijainti, tila (vapaa / varattu / lastattu / tyhjä / huollossa), seisontapäivät ja siirtohistoria | resurssi |
| **Asiakkaat** | ✅ rekisteri, tyyppi, asiakashinnasto, lisäsäännöt | ⚠️ demonimet jobeilla | ✅ rekisteri ja toimipaikat (`locations`) 2B-1:ssä; asiakashinnasto ja lisäsäännöt vaiheessa 3 | kuorma |
| **Kuljetusliikkeet** | ✅ kuljetusyhtiöt | ⚠️ carrier jobilla | ✅ rekisteri (oma / alihankkija) 2B-1:ssä, kuljettajat kuljetusliikkeittäin | resurssi |
| **Vetäjät** | ✅ vetäjät kuljetusyhtiöittäin | ✅ truck-keskeinen suunnittelu (Fleet Timeline) | FP:n rekisteri + varaukset ja päivän työjono | resurssi |
| **Kuljettajat** | — | ✅ kuljettaja jobilla, ajotunnit | ✅ rekisteri ja pätevyydet voimassaolojaksoina (D67) 2B-1:ssä; aikalaskenta vaiheessa 5 | resurssi |
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
| **Terminaalit** | ✅ 16 demoterminaalia, CRUD | ⚠️ nodet | ✅ `locations` 2B-1:ssä (mm. terminaali, satama, junaterminaali, tullitoimipaikka, asiakkaan toimipaikka, varikko) | yhteinen |
| **Maarajoitukset** | ✅ ajokiellot, painorajat, reittitarkistin | — | Syötteenä toteutettavuustarkistukseen | resurssi |
| **Ajo-, työ- ja lepoajat** | 📄 suunniteltu laskuri | ⚠️ 4,5 h -tarkistus | Toteutettavuusmoottori (luku 4) | resurssi |
| **Kartta ja reitit** | 📄 #13 OpenRouteService | ✅ Leaflet, Route & Risk | Leaflet-näkymä + reitityspalvelu | resurssi |
| **Kulut, hinnoittelu, kate** | ✅ palvelukoodisto, lisähinnat, asiakashinnasto, km-hinnat | 📄 kustannusten jako | FP:n moottori + jakoperuste (R2) | kuorma |
| **FEC-kuittaukset** | ✅ kuljettajan mobiilisivu, odotusaika-automaatti | 📄 simuloitu FEC | FP:n sivu + salainen token + kuittaukset `handling_events`-tauluun | molemmat |
| **Dokumentit** | 📄 Transport Order, CMR, lasku, Credit Note | 📄 Gateway Instructions PDF | Yksi dokumenttimoduuli (R7) | kuorma |
| **Dashboard ja KPI** | ✅ dashboard, Costs Dashboard | ✅ Board, päivän yhteenveto | Kuorma- ja liikennenäkymä erikseen, yhteiset KPI:t | molemmat |
| **Hallinta ja asetukset** | ✅ kalusto, hinnoittelu, asetukset | ✅ teemat | FP:n hallinta + FF:n teemat | yhteinen |
| **Tripsuunnittelu** | — | ⚠️ Board | Tripin kokoaminen: vapaat orderit, kuormatila, vetäjät, lautat ja Nodet, Plan Check ennen vahvistusta (D42) | kuorma |
| **Tullaus** | ⚠️ tullattava-lippu | — | Tullitiedot orderilla, tullin vaiheet Nodeissa, T1-passitus ja demo-PDF (D48) | kuorma |
| **Lavanvaihto ja lavasaldot** | — | — | Lavatyyppi ja vaihdetut / vaihtamatta jääneet lavat käsittelytapahtumissa, saldot asiakkaittain (D41) | kuorma |
| **Lämpötilavalvonta** | ⚠️ min/max ja seuranta | — | Kuormatilan lohkot, kylmäkone ja ATP, anturit ja kalibrointi, lukemat ja hälytykset, raportti (D47) | resurssi |
| **Peruutukset** | ⚠️ peruutusmaksu lisänä | — | Peruttu-tila kaikissa ketjuissa ja peruutusmaksu myyntirivinä (D50, A2) | kuorma |
| **Juna** | — | — | Kulkumuoto RAIL, junaterminaalit paikkoina, rautatieoperaattori (Demo Rail), linjat ja vuorot lauttojen rinnalla, kuormatilan junakelpoisuus (D63) | kuorma |
| **HCT ja dolly** | — | — | Dolly kalustona ilman kuormatilaa, kytketään legille; yhdistelmän pituus, kokonaismassa ja sallittu reitti Plan Checkissä (D61) | resurssi |
| **Reititysehdotus** | — | — | Asetustaulukko kohdemaan mukaan (satama, linja, jatko), ehdotus orderin luonnissa (D64) | kuorma |
| **Sisäiset orderit, huolto, pesu, katsastus** | — | — | Order-tyypit (tavara, tyhjä kuormatila, huolto, pesu, katsastus, siirto), sisäinen order ja sisäinen laskutus, pesun laskutus aiheuttajalle (D54) | kuorma |
| **Tullitoimipaikat** | — | — | ✅ paikkoina (`locations`, tyyppi tullitoimipaikka) aukioloaikoineen 2B-1:ssä; tullialueet `customs_areas` (D48) | kuorma |
| **Käyttäjän asetukset** | — | ⚠️ teema selaimessa | Teema ja kieli käyttäjälle (D49), toteutettu | yhteinen |

Jos lista ei ole kattava, puuttuva käsite lisätään tähän ennen vaiheen 2 tietomallia.

---

## 3. Tavoitearkkitehtuuri

```
Frontend (React + TypeScript + Vite)
├── Kuormasuunnittelu   Orderit · Tripsuunnittelu · Tripit · Routing · Asiakkaat · Kulut · Dashboard
├── Liikennesuunnittelu Board · Job Workspace · Fleet Timeline · Route & Risk   ← FleetFlow
├── Hallinta            Kalusto · Kuormatilat · Kuljettajat · Linjat (lautta ja juna) · Hinnoittelu · Asetukset
└── Kuljettaja (FEC)    mobiili, salainen kertakäyttölinkki
API-tyypit generoidaan backendin OpenAPI-kuvauksesta (openapi-typescript)

Backend (FastAPI + Pydantic + SQLAlchemy, moduuleittain)
├── auth          käyttäjät, roolit, palvelinpuolen istunnot
├── orders        orderit ja order-tyypit (D54), order routing, käsittelytapahtumat, ADR-, lämpötila- ja tullitiedot
├── trips         tripit, Nodet ja legit (`leg_trips`, D55), siirtymät, kapasiteetti legin aikavälillä
├── pricing       kulut, jakoperusteet, lisähinnat, asiakashinnasto, kate   ← FP:n moduulit
├── resources     kuljettajat, vetäjät, kuormatilat ja trailer pool, dollyt, pätevyydet, varaukset
├── lines         lautta- ja junaoperaattorit, reitit, vuorot, varaukset, satamakäsittely (D62, D63)
├── planning      jobit, duty-tapahtumat, toteutettavuus, ehdotukset   ← FleetFlow'n ydin
├── documents     Transport Order, CMR, Gateway Instructions, lasku, Credit Note
└── reporting     KPI:t, Power BI -endpointit
Domain-logiikka on puhtaita Python-moduuleja (`backend/domain/`) ilman riippuvuutta
web-kehykseen tai tietokantaan, jotta ne voidaan testata erikseen.

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

Lisäksi yhteiset semanttiset tokenit molempiin teemoihin: tilavärit väriryhminä (D51: Avoin, Suunniteltu, Vahvistettu, Käynnissä, Valmis, Lukittu, Peruttu) ja poikkeamamerkki, kapasiteettipalkit (vihreä / oranssi / punainen), rajoitusten vakavuus (red / orange / yellow) sekä ADR-, GDP- ja thermo-merkit. Näin värikoodaus toimii samoin kummassakin teemassa.

Johdetut tokenit (molemmissa teemoissa): `--text-muted-strong`, `--accent-text`, `--accent-contrast` (teksti aksenttivärin päällä), `--border-strong`, `--surface-hover` ja `--surface-selected`.

Sääntö (WCAG AA, 4.5:1 tekstille): perusarvot `--text-muted` ja `--accent` kelpaavat tekstinä vain pinnoilla, joilla ne läpäisevät AA:n (`--panel-bg`, Control Darkissa myös `--bg-main`). Muilla pinnoilla (esim. `--panel-header`) käytetään johdettuja `--text-muted-strong` ja `--accent-text`. Kontrastitesti valvoo tätä.

Tiiviys pysyy samana molemmissa: business-UI, paljon tietoa yhdellä ruudulla.

### Tietomalli v1 (vaihe 2)

Tila: **Hyväksytty 17.11.2026, täydennetty 18.11.2026 (D62–D69, ylempi paikka)** (Toni, chat; ff-logistiikka tarkistanut). Kokoaa päätökset D13–D69; kysymykset K1–K7 ratkaistu 17.11.2026 (D52–D59), kuormatilarekisteri ja HCT D60–D61. Taulut luodaan Alembic-revisioina taulukoiden järjestyksessä: perusrekisterit → kuorma → keikka (Jobit ennen legejä) → resurssit ja ajoaika → kylmä, tulli ja dokumentit → kulut ja lavasaldot. Viittaus osoittaa aina aiemmin luotuun tauluun. Kentät ovat pääkenttiä; tarkat tyypit, indeksit ja rajoitteet päätetään kunkin revision PR:ssä.

**Yhteiset säännöt kaikille tauluille**
- Raha kokonaislukuina (`*_cents`, `*_e4`, D28). Ajat `timestamptz`; paikallinen aika lasketaan paikan aikavyöhykkeestä.
- Voimassaolot ja päivämäärät `DATE`, molemmat päät mukaan lukien (voimassa koko viimeisen päivän). Voimassaolojaksot omina riveinään (D67).
- **Toteumataulut** (`handling_events`, `customs_events`, `duty_events`, `temperature_readings`, `pallet_ledger`, `costs`): rivit vain lisätään. Jokaisella on `source` (FEC, terminaali, asiakas, manuaali, ajopiirturi, simulaatio) ja `reversal_of_id` korjauksia varten (sääntö 9).
- **Johdettuja tietoja ei tallenneta toiseen kertaan:** tripin alku ja loppu (Nodeista), purkujärjestys (Nodejen järjestyksestä), keikan resurssivaraukset (tripeistä ja Jobeista), lavasaldo (riveistä).
- **Liput ja alirivit täsmäävät:** orderin ADR-, thermo- ja tullattava-lippu vaativat vastaavat rivit (tarkistus).

**Olemassa (vaihe 1 ja 2A):** `users` (rooli, teema, kieli), `sessions`.

#### Perusrekisterit ja asetustaulut

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| customers | nimi, tyyppi (asiakas / oma yritys), Y- tai ALV-tunnus (keksitty), maa, lavanvaihto sovittu (oletus ei, D59) (asiakashinnaston viite lisätään vaiheessa 3) | 2B |
| locations | tyyppi (asiakkaan toimipaikka, terminaali, satama, junaterminaali (D63), varikko, korjaamo, pesu, katsastus, pysäköinti, tankkaus, tullitoimipaikka), ylempi paikka (valinnainen, esim. satama-alueen terminaalit Lehmannkai ja Seelandkai Lübeckissä; lisätty 18.11.2026, Toni), asiakas (pakollinen asiakkaan toimipaikalla), osoite (keksitty katuosoite), postinumero ja kaupunki (D68), maa, koordinaatit, **IANA-aikavyöhyke**, aukioloajat (NULL = ei tarkisteta), ajanvaraus pakollinen, lastauslaituri asiakkaan toimipaikalla (kyllä / ei / tuntematon), suurin sallittu ajoneuvo, sivulastaus mahdollinen; terminaalilla laiturit, kylmätila, lämpötila-alue ja pistokkeiden määrä | D31–D33 |
| customs_areas | maa tai alue, EU:n tullialue, arvonlisäveroalue, yhteinen passitus; voimassaolo (versioitu) | D48 |
| adr_rules | ADR-painos, kuljetuskategorioiden rajat ja kertoimet, yhteenkuormauskiellot lipukkeittain; voimassaolo (versioitu, sisältö tarkistetaan lähteistä luvun 3C mukaan) | D45, D46 |
| pallet_types | lavatyyppi, mitat, LDM | D40, D41 |
| road_restrictions | maa tai reittiosuus, tyyppi (ajokielto, painoraja, yhdistelmän pituus- ja massaraja, HCT-reitti), voimassaolo ja aikaväli | 2B |
| ltl_linehauls | runkolinja terminaalien välillä, lähtöajat, cut-off, toimitusaikalupaus | 3B |
| carriers | kuljetusliike: oma tai alihankkija, maa, Y- tai ALV-tunnus (keksitty), liikennelupa ja vastuuvakuutus voimassaoloineen, arkistointi; **oma liike viittaa oman yrityksen asiakasriviin, ja sen nimi, tunnus ja maa luetaan sieltä** (D73) | 2B, D72, D73 |
| drivers | kuljetusliike, nimi (Demo), kotipaikka, työsuhde (oma / alihankkijan nimetty) | R6, D20 |
| trucks | kuljetusliike, rekisteri (keksitty), tyyppi (vetäjä / kuorma-auto), pituus, vetopöydän etäisyys keulasta, matala vetopöytä, vetolaite (kuorma-auto), omamassa, suurin kokonaismassa ja yhdistelmämassa, akselit, kotipaikka, arkistointi; katsastus jaksoina (D67); kuorma-auton kiinteä kori on `load_units`-taulussa | D39, D55, D60, D61, D72 |
| dollies | kuljetusliike, rekisteri (keksitty), pituus, omamassa, suurin kokonaismassa, akselit, arkistointi; katsastus jaksoina | D61, D72 |
| load_units | **kuormatila**: tyyppi (traileri, kiinteä kori; vaihtokori myöhemmin), kytkentätyyppi (puoliperävaunu, täysperävaunu, keskiakseliperävaunu; D55, D25), mallikoodi (FB, FD, FS, CS, MEGA, COIL; D75), kiinteällä korilla kuorma-auto, haltija ja omistusmuoto (oma, leasing, vuokra, partneri, asiakkaan) sekä vuokrakausi, rekisteri tai tunnus (keksitty), korityyppi, sisä- ja ulkomitat, oviaukko, kingpin-etäisyys, LDM, lavapaikat, massat ja akselit, erityisominaisuudet (XL, kelakouru, TIR-vaijeri, ylhäältä lastaus, perälauta, sivuovet), junakelpoisuus (D63), väliseinä vain FD:llä (paksuus, askel, osastojen vähimmäislavat, takaosaston enimmäisosuus; D76), arkistointi; ATP ja katsastus jaksoina (D67) | D25, D36, D39, D47, D55, D60, D63, D75, D76 |
| reefer_units | **kylmäkone**: kuormatila (yksi kone, keulassa; D76), malli (keksitty), voimanlähde (diesel / sähkö / hybridi); kylmäkonehuolto jaksoina kelpoisuustauluissa | D47, D76 |
| reefer_evaporators | **sisäyksikkö**: kylmäkone ja sen kuormatila, sijainti (keula / perä; FB ja FS 1, FD 2; D76) | D76 |
| compartments | kuormatila (`load_units`), lohkon numero (FB ja FS 1, FD 2; D76), lämpötila-alue, lavapaikat (FD:llä ei kiinteitä), sisäyksikkö (saman kuormatilan, yksi lohko per sisäyksikkö), itsenäisesti säädettävä; väliseinätiedot kuormatilalla (D76) | D47, D76 |
| driver_qualifications, equipment_qualifications | **kuljettajan** pätevyys (ADR ja laajuus, ajokortti C / CE, ammattipätevyys, kuljettajakortti, GDP) ja **kaluston** kelpoisuus (kohde tasan yksi: vetäjä/kuorma-auto, dolly, kuormatila tai kylmäkone; tyypit ATP ja luokka, katsastus, kylmäkonehuolto, perälautatarkastus, GDP-lämpötilakartoitus, ADR-hyväksyntä) omissa tauluissaan (D70); voimassaolo jaksoina, päällekkäiset estetty (D67) | R6, D67, D70 |
| line_operators, line_routes, line_departures | **lautta- ja junaoperaattori** (Demo), reitti suuntineen ja välisatamineen tai -terminaaleineen (kulkumuoto FERRY / RAIL), vuoro: alus (rahti / ro-pax), lähtö, saapuminen, check-in, cut-off, kesto | D23, D27, D62, D63 |
| routing_preferences | kohdemaa (myöhemmin alue), ehdotettu satama tai terminaali, linja, jatko (maantie / juna), prioriteetti | D64 |

#### Kuorma

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| orders | **tyyppi** (tavara, tyhjä kuormatila, huolto, pesu, katsastus, siirto; D54), tilaava asiakas, **lähettäjä ja vastaanottaja**, rahdinmaksaja (asiakas tai oma yritys = sisäinen order), aiheuttanut order (esim. pesu), asiakkaan viite, **kuormatyyppi FTL / PTL / LTL**, tila (Order-ketju + Peruttu), lastaus- ja purkupaikka, **aikatyyppi ja aika erikseen lastaukselle ja purulle** (FIX / Termin / ETA / Sovittava; päivä FIX:lle ja ETA:lle, alku ja loppu Terminille; CHECK-ehdot `domain/time_types.py`:n rakennesääntöjen mukaan, D80), Incoterms, **tavaralaji** (elintarvike, rehu, lääke, kemikaali, yleinen; K4), vaatimukset (perälauta, XL, kelakouru, TIR, ylhäältä lastaus), liput tullattava, ADR, thermo, alkuperäinen Order ID (jaettu order) | D22, D24, D37, D41, D44, D48, D50, D80 |
| order_lines | tavaran kuvaus, kollilaji, merkinnät, lavatyyppi, määrä, mitat, paino, tilavuus, pinottavuus; laskettu LDM ja rahdituspaino | 3B, D40 |
| dangerous_goods | order ja valinnainen order_line, UN-numero, kuljetusnimi, luokka, varoituslipukkeet (pää- ja sivuvaarat), pakkausryhmä, kollien määrä ja pakkauslaji, määrä ja yksikkö, kuljetuskategoria, tunnelikoodi, ympäristölle vaarallinen / merta saastuttava, rajoitettu määrä- ja poikkeusmäärä-liput | D44, D46 |
| temperature_requirements | order, min, max, esijäähdytys vaaditaan, GDP | D44, D47 |

#### Keikka (Node–Leg)

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| jobs | vetäjä tai kuorma-auto (tyhjä sallittu alihankkijan työssä), kuljetusliike, tila (Job-ketju + Peruttu); ei omaa `trip_id`:tä; **kuljettajat aikajaksoina `job_drivers`-taulussa** (kuljettaja tyhjä alihankkijan työssä, D20) | D18, D20, D50, D78 |
| job_drivers | job, kuljettaja, alku ja loppu (vaihto Nodessa), rooli (v1: yksi kerrallaan; kaksimiehitys myöhemmin, D21) | D78 |
| trips | **kuormatila** (`load_units`; tyhjä Luonnos-tilassa ja vetäjän siirtotripillä), tila (Luonnos → … + Peruttu) | D14, D39, D50, D52–D54 |
| nodes | fyysinen pysähdys (ei omaa trippiä; tripin ketju legien kautta, D71), järjestys vetoyksikön ajossa, sijainti, tyyppi, toiminnot (irti / kiinni, vetäjänvaihto, sähköön kytkentä, sinetöinti), live / drop, aikaikkuna, **saapuminen ja lähtö: suunniteltu, ennuste ja toteutunut**, suunniteltu käsittelyaika, ajanvarausnumero | D13, D18, D27 |
| legs | lähtö- ja tulo-Node, job (valinnainen), ajotyyppi (SOLO, EMPTY_TRAILER, LOADED_TRAILER, kuorma-auton kuormattu ajo; tarkistetaan kyydissä olevista ordereista), kulkumuoto (ROAD / FERRY / RAIL; RAIL: D63), tarkoitus (esim. RETURN_TO_BASE), km, ajoaika (FERRY: 0), **reitin maat ja km per maa, tiukin tunnelikategoria**; tripit liitostaulun `leg_trips` kautta (yhdistelmässä sama legi usealla tripillä), dolly (valinnainen), yhdistelmän pituus ja kokonaismassa (johdettu tarkistusta varten) | D13, D17, D39, D55, D61 |
| order_nodes | order, Node, toiminto LOAD / UNLOAD / REMAIN (REMAIN vain ohjetta vaativissa terminaaleissa), järjestys saman Noden sisällä, lastauskohta kuormatilassa, lohko (thermo) | D14, D33, D41 |
| line_bookings | legi (FERRY / RAIL), vuoro, varausnumero, saattaen / saattamaton, tila (varattu → gate-in → laivassa → purettu → vapautettu → noudettu; myöhästynyt, uudelleenvarattu), yksikön pituus, korkeus, paino ja rekisterit, hytti tai makuupaikka (saattaen), cut-off, release, noutotunnus, ilmainen säilytysaika, sähköön kytkentä, DG-ilmoitus lähetetty; maksut `costs`-riveinä | D23, D27, D46 |
| handling_events | order, Node, tyyppi (IOP, LOAD, UNLOAD, IOD, POD, esijäähdytys kuitattu), aika, kollimäärä, lavatyyppi ja vaihdetut / vaihtamatta jääneet lavat, source, reversal_of_id | D16, D41, D47 |
| deviations | order, Node tai trip, tyyppi (vaurio, vajaus, myöhästyminen, CMR-huomautus), kuvaus, syy | 2B |
| seals | kuormatila (`load_units`) ja trip, numero, kiinnitetty Nodessa, tarkistettu Nodessa, ehjä | D48 |

#### Resurssit ja ajoaika

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| duty_events | kuljettaja, job, tyyppi (ajo, muu työ, tauko, lepo, valmius, lauttalepo, matkustus), alku ja loppu, sijainti tai maa, levon paikka (ajoneuvo / majoitus / lautta), source | D23 |
| resource_reservations | vetäjä, kuormatila, dolly tai kuljettaja, aikaväli, syy (huolto, loma, poissaolo); ei keikkavarauksia | — |
| trailer_positions | kuormatila (`load_units`: traileri), sijainti, tila (vapaa, lastattu, tyhjä, merellä, satamassa odottaa vapautusta, huollossa), alku, source; trailer poolin oma toteumahistoria (seisontapäivät ja siirrot myös ilman keikkaa), kirjataan Noden toteumista tai käsin | 2B |

#### Kylmä, tulli ja dokumentit

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| sensors | lohko tai order (asiakkaan oma loggeri), tunniste, kalibrointi ja seuraava kalibrointi | D47 |
| trip_compartment_settings | trip, lohko, asetusarvo, hälytysrajat, mistä Nodesta alkaen | D47 |
| temperature_readings | sensori, aika, lämpötila, source | D47 |
| temperature_alarms | trip, lohko, alku ja loppu, raja, kuittaaja ja syy | D47 |
| customs_declarations, customs_items | menettely, MRN (demo), edellinen asiakirja, tullitoimipaikat, ilmoittaja, vakuus; ilmoitus ↔ order N:M (D58); T1-tavararivit | D48 |
| customs_events | ilmoitus, Node, vaihe (vienti hyväksytty, passitus avattu, saapunut, päätetty, tullattu), aika, source, reversal_of_id | D48 |
| documents | tyyppi (Transport Order, CMR, kotimaan rahtikirja, Gateway Instructions, lastauslista, tulliyhteenveto, lämpötilaraportti), order / trip / job / Node, versio, luotu, lähetetty, sisällön tiiviste, tila | R7, D47, D48 |

#### Kulut, laskutus ja lavasaldot

| Taulu | Pääkentät | Päätökset |
|---|---|---|
| service_codes | palvelukoodi (keksitty), nimi, oletusjakoperuste; taulu luodaan vaiheessa 2 ennen `costs`-taulua, ja Freight Plannerin koodisto ja sen logiikka tuodaan siihen vaiheessa 3 | D19 |
| costs | kulu- tai myyntirivi, palvelukoodi, määrä, yksikkö, yksikköhinta `*_e4`, summa `*_cents`, ALV-koodi, linkki tripiin, orderiin, legiin tai jobiin, kuljetusliike (ostot legeittäin), ostolaskun viite, source, reversal_of_id (myös peruutusmaksu) | D18, D28, A2 |
| cost_allocations | kulu, order, jakoperuste (LDM oletus, myös tripin kiinteät kulut, D57), osuus; jäädytetään laskutuksessa | R2, D15, D19 |
| invoices, invoice_lines | asiakas, numero, päivä, tila; rivi viittaa `costs`-riviin; hyvityslasku viittaa alkuperäiseen laskuun | D16, R3 |
| pallet_ledger | vastapuoli (asiakas, kuljetusliike tai paikka; D59), lavatyyppi, käsittelytapahtuma, lavakuitin numero, muutos (+/−), source, reversal_of_id; saldo lasketaan riveistä | D41 |

Asiakashinnasto, lisähintamoottori ja lauttahinnat (Freight Plannerin `ferry_rates`) siirtyvät Freight Plannerista vaiheessa 3, ja niiden taulut suunnitellaan siellä.

#### Ratkaistut kysymykset (17.11.2026)

K1 → D52 (luonnostrippi) ja D53 (tila Luonnos), K2 → D54, K3 → D55, K4 → D56, K5 → D57, K6 → D58, K7 → D59.

---

## 3B. Kuormatyypit (D37 Hyväksytty; yksityiskohdat Ehdotus)

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

## 3D. Tullauksen lähteet (D48)

Lähteet avattu 16.11.2026 verkkohaulla (hakutulosten otteet, ei koko säädöstekstiä). Ennen vaiheen 5 toteutusta maat, menettelyt ja koodit tarkistetaan Tullin ja EU:n ohjeista, ja ne kirjataan versioituna sääntötaulukkona kuten ADR (D45).

| Asia | Sisältö | Lähde | Tila |
|---|---|---|---|
| Ahvenanmaa | Kuuluu EU:n tullialueeseen, mutta ei arvonlisä- eikä valmisteveroalueeseen. Verorajan ylitys rinnastuu vientiin ja tuontiin | [Verohallinto: Ahvenanmaan veroraja, valmisteverotus](https://vero.fi/syventavat-vero-ohjeet/ohje-hakusivu/48585/ahvenanmaan_veroraja__valmisteverotu/) | Tarkistettu otteesta |
| T1-passitus | Muiden kuin unionitavaroiden siirto EU-maissa tai yhteisen passituksen maiden välillä ilman tullausta | [Tulli: Passitus](https://tulli.fi/en/businesses/transport/transit) | Tarkistettu otteesta |
| Ilmoituslajit | T1 (ei EU-asemaa), T2 (EU-asema), T- (sekalähetys). Lähde on Norjan tulli, koska Norja on yhteisen passituksen maa ja sen ohje oli selkein; tarkistetaan Tullin ohjeesta | [Toll.no: Transit declaration](https://www.toll.no/en/corporate/transport-and-customs-warehouse/transit-declaration) | Tarkistettava Tullilta |
| MRN | Jokainen passitus saa yksilöllisen MRN-tunnuksen. Edellisen asiakirjan koodit Tullin koodilistasta | Toll.no (yllä), [Tulli: Edellisen asiakirjan ilmoittaminen](https://tulli.fi/en/businesses/transport/transit/declaring-the-previous-document) | Tarkistettu otteesta |
| Vakuus | Passituksen aloittajalla on oltava voimassa oleva vakuus tulleille ja veroille | Alan palveluntarjoajan ohje | Tarkistettava Tullilta |
| Maataulukko | EU:n tullialue, yhteisen passituksen maat, veroalueen ulkopuoliset alueet | — | Avoin, kootaan ennen vaihetta 5 |

---

## 4. Optimointi: FleetFlow'n alkuperäinen ydin

Optimointi rakennetaan kolmessa kerroksessa. Jokainen kerros on käyttökelpoinen sellaisenaan:

### Kerros 1: toteutettavuustarkistus (Plan Check)
Puhdas Python-moduuli `backend/domain/feasibility.py`, joka on kattavasti testattu ja deterministinen.
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
- [x] Repo `fleetfreight-tms` luotu
- [x] FleetFlow ja Freight Planner jäädytetty 18.11.2026 (D7): FleetFlow'n PR #6 suljettu
- [ ] README-merkinnät ja linkit FleetFreight TMS:ään: fleetflow-planner PR #15 ja freight-planner PR #38 odottavat yhdistämistä
- [ ] Freight Planner: KONTEKSTI-tiedostoon merkitään, mitä on oikeasti toteutettu (esim. perälaudan flow ja pitkien tavaroiden esto ovat vain dokumentoituja)

### Vaihe 1: runko
- [x] Repo, Docker Compose (PostgreSQL), FastAPI-runko, Vite + React + TypeScript -runko, CI (pytest, Vitest, lint, typecheck)
- [x] Teemat CSS-muuttujina (D9, D10) ja sovelluksen layout (sivupalkki ja välilehdet)
- [x] Autentikointi ja roolit alusta asti
- [x] `CLAUDE.md` + `AGENTS.md` (D5) ja agenttien ohjeet uudelle pinolle
- [x] OpenAPI → TypeScript-tyyppien generointi

### Vaihe 2: tietomalli
Tarkempi suunnitelma, alavaiheet ja valmis-kriteerit: `vaihe-2.md`.
- [x] Teema- ja kielivalinta käyttäjälle tietokantaan (D49), PR #13
- [x] Tietomalli v1 hyväksytty (luku 3), PR #14
- [x] 2B-1 perusrekisterit: asiakkaat, paikat, kuljetusliikkeet, kuljettajat ja pätevyydet demodatoineen, PR #15
- [ ] Alembic-revisiot luvun 3 "Tietomalli v1" mukaisessa järjestyksessä: perusrekisterit, kuorma, keikka, resurssit ja ajoaika, kylmä, tulli ja dokumentit, kulut ja lavasaldot
- [ ] Orderin tullitiedot, tullitapahtumat Nodeissa ja T1-tavararivit (D48)
- [ ] Orderin DG-rivit ja lämpötilavaatimus (D44) sekä kuormatilan lohkot, kylmäkone, ATP ja anturit (D47)
- [ ] Kolmen tilaketjun tilakoneet testeineen, Trip-tila Luonnos ja Peruttu-säännöt mukaan lukien (R3, D50, D53)
- [ ] Tilatokenit väriryhmiksi ja teeman esikatselu niiden mukaan (D51; Luonnos ryhmään Avoin, D53)
- [ ] Demodata: molempien projektien demodata yhdistettynä, "Demo"-säännöt, FleetFlow'n ristiriitainen JOB-001-data korjattuna

### Vaihe 3: siirrettävät moduulit
- [ ] Sellaisenaan: `money.py`, lisähintamoottori (`select_rate`, `compute_amount`, `derive_trade_type`), asiakashinnaston postinumerologiikka, palvelukoodisto. Noin 120 testiä mukana
- [ ] Muokattuina: automaatit (120 → 200, 400-rivit, 800), maarajoitusmoottori (testit ensin), kapasiteetti, validoinnit ja 409-tarkistukset
- [ ] Yksi hintalähde lautoille ja kilometreille (nyt kolme ja kaksi)
- [ ] FEC-odotusaika uudelleen: aikavyöhykkeet oikein, virheet näkyviin, lukitus tarkistetaan, raha `Decimal`

### Vaihe 4: läpimenevä polku (ensimmäinen demottava versio)
- [ ] Order → Trip → Nodet ja legit → Job kuljettajalle → yksinkertainen Plan Check
- [ ] Luonnostrippi: trippi syntyy tilaan Luonnos ensimmäisestä orderista, reitti suoraan Node–Leg-ketjuun, kuormatila valinnainen Luonnoksessa (D52, D53)
- [ ] Order-tyypit orderin luonnissa (tavara, tyhjä kuormatila, huolto, pesu, katsastus, siirto), sisäinen order ja aiheuttanut order (D54)
- [ ] Yhdistelmät: sama legi usealla tripillä (`leg_trips`), Job irtoaa ja liittyy Nodessa (D55); dolly legillä (D61)
- [ ] RAIL-legit junayhteydellä (D63) sekä lautta- ja junavuorojen varaus tripsuunnittelusta demodatan yhteyksillä (D62, D63)
- [ ] Reititysehdotus orderin luonnissa kohdemaan mukaan, liikenteenohjaaja hyväksyy (D64)
- [ ] Näkymät: Orderit, Tripsuunnittelu, Tripit, tripin tietosivu (D42, D43; DG- ja lämpötilavälilehtien sisältö D44, D46 ja D47 mukaan), Routing, Board ja Job Workspace
- [ ] Jokainen näkymä puhelimen ja tabletin leveydellä (D81): puhelimella tripin tiedot, tilat, Plan Check -huomiot, kuittaukset ja hyväksynnät; Board ja Tripsuunnittelu tietokone ja tabletti
- [ ] Navigaatioon tripsuunnittelu, Routing, kuormatilat, kuljettajat ja linjat (lautta ja juna)
- [ ] Orderin ADR-, lämpötila- ja tullivälisivut (passitusilmoitus voi kattaa useita ordereita, D58), tripin ADR-, TULLI- ja thermo-merkit Tripit-listassa ja tripsuunnittelussa, käännösavaimet en ja fi (D34, D44, D48)
- [ ] GDP-koulutuksen oletusvoimassaolo merkitään käyttöliittymässä yrityksen käytännöksi, ei säädökseksi (D69)
- [ ] Skenaario Jyväskylä–Vantaa–Lübeck (D65) toimii demossa alusta loppuun

### Vaihe 5: toteutettavuus (kerros 1)
- [ ] Orderin aikatyyppi Plan Checkiin: Noden suunniteltu saapuminen `time_types.evaluate`-funktiolla, marginaali asetuksena (D80). Lastausaikaa verrataan orderin lastauspaikan Nodeen ja purkuaikaa orderin purkupaikan Nodeen (ei terminaalikäsittelyihin); yhteisessä Nodessa (D71) jokainen order erikseen
- [ ] Paikan aukioloajat ja käsittelyaika erillisinä tarkistuksina aikatyypistä riippumatta; Noden lähtö = myöhäisin (saapuminen, ikkunan alku, aukeaminen) + käsittelyaika
- [ ] `feasibility.py` sääntö kerrallaan: 561/2006 (myös lauttalepo, D23), 2002/15/EY, aikaikkunat, lautat, maarajoitukset, kaluston ja kuljettajan soveltuvuus (ADR, GDP, thermo, pitkät tavarat, perälauta)
- [ ] Tulli- ja verorajan tunnistus reitiltä ja tullivaroitukset (D48)
- [ ] ADR-avustin (D45, D46) ja lämpötilasäännöt (D47) Plan Checkiin
- [ ] ADR + elintarvike legeittäin, kuormatilan ADR-historia ja pesu-Noden ehdotus, kirjattu vuoto estona (D56)
- [ ] HCT- ja dollyyhdistelmän pituus, kokonaismassa ja sallittu reitti (D61; raja-arvot lähteistä ennen toteutusta)
- [ ] Kuormatilan junakelpoisuus RAIL-legillä (D63)
- [ ] Terminaalin kylmätila ja lämpötila-alue thermo-orderille (D66)
- [ ] Kuljettajan pätevyydet ja kaluston kelpoisuudet "voimassa ajopäivänä" jaksoista (D67)
- [ ] Fleet Timeline ja Route & Risk

### Vaihe 6: kaupallinen puoli
- [ ] Hinnoittelumoottori ja kulujen jako (R2; tripin kiinteät kulut LDM:n mukaan, D57), kate orderille ja Tripille
- [ ] Sisäinen laskutus sisäisille ordereille ja kulut kalustolle; pesun laskutusehdotus aiheuttaneelle orderille (D54)
- [ ] Dokumentit: Transport Order, CMR, Gateway Instructions, lasku, Credit Note
- [ ] Tulliyhteenveto ja T1-yhteenveto PDF:nä (D48): oma asettelu, ei virallisen asiakirjan asettelua eikä viivakoodia, "DEMO" näkyvästi jokaisella sivulla
- [ ] Lavanvaihdon kirjaus purussa ja lastauksessa, kun asiakkaalla on lavanvaihto sovittu (D59); lavasaldot kaikille vastapuolille ja vajeiden laskutus (D41, D59)
- [ ] Kuormatilat ja trailer pool -näkymä, linjat (lautta ja juna) ja satamakäsittely, raportit ja Power BI -endpointit

### Vaihe 6B: live-seuranta (D30)
- [ ] Simuloidut sijainnit legeistä ja FEC-kuittauksista, WebSocket, ETA-ennuste ja myöhästymisvaroitus Route & Risk -näkymään
- [ ] Simuloitu lämpötiladata, hälytykset ja Lämpötilavalvonta-näkymä, lämpötilaraportti PDF (D47)

### Vaihe 7: ehdotukset (kerros 2)
- [ ] Jobin sijoitusehdotukset ja hyväksyntä
- [ ] Siirtymäajojen ehdotukset (SOLO / EMPTY_TRAILER)

### Vaihe 8: tuotantovalmius
- [ ] Julkinen live-demo, joka nollautuu yöllä
- [ ] Audit trail, lokitus, virheseuranta
- [ ] Vanhat repot jäädytetään ja jäävät GitHubiin portfolioon (D7), ja niiden README ohjaa uuteen

**Jatkotehtävät (auditoinnista 18.11.2026, tehdään viimeistään tässä vaiheessa):**
- [ ] Plan Checkin tarkistusten pakollisuus pääkäyttäjän asetukseksi (D77; v1:ssä kiinteä)
- [ ] Domain-validointien kutsu API:ssa: aukioloajat, aikavyöhyke, työsuhde ja kuljetusliike, ADR
- [ ] Kuljettajan poiston käyttäytyminen (odottaa Tonin päätöstä)
- [ ] Jaettu pyyntörajoitus (useampi backend-instanssi)
- [ ] Content Security Policy (CSP)
- [ ] CORS-linjaus, jos frontendin ja backendin originit erotetaan
- [ ] argon2-bindings-pinnin poisto, kun 26.x toimii
- [ ] Literal-tyypit OpenAPI-kuvaukseen (teema, kieli, rooli) ja roolin synkronointitesti
- [ ] Demo Terminal Centralin koordinaatit Vantaalle (postinumero 01510)
- [ ] `locations.name`-yksilöllisyys asiakaskohtaiseksi

### Vaihe 9: optimointi (kerros 3)
- [ ] VRPTW-ratkaisija ehdotuksena

**Miksi tässä järjestyksessä:** tietomalli ja autentikointi tehdään ennen ominaisuuksia, koska muuten ne joudutaan kirjoittamaan uudelleen. Vaihe 4 tuottaa mahdollisimman aikaisin demottavan version, jossa koko ketju toimii ohuena. Sen jälkeen jokainen vaihe syventää sitä. Näin projekti ei jää keskeneräiseksi kokoelmaksi irrallisia osia.

---

## 6. Työtapa

- Ensin suunnitelma, sitten Tonin hyväksyntä, sitten koodi
- Oma haara per tehtävä. PR, testit ja katselmointi ennen yhdistämistä
- Claude Code -agentit (ohjeet päivitetään uudelle pinolle vaiheessa 1): logistiikka (logiikka ennen koodia), backend, frontend, reviewer (jokainen PR), security (auth, oikeudet, endpointit) ja auditor (vaiheiden välissä)
- Codexia käytettäessä `AGENTS.md` viittaa samaan `CLAUDE.md`:hen, joten säännöt ovat samat molemmille
- Päätösrekisteri (luku 2) päivitetään aina, kun päätös syntyy tai muuttuu
