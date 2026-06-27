# Ontwerp: Deprovisioning zonder SCIM

*April 2026*

## Context

De profielservice slaat profielen op met het Rijks-SSO subject-ID als sleutel. Wanneer een ambtenaar uit dienst gaat, wordt die in Rijks-SSO gedeactiveerd. Maar:

- De architectuur gebruikt Keycloak als broker tussen Rijks-SSO en de afnemer-apps (zie [keycloak-integratie.md](../docs/keycloak-integratie.md)). Directe koppelingen tussen profielservice en Rijks-SSO zijn niet voorzien.
- SCIM 2.0 is niet in scope. Keycloak biedt geen volwassen SCIM-support (community-extensies zoals sventorben/keycloak-scim zijn gearchiveerd; outbound SCIM zit nog niet in de Keycloak core GA).
- Daarmee is er **geen automatisch signaal** dat een user in Rijks-SSO is gedeactiveerd. Keycloak's eigen userlist is geen goede proxy — users worden daar just-in-time aangemaakt bij eerste login en blijven bestaan ook na deactivering upstream.

De vraag: hoe ruim je profielrecords op van ex-ambtenaren als je hun vertrek niet direct gesignaleerd krijgt?

## Het probleem

Zonder uit-dienst-signaal blijven profielen staan van mensen die niet meer in dienst zijn. Dat is problematisch om drie redenen:

1. **Privacy/AVG**: persoonsgegevens mogen niet langer bewaard worden dan noodzakelijk. Een profiel van een ex-ambtenaar heeft geen grondslag meer.
2. **Datakwaliteit**: afnemer-apps (Wies, AMT) kunnen collega-profielen tonen van mensen die er niet meer zijn.
3. **Lifecycle-governance**: de CISO heeft expliciet om een uit-dienst-treding-aanpak gevraagd (zie [patrick_ciso_20260422.txt](./patrick_ciso_20260422.txt)).

Tegelijk: hard-delete op basis van een zwak signaal (bv. "60 dagen geen login") is risicovol. Iemand met langdurig verlof (ouderschap, ziekte, sabbatical) kan gewoon nog in dienst zijn. Hard-delete zou betekenen dat die persoon bij terugkomst een leeg profiel heeft, consent-records kwijt is, en door afnemer-apps als nieuwe gebruiker wordt behandeld.

## Principes

Voordat we opties afwegen, de uitgangspunten:

1. **Activiteit, niet aanwezigheid, is het signaal.** We meten of iemand recent heeft ingelogd via een van de aangesloten apps (inclusief de profielservice zelf). Een login via Rijks-SSO → Keycloak → app is bewijs dat Rijks-SSO de user nog steeds authenticeert.
2. **Inactief ≠ verwijderd.** Inactiviteit is een zachte, reversibele vlag. Hard-delete is destructief en wordt alleen toegepast na een veel langere periode.
3. **Idempotent herstel.** Als een "inactieve" user terugkomt, moet alles weer werken zonder handmatige tussenkomst.
4. **Duidelijkheid over bewaartermijn.** Bewaartermijnen worden expliciet afgestemd met de CISO/FG, niet impliciet gecodeerd.

## Wat tellen we als "activiteit"?

Een activiteit is elke **succesvolle authenticatie** van een ambtenaar bij:

- De profielservice zelf (ambtenaar logt in om profiel te bewerken of toestemmingen te beheren).
- Een aangesloten afnemer-app (Wies, AMT, ZAD, ...) — zichtbaar als de app namens de ambtenaar een request doet richting de profielservice met een geldige client-credentials-token én een bekend subject-ID.

Concreet: elke keer dat de profielservice een API-call afhandelt voor subject-ID X met een geldig token, is dat bewijs dat X net is ingelogd bij de aanroepende app. We registreren dat als `last_seen_at`.

```
Ambtenaar A logt in bij Wies (via SSO Rijk → Keycloak)
  → Wies krijgt id_token met subject-ID van A
  → Wies doet API-call naar profielservice voor teamprofielen
  → Profielservice ziet A's subject-ID voorbijkomen in de request-context
  → Profielservice update: UPDATE profiles SET last_seen_at = NOW() WHERE subject_id = 'A'
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

### Drempel 1 — Inactiviteit (voorstel: 90 dagen)

Na 90 dagen zonder activiteit wordt een profiel als **inactief** gemarkeerd (veld `marked_inactive_at`). Wat dat inhoudt:

- Het record blijft bestaan. Alle velden, consent-records en avatar blijven staan.
- Zichtbaarheid voor afnemer-apps hangt af van **wie de subject van de call is**:

  | Type call | Voorbeeld | Inactief profiel zichtbaar? | Effect op `marked_inactive_at` |
  |-----------|-----------|------------------------------|--------------------------------|
  | Ambtenaar haalt eigen profiel op (subject van de call = profiel-eigenaar) | Ambtenaar opent Wies → Wies vraagt het eigen profiel op | **Ja** | Wordt gereset (profiel weer actief) |
  | Batch-call namens een ambtenaar over diens eigen relaties | Wies vraagt namens de ingelogde ambtenaar de profielen van diens team op | **Ja** voor het profiel van de aanroepende ambtenaar zelf, en reset diens vlag | Reset alleen voor de aanroepende ambtenaar; inactieve collega's blijven onzichtbaar |
  | Batch-call over andermans relaties | Wies vraagt teamprofielen op voor ambtenaar B; profiel van inactieve collega A zit in de batch | **Nee** — A wordt stilletjes weggelaten | Geen reset |
  | Lookup van losse andere ambtenaar | App vraagt direct het profiel van A op terwijl B is ingelogd | **Nee** — 404 | Geen reset |

  Kortom: de inactieve user kan zichzelf altijd reactiveren door simpelweg in te loggen bij een aangesloten app; collega's "zien" diens profiel pas weer nadat de user dat zelf heeft gedaan. Dit voorkomt dat een passieve batch-call door iemand anders genoeg is om een inactief profiel ongemerkt terug te brengen naar actief.
- Er kan optioneel een waarschuwings-e-mail richting de ambtenaar gaan ("we hebben je al 90 dagen niet gezien — je profiel wordt na 2 jaar verwijderd").
- Op een interne dashboard/admin-view zichtbaar als "inactief sinds".

**Waarom onzichtbaar maken al bij inactief, niet pas bij hard-delete?** De profielservice is een **verrijkingslaag** bovenop de eigen user-administratie van de afnemer-app. Een afnemer-app (Wies, AMT) heeft zelf een lijst van gebruikers en moet bruikbaar blijven zonder de verrijking — geen avatar, geen functietitel uit de profielservice, maar de collega is in de app niet "verdwenen". De app heeft daarnaast haar eigen bewaartermijn voor die basisgegevens. Door inactieve profielen niet meer te leveren halen we onnodige persoonsgegevens uit de afnemer-flows zodra het signaal "deze ambtenaar is mogelijk weg" ontstaat, zonder dat dat de werking van de app breekt. Bij ouderschapsverlof of detachering blijft de collega gewoon in de teamlijst van Wies staan — alleen zonder de verrijkte velden, totdat 'ie weer inlogt.

### Drempel 2 — Hard-delete (voorstel: 2 jaar)

Na 2 jaar zonder activiteit wordt het profiel **verwijderd**. Wat dat inhoudt:

- Cascade-delete: profielrecord, consent-records, avatar-blob.
- Audit-log regel: wie/wanneer/welk subject-ID (vermoedelijk 7 jaar bewaren o.b.v. Archiefwet — af te stemmen).
- Notificatie (webhook) naar afnemer-apps met eerder actieve consent, zodat zij hun caches/kopieën kunnen opruimen.

Na hard-delete: als dezelfde subject-ID ooit weer opduikt in een login (bv. omdat iemand na 3 jaar terugkomt bij het Rijk), wordt die behandeld als **nieuwe gebruiker**. Consent-records zijn weg, avatar is weg, toestemmingen moeten opnieuw worden gegeven. Dat is acceptabel omdat 2 jaar inactiviteit bij een rijksambtenaar een sterke indicatie is dat de arbeidsrelatie is beëindigd.

### Waarom deze twee drempels?

| Drempel | Doel | Risico bij te kort | Risico bij te lang |
|---------|------|--------------------|--------------------|
| 90 dagen (inactief-vlag) | Verrijking stoppen, vroegsignalering, governance-dashboard, herinneringsmail | Onnodige flags bij normale verlofpatronen (apps vallen terug op basis-weergave) | Onnodig lang verrijken van mogelijk-ex-ambtenaren |
| 2 jaar (hard-delete) | Privacy-compliance, dataminimalisatie | Terugkerende ambtenaar moet opnieuw consent geven | Onnodig lang bewaren van persoonsgegevens |

Belangrijk: de 90-dagen-vlag is bewust **niet** destructief. Het profielrecord blijft volledig intact en herstelt zichzelf bij de eerstvolgende login. Alleen de 2-jaar-drempel is irreversibel.

## Zwakte van deze aanpak

Deze strategie is een **proxy** voor uit-dienst-treding, geen direct signaal. Gevolg:

- Een ambtenaar die wél in dienst is maar 2 jaar niet inlogt bij enige aangesloten app (bv. detachering bij een externe organisatie, ouderschapsverlof gevolgd door ziekte), wordt per ongeluk verwijderd.
- Omgekeerd: een ex-ambtenaar die nog actieve sessies/tokens had in een app, kan nog even "actief" blijven lijken na vertrek.

De eerste is het grotere probleem. Mitigaties:

- **Waarschuwingsmails** op 90 dagen en bv. 21 maanden, zodat de ambtenaar kan ingrijpen voordat hard-delete plaatsvindt.
- **Export-functie** voor de ambtenaar (conform AVG dataportabiliteit) zodat men zelf de gegevens kan bewaren.
- **Opt-in "houd mijn profiel actief"-knop** die `last_seen_at` bijwerkt zonder login te vereisen — zie Open vragen.

Als Rijks-SSO in de toekomst alsnog een lookup- of SCIM-feed biedt, kan die worden toegevoegd als **hard signaal** bovenop deze drempels: is de user bevestigd weg bij Rijks-SSO, dan direct naar de verwijderd-status zonder op 2 jaar te wachten.

## Concrete implementatie-schets

### Schema-uitbreidingen op het `Profile`-model

```python
class Profile(models.Model):
    subject_id = models.CharField(max_length=255, unique=True, db_index=True)
    # ... bestaande velden: naam, email, avatar_blob_ref, functie, ...

    last_seen_at = models.DateTimeField(null=True, db_index=True)
    marked_inactive_at = models.DateTimeField(null=True)
    # deletion_scheduled_at wordt pas gezet door de management command
    # als de user richting de 2-jaar-drempel gaat, voor notificatie-doeleinden.
    deletion_scheduled_at = models.DateTimeField(null=True)
```

### Bijwerken van `last_seen_at`

In de middleware / view die inkomende API-requests afhandelt:

```python
def handle_api_request(request, subject_id):
    # ... token validatie, consent check ...
    Profile.objects.filter(subject_id=subject_id).update(
        last_seen_at=timezone.now(),
        marked_inactive_at=None,  # idempotent herstel
        deletion_scheduled_at=None,
    )
    # ... rest van de request ...
```

Eén UPDATE per request, goedkoop. Idempotent herstel: als de user terugkomt na een inactieve periode, worden de vlaggen automatisch gereset.

### Management command (dagelijks via cron)

```
# profielservice/management/commands/reconcile_users.py

class Command(BaseCommand):
    def handle(self, *args, **opts):
        self.flag_inactive()            # last_seen_at < 90d → marked_inactive_at
        self.warn_approaching_delete()  # marked_inactive_at < (2j - 30d) → stuur waarschuwingsmail
        self.hard_delete_overdue()      # marked_inactive_at < 2j → cascade delete + webhook
```

Cron: `0 3 * * * python manage.py reconcile_users`. Met `--dry-run`-flag voor de eerste productieruns.

### Cascade bij hard-delete

```
delete profile ──┬── delete consents (of archive met reden 'user_deprovisioned')
                 ├── delete avatar blob (uit object store)
                 ├── write audit log entry (bewaard los van profiel)
                 └── POST webhook naar afnemer-apps met eerder actieve consent
                       { "event": "profile_deleted", "subject_id": "..." }
```

## Open vragen

1. **Drempels definitief**: 90 dagen en 2 jaar zijn voorstellen. Afstemming met CISO/FG nodig. Alternatieven: 60/365 (strenger), 180/1095 (soepeler).
2. **Bewaartermijn audit-logs**: vermoedelijk 7 jaar o.b.v. Archiefwet; verifiëren bij FG.
3. **Opt-in "houd mijn profiel actief"-knop**: moet een ambtenaar kunnen ingrijpen zonder in te loggen bij een afnemer-app? Handig bij langdurige detachering. Technisch simpel (nieuwe endpoint die `last_seen_at` bijwerkt), maar productbeslissing.
4. **Waarschuwingskanaal**: e-mail is de voor de hand liggende optie, maar de profielservice heeft niet per se een werkend e-mailadres (of: het adres kan stale zijn). Alternatief: bij volgende login bij een afnemer-app een banner tonen.
5. **Afnemer-app webhook-contract**: welke apps krijgen welke notificaties? Een deleted-event is eenduidig; een inactive-event is optioneel (apps kunnen ook gewoon niks doen totdat de user definitief weg is).
6. **Wanneer wél direct-delete?** Als Rijks-SSO alsnog een lookup biedt, of als een admin handmatig signaleert dat iemand uit dienst is — moeten die paden dezelfde cascade gebruiken?
