# Business case

## Waarom dit nodig is

Vanuit het Digi Gilde worden er verschillende webapplicaties ontwikkeld waarin gebruikers (ambtenaren) samenwerken. Voor deze applicaties is het waardevol om profielinformatie van collega's te kunnen zien (naam, e-mail, telefoonnummer, functie, foto). Enerzijds voor de herkenning, anderzijds voor snel contact.

Als gebruiker is het storend om deze informatie herhaardelijk in toe moeten voeren en bij te houden bij wijzigingen. Daarnaast is het voor de ontwikkelaars niet makkelijk om te voldoen aan de privacy regels, wat hen belemmert deze informatie toe te voegen. 

Dit is een mooie kans. Door op een gecontroleerde manier profielinformatie te delen wordt samenwerking bevorderd en kunnnen we effectievere digitale tools realiseren.

## Wat de profielservice doet

Eén plek waar een ambtenaar zijn profiel beheert. Eén API waar elke aangesloten app dat profiel — en dat van collega's — kan ophalen. Met expliciete toestemming per app, per veld.

Voor de ambtenaar: één keer invullen, overal up-to-date. Voor de app-bouwer: geen eigen profielscherm meer onderhouden, en collega-profielen gewoon beschikbaar via een batch-call. Daarnaast is de privacy afhandeling afgedekt.

## Aantoonbare vraag

De volgende apps van het Digi Gilde hebben profijt van een profielservice. Deze applicaties zijn nog niet allemaal in gebruik:

- **Wies**
- **ZAD**
- **AMT**
- **Invulhulpen** (pre-DPIA en IAMA)
- **Bouwmeester**
- **Regelrecht-editor**
- **Grip**
- **Begane Grond**

## Buiten het Digi Gilde

- **PleinBZK** — gebruikt nu al OAuth om een profielfoto uit LinkedIn op te halen. Dezelfde technische koppeling, alleen dan met een bron die wél van het Rijk is.

## Verdere mogelijke uitbreidingen (verkenning)

- **Mijn Bureau — chat**
- **Mijn Bureau — docs**
- **Mattermost**

## Alternatieven onderzocht

- **Rijksadresgids** — onderzocht als bestaande bron, maar valt af. Het team achter de Rijksadresgids gaf desgevraagd aan geen gegevens te mogen verstrekken: zij zijn niet de eigenaar van de data. De foto in de Rijksadresgids is bijvoorbeeld alleen bedoeld voor de Rijksadresgids zelf, niet om naar andere systemen te synchroniseren. Voor hergebruik moet je bij de medewerker zelf zijn — precies wat de profielservice mogelijk maakt.
- **Gravatar** - Dit is een publieke online dienst waar je een profiel kan aanmaken die wordt gematcht op basis van je mailadres. Deze informatie is voor iedereen inzichtelijk en daardoor niet geschikt voor gevoeligere informatie zoals bijvoorbeeld een telefoonnummer
- **Keycloak** - Hier kunnen gebruikersprofielen worden aangemaakt, maar is niet geschikt om collega's in op te vragen.
