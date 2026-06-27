# Uit-dienst-treding

## Het probleem

Profielen zijn gekoppeld aan het Rijks-SSO subject-ID. Als een ambtenaar uit dienst gaat, wordt die in Rijks-SSO gedeactiveerd — maar de profielservice krijgt daarvan **geen direct signaal**. Keycloak zit als broker tussen Rijks-SSO en de afnemer-apps, en SCIM is niet beschikbaar.

Zonder opruimstrategie blijven profielen van ex-ambtenaren in de service staan. Dat is in strijd met de AVG (geen grondslag meer), vervuilt de data van afnemer-apps, en is door de CISO expliciet aangemerkt als governance-gat.

Tegelijk is hard-delete op een zwak signaal risicovol: iemand met langdurig verlof (ouderschap, ziekte, detachering) is nog wel in dienst.

## Uitgangspunten

1. **Activiteit, niet aanwezigheid, is het signaal.** Elke succesvolle authenticatie via een aangesloten app (inclusief de profielservice zelf) is bewijs dat Rijks-SSO de user nog steeds authenticeert.
2. **Inactief ≠ verwijderd.** Inactiviteit is een zachte, reversibele toestand. Hard-delete komt pas veel later en is destructief.
3. **Idempotent herstel.** Als een inactieve user terugkomt, werkt alles weer zonder handmatige tussenkomst.
4. **De profielservice is een verrijkingslaag.** Afnemer-apps (Wies, AMT) hebben een eigen user-administratie en eigen bewaartermijn. Als de profielservice een profiel niet meer levert, blijft de collega in de app gewoon zichtbaar — alleen zonder verrijking (avatar, functietitel).

## Wat tellen we als activiteit?

Elke API-call die de profielservice afhandelt voor subject-ID X met een geldig token is bewijs dat X recent is ingelogd bij de aanroepende app. Bij iedere zulke call wordt `last_seen_at` voor X bijgewerkt.

```
Ambtenaar A logt in bij Wies (via SSO Rijk → Keycloak)
  → Wies krijgt id_token met subject-ID van A
  → Wies doet API-call naar profielservice
  → Profielservice: UPDATE profiles SET last_seen_at = NOW() WHERE subject_id = 'A'
```

## De twee drempels

```
                   ┌─────────────┐
                   │    actief   │
                   └──────┬──────┘
                          │
                   90 dagen geen activiteit
                          │
                          ▼
                   ┌─────────────┐
                   │  inactief   │ ←── reversibel
                   └──────┬──────┘     (herlogin = weer actief)
                          │
                   2 jaar geen activiteit
                          │
                          ▼
                   ┌─────────────┐
                   │  verwijderd │ ←── destructief
                   └─────────────┘     (cascade: consents, avatar, audit)
```

### Drempel 1 — Inactief (90 dagen)

Na 90 dagen zonder activiteit wordt een profiel gemarkeerd als **inactief**. Het record blijft volledig intact (alle velden, consent-records, avatar). Wat verandert is de zichtbaarheid voor afnemer-apps:

| Type call | Voorbeeld | Inactief profiel zichtbaar? | Reset `marked_inactive_at`? |
|-----------|-----------|------------------------------|------------------------------|
| Ambtenaar haalt eigen profiel op | Ambtenaar opent Wies → Wies vraagt eigen profiel | **Ja** | Ja |
| Batch over eigen relaties | Wies vraagt namens de ingelogde ambtenaar teamprofielen | **Ja** voor de aanroepende ambtenaar zelf | Alleen voor de aanroeper |
| Batch over andermans relaties | Profiel van inactieve collega A zit in batch namens B | **Nee** — A wordt weggelaten | Nee |
| Losse lookup van een ander | App vraagt direct profiel van A op terwijl B is ingelogd | **Nee** — 404 | Nee |

Kortom: een inactieve user kan zichzelf altijd reactiveren door simpelweg in te loggen bij een aangesloten app. Collega's "zien" het profiel pas weer nadat de user dat zelf heeft gedaan. Een passieve batch-call door iemand anders is niet genoeg om een inactief profiel ongemerkt terug te brengen naar actief.

### Drempel 2 — Hard-delete (2 jaar)

Na 2 jaar zonder activiteit wordt het profiel **verwijderd**. Cascade:

- Profielrecord, consent-records en avatar-blob worden verwijderd.
- Audit-log entry wordt geschreven (los van het profiel bewaard).

Als dezelfde subject-ID later weer opduikt (bv. iemand komt na 3 jaar terug bij het Rijk), wordt die behandeld als **nieuwe gebruiker**: consents zijn weg, avatar is weg, toestemmingen moeten opnieuw worden gegeven. Acceptabel, omdat 2 jaar inactiviteit bij een rijksambtenaar een sterke indicatie is dat de arbeidsrelatie is beëindigd.

## Mogelijke uitbreidingen

Onderdelen die nuttig zijn maar niet in de eerste implementatie zitten:

- **Waarschuwingsmails** op 90 dagen en ±21 maanden, zodat de ambtenaar kan ingrijpen vóór hard-delete. Vereist een betrouwbaar e-mailkanaal en stale-adres-afhandeling.
- **Webhook naar afnemer-apps** bij hard-delete (`{"event": "profile_deleted", "subject_id": "..."}`) zodat zij hun caches/kopieën kunnen opruimen. Vereist een webhook-contract en intrekkings-/retry-beleid per afnemer.
- **Hard signaal vanuit Rijks-SSO**: als Rijks-SSO in de toekomst een lookup of SCIM-feed biedt, kan bevestiging "user is weg" direct naar de verwijderd-status leiden zonder op 2 jaar te wachten.
