# Keycloak (lokaal)

Lokale Keycloak voor de `profielservice` realm — uitgeven van client-credentials tokens aan consuming apps (`mock-wies`, `mock-amt`) voor de REST API.

SSO-login voor ambtenaren gebruikt een externe realm (Wies-dev Keycloak), niet deze instance. Zie `OIDC_*` in `.env`.

## Bereikbaarheid

- Admin console: <http://localhost:8081/admin> — login `admin` / `admin`
- Realm URL: <http://localhost:8081/realms/profielservice>
- Token endpoint: `<http://localhost:8081/realms/profielservice/protocol/openid-connect/token>`

Of: `just keycloak-info`.

## Realm herladen

De realm wordt geïmporteerd uit `realms/profielservice-realm.json` bij eerste start. Daarna slaat `--import-realm` over. Voor een schone re-import:

```sh
docker compose down -v
docker compose up keycloak
```

## Secrets

Alle client-secrets in `realms/profielservice-realm.json` zijn lokaal-only voor PoC. Niet hergebruiken in productie.
