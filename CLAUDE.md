# FleetFreight TMS — CLAUDE.md

Tämä tiedosto on projektin **ainoa sääntölähde** kaikille AI-työkaluille (Claude Code, Codex ym.).
`AGENTS.md` viittaa tähän. Jos sääntö muuttuu, se muutetaan vain tänne.

Kuljetustenhallintajärjestelmä (TMS), jossa yhdistyvät kuormasuunnittelu ja kuljettajan
päivätason resurssisuunnittelu ajo-, työ- ja lepoaikoineen. Portfolioprojekti, jossa on vain fiktiivistä demodataa.
Yhdistää aiemmat prototyypit Freight Planner ja FleetFlow Planner.

**Päätökset:** `docs/suunnitelma.md`, luku 2 (päätösrekisteri D1–D95).
Lue päätösrekisteri ennen tietomalliin, logiikkaan tai arkkitehtuuriin koskevaa työtä. Jos pyyntö on
ristiriidassa hyväksytyn päätöksen kanssa, sano se ääneen äläkä ohita päätöstä hiljaa.

---

## Pino (D11, D12)

- **Frontend:** React + TypeScript + Vite, Vitest, ESLint
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest
- **Tietokanta:** PostgreSQL (Docker Compose)
- **Mobiili (D81):** responsiivinen web ja PWA; taitekohdat tabletti ≤ 1024 px ja puhelin ≤ 640 px (`layout/useMediaQuery.ts` ja `layout.css`). Jokainen näkymä toimii ja testataan myös puhelimen ja tabletin leveydellä.
- **Tyypit:** frontendin API-tyypit generoidaan backendin OpenAPI-kuvauksesta (`openapi-typescript`). Älä kirjoita API-tyyppejä käsin.

### Käynnistys (kehitys)

```bash
cp .env.example .env                 # vain kehitysarvot, ei salasanoja repoon
docker compose up --build            # override-tiedosto tuo kehitysasetukset automaattisesti
curl http://localhost:8000/health    # {"status":"ok","database":"ok"}
docker compose exec backend python -m scripts.seed_demo_users   # demokäyttäjät; vain kehityskäynnistyksellä (override), DEMO_PASSWORD .env:stä
docker compose exec backend python -m scripts.seed_demo_data    # demodata (yritys, terminaalit, satamat, junaterminaalit, tullitoimipaikat, turvaparkit, rajanylitykset, satamien ja junaterminaalien säilytysehdot, pesupaikat, lautta- ja junalinjat aluksineen, aikatauluineen ja lähtöineen, rahtirikosraportit, riskialueet ja demojonohavainnot, asiakkaat, kuljetusliikkeet, kuljettajat, pätevyydet, kalusto); vain kehityskäynnistyksellä, idempotentti
docker compose exec backend python -m scripts.seed_reference_data  # viitedata (maat, pyhät, ajokiellot; D84); myös tuotannossa, idempotentti
cd frontend && npm ci && npm run dev
```

Tuotanto ilman override-tiedostoa: `docker compose -f docker-compose.yml up -d`.
Tarkemmat ohjeet: `backend/README.md`.

### Tarkistukset ennen PR:ää (CI ajaa samat)

```bash
# backend/
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                        # TEST_DATABASE_URL, nimen loppu _test

# frontend/
npm run typecheck && npm run lint && npm test && npm run build

# API-tyypit backendin muutosten jälkeen
cd backend && uv run python -m scripts.export_openapi /tmp/openapi.json
cd ../frontend && OPENAPI_URL=/tmp/openapi.json npm run gen:api
git diff --exit-code src/api/schema.ts   # CI kaatuu, jos tyypit ovat vanhentuneet
```

CI ajaa lisäksi `uv run alembic upgrade head` tyhjää kantaa vasten.

Uusi migraatio: `cd backend && uv run alembic revision -m "describe the change"` (sääntö 2).

---

## Ehdottomat säännöt

1. **Työtapa:** ensin suunnitelma, sitten Tonin hyväksyntä, vasta sitten koodi. Oma haara per tehtävä,
   PR, testit ja katselmointi. **Ei automaattista yhdistämistä mainiin.**
2. **Skeemamuutos = uusi Alembic-revisio.** Valmiita revisioita ei muokata. Demodata ei kuulu migraatioihin.
3. **Raha (D28):** kannassa INTEGER (`*_cents` ×100 summille, `*_e4` ×10 000 yksikköhinnoille ja prosenteille),
   laskenta `Decimal` ROUND_HALF_UP, API euroina. Muunnokset vain `money`-moduulissa.
   Ei `float`ia eikä `round()`:ia rahassa, ei backendissä eikä frontendissä.
4. **Ei työnantajan tietoja, ehdoton sääntö:** repossa ei saa näkyä mitään Tonin nykyisestä tai aiemmista
   työnantajista. Ei nimiä, logoja, järjestelmien nimiä, sisäisiä lyhenteitä tai koodeja, asiakkaita, reittejä,
   hintoja, prosessikuvauksia, kuvakaappauksia eikä dataa. Tämä koskee koodia, demodataa, dokumentaatiota,
   commit-viestejä, PR:iä ja issueita. Toimialan käytäntöjä kuvataan yleisinä alan käytäntöinä.
   Jos et ole varma, onko termi yleinen alan termi vai yrityksen sisäinen, kysy ennen käyttöä.
5. **Demodata:** kaikki yritys- ja henkilönimet ovat keksittyjä ja sisältävät sanan "Demo", sähköpostit `*.example.com`.
   Ei oikeita yrityksiä, rekisterinumeroita, osoitteita eikä yhteystietoja (postinumero ja kaupunki saavat olla oikeita
   ja katuosoite keksitty, D68; julkiset paikannimet kuten satamien ja rajanylitysten nimet sallittu).
6. **Domain-logiikka on puhtaita Python-moduuleja** ilman riippuvuutta FastAPI:hin tai tietokantaan, jotta ne voidaan testata erikseen.
7. **Tyylit CSS-muuttujina (D9, D10).** Kaksi teemaa: *Business Light* ja *Control Dark*. Komponenteissa ei kovakoodattuja värejä.
8. **Järjestelmä laskee, tarkistaa ja ehdottaa; liikenteenohjaaja päättää.** Mikään automaatti ei muuta hyväksyttyä suunnitelmaa itse.
9. **Toteutuneita tapahtumia ei poisteta** uudelleensuunnittelussa. Korjaukset vastakirjauksina.
10. Älä merkitse ehdotusta hyväksytyksi. Päätösrekisterin tilat: Hyväksytty / Ehdotus / Oletus / Avoin / Korvattu ("Korvattu → Dxx").

---

## Tietomallin ydin (yksityiskohdat: `docs/suunnitelma.md` luku 3)

- **Node–Leg (D13):** keikka on Node-ketju, ja legi on aina kahden peräkkäisen Noden välissä. Node voi olla esimerkiksi
  vetäjän lähtö, trailerin nouto, terminaali, lastaus, purku, satama lähtö tai saapuminen, korjaamo, katsastus tai pesu.
  Kilometrit ja ajoaika lasketaan vain legeistä.
- **Trip seuraa kuormatilaa (D14, D55, D60):** kuormatila (`load_units`) on traileri tai kuorma-auton kiinteä kori.
  Trip on kuormatilan kuormattu kierros, johon kuuluvat myös alun siirtymät (D17).
- **Kaikki ajot muodostavat tripin (D54):** jokainen trippi koostuu orderista, Nodeista ja legeistä. Order-tyypit: tavara,
  tyhjä kuormatila, huolto, pesu, katsastus, siirto. Maksaja asiakas tai oma yritys (sisäinen order).
- **Yhdistelmät (D55, D61):** legi on vetoyksikön fyysinen siirtymä, ja sama legi voi kuulua usealle tripille (`leg_trips`),
  joten km ja ajoaika lasketaan kerran. Node on fyysinen pysähdys, jonka tripit voivat jakaa (D71). Dolly kytketään legille; HCT-yhdistelmän pituus ja massa tarkistetaan.
- **Vetäjänvaihto Nodessa (D18):** vetäjän 1 Job päättyy ja vetäjän 2 Job alkaa, Trip jatkuu.
- **Job** = vetoauto (D78): vetoauton vaihto muodostaa uuden Jobin, kuljettajan vaihto ei; kuljettajat Jobin sisällä aikajaksoina. Job ja Trip ovat N:M legien kautta. Kuljettaja voi olla tyhjä alihankkijan työssä (D20).
- **Kuormatyypit (D37):** FTL, PTL ja LTL, joilla on omat reititys-, kapasiteetti-, hinnoittelu- ja Plan Check -säännöt (`docs/suunnitelma.md` luku 3B).
- **Ajotyypit:** SOLO, EMPTY_TRAILER, LOADED_TRAILER ja kuorma-auton kuormattu ajo (D17, D39), omilla hinnoillaan.
  Kulkumuoto ROAD, FERRY tai RAIL (D63; juna kuten saattamaton lautta, ilman Jobia).
- **Kolme tilaketjua (R3, D50, D53):** Order, Trip (Luonnos → Suunniteltu → …) ja Job, kaikissa päätetila Peruttu.
  Laskutus kohdistuu orderiin toimituksen (IOD) jälkeen (D16).
- **Voimassaolot jaksoina (D67):** jokaisesta voimassaolojaksosta oma rivi; uusiminen luo uuden rivin, historia säilyy. Kuljettajien pätevyydet ja kaluston kelpoisuudet ovat omissa tauluissaan (D70).
- **Rekisteririvit arkistoidaan, ei poisteta (D72):** `archived_at`; poisto estetään (RESTRICT), jos riviin viitataan. Oma kuljetusliike viittaa oman yrityksen asiakasriviin (D73).
- **Reititysehdotus (D64):** asetustaulukko kohdemaan mukaan; järjestelmä ehdottaa, liikenteenohjaaja päättää.
- **Ajo- ja työaika lasketaan kuljettajalle** yli Jobien ja päivien: EU 561/2006 (myös lauttalepo, D23) ja 2002/15/EY.
  Säädösten raja-arvot tarkistetaan säädöstekstistä ennen toteutusta, eikä niitä kirjoiteta muistista.

---

## Kieli

- Koodi, nimet, kommentit ja commit-viestit englanniksi
- UI-termistö on alan arkikieltä ja sama kuin dokumentaatiossa (D74), esim. Tripit, Orderit, Tripsuunnittelu, Board
- Dokumentaatio (`docs/`) suomeksi, README englanniksi
- **Käyttöliittymä on kaksikielinen, englanti ja suomi (D34).** Kaikki käyttäjälle näkyvät tekstit käännösavaimina
  käännöstiedostoissa (`en` ja `fi`), ei kovakoodattuja tekstejä komponenteissa. Uusi teksti lisätään aina molemmille kielille.
  Oletuskieli englanti.

---

## Agentit (`.claude/agents/`)

| Agentti | Milloin |
|---|---|
| `ff-logistiikka` | Ennen uutta toimialuelogiikkaa ja sen jälkeen: vastaako malli oikeaa kuljetustyötä |
| `ff-backend` | FastAPI, SQLAlchemy, Alembic, domain-moduulit |
| `ff-frontend` | React, TypeScript, näkymät, teemat |
| `ff-reviewer` | Jokainen PR ennen yhdistämistä |
| `ff-security` | Autentikointi, oikeudet, syötteet ja jokainen uusi endpoint |
| `ff-auditor` | Vaiheiden välissä: koko koodikannan ristiriidat ja päällekkäisyydet |
