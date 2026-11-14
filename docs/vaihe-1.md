# Vaihe 1: runko

Tila: **suunnitelma, odottaa Tonin hyväksyntää** · Päivitetty 14.11.2026

Tavoite: toimiva, testattu ja suojattu tyhjä sovellus, jonka päälle vaiheen 2 tietomalli rakennetaan.
Vaiheessa ei vielä tehdä toimialuelogiikkaa.

## Tekniset oletukset

| Asia | Valinta |
|---|---|
| Python | 3.15, riippuvuudet `uv`. Jos jokin riippuvuus ei vielä tue 3.15:tä, siitä kerrotaan PR:ssä eikä versiota lasketa hiljaa |
| Node | 22 LTS |
| Tietokanta | PostgreSQL 17 (Docker Compose) |
| Backendin laatu | ruff (lint ja muotoilu), mypy (tyypit), pytest |
| Frontendin laatu | TypeScript strict, ESLint, Vitest |
| Käännökset | kevyt i18n-kirjasto, `en` ja `fi` (D34) |

## Kansiorakenne

```
fleetfreight-tms/
├── backend/
│   ├── app/            FastAPI-sovellus, reitit, riippuvuudet
│   ├── domain/         puhtaat Python-moduulit (ei FastAPI- eikä tietokantariippuvuutta)
│   ├── db/             SQLAlchemy-mallit ja istunto
│   ├── migrations/     Alembic
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/        generoidut tyypit ja API-asiakas
│       ├── i18n/       en.json, fi.json
│       ├── theme/      tokenit, Business Light, Control Dark
│       ├── layout/     sivupalkki, välilehdet, yläpalkki
│       └── features/
├── docs/
└── docker-compose.yml
```

## Pull requestit

Jokainen on oma haaransa ja PR:nsä. ff-reviewer katselmoi jokaisen, eikä mitään yhdistetä automaattisesti.

### 1A Backend-runko
- FastAPI-sovellus ja `/health`-endpoint, joka tarkistaa myös tietokantayhteyden
- Asetukset ympäristömuuttujista (`pydantic-settings`) ja `.env.example`
- SQLAlchemy, Alembic ilman tauluja ja testikanta, joka ei koske kehityskantaan
- Docker Compose: PostgreSQL ja backend
- **Valmis kun:** `docker compose up` käynnistää backendin, `/health` palauttaa ok, pytest, ruff ja mypy menevät läpi

### 1B Frontend-runko
- Vite + React + TypeScript strict, ESLint, Vitest
- `npm run gen:api` generoi tyypit backendin OpenAPI-kuvauksesta
- i18n-pohja: `en.json` ja `fi.json`, sekä testi, joka varmistaa että kummassakin on samat avaimet
- **Valmis kun:** typecheck, lint, test ja build menevät läpi, ja etusivu näyttää backendin terveystilan

### 1C Teemat ja layout
- Design tokenit CSS-muuttujina: Business Light ja Control Dark (värit: `suunnitelma.md` luku 3), sekä semanttiset tokenit (tilat, kapasiteetti, rajoitusten vakavuus, ADR, GDP, thermo)
- Layout: yläpalkki, sivupalkki (Kuormasuunnittelu, Liikennesuunnittelu, Hallinta) ja välilehdet
- Teema- ja kielivalitsin, valinta muistetaan selaimessa
- **Valmis kun:** molemmat teemat ja kielet vaihtuvat lennossa, eikä komponenteissa ole kovakoodattuja värejä tai tekstejä

### 1D Kirjautuminen ja roolit
- Ensimmäinen Alembic-revisio: `users` (sähköposti, salasanatiiviste, rooli, aktiivinen)
- Salasanat argon2:lla, istunto httpOnly-evästeessä, istunnon vanheneminen
- Roolit: `admin`, `planner` (suunnittelija), `viewer` (katselija). Kuljettajan FEC-linkki tehdään myöhemmin omalla tokenillaan
- Kaikki endpointit suojattu oletuksena, ja poikkeukset (esim. `/health`, kirjautuminen) on merkitty erikseen
- Kirjautumissivu ja uloskirjautuminen. Demokäyttäjät luodaan demodatan siemennyksessä, ei migraatiossa
- ff-security tarkistaa ennen yhdistämistä
- **Valmis kun:** kirjautumaton käyttäjä ei pääse mihinkään muualle kuin kirjautumissivulle, ja roolitarkistus on testattu

### 1E CI
- GitHub Actions, backend: ruff, mypy ja pytest oikeaa PostgreSQL:ää vasten Python 3.15:llä
- GitHub Actions, frontend: typecheck, lint, test ja build
- Tarkistus, että generoidut API-tyypit vastaavat backendin nykyistä OpenAPI-kuvausta
- **Valmis kun:** jokainen PR ajaa tarkistukset automaattisesti

## Järjestys

1A → 1B → 1C, ja 1D vasta kun 1A ja 1B ovat valmiit. 1E voidaan tehdä 1A:n jälkeen milloin tahansa.

## Vaiheen 1 lopuksi
- ff-auditor tarkistaa koko rungon
- `CLAUDE.md`:hen lisätään käynnistys- ja testikomennot
