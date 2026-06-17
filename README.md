# Rijksprofielservice

Het doel van de rijksprofielservice is om een enkel portaal te hebben waarin ambtenaren hun profiel kunnen beheren welke applicaties gebruiken mogen maken van deze gegevens. Aan de gebruikers kant hoeven ambtenaren daardoor hun informatie maar op 1 plek hij te houden (data bij de bron) en voor applicaties is het makkelijker om dit te implementeren.

## Status
Huidige status: PoC2 — echte OAuth Authorization Code flow voor consent (via `django-oauth-toolkit`); profielservice is zelf de OAuth Authorization Server voor zowel user-bound (Authorization Code + PKCE) als M2M (Client Credentials). Onderzoek (`onderzoek/`) en ontwerp (`docs/`) zijn de basis. De HTML-prototype in `demo/` blijft als UX-referentie.

> **Keycloak overwogen:** een variant was om Keycloak ook de Authorization Server voor consuming apps te laten zijn (eigen `profielservice`-realm). Doorslaggevend nadeel: consent past niet natuurlijk in Keycloak en intrekken zou DB-checks per request vereisen — wat de winst van stateless tokens neutraliseert. Met `django-oauth-toolkit` valt consent samen met grant: revoke verwijdert tokens direct. Keycloak blijft alleen in beeld als SSO Rijk broker voor ambtenaar-login (extern, geen lokale instance meer nodig).

## Scope PoC

PoC v1 = "make it work" — meeting met Patrick. Opgesplitst in PoC1 (technische basis end-to-end) en PoC2 (productie-rijp maken). Volledig plan: zie `/Users/matthijs/.claude/plans/ik-wil-een-proof-optimized-bentley.md`.

### PoC1 — klaar
- Django app in Wies-stijl (Jinja2 + HTMX, `config/` + één app `core`, uv, Postgres via Docker)
- Auth via `rijksauth` (gevendord uit [Wies](https://github.com/RijksICTGilde/wies)); OIDC tegen SSO Rijk realm, `SKIP_OIDC` voor dev
- Profielbeheer door ambtenaar: telefoon, functie, organisatie, avatar upload
- Per-app consent + beheerscherm voor intrekken
- Avatar serving op aparte URL met caching
- Django admin voor app-goedkeuring
- REST API: `GET /api/v1/profiles/{subject-id}`, `POST /api/v1/profiles/batch`, response gefilterd op `requested_fields ∩ consent`
- Seed-data: 3 ambtenaren + 2 mock consuming apps (Wies, AMT)

### PoC2 — klaar
- Echte OAuth 2.0 Authorization Code flow (+ PKCE) voor consent — profielservice is zelf de OAuth Authorization Server via `django-oauth-toolkit`
- Eén unified token-systeem: ook M2M (Client Credentials) loopt via dezelfde server; lokale Keycloak verdwenen
- `/api/v1/profiles/me` endpoint voor user-bound flows (token = bewijs van consent)
- Consent intrekken → directe revoke van AccessTokens/Grants/RefreshTokens (geen wachten op expiry)
- 2e consuming app (mock-amt) als demo-client

### PoC2 — volgende iteratie
- HTTP caching headers (`ETag`, `Cache-Control`, `Vary: Authorization`) op API
- Smoke test mgmt command (token → call → verify)

### Bewust uit beide PoCs
- Per-veld consent granulariteit
- Webhooks / change notifications
- Deprovisioning automation
- DPIA, audit log, export
- Rate limiting, observability
- Productie hosting / CDN

## v2 Make it scale (na PoC)
- Heroverweeg stack op basis van échte load
- Aanvullen met meer apps

## Lokale poorten

| Service | Host-poort | Reden |
|---|---|---|
| Django (rijksprofielservice) | `8000` | Standaard Django; uit de weg van Wies (8080). |
| Postgres | `5433` | Naast standaard 5432 om naast Wies te kunnen draaien. |

Zo kun je deze PoC én Wies (poort 8080/5432) tegelijk lokaal draaien.

## OAuth Authorization Server (intern)

De profielservice serveert zelf de OAuth 2.0 endpoints via [django-oauth-toolkit](https://django-oauth-toolkit.readthedocs.io/):

- `GET /o/authorize/` — Authorization Code (+ PKCE) entry, toont consent-scherm
- `POST /o/token/` — code/token exchange én client-credentials grant
- `POST /o/revoke_token/` — token revocation

Twee DOT-clients per business-app: bv. `mock-wies` (Authorization Code, voor user-flows) en `mock-wies-m2m` (Client Credentials, voor batch-API).

```bash
# M2M token ophalen
just m2m-token mock-wies-m2m local-dev-secret-wies

# User-flow demo
open http://localhost:8000/demo/mock-wies-landing/
```

## SSO-login (rijksauth)

SSO-login voor ambtenaren gaat via een externe Wies-dev realm — vul `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` en `OIDC_DISCOVERY_URL` in `.env` aan. Zet daarna `SKIP_OIDC=false` (of gebruik `just demo-sso`).




