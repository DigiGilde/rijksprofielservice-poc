# Test JWT keypair

Lokaal-only RS256 keypair voor de `mint_test_token` mgmt command. Wordt door `core/api/auth.py` herkend wanneer `PROFIELSERVICE_JWT_ALLOW_TEST_KEY=true` én het token `kid: "test-kid"` heeft.

**Niet in productie inschakelen.** `production.py` mag deze setting nooit op `true` zetten.

Doel: lokale demo-flow (mock-landing pagina's) kan de batch-API aanroepen zonder dat er een echte Keycloak-roundtrip nodig is. Voor echte M2M-flow gebruik je `just keycloak-token` tegen de lokale Keycloak.
