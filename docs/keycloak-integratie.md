# Keycloak-integratie — Technisch Detail

## Architectuur: SSO Rijk, Keycloak en de profielservice

Keycloak fungeert als broker tussen SSO Rijk (de centrale identity provider van het Rijk) en de individuele applicaties. Via Keycloak wordt een enkele SSO Rijk-aansluiting gedeeld over meerdere apps. De apps praten met Keycloak, niet rechtstreeks met SSO Rijk.

```
SSO Rijk (centrale identity provider)
    │
    │  een aansluiting (OIDC/SAML)
    │
    ▼
Keycloak (identity broker, eigen beheer)
    │
    ├── SSO Rijk realm
    │     ├── Wies (client) ─── gebruikerslogin
    │     ├── AMT (client)
    │     └── Profielservice (client)
    │
    └── Profielservice realm
          ├── Wies (client) ─── API-toegang via client-credentials
          ├── AMT (client)
          └── ...
```

## Twee realms

### SSO Rijk realm (gebruikerslogin)

Hier loggen ambtenaren in. Apps zijn geregistreerd als OIDC clients met de standaard authorization-code flow. Na login ontvangt de app een token met het **subject-ID** van de ambtenaar.

Dit is het bestaande SSO-mechanisme en wordt niet verder beschreven in dit document.

### Profielservice realm (app-authenticatie)

Een aparte realm specifiek voor de profielservice API. Afnemer-apps registreren zich hier als client om via **client-credentials** tokens op te halen waarmee ze de profielservice API kunnen aanroepen.

Geen gebruikerslogin — puur machine-to-machine communicatie.

## Keycloak client-configuratie (profielservice realm)

Bij het aanmaken van een client in de profielservice realm moeten de instellingen als volgt staan:

### Scherm 1: General settings

| Setting | Waarde | Waarom |
|---------|--------|--------|
| Client type | OpenID Connect | Standaard protocol; tokens zijn JWTs die de profielservice stateless kan valideren |
| Client ID | bijv. `wies` | Identifier waarmee de profielservice de app herkent in het token (`azp` claim) |
| Name | bijv. `Wies` | Leesbare naam voor de Keycloak admin UI |
| Description | Optioneel | Voor beheerders, geen technisch effect |
| Always display in UI | Off | Er is geen gebruikerslogin in deze realm, niets om te tonen |

### Scherm 2: Capability config

| Setting | Waarde | Waarom |
|---------|--------|--------|
| Client authentication | **On** | Maakt het een *confidential* client met een `client_secret`. Nodig voor server-side apps die zich moeten authenticeren |
| Authorization | Off | Keycloak's eigen fine-grained authorization (UMA/policies). Niet nodig — de profielservice handelt toestemming zelf af |
| Standard flow | **Uit** | Authorization-code flow voor gebruikerslogin. Niet nodig in deze realm |
| Direct access grants | **Uit** | Resource owner password grant — app ontvangt direct username/wachtwoord. Onveilig, niet nodig |
| Implicit flow | **Uit** | Verouderd patroon voor browser-apps, niet relevant |
| Service accounts roles | **Aan** | Activeert de client-credentials grant. Hiermee kan de app een token aanvragen namens zichzelf, zonder gebruiker. Dit is de kern van de setup |
| OAuth 2.0 Device Authorization Grant | **Uit** | Voor apparaten zonder browser, niet relevant |
| OIDC CIBA Grant | **Uit** | Client-initiated backchannel auth, niet relevant |

### Scherm 3: Login settings

| Setting | Waarde | Waarom |
|---------|--------|--------|
| Root URL | Leeg | Geen gebruikerslogin, geen redirects nodig |
| Home URL | Leeg | Idem |
| Valid redirect URIs | Leeg | Standard flow staat uit, er zijn geen redirects |
| Valid post logout redirect URIs | Leeg | Idem |
| Web origins | Leeg | CORS voor browser-calls, niet relevant voor server-to-server |

**Samengevat:** alles staat uit behalve **Client authentication** en **Service accounts roles**. De client doet een ding: met een secret een token ophalen om de profielservice API te callen.

## Flow: profiel ophalen

```
1. Ambtenaar logt in bij Wies via SSO Rijk realm
   → Wies kent het subject-ID van de ambtenaar

2. Wies vraagt token aan bij profielservice realm (client-credentials)
   → POST /realms/profielservice/protocol/openid-connect/token
     grant_type=client_credentials
     client_id=wies
     client_secret=...

3. Wies stuurt request naar profielservice API
   → GET /profiles/{subject-id}
     Authorization: Bearer <token>

4. Profielservice:
   → Valideert token (JWT signature check tegen Keycloak public key)
   → Identificeert de app uit het token (azp=wies)
   → Checkt toestemming (heeft deze ambtenaar toestemming gegeven aan Wies?)
   → Retourneert profielgegevens
```

## Aansluiting nieuwe afnemer-app

Het aansluiten van een nieuwe app is een twee-staps proces:

1. **Keycloak**: client aanmaken in de profielservice realm (configuratie zoals hierboven)
2. **Profielservice**: een admin keurt de app goed

Profielservice-admins worden beheerd via de `STAFF_EMAILS` environment variable (zoals bij Wies). Alleen admins kunnen nieuwe apps goedkeuren.

Een app die wel als Keycloak client bestaat maar niet door een admin is goedgekeurd, wordt geweigerd door de profielservice. Dit is een bewuste extra beveiligingslaag bovenop Keycloak.

## Token-validatie in de profielservice

De profielservice valideert tokens **stateless** — zonder Keycloak per request aan te roepen:

1. Haal bij opstarten de public key op van de profielservice realm (`/realms/profielservice/protocol/openid-connect/certs`)
2. Bij elk request: valideer de JWT-signature, check `exp` (verlopen?), check `iss` (juiste realm?)
3. Lees `azp` of `client_id` uit het token om de afnemer-app te identificeren
4. Check of die app is goedgekeurd door een admin

Dit is standaard JWT-validatie die Django libraries (bijv. `djangorestframework-simplejwt`) grotendeels afhandelen.
