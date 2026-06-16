# Ontwerp: Technische stack-keuze

*April 2026*

## Context

Het conceptueel ontwerp (`docs/main.md`) noemt Django (Python) als technische
stack. Bij verdere uitwerking kwamen twee zorgen op:

- **Schaalbaarheid**: het loadmodel is `apps × users` — elke aangesloten app
  vraagt voor elke ingelogde ambtenaar profielen op.
- **Geen app-side caching bij afnemers**: profieldata moet altijd bij de bron
  worden opgevraagd. Afnemer-apps mogen geen lokale kopie of in-memory cache
  houden (zie [collega-profielen.md](./collega-profielen.md), Laag 4).

De vraag: past Django wel bij die eisen, of is er een betere stack?

## Het loadmodel concreet

Snelle orde-van-grootte-schatting:

- ~150k rijksambtenaren
- ~10 aangesloten apps op termijn
- ~20 page-views/dag per ambtenaar per app met team-context
- 1 batch-call per team-pagina, ~20–50 profielen per batch

Dat geeft:

- ~30M batch-requests/dag → **~350 RPS gemiddeld**
- Werkdag-piek (ochtend) → **1000–2000 RPS**
- Per piek-batch ~20–50 profielen → ~50k–100k profiel-resolves/s

Niet "Google-schaal", wél "dit is geen CRUD-app meer, dit is core
platform-infra op de request-path". De avatar-traffic (binary blobs, 10–50 KB
per foto) komt daar nog bovenop — zie
[avatar-serving.md](./avatar-serving.md).

## Wat HTTP-caching + CDN doet met dat probleem

Als de profielservice `Cache-Control` + `ETag` + `Vary: Authorization`
meegeeft, en er een CDN of proxy vóór `/profiles/*` staat, dan:

- Profielen veranderen zelden. `max-age=300` + conditional GET levert dat
  het overgrote deel van de requests op `304 Not Modified` eindigt, vaak nog
  vóór de app-server.
- `apps × users` slaat in ruwe vorm op de CDN, niet op Django. Django ziet
  vooral de misses (eerste call na wijziging, cache-eviction) en writes.
- Avatars op eigen URL met lange cache → bulk van het byte-volume wordt op
  CDN/browser afgehandeld.

Hiermee daalt de eerder berekende 1000–2000 RPS-piek aan de kant van de
applicatie ordes van grootte. Django komt daarmee weer ruim binnen bereik —
mits de caching-strategie vanaf dag 1 serieus is.

## Implicaties van "geen app-side caching"

Een strikte interpretatie ("élke request tot aan de DB") maakt elke stack
pijnlijk: je verbiedt dan de enige laag die het loadmodel kan dempen. Een
werkbare interpretatie is:

- **Afnemer-apps** slaan niks op — geen DB-kopie, geen in-memory cache,
  geen Django-cache-framework — zodat "data bij de bron" gewaarborgd blijft.
- **Profielservice + CDN/proxy** mogen wél cachen, want dat is dezelfde
  bron — de afnemer ziet daarbij nog steeds een verse 200/304 response,
  geen gestolde lokale kopie.

Met deze interpretatie blijft het principe overeind én is de service
schaalbaar.

## Opties — gegeven "één codebase"

Een gesplitste deploy (bijv. Django voor UI/admin + losse Go/Rust-API voor
de hot-path) is bewust **niet** in scope: één codebase heeft sterke voorkeur
om operationele complexiteit te beperken. Dat laat vier serieuze
single-codebase-kandidaten:

### Optie A — Django (monoliet) — aanbevolen

- Past bij bestaand ontwerp, bestaand HTMX-patroon
  ([integratie-patronen.md](../docs/integratie-patronen.md)), Wies-team-stack.
- Django admin gratis voor app-goedkeuring en audit-views
  (zie [keycloak-integratie.md](../docs/keycloak-integratie.md)).
- Management commands voor `reconcile_users` zoals al uitgewerkt in
  [deprovisioning.md](./deprovisioning.md).
- Met ETag/304 + CDN haalt de API-kant ruim de schaal — Python per-request
  overhead komt nauwelijks aan bod.
- **Risico**: als HTTP-caching niet goed wordt geïmplementeerd, zit je met
  een Python-heavy hot path. Dit is een implementatiekwestie, geen
  stack-tekort.

### Optie B — FastAPI (+ Alembic + eigen admin + Jinja/HTMX)

- Lichter framework, type-hints first, OpenAPI-schema automatisch →
  SDK-generatie voor afnemers gratis.
- Async I/O helpt bij uitgaande webhooks; niet bij `GET /profiles/batch`
  (puur DB read).
- **Kostenpost**: alles wat Django gratis levert (admin, auth, templating,
  sessions, permissions, management commands) bouw je zelf. Voor een
  service met consent-UI én admin-UI is dat fors eigen werk.
- Python per-request cost is vergelijkbaar met Django; geen significante
  schaal-winst.
- Logisch als er nauwelijks UI is. Hier wel — dus minder passend.

### Optie C — Quarkus (Java 21) monoliet

- Veel hogere per-request throughput dan Python, stateless JWT eersteklas.
- Hibernate Envers levert audit-log kant-en-klaar.
- Native compilatie (GraalVM) voor harde performance.
- **Verloren**: geen Django-admin-equivalent (Panache + handgemaakte UI komt
  in de buurt). Qute + htmx is werkbaar maar minder natuurlijk dan Django.
- MOZA gebruikt Quarkus, maar alignment met MOZA telt voor dit project niet
  zwaar — het strategische argument is daarmee weg.
- Met CDN ervoor vervalt het performance-voordeel grotendeels. Je geeft
  Django-productiviteit op zonder duidelijke winst.

### Optie D — Go monoliet (Echo/Chi + sqlc + templ)

- Laagste latency, kleinste footprint, single binary.
- UI en admin zelf bouwen. Consent-flow is niet triviaal in Go's
  template-ecosysteem.
- Kleiner rijks-ecosysteem voor Go dan voor Python/Java.
- Met CDN ervoor weegt het latency-voordeel minder, het bouwwerk voor
  UI/admin meer.

## Vergelijking

| Aspect | Django | FastAPI | Quarkus | Go |
|---|---|---|---|---|
| Past bij bestaand ontwerp | ✅ | ⚠️ deels | ❌ | ❌ |
| Admin-UI gratis | ✅ | ❌ | ❌ | ❌ |
| HTMX/templating natuurlijk | ✅ | ⚠️ Jinja | ⚠️ Qute | ⚠️ templ |
| Per-request throughput | ⚠️ Python | ⚠️ Python | ✅ | ✅✅ |
| Bouwlast UI/admin | Laag | Hoog | Hoog | Hoog |
| Rijks-ecosysteem | ✅ | ⚠️ | ✅ (MOZA) | ⚠️ |
| Schaal met CDN ervoor | ✅ | ✅ | ✅ | ✅ |
| Schaal zonder CDN | ⚠️ | ⚠️ | ✅ | ✅✅ |

## Aanbeveling

**Blijf bij Django, en maak HTTP-caching + CDN een first-class
ontwerpbeslissing.**

De schaal-zorg is reëel maar wordt geadresseerd door de cache-laag, niet
door de programmeertaal. Geen van de alternatieven biedt voldoende winst om
op te wegen tegen wat Django oplevert (admin, HTMX-patroon, bestaande
ontwerpdocumenten, team-fit).

### Concrete randvoorwaarden om dit waar te maken

1. **HTTP-cache headers vanaf dag 1 goed**: `Cache-Control`, `ETag`,
   `Vary: Authorization`, 304-pad via `If-None-Match`. Geen ad-hoc
   caching-middleware achteraf.
2. **CDN/proxy vóór `/profiles/*` en `/avatars/*`** als deploy-eis, niet
   als optioneel. Avatars met lange TTL, profielen met korte TTL. Zie ook
   [avatar-serving.md](./avatar-serving.md).
3. **Index-strategie op consent**: composite index op `(app_id, subject_id)`,
   `IN`-lookups in één query, read-replicas indien nodig.
4. **Loadtest vóór productie** tegen het batch-endpoint met realistische
   `subject_ids × app_id`-mix. Hoge ETag-hit-ratio (>80%) betekent dat
   Django ruim voldoende is.
5. **Triggers voor stack-heroverweging documenteren**: bv. app-server
   CPU > 70% bij 5× verwachte load, of P99 latency > target. Voorkomt
   vaagheid later.

## Open vragen

1. **Beheer in productie**: wie gaat de service uiteindelijk operationeel
   draaien — SSC-ICT, CIO-Rijk, het Wies-team? Dat is de overgebleven
   strategische as. Een Java-team bij SSC-ICT zou alsnog Quarkus rechtvaardigen.
2. **CDN/proxy-product**: welk product is beschikbaar in de
   rijks-hostingcontext? Rijks-CDN, Cloudflare, eigen nginx-tier? Dit moet
   vroeg uitgevraagd worden — de keuze raakt deploy-architectuur, niet code.
3. **Concrete loadtest-getallen**: hoeveel apps op termijn realistisch,
   gemiddelde batch-grootte, verwachte ETag-hit-ratio. Anders blijven de
   schaal-getallen aannames.
4. **Vervolgupdate van andere documenten** (vooruitwijzing):
   - `docs/main.md` — kernbeslissingen-tabel onderbouwen met deze rationale.
   - `onderzoek/collega-profielen.md` — Laag 4 (lokale kopieën) expliciet
     verbieden in aansluitvoorwaarden; Laag 2 (HTTP caching) promoveren
     van best practice naar core-eis.
   - `docs/integratie-patronen.md` — caching-guidance naar afnemers strakker
     formuleren ("geen lokale kopieën, geen in-memory cache van profieldata").

## Bronnen

- [docs/main.md](../docs/main.md) — huidige kernbeslissing voor Django
- [onderzoek/collega-profielen.md](./collega-profielen.md) — gelaagd
  cache-model, batch-endpoint
- [onderzoek/avatar-serving.md](./avatar-serving.md) — avatar-pad buiten
  Django
- [docs/keycloak-integratie.md](../docs/keycloak-integratie.md) — stateless
  JWT-validatie, client-credentials
- [docs/integratie-patronen.md](../docs/integratie-patronen.md) — Django
  + HTMX integratie-patroon voor afnemer-apps
- [background/moza_profielservice.md](../background/moza_profielservice.md)
  — MOZA stack (Java 21 + Quarkus) als referentie
