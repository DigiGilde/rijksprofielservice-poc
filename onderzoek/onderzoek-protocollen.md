# Onderzoek: AT Protocol en Solid Protocol voor de Rijksprofielservice

*Onderzoek uitgevoerd: april 2026*

## Context

De Rijksprofielservice wil een centrale plek bieden waar rijksambtenaren hun profiel beheren, en waar applicaties (Wies, AMT, ZAD, etc.) die gegevens kunnen ophalen. Het huidige concept-ontwerp beschrijft een Django-app met een PostgreSQL database, OAuth2 via Keycloak, en een opt-in toestemmingsmodel per app.

De vraag is: kunnen gedecentraliseerde protocollen zoals het AT Protocol (Bluesky) of Solid (Tim Berners-Lee) dezelfde doelen bereiken op een manier waarbij de ambtenaar echt eigenaar is van de data?

---

## AT Protocol

### Wat is het?

Het AT Protocol is een gedecentraliseerd protocol waarbij gebruikersdata wordt opgeslagen in een **Personal Data Server (PDS)** — te vergelijken met een persoonlijke Git-repo voor gestructureerde data. Kernconcepten:

- **PDS**: host je data, beheert je identiteit, distribueert updates. Kan 1 tot honderdduizenden accounts hosten.
- **Data repos**: gesigneerde datarepositories (Merkle Search Tree), cryptografisch verifieerbaar. Elke record heeft een schema (Lexicon).
- **DIDs**: Decentralized Identifiers — permanente, cryptografische identiteit losgekoppeld van je server.
- **Handles**: menselijk leesbare namen (domeinnamen) die naar een DID verwijzen.
- **OAuth**: apps vragen toegang tot je PDS via OAuth 2.0 met extra beveiliging (DPoP, PAR). Gebruiker geeft toestemming.
- **Lexicon**: schema-systeem waarmee je custom record types kunt definiëren — niet beperkt tot social media.

### Analyse voor de Rijksprofielservice

**Wat past:**
- Data-eigenaarschap door de gebruiker — AT Protocol is hier letterlijk voor ontworpen
- Apps vragen toestemming via OAuth — vergelijkbaar met het huidige concept
- Custom schemas (Lexicons) — je kunt profieldata-schemas definiëren
- Gebruiksvriendelijkheid is oplosbaar — een managed PDS kan duizenden accounts hosten

**Wat niet past:**
- **Alle repo-data is publiek** — dit is een showstopper. Profielgegevens van ambtenaren mogen niet publiek toegankelijk zijn. Er is een [Private Data Working Group](https://atproto.wiki/en/working-groups/private-data) bezig, maar zonder concrete timeline of specificatie.
- **Collega-profielen ophalen** vereist een directory/discovery service (AT Protocol lost dit op via publieke Relays die alles crawlen — niet bruikbaar voor private data)
- **Integratie met Rijks-SSO (Keycloak)** is niet triviaal — AT Protocol heeft een eigen identiteitssysteem (DIDs) en eigen OAuth

### Conclusie AT Protocol

**Niet geschikt** — alle data publiek, geen privacy-mechanisme, en het protocol is ontworpen voor social media/publieke data.

---

## Solid Protocol

### Wat is het?

Solid (Social Linked Data) is een gedecentraliseerd webproject geleid door Tim Berners-Lee. Het kernconcept: gebruikers slaan hun data op in **Pods** (Personal Online Data Stores) en bepalen zelf welke apps toegang krijgen tot welke data.

### Architectuur

```
Gebruiker
  └── Pod (data store, te vergelijken met persoonlijke Dropbox met access control)
       ├── /profiel/naam.ttl
       ├── /profiel/contact.ttl
       ├── /voorkeuren/...
       └── .acl bestanden (access control per resource)

App (bijv. Wies)
  └── Vraagt toegang via Solid-OIDC
       └── Pod checkt ACL: heeft deze app toegang tot deze resource?
```

- **Pods** zijn webservers die data hosten als linked data (RDF/Turtle) en gewone bestanden
- Data is georganiseerd in **containers** (mappen) met elk hun eigen access control
- Elke resource heeft een URI en is via standaard HTTP benaderbaar
- Pods kunnen door een **provider** gehost worden (vergelijkbaar met email: je hebt een provider maar het protocol is open)

### Access control — kernfeature

Solid heeft **twee access control systemen**:

1. **WAC (Web Access Control)**: ACL-gebaseerd, per resource/container definieer je wie (welke WebID/app) welke rechten heeft (Read, Write, Append, Control)
2. **ACP (Access Control Policy)**: nieuwer, flexibeler beleidssysteem

Dit is precies wat de Rijksprofielservice nodig heeft: ambtenaren kunnen per app instellen welke profielgegevens gedeeld worden, met granulariteit tot op resource-niveau.

### Authenticatie: Solid-OIDC

Solid gebruikt **Solid-OIDC** (OpenID Connect) voor authenticatie:
- Gebruikers hebben een **WebID** (HTTP URI die naar hun profiel verwijst)
- Authenticatie gaat via een **OpenID Provider** (vergelijkbaar met Keycloak)
- Apps authenticeren via Authorization Code Flow met PKCE

**Dit past goed bij Rijks-SSO**: Keycloak is een OpenID Connect provider. In theorie zou Keycloak kunnen dienen als de OpenID Provider voor Solid-OIDC.

### Collega-profielen ophalen

Dezelfde uitdaging als bij AT Protocol: om het profiel van een collega op te halen moet de app:
1. De WebID/Pod-locatie van de collega kennen
2. Daar de profieldata ophalen
3. Gecheckt worden tegen de ACL

Dit vereist een **directory service** die WebID-naar-ambtenaar mappt, maar dit is eenvoudiger dan bij AT Protocol (gewoon een HTTP URI, geen DID-resolutie).

### Vlaanderen/België als precedent

De **Vlaamse overheid** is de meest relevante referentie:
- Investering van **€14 miljoen** in [SolidLab](https://solidlab.be/) (2022-2026, via imec + UGent/KU Leuven/VUB)
- Doel: elke burger (~6,5 miljoen) krijgt een Solid Pod als persoonlijke datastore
- **"My Citizen Profile"** — precies het concept van een profielservice
- [Athumi](https://www.athumi.be/) opgericht als Europese eerste "data utility company" voor veilige data-uitwisseling
- Microsoft-partnership: Entra (identity) wordt geïntegreerd met Solid
- Het SolidLab-programma is nu afgelopen en overgegaan in **Trustflows**

### Beperkingen en kritiek

**Volwassenheid**:
- De Solid Protocol specificatie is nog een **Draft Community Group Report** (geen W3C Recommendation)
- De twee open-source server-implementaties (Community Solid Server, Node Solid Server) zijn primair research/experimenteel
- Er zijn weinig productie-deployments buiten Vlaanderen

**Gebruikerservaring**:
- De huidige Pod-interfaces zijn niet gebruiksvriendelijk
- Het "inloggen met Solid" concept is voor eindgebruikers verwarrend
- Fine-grained permission management (per veld) is in de UI nog niet goed opgelost

**Technische beperkingen**:
- Pods zijn in essentie een **document store** — geen query-mogelijkheden
- Apps moeten zelf data ophalen en samenvoegen uit individuele Pods — dit schaalt lastig
- RDF/Linked Data als dataformaat heeft een steile leercurve voor ontwikkelaars
- Performance bij het ophalen van profielen uit honderden individuele Pods is onduidelijk

**Security**:
- Access control werkt op resource-niveau (niet op veld-niveau) — gebruikers kunnen onbedoeld gevoelige info delen
- Geen ingebouwde audit trail in het protocol

### Server-implementaties

| Implementatie | Taal | Status |
|---|---|---|
| [Community Solid Server](https://github.com/CommunitySolidServer/CommunitySolidServer) | TypeScript/Node.js | Actief onderhouden, research-focus |
| [Node Solid Server](https://github.com/nodeSolidServer/node-solid-server) | Node.js | Ouder, minder actief |
| Inrupt Enterprise Solid Server | Commercieel | Productie-ready (gebruikt door Vlaanderen) |

### Conclusie Solid Protocol

**Conceptueel de beste match**, maar met significante risico's rond volwassenheid, performance, en developer experience.

---

## ActivityPub

### Wat is het?

ActivityPub is een **W3C Recommendation** (officiële standaard sinds januari 2018) voor gedecentraliseerd social networking. Het is het protocol achter het "Fediverse" — het netwerk van Mastodon, Lemmy, PeerTube, Pixelfed, en tientallen andere platforms die onderling communiceren.

### Architectuur

```
Server A (bijv. mastodon.social)           Server B (bijv. rijks.nl)
  ├── Actor: @alice                          ├── Actor: @bob
  │    ├── inbox  (ontvangt berichten)       │    ├── inbox
  │    ├── outbox (verzendt berichten)       │    ├── outbox
  │    └── profiel (naam, bio, avatar)       │    └── profiel
  │                                          │
  └── Federatie: S2S protocol ──────────────>└── Ontvangt activities via POST
```

- **Actors**: gebruikers, groepen, of applicaties — elk met een inbox/outbox
- **Activities**: acties zoals Create, Follow, Like, Update — in ActivityStreams 2.0 (JSON-LD) formaat
- **Server-centric**: data leeft op de server van de gebruiker, niet in een persoonlijke datastore
- **Federatie**: servers praten met elkaar via HTTP POST naar inboxes (server-to-server protocol)
- **Client API**: er is ook een client-to-server API, maar deze wordt weinig gebruikt in de praktijk

### Access control — adressering-gebaseerd ⚠️

ActivityPub heeft **geen ACL-systeem**. Zichtbaarheid wordt bepaald door **adressering** (vergelijkbaar met email):
- `to: [as:Public]` — openbaar, zichtbaar voor iedereen
- `to: [followers-collectie]` — alleen voor volgers
- `to: [@specifieke-persoon]` — direct message

De **server** is verantwoordelijk voor het afdwingen van deze regels. Er is geen cryptografische garantie dat een ontvangende server de privacy respecteert. "After an activity has been transmitted from an origin server to a remote server, there is nothing in the ActivityPub protocol that can enforce remote deletion."

### Authenticatie

ActivityPub heeft **geen standaard authenticatie-spec**:
- De meeste implementaties gebruiken **HTTP Signatures** voor server-to-server communicatie
- Sommige servers ondersteunen "authorized fetch" (secure mode) waarbij GET-requests ook gesigneerd moeten zijn
- Er is geen standaard voor gebruikersauthenticatie — elke implementatie (Mastodon, Lemmy, etc.) doet dit anders
- **Geen OIDC/OAuth standaard** in het protocol zelf

### Analyse voor de Rijksprofielservice

**Wat past:**
- **W3C standaard** — de enige van de drie protocollen die een officiële W3C Recommendation is
- **Breed ecosysteem** — Mastodon, Lemmy, PeerTube, Nextcloud, WordPress (via plugin), etc.
- **Laagdrempelig** — relatief eenvoudig te implementeren, veel libraries beschikbaar
- **Profiel-concept** — elke Actor heeft profielgegevens (naam, bio, avatar, URL)
- **Followers-only content** — er is een mechanisme voor niet-publieke data

**Wat niet past:**
- **Geen echte access control** — zichtbaarheid is gebaseerd op adressering, niet op permissions. Je kunt niet zeggen "app Wies mag mijn naam en email zien maar niet mijn telefoon"
- **Server-centric, niet user-centric** — data leeft op de server, niet in een persoonlijke datastore. De serveradmin heeft volledige toegang. Dit is fundamenteel anders dan het "data bij de bron" principe.
- **Geen consent-model** — er is geen mechanisme waarbij een gebruiker per app toestemming geeft voor toegang tot specifieke gegevens
- **Ontworpen voor social interactie** — het protocol gaat over het versturen van activities (posts, likes, follows), niet over het ophalen van profieldata door applicaties
- **Geen data-portabiliteit** — als je server stopt, ben je je data kwijt (tenzij de implementatie export ondersteunt). Het protocol zelf garandeert dit niet.
- **Privacy is zwak** — geen cryptografische garanties, vertrouwen op server-beheerders

### Conclusie ActivityPub

**Niet geschikt voor de Rijksprofielservice.** Het protocol is ontworpen voor gefedereerde social communicatie, niet voor gecontroleerde toegang tot persoonsgegevens. Het mist de fundamentele bouwstenen die nodig zijn: per-app consent, fine-grained access control, en data-eigenaarschap door de gebruiker.

---

## Vergelijking: AT Protocol vs. Solid vs. ActivityPub vs. Huidig concept (Django)

| Aspect | AT Protocol | Solid | ActivityPub | Django (huidig concept) |
|---|---|---|---|---|
| **Privacy/access control** | ❌ Alles publiek | ✅ Ingebouwde ACL | ⚠️ Alleen adressering | ✅ Zelf te bouwen |
| **Data-eigenaarschap** | ✅ User-owned PDS | ✅ User-owned Pod | ❌ Server-owned | ⚠️ Centraal beheerd |
| **Consent per app** | ⚠️ OAuth scopes | ✅ ACL per app/resource | ❌ Geen model | ✅ Zelf te bouwen |
| **Collega-profielen** | ⚠️ Vereist directory | ⚠️ Vereist directory | ⚠️ Via federatie | ✅ Simpele API call |
| **SSO-integratie** | ⚠️ Eigen identiteit (DID) | ✅ OIDC (past bij Keycloak) | ❌ Geen standaard | ✅ Direct via Keycloak |
| **Volwassenheid** | ✅ Productie (Bluesky) | ⚠️ Experimenteel/early | ✅ W3C standaard, breed | ✅ Bewezen stack |
| **Schaalbaarheid** | ✅ Bewezen op schaal | ⚠️ Onduidelijk | ✅ Bewezen (Mastodon) | ✅ Standaard |
| **Overheidsreferentie** | ❌ Geen | ✅ Vlaanderen | ⚠️ EU social (Mastodon) | ✅ Standaard |
| **Developer experience** | ⚠️ Nieuw ecosysteem | ⚠️ RDF/Linked Data | ✅ Veel libraries | ✅ Bekend (Python/REST) |
| **Adoptiedrempel users** | ⚠️ DID-concept | ⚠️ Pod/WebID-concept | ✅ Normaal account | ✅ Normaal account |
| **Extensibility** | ✅ Lexicons | ✅ RDF schemas | ✅ ActivityStreams | ⚠️ Zelf te bouwen |

---

## Samenvattend oordeel per protocol

| Protocol | Oordeel | Kernreden |
|---|---|---|
| **AT Protocol** | ❌ Niet geschikt | Alle data publiek — showstopper voor persoonsgegevens |
| **ActivityPub** | ❌ Niet geschikt | Geen access control of consent-model — ontworpen voor social communicatie, niet voor gecontroleerde datatoegang |
| **Solid** | ⚠️ Conceptueel goed, nog niet rijp | Ingebouwde ACL en OIDC passen perfect, maar technologie is nog experimenteel |
| **Django (huidig)** | ✅ Pragmatisch beste keuze | Bewezen stack, volledige controle, kan Solid-principes incorporeren |

## Aanbeveling

### Pragmatische aanpak

1. **Kort-termijn**: bouw de Rijksprofielservice als het huidige Django-concept, maar met **Solid-achtige principes**:
   - Opt-in consent model (al in concept)
   - Per-app en eventueel per-veld toestemming
   - Data-portabiliteit als exportfunctie
   - REST API met OAuth2 (al in concept)

2. **Middellang**: volg de ontwikkelingen bij Solid (vooral Vlaanderen/Athumi/Trustflows) en AT Protocol (Private Data Working Group). Als Solid volwassener wordt, kan de profielservice later gemigreerd worden naar een Pod-architectuur.

3. **Concreet contact**: neem contact op met **SolidLab/Athumi** in Vlaanderen om te leren van hun ervaring met "My Citizen Profile" — dit is de meest directe referentie.

---

## Bronnen

### AT Protocol
- [AT Protocol Overview](https://atproto.com/guides/overview)
- [Personal Data Server (PDS) Wiki](https://atproto.wiki/en/wiki/reference/core-architecture/pds)
- [AT Protocol OAuth Spec](https://atproto.com/specs/oauth)
- [Private Data Working Group](https://atproto.wiki/en/working-groups/private-data)
- [Lexicon Schema System](https://atproto.com/guides/lexicon)
- [Self-hosting Guide](https://atproto.com/guides/self-hosting)
- [Beyond Bluesky: apps on AT Protocol (TechCrunch)](https://techcrunch.com/2025/06/13/beyond-bluesky-these-are-the-apps-building-social-experiences-on-the-at-protocol/)

### Solid Protocol
- [Solid Project](https://solidproject.org/about)
- [Solid Protocol Specificatie](https://solidproject.org/TR/protocol)
- [Solid-OIDC Specificatie](https://solidproject.org/TR/oidc)
- [Community Solid Server (GitHub)](https://github.com/CommunitySolidServer/CommunitySolidServer)
- [SolidLab Vlaanderen](https://solidlab.be/)
- [Inrupt: Flanders & Solid](https://www.inrupt.com/blog/flanders-solid)
- [Athumi — data utility company](https://www.athumi.be/)
- [Kritiek op Solid (Leigh Dodds)](https://blog.ldodds.com/2024/03/12/baffled-by-solid/)
- [Schneier on Solid](https://www.schneier.com/blog/archives/2025/07/how-solid-protocol-restores-digital-agency.html)

### ActivityPub
- [ActivityPub W3C Recommendation](https://www.w3.org/TR/activitypub/)
- [ActivityPub — Wikipedia](https://en.wikipedia.org/wiki/ActivityPub)
- [Understanding ActivityPub — Protocol Fundamentals](https://seb.jambor.dev/posts/understanding-activitypub/)
- [ActivityPub Authentication & Authorization (W3C Wiki)](https://www.w3.org/wiki/ActivityPub/Primer/Authentication_Authorization)
- [AT Protocol vs ActivityPub debate](https://biggo.com/news/202509270113_AT_Protocol_vs_ActivityPub_Debate)

### Vergelijking
- [Solid + AT Protocol + ActivityPub discussie](https://forum.solidproject.org/t/exploring-a-hybrid-protocol-stack-solid-at-protocol-activitypub/8252)
