# Rijksprofielservice Demo

Interactieve proof-of-concept om het idee achter de Rijksprofielservice te demonstreren. Drie nep-applicaties draaien lokaal en delen profieldata via `localStorage`.

## Starten

```bash
cd demo
python3 -m http.server 8000
```

Open `http://localhost:8000/index.html` in je browser.

## Demo-verhaal

### 1. Profiel aanmaken in Rijksprofielservice

- Open **Rijksprofielservice** (`index.html`)
- Klik op **Inloggen met Rijks-SSO** en kies één van de drie nep-accounts
- Bovenaan zie je je SSO-gegevens (voornaam, achternaam, e-mail) — die worden centraal door de SSO beheerd en zijn hier niet aanpasbaar
- Vul je profielgegevens in: profielfoto, telefoonnummer en functie
- Klik op **Opslaan**

*Punt: naam en e-mail komen uit de SSO. De Rijksprofielservice voegt daar extra profielgegevens aan toe die de ambtenaar zelf beheert.*

### 2. Wies koppelen

- Open **Wies** (`wies.html`) in dezelfde browser
- Klik op **Inloggen met Rijks-SSO** (al ingelogd? dan kun je meteen door)
- De onboarding-modal verschijnt: Wies wil aanvullende gegevens uit de Rijksprofielservice gebruiken
- Klik op **Profiel koppelen** — je wordt doorgestuurd naar Rijksprofielservice
- De consent-popup toont welke gegevens Wies uit de profielservice opvraagt: profielfoto, telefoonnummer, functie. (Naam en e-mail krijgt Wies al via de SSO.)
- Klik op **Toestaan** — je wordt teruggestuurd naar Wies
- Wies toont nu je naam (uit SSO) met functie eronder, en klikken op je banner of een collega toont een modal met telefoon + e-mail

*Punt: de gebruiker bepaalt zelf welke aanvullende gegevens een app uit de profielservice mag halen.*

### 3. AMT koppelen

- Open **AMT** (`amt.html`)
- Doorloop dezelfde flow als bij Wies
- Let op: AMT vraagt alleen je profielfoto uit de profielservice op — naam komt al via de SSO, contactgegevens vraagt AMT niet
- Na toestemming toont AMT je foto met je naam ernaast

*Punt: verschillende apps krijgen verschillende aanvullingen — granulaire consent op profielniveau.*

### 4. Instellingen bekijken en toegang intrekken

- Ga terug naar **Rijksprofielservice** (`index.html?tab=settings`)
- Onder **Instellingen** zie je Wies en AMT met hun respectieve rechten
- Klik op **Toegang intrekken** bij een app
- Ga terug naar die app — het profiel is verdwenen

*Punt: de ambtenaar heeft volledige controle en kan altijd toegang intrekken.*

## Technische details

- Geen backend — alles draait client-side met `localStorage`
- Het actieve "SSO-account" zit in `localStorage` onder `sso_identity` (gedeeld tussen alle apps op dezelfde origin) en simuleert de Rijks-SSO
- Profielgegevens en consent-status zijn per SSO-account opgeslagen (`rps_profile_<id>` en `rps_consents_<id>`)
- App-sessies (Wies/AMT ingelogd ja/nee) zitten in `sessionStorage`
- Redirects tussen apps gebruiken URL-parameters (`?from=wies&callback=wies.html`)
