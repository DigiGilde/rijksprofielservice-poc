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
- Per-app consent (geven / intrekken)
- Avatar serving op aparte URL met caching
- Django admin voor app-goedkeuring
- Keycloak `profielservice`-realm (dual-realm) met client-credentials per app
- REST API: `GET /api/v1/profiles/{subject-id}` en `POST /api/v1/profiles/batch`, response gefilterd op `requested_fields ∩ consent`
- Seed-data: 3 ambtenaren + 2 mock consuming apps (Wies, AMT)

### PoC2 — volgende iteratie
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




