# Lastaussuunnittelu (2D ja 3D)

Tila: **Ehdotus** (D91, odottaa Tonin päätöstä) · Päivitetty 21.11.2026

Kuorman sijoittelu kuormatilaan: järjestelmä ehdottaa, liikenteenohjaaja muokkaa ja hyväksyy (sääntö 8).
Moduuli on osa FleetFreight TMS:ää eikä erillinen sovellus, koska se käyttää samaa dataa kuin kuljetukset
(orderit, kollit, kuormatilat, tripit ja legit). Ketju: order → trippi → lastaussuunnitelma → CMR.

## 1. Paikka järjestelmässä

- Tripsuunnittelussa kuormatilalla on oma Lastaus-näkymä.
- Suunnitelma tehdään kuormatilalle, ja sen tila näytetään jokaiselle legille, koska PTL- ja LTL-kuorma
  muuttuu purkujen myötä (D37).

## 2. Käyttäjät

| Käyttäjä | Mitä tekee |
|---|---|
| Liikenteenohjaaja | Laatii, muokkaa ja hyväksyy suunnitelman |
| Terminaalin lastaaja | Näkee lastausohjeen puhelimella ja kuittaa kollit lastatuiksi |
| Kuljettaja | Näkee suunnitelman |

Kaikki käyttävät samaa suunnitelmaa omilla oikeuksillaan. Tulostettava lastausohje (PDF): kuormakuva
ylhäältä ja sivulta sekä kollilista lastausjärjestyksessä.

## 3. Tietomalli (taulut vaiheessa 2, jotta myöhempiä migraatioita ei tarvita)

| Taulu | Sisältö |
|---|---|
| `package_types` (kollilajit) | EUR, FIN, puolilava, IBC, häkkilava, rullakko, pitkä tavara, rulla, kela, rumpu ja vapaa mitta. Oletusmitat (muutettavissa order-rivillä), pinottavuus, päälle sallittu paino, pyörällinen (lukittava ja sidottava), saako kääntää, asento (kela makaa, rumpu seisoo) ja tarvitaanko kelakouru |
| `order_lines` (lisäykset) | kollilaji, mittojen ja pinottavuuden ylikirjoitus, "ei saa kääntää" |
| `load_plans` | kuormatila ja trippi, versio, tila (Luonnos / Hyväksytty), laskettu vai käsin muokattu |
| `load_plan_items` | order-rivin kolli, sijainti kolmessa ulottuvuudessa (pituus, leveys, korkeus) ja kierto |
| `load_units` (lisäykset) | akseliston paikka; vetotapin etäisyys ja sisämitat ovat jo taulussa |

Oletusmitat ovat tyyppimittoja, eivät säädösarvoja; ne merkitään kollilajille muutettaviksi.

## 4. Laskenta (`domain/load_plan.py`, puhdas Python)

- Jokaisella kollilla on paikka kolmessa ulottuvuudessa ensimmäisestä versiosta lähtien. 2D- ja 3D-näkymät
  ovat saman suunnitelman eri kuvia.
- Sijoittelu: ensin pinot, sitten rivit ja vierekkäiset kaistat (esimerkiksi pitkä tavara ja EUR-lavat
  rinnakkain samalla matkalla).
- LIFO: ensin purettava sijoitetaan ovien puolelle. Painavat kollit alas ja kuorman painopisteen lähelle.
- Painonjako vetotapille ja perävaunun akselistolle (vaihe 1, ks. luku 7).
- Samasta lähtötiedosta syntyy aina sama tulos, ja jokaiselle tarkistukselle on testit.

## 5. Plan Check

| Tulos | Milloin |
|---|---|
| BLOCKED | lattiapinta, korkeus tai paino ylittyy; vetotapin tai akseliston kuorma ylittää rajan tai vetotapille jää liian vähän painoa |
| RISK | LIFO-järjestys väärin, pinoamissääntöä rikotaan, paino jakautuu epätasaisesti |
| OPEN | kollin mitat puuttuvat, tai kuormatilan akseliston paikka tai rajat puuttuvat (ei arvausta) |

Rajat kirjataan lähteistä kuten maiden painorajat (D89, D90).

## 6. Ehdotus ja muokkaus

- **Ehdotus:** optimointialgoritmi laskee sijoittelun. Algoritmi on deterministinen ja tarkistettava.
- **Tekoäly:** lukee orderin vapaan tekstin kolleiksi ("3 IBC + 4 rullakkoa"), muuttaa vapaat ohjeet
  algoritmin ehdoiksi ("IBC:t eteen, ei mitään rumpujen päälle"), perustelee ehdotuksen ja tarjoaa
  vaihtoehtoja. Tekoäly ei sijoittele kolleja itse.
- **Siirtäminen:**
  - Kollia raahataan, tai puhelimella napautetaan kollia ja sitten kohdetta.
  - Kolli imeytyy lähimpään sopivaan paikkaan (seinään tai viereiseen kolliin), kun sellainen on lähellä.
  - Jos kolli ei mahdu, se palaa alkuperäiselle paikalleen.
  - Pudotus toisen samankokoisen kollin päälle vaihtaa kollien paikat; tarkistus tehdään vasta
    lopputilanteelle, jotta vaihto onnistuu.
  - Kääntö, jos kollilaji sallii.
- **Jatkuva tarkistus:** painonjako ja säännöt päivittyvät jokaisen siirron jälkeen. Siirto, joka tekisi
  kuormasta vaarallisen (BLOCKED), estetään ja kolli palaa paikalleen.
- **Hyväksyntä:** liikenteenohjaaja hyväksyy suunnitelman; hyväksytty suunnitelma ei muutu automaattisesti.

## 7. Painonjako ja akselipainot

1. **Vaihe 1:** yksinkertaistettu painonjako vetotapin ja perävaunun akseliston kesken. Tarvitaan
   kuormatilan vetotapin ja akseliston paikat sekä vetopöydän ja akseliston rajat lähteistä.
2. **Myöhemmin (tärkeä):** täydet akselipainot, joissa mukana vetoauton akselit, tyhjäpainot ja polttoaine.

## 8. Toteutusjärjestys

1. Tietomalli, kollilajit ja demodata (vaihe 2)
2. Laskentamoduuli ja testit
3. Plan Check -säännöt (vaihe 5)
4. 2D-ylä- ja sivunäkymä muokkauksineen (vaiheen 4 jälkeen); muokkaus tabletilla ja tietokoneella,
   katselu ja kuittaus myös puhelimella
5. 3D-näkymä katseluun (three.js)
6. Lastaajan kuittaukset ja PDF-lastausohje
7. Myöhemmin: täydet akselipainot, kahden lohkon FD-kuormatila (D76) ja sivulta lastaus

## 9. Luonnokset

Chatissa 21.11.2026 tehdyt luonnokset: ylänäkymä legivalitsimella ja LIFO-tarkistuksella, sekakuorma
(pitkä tavara pinottuna, EUR-lavat, IBC-kontit ja häkkilavat) ylä-, sivu- ja 3D-näkymänä sekä siirtäminen
imulla, palautuksella ja painonjaon estolla.
