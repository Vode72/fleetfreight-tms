---
description: Vie valmiin haaran PR:ksi asti — tarkistukset, katselmointiagentit, korjaukset (max 2 kierrosta), PR ja CI-korjaukset. Ei yhdistä mainiin.
argument-hint: "[lisäohje, esim. 'ilman logistiikkatarkistusta']"
---

Vie nykyisen haaran muutos valmiiksi PR:ksi FleetFreight TMS:ssä. Lisäohje: $ARGUMENTS

Noudata `CLAUDE.md`:tä. **Älä koskaan yhdistä mainiin äläkä hyväksy PR:ää** (sääntö 1) — merge-päätös on Tonin.

## 1. Lähtötilanne
- Jos haara on `main`, pysähdy ja kysy haaran nimi.
- `git status`, `git fetch origin main`, `git diff origin/main...HEAD --stat` ja `git log origin/main..HEAD --oneline`. Commitoimattomat muutokset: kysy ennen commitointia.
- Jos muutos on ristiriidassa päätösrekisterin (`docs/suunnitelma.md`) kanssa, pysähdy ja kerro.

## 2. Omat tarkistukset (CLAUDE.md "Tarkistukset ennen PR:ää")
- Aja vain osat, joita muutos koskee (backend/, frontend/, API-tyypit).
- **pytest ajetaan vain tässä, yhden kerran** — jaettu testikanta, rinnakkaisajo aiheuttaa deadlockeja.
- Korjaa kaatuneet tarkistukset ennen agentteja.

## 3. Tarkistusagentit rinnakkain taustalle
Kerro jokaiselle haara, muutoksen tarkoitus, D-numerot ja omien tarkistusten tulos.
Kiellä jokaiselta pytestin ajo ja tiedostojen muokkaus. Vastaus suomeksi, vakavuusjärjestyksessä, tiedosto:rivi.

| Agentti | Milloin |
|---|---|
| `ff-reviewer` | aina |
| `ff-security` | endpointit, autentikointi, oikeudet, syötteet, tiedostot, riippuvuudet, julkaistava sisältö |
| `ff-logistiikka` | toimialuelogiikka tai demodata |

## 4. Korjaukset — enintään 2 kierrosta
- Korjaa Kriittiset ja Tärkeät. Isot backend-muutokset `ff-backend`ille, frontend `ff-frontend`ille.
- Pienistä löydöksistä päätä itse; jätetyt ja perustelut PR-kuvaukseen.
- Jos agentti on mielestäsi väärässä, älä korjaa — kirjaa perustelu.
- Korjausten jälkeen aja kohdan 2 tarkistukset uudelleen; agentit uudelleen vain jos korjaus oli iso.
- Jos Kriittinen jää auki 2 kierroksen jälkeen: pysähdy, älä avaa PR:ää, raportoi.

## 5. PR
- Push ja `gh pr create` (base `main`). Pilvi-istunnossa GraphQL on estetty: käytä
  `gh api repos/{owner}/{repo}/pulls -f title=... -f head=<haara> -f base=main -f body=...`. Kuvaus suomeksi: mitä ja miksi, D-numerot, tarkistusten tulokset,
  agenttien löydökset ja mitä niille tehtiin, jätetyt pienet huomiot.
- Ei työnantajatietoja missään (sääntö 4) — tarkista myös commit-viestit ja PR-kuvaus.

## 6. CI ja konfliktit — enintään 2 korjauskierrosta
- Seuraa: `gh pr checks --watch` (pilvessä `gh run list --branch <haara>` ja `gh run watch <id>`).
- Kaatunut ajo: `gh run view --log-failed`, korjaa syy (ei oireita, ei testien ohittamista), push.
- Konflikti mainin kanssa: `git fetch origin main && git rebase origin/main` — vain omassa tehtävähaarassa; migraatiokonfliktissa korjaa Alembicin
  `down_revision`-ketju, ei vanhoja revisioita. Selvä konflikti: ratkaise ja `git push --force-with-lease origin <haara>`.
  **Force push vain omaan tehtävähaaraan, ei koskaan mainiin.** Jos haaraan on pushannut joku muu, käytä `git merge origin/main`.
  Epäselvä (molemmat muuttaneet samaa logiikkaa): pysähdy ja kysy.
- Epävakaa testi (menee läpi uudelleenajossa): älä ohita — raportoi.

## 7. Raportti Tonille
Lyhyesti: PR-linkki, CI-tila, korjatut löydökset, jätetyt huomiot ja mahdolliset avoimet kysymykset.
Viimeinen rivi on suositus, ei hyväksyntä (sääntö 8): **"Suositus: yhdistettävissä"** tai **"Suositus: ei yhdistettävissä: <syy>"**. Merge-päätös on Tonin.
