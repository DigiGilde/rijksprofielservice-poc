# Rijksprofielservice — Conceptueel Ontwerp

## Context

Rijksambtenaren gebruiken meerdere applicaties (Wies, AMT, ZAD, etc.) die elk profielgegevens nodig hebben. Nu moet een ambtenaar op elke plek apart een profiel bijhouden. De Rijksprofielservice lost dit op door een enkele centrale plek te bieden waar ambtenaren hun profiel beheren, en waar applicaties die gegevens kunnen ophalen — inclusief profielen van collega's.

Inspiratie komt van [MOZA profielservice](https://github.com/MinBZK/moza-profiel-service) (vergelijkbaar project voor burgers/ondernemers) en de ervaring dat Keycloak niet geschikt is voor het ophalen van collega-profielen.

## Kernbeslissingen

| Vraag | Besluit |
|---|---|
| Doelgroep | Alle rijksambtenaren (rijksbreed) |
| Relatie tot MOZA | Los project, MOZA als referentie |
| Databron | Ambtenaren beheren zelf hun profiel |
| Identiteit | Via Rijks-SSO (subject-ID) |
| Relatie Rijks-SSO | Aanvulling — profielservice verrijkt SSO met extra gegevens |
| Afnemer-voorwaarde | Alleen apps die Rijks-SSO gebruiken kunnen aansluiten |
| Auth app → service | OAuth2 (Authorization Code + Client Credentials) via profielservice zelf (django-oauth-toolkit) + SSO subject-ID |
| Toestemmingsmodel | Opt-in, per app toestemming |
| Collega-profielen | Ja, essentieel |
| Avatar/profielfoto | Vanaf het begin meenemen, DPIA direct oppakken |
| Technische stack | Django (Python) |

## Profielgegevens

### Basisgegevens
- Naam (voornaam, achternaam, eventueel weergavenaam)
- E-mailadres
- Telefoonnummer
- Functie/rol
- Organisatie/ministerie

### Visueel
- Profielfoto/avatar (biometrisch gegeven → DPIA vereist)
- Fallback: gegenereerde avatar op basis van initialen

### Voorkeuren (nader te bepalen)
- Mogelijk: taalvoorkeur, notificatie-instellingen, thema

## Toestemmingsmodel

Het toestemmingsmodel is volledig **opt-in**: ambtenaren moeten actief toestemming geven per applicatie.

```
Ambtenaar
  └── Profiel (naam, email, avatar, etc.)
       └── Toestemming per app
            ├── Wies: mag naam + email + avatar zien ✓
            ├── AMT: mag naam + email zien ✓
            └── ZAD: (geen toestemming gegeven)
```

### Hoe werkt het?

- Een ambtenaar geeft per applicatie toestemming
- Als toestemming is gegeven, kan de app het profiel ophalen — ook voor collega's
- Belangrijk: als een ambtenaar toestemming geeft aan app X, kan een collega die app X gebruikt diens profiel zien (dat is het hele punt)
- De granulariteit is per app (niet per veld, in eerste instantie)

### Adoptie-strategie

Omdat opt-in een drempel kan vormen voor adoptie:

- **Eerste gebruik**: bij eerste gebruik van een aangesloten app een duidelijke prompt: "Wil je je profiel delen met [app]?"
- **Bulk-toestemming**: bij aanmaken profiel in een keer voor meerdere apps toestemming geven
- **Waarde tonen**: laten zien wat het oplevert ("je collega's kunnen je foto en naam zien")

## Collega-profielen

Dit is een kernfeature en was het probleem dat Keycloak niet oploste: je kunt je eigen profiel ophalen, maar niet dat van collega's.

De Rijksprofielservice lost dit op:

- Apps vragen het profiel op via het Rijks-SSO subject-ID
- De service checkt of de opvragende app toestemming heeft van die ambtenaar
- Zo ja: gegevens worden teruggegeven
- Zo nee: `null` in de response, de app toont een fallback

### API: individueel en batch

Twee endpoints voor het ophalen van collega-profielen:

```
GET  /api/v1/profiles/{subject-id}      — één profiel
POST /api/v1/profiles/batch             — meerdere profielen in één call
```

Het batch endpoint voorkomt N+1-calls bij bijv. een teamoverzicht (20 profielen in één request in plaats van 20 losse calls).

```json
// Request
POST /api/v1/profiles/batch
Authorization: Bearer <client-credentials-token>

{ "subject_ids": ["abc-123", "def-456", "ghi-789"] }

// Response
{
  "profiles": {
    "abc-123": { "naam": "Jan Jansen", "avatar_url": "https://profiel.rijks.nl/avatars/abc-123", "email": "j.jansen@minbzk.nl" },
    "def-456": { "naam": "Piet Pietersen", "avatar_url": "...", "email": null },
    "ghi-789": null
  }
}
```

Profielen waarvoor geen toestemming is gegeven komen als `null` terug.

### Caching: gelaagd model

De strategie voor performance en versheid is een gelaagd model:

| Laag | Wat | Wanneer |
|---|---|---|
| 1. REST API met batch endpoint | Basis — altijd verse data | Vanaf dag 1 |
| 2. HTTP caching | `Cache-Control: max-age=300` + `ETag` headers op de API; avatar op aparte URL met lange cache (24 uur) | Vanaf dag 1 |
| 3. Webhooks | Push-notificaties bij profielwijzigingen voor apps die real-time updates nodig hebben | Later, alleen als nodig |
| 4. Lokale kopieën | App slaat profieldata op in eigen database | Vermijden — alleen als het echt niet anders kan |

**Waarom dit werkt**: profielen veranderen zelden, dus een cache van 5 minuten is ruim voldoende. De app slaat zelf geen profieldata op (GDPR-voordeel), alles zit in de HTTP-cache van de browser of een tussenliggende proxy.

### Drie authenticatie-flows

| Flow | Grant type | Wie authenticeert | Tokens van | Waarvoor |
|---|---|---|---|---|
| App haalt collega-profielen op | Client-credentials | De app (bijv. Wies) | profielservice | Batch-API `/api/v1/profiles/batch`, `/{subject-id}` |
| App handelt namens ambtenaar | Authorization-code + PKCE | De app + ambtenaar | profielservice | Eigen profiel via `/api/v1/profiles/me` |
| Ambtenaar beheert profiel | Authorization-code (SSO) | De ambtenaar | Keycloak (SSO Rijk) | Eigen profiel bewerken, toestemmingen beheren |

Bij client-credentials authenticatie is er **één token per app**, niet per gebruiker. De toestemming is gekoppeld aan de app: als ambtenaar B toestemming heeft gegeven aan Wies, dan mag *elke gebruiker van Wies* het profiel van B zien — dat is het hele punt van collega-profielen.

Bij de Authorization Code + PKCE flow is het token aan een specifieke ambtenaar gekoppeld. Hier valt **consent = grant** samen: het bestaan van een geldig AccessToken voor (gebruiker, app) is op zichzelf bewijs dat toestemming is verleend.

Zie [Integratie-patronen](integratie-patronen.md) voor concrete voorbeelden van hoe afnemer-apps (zoals Django + HTMX) de profielservice integreren.

## SSO-integratie en authenticatie

### Drie rollen van Rijks-SSO

Rijks-SSO (Keycloak, OIDC/OAuth2) speelt drie rollen:

1. **Authenticatie voor de profielservice** — ambtenaren loggen in via SSO om hun profiel te beheren
2. **Authenticatie voor eind-apps** — ambtenaren loggen in via SSO bij apps zoals Wies
3. **Gemeenschappelijke identifier** — het SSO subject-ID koppelt alles aan elkaar

### Voorwaarde voor afnemers

Alleen apps die Rijks-SSO gebruiken kunnen aansluiten op de profielservice. Dit is een harde eis omdat het SSO subject-ID de gemeenschappelijke identifier is. Van de eerste afnemers (Wies, AMT, ZAD) is dit momenteel een mix — sommige gebruiken al SSO, andere nog niet.

Sommige apps ondersteunen meerdere login-methoden (bijv. AMT ondersteunt ook GitHub-login). Elke ambtenaar *heeft* een Rijks-account en kan via SSO inloggen. Een app die meerdere login-methoden aanbiedt kan bij de eerste SSO-login het subject-ID koppelen aan het app-account, zodat het profiel ook beschikbaar is bij latere logins via andere methoden. Dit is een implementatiekeuze van de afnemer-app.

### Architectuur

Twee verantwoordelijkheden, twee servers:

- **Keycloak (extern, SSO Rijk realm)** — gebruikerslogin voor ambtenaren. Apps en de profielservice consumeren dit via OIDC.
- **Profielservice OAuth-server (django-oauth-toolkit, intern)** — Authorization Server voor app-toegang tot profielgegevens. Geeft zowel Authorization Code (+ PKCE) tokens uit voor user-flows als Client Credentials tokens voor M2M-flows.

```
SSO Rijk (centrale identity provider)
    │
    └── Keycloak (broker, eigen beheer)
            └── SSO Rijk realm → gebruikerslogin voor apps en profielservice

Profielservice (Django + django-oauth-toolkit)
    │
    ├── /o/authorize/   ── Authorization Code + PKCE (consent-scherm)
    ├── /o/token/       ── code/token exchange + client_credentials
    └── /o/revoke_token/
```

### Authenticatie: app → profielservice

**Client-credentials (M2M, batch-API):**
1. App vraagt token aan bij profielservice `/o/token/` (grant_type=client_credentials)
2. App stuurt token + subject-ID naar `/api/v1/profiles/{subject-id}` of `/batch`
3. Profielservice valideert token (DOT), checkt `Consent`, retourneert gefilterde gegevens

**Authorization Code + PKCE (user-bound):**
1. Ambtenaar is ingelogd bij de app via SSO Rijk realm
2. App stuurt user naar `/o/authorize/` met `code_challenge`, redirect_uri, state
3. Profielservice toont consent-scherm; bij grant → redirect met `?code=...`
4. App ruilt code in bij `/o/token/` (met code_verifier en client_secret)
5. App roept `/api/v1/profiles/me` aan met het AccessToken → eigen profiel van de ambtenaar
6. Het AccessToken zelf is bewijs van consent (geen aparte DB-check nodig)

### Aansluiting nieuwe afnemer-apps

Profielservice-admins (beheerd via `STAFF_EMAILS`, zoals bij Wies) beslissen welke apps mogen aansluiten. Een nieuwe app aansluiten vereist:

1. Twee DOT-Applications aanmaken in Django admin: één voor Authorization Code (`<naam>`), één voor Client Credentials (`<naam>-m2m`)
2. Bijbehorende business-`Application` aanmaken en koppelen via `oauth_app`
3. Goedkeuring door een profielservice-admin (`is_approved=true`)

### Waarom geen Keycloak voor app-authenticatie

Een alternatief was Keycloak ook de Authorization Server voor consuming apps laten zijn. Doorslaggevend argument tegen: **consent past niet natuurlijk in Keycloak**. In ons model is consent de autorisatiebeslissing — het AccessToken is daar precies het juiste bewijs van. Bij Keycloak-tokens (~5 min lifetime) zou "consent intrekken werkt direct" een DB-check per request betekenen, wat de winst van stateless tokens neutraliseert. Met django-oauth-toolkit valt consent samen met grant: revoke = AccessToken verwijderen, direct effect.

Zie [Keycloak-integratie](keycloak-integratie.md) voor historische context van de oorspronkelijke architectuur (Keycloak als M2M-broker).

## Eerste afnemers

1. **Wies** — zeker
2. **AMT** — waarschijnlijk
3. **ZAD** — waarschijnlijk

## Open vragen

1. **Wat biedt Rijks-SSO al?** Welke profielgegevens zitten er al in het SSO-token/userinfo endpoint?
2. **DPIA voor avatar** — moet opgestart worden, kost doorlooptijd (afstemming CPO en FG nodig)
3. **CPO/FG betrekken** — juridische betrokkenheid moet geregeld worden voor zowel DPIA als het toestemmingsmodel
4. **Granulariteit toestemming** — is per-app genoeg, of willen we later per-veld?
5. **Wat hebben Wies/AMT/ZAD concreet nodig?** Welke profielvelden gebruiken ze nu?
6. **Beheer en governance** — wie beheert de service? App-aansluiting wordt beheerd door profielservice-admins via `STAFF_EMAILS`. Bredere governance (wie mag admin worden, escalatie) is nog open.
7. **Identificatie** - er wordt nu voorgesteld om het Rijks-SSO subject-ID te gebruiken voor de identificatie, maar het is niet zeker of dit het juiste gegeven is. Zo kan het zijn dat keycloak dit niet goed doorgeeft. Alternatieven: email adres, Rijks identificerend nummer (RIN). Moet worden uitgezocht wat er wordt doorgegeven en wat het meest geschikt is.
8. **Offboarding** - Hoe gaan we om met mensen die uit dienst gaan?
