# Rijksprofielservice

Het doel van de rijksprofielservice is om een enkel portaal te hebben waarin ambtenaren hun profiel kunnen beheren welke applicaties gebruiken mogen maken van deze gegevens. Aan de gebruikers kant hoeven ambtenaren daardoor hun informatie maar op 1 plek hij te houden (data bij de bron) en voor applicaties is het makkelijker om dit te implementeren.

## Status
Huidige status: start van de Django PoC. Onderzoek (`onderzoek/`) en ontwerp (`docs/`) zijn de basis. De HTML-prototype in `demo/` blijft als UX-referentie.

## Scope PoC

PoC v1 = "make it work" — meeting met Patrick. Opgesplitst in PoC1 (technische basis end-to-end) en PoC2 (productie-rijp maken). Volledig plan: zie `/Users/matthijs/.claude/plans/ik-wil-een-proof-optimized-bentley.md`.

### PoC1 — in scope
- Django app in Wies-stijl (Jinja2 + HTMX, `config/` + één app `core`, uv, Postgres via Docker)
- Auth via `rijksauth` (gevendord uit [Wies](https://github.com/RijksICTGilde/wies)); OIDC tegen SSO Rijk realm, `SKIP_OIDC` voor dev
- Profielbeheer door ambtenaar: telefoon, functie, organisatie, avatar upload
- Per-app consent: OAuth-style redirect-flow (consuming app → consent-scherm → terug) voor eerste toestemming; beheerscherm voor intrekken
- Avatar serving op aparte URL met caching
- Django admin voor app-goedkeuring
- Keycloak `profielservice`-realm lokaal in Docker met client-credentials per app; SSO-login via externe Wies-dev realm
- REST API: `GET /api/v1/profiles/{subject-id}` en `POST /api/v1/profiles/batch`, response gefilterd op `requested_fields ∩ consent`
- Seed-data: 3 ambtenaren + 2 mock consuming apps (Wies, AMT)

### PoC2 — volgende iteratie
- Echte OAuth Authorization Code flow voor consent (code/token exchange via Keycloak in plaats van eigen redirect; `redirect_uri`-validatie verhuist naar Keycloak)
- Productie-grade JWT-validatie (JWKS-cache, strikte `iss`/`exp`/`azp` checks)
- HTTP caching headers (`ETag`, `Cache-Control`, `Vary: Authorization`)
- 2e consuming app als demo-client voor end-to-end verhaal
- Smoke test mgmt command (mint token → batch → verify)

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
| Keycloak | `8081` | Eigen waarde; geen conflict. |

Zo kun je deze PoC én Wies (poort 8080/5432) tegelijk lokaal draaien.

## Keycloak lokaal

`docker compose up` start een lokale Keycloak op <http://localhost:8081> met de `profielservice` realm (voor M2M client-credentials tokens). Zie [keycloak/README.md](keycloak/README.md) voor details, of `just keycloak-info`.

SSO-login voor ambtenaren gaat via een externe Wies-dev realm — vul `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` en `OIDC_DISCOVERY_URL` in `.env` aan. Zet daarna `SKIP_OIDC=false` (of gebruik `just demo-sso`).




