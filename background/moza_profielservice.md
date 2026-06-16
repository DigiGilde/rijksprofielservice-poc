# MOZA profielservice

MOZA profielservice is een vergelijkbaar project wat zich richt op burgers en ondernemers.

> De Profiel Service stelt burgers en ondernemers in staat om op één vertrouwde plek hun contactgegevens en communicatievoorkeuren te beheren, en biedt overheidsinstanties via federatieve koppelingen veilige, actuele en herbruikbare profielinformatie voor persoonlijke en efficiënte dienstverlening.

De code is te vinden: https://github.com/MinBZK/moza-profiel-service

Status: pre-alpha, actieve ontwikkeling. Onderdeel van het bredere MijnOverheid Zakelijk (MOZ) ecosysteem.

## Welke gegevens beheert MOZA?

**Contactgegevens:**
- E-mailadressen (met verificatie-workflow via NotifyNL)
- Telefoonnummers
- Postadressen
- Elk contactgegeven kan gekoppeld worden aan een specifieke afdeling van een dienstverlener

**Voorkeuren:**
- WebsiteTaal (taalvoorkeur)
- MagGebeldWorden (toestemming om gebeld te worden)
- WebsiteThema (bijv. light/dark mode)
- PostcodeInUwBuurt (buurt-gerelateerde voorkeur)
- ActueleOnderwerpVoorkeur (onderwerp-voorkeur)

**Identificatie:**
- BSN (Burgerservicenummer) voor burgers
- KVK (Handelsregister) voor bedrijven
- RSIN voor organisaties

## Hoe krijgen applicaties toegang?

REST API met API-key authenticatie:
- `GET /{identificatieType}/{identificatieNummer}` — volledig profiel ophalen
- CRUD endpoints voor contactgegevens en voorkeuren
- Dienstverleners registreren zichzelf en hun afdelingen

Profieldata wordt teruggegeven als een `PartijResponse` met identificaties, contactgegevens en voorkeuren.

## Consent/toestemming model

- Voorkeuren-gebaseerd: gebruikers beheren zelf welke contactgegevens en voorkeuren er zijn
- Audit trail via Hibernate Envers (alle wijzigingen worden bijgehouden)
- Contactgegevens kunnen geverifieerd worden (met timestamp en referentie-ID)

## Technische stack

- Java 21 + Quarkus 3.32
- PostgreSQL database
- Hibernate met Panache + Envers (audit)
- Jakarta REST met OpenAPI/Swagger documentatie
- ClickHouse voor audit logging
- Docker/Kubernetes deployment
