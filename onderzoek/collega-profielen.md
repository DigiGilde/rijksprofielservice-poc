# Ontwerp: Collega-profielen ophalen

*April 2026*

## Context

De Rijksprofielservice moet het mogelijk maken dat apps (Wies, AMT, ZAD) profielen van **collega's** kunnen tonen. De huidige flow (uit concept.md): een app vraagt het profiel op via subject-ID, de service checkt toestemming, en retourneert de gegevens.

De kernvraag is: hoe voorkom je dat afnemer-apps kopieën opslaan die out-of-date raken, terwijl je ook geen trage eindapplicaties krijgt?

## Het probleem

### Scenario: Wies toont een teamoverzicht

```
Wies wil een pagina tonen met 20 teamleden:
  → 20× API call naar profielservice: "geef profiel van subject-ID X"
  → Elke call: auth check + DB lookup + consent check + response
  → Totaal: 20 round-trips, elk ~50-200ms
  → Paginalaadtijd: 1-4 seconden (sequentieel) of ~200ms (parallel)
```

### Drie spanningen

1. **Versheid vs. performance** — real-time ophalen is altijd vers, maar langzamer. Caching is snel, maar kan stale zijn.
2. **Geen kopie vs. praktijk** — idealiter slaat een app geen profieldata op, maar in de praktijk zal elke app die profielen toont minstens een cache nodig hebben.
3. **Simpliciteit vs. schaalbaarheid** — een simpele REST API is makkelijk te begrijpen, maar schaalt minder goed bij bulk-operaties.

---

## Ontwerpopties

### Optie A: Directe API calls (geen caching bij de app)

```
Wies ──GET /profiles/{subject-id}──> Profielservice
     <── { naam, avatar_url, email } ──
```

**Werking**: App haalt bij elke pageload de profieldata real-time op.

**Voordelen**:
- Altijd up-to-date
- Geen stale data, geen sync-problemen
- Simpelst mogelijke model — één bron van waarheid
- App hoeft geen profieldata op te slaan (GDPR-voordeel)

**Nadelen**:
- Bij een teamoverzicht van 20 personen: 20 API calls per pageload
- Latentie voelbaar bij grotere lijsten
- Profielservice wordt bottleneck als veel apps veel calls doen

**Mitigaties**:
- Batch endpoint: `POST /profiles/batch` met lijst van subject-IDs → één call voor 20 profielen
- Profielservice zet zelf HTTP cache headers (`Cache-Control: max-age=300`, 5 min) zodat browsers/CDNs cachen zonder dat de app dit expliciet hoeft te doen
- Avatar via URL (niet inline): `avatar_url` verwijst naar de profielservice, browser cachet de afbeelding los

**Beoordeling**: dit is de aanbevolen basis. Eenvoudig, correct, en met een batch endpoint en HTTP caching performant genoeg voor de verwachte schaal.

---

### Optie B: HTTP caching (profielservice stuurt cache headers)

```
Wies ──GET /profiles/{id}──> [CDN/proxy cache] ──> Profielservice
     <── Cache-Control: max-age=300, ETag: "abc123"

(5 min later, zelfde request)
Wies ──GET /profiles/{id}, If-None-Match: "abc123"──> Profielservice
     <── 304 Not Modified (geen body, supersnel)
```

**Werking**: De profielservice stuurt HTTP cache headers mee. De app (of een tussenliggende proxy/CDN) cachet de response. Na de `max-age` wordt er een conditional request gestuurd.

**Dit is een uitbreiding op Optie A**, niet een alternatief. Het is het standaard HTTP-mechanisme en vereist geen extra logica bij de app.

**Key design beslissingen**:
- `max-age`: hoe lang is een profiel "vers genoeg"? 5 minuten is waarschijnlijk prima — profielen veranderen zelden
- `ETag`: hash van de profieldata, zodat conditional requests (304 Not Modified) supersnel zijn
- `Vary: Authorization` header: cache is per-app (Wies ziet mogelijk andere velden dan AMT)
- Profielfoto apart serveren op eigen URL met lange `max-age` (foto's veranderen nog minder vaak)

**Beoordeling**: dit zou standaard onderdeel moeten zijn van de API. Het is geen keuze maar een best practice.

---

### Optie C: Webhook/event-driven updates

```
Ambtenaar wijzigt profiel ──> Profielservice
                                ├── slaat op
                                └── stuurt event naar geabonneerde apps:
                                    ├── Wies: "profiel van subject-ID X is gewijzigd"
                                    ├── AMT: "profiel van subject-ID X is gewijzigd"
                                    └── (alleen apps met toestemming)
```

**Werking**: Apps abonneren zich op profiel-wijzigingen. Bij een update pusht de profielservice een event (webhook of message queue).

**Voordelen**:
- Apps weten onmiddellijk wanneer een profiel verandert
- Combineert goed met caching: cache lang, invalideer bij event
- Geen polling nodig

**Nadelen**:
- Complexer protocol — apps moeten een webhook endpoint hebben
- Delivery-garanties zijn lastig (wat als de webhook faalt?)
- Apps moeten toch een lokale cache/kopie bijhouden om het event te verwerken

**Beoordeling**: overkill voor de eerste versie. Voeg dit toe als er apps zijn die real-time updates nodig hebben. Niet nodig voor de typische use case (teamoverzicht, profielkaartje).

---

### Optie D: App slaat kopie op (lokale cache met TTL)

```
Wies ──GET /profiles/{id}──> Profielservice
     <── profiel + Last-Modified header

Wies slaat op in eigen DB: { subject_id, naam, avatar_url, ..., cached_at }

Bij volgende pageload:
  → Is cached_at < 1 uur geleden? → toon uit cache
  → Anders → haal opnieuw op
```

**Werking**: De app slaat profieldata op in zijn eigen database met een TTL.

**Voordelen**:
- Snelste mogelijke responstijd voor de eindgebruiker
- Werkt ook als de profielservice tijdelijk onbereikbaar is

**Nadelen**:
- Nu heeft elke app een **kopie** van profieldata — precies wat we wilden voorkomen
- Stale data: als iemand zijn naam wijzigt, duurt het tot TTL verloopt voordat apps dit zien
- GDPR-complicatie: als ambtenaar toestemming intrekt, moet de app de kopie verwijderen
- Sync-logica in elke app: elke afnemer moet dit zelf bouwen

**Beoordeling**: vermijd dit als het kan. Als apps dit toch doen, dan moet de profielservice API hier rekening mee houden — bijv. door een `consent-revoked` webhook te sturen zodat apps hun kopie kunnen verwijderen.

---

## Aanbeveling: gelaagd model

```
Laag 1 (basis):    REST API met batch endpoint
                   GET  /profiles/{subject-id}
                   POST /profiles/batch  (lijst van subject-IDs)

Laag 2 (standaard): HTTP caching
                   Cache-Control + ETag headers
                   Avatar op aparte URL met lange cache

Laag 3 (later):    Webhooks voor profiel-wijzigingen (optioneel)
                   Alleen voor apps die real-time updates nodig hebben

Laag 4 (vermijd):  Lokale kopieën in afnemer-apps
                   Alleen als het echt niet anders kan, met duidelijke regels
```

### Concrete API flow voor een teamoverzicht

```
1. Wies kent de subject-IDs van 20 teamleden (uit eigen data)

2. Wies doet één call:
   POST /api/v1/profiles/batch
   Authorization: Bearer <client-credentials-token>
   Content-Type: application/json

   { "subject_ids": ["abc-123", "def-456", ...] }

3. Profielservice retourneert:
   HTTP 200
   Cache-Control: max-age=300
   ETag: "batch-hash-xyz"

   {
     "profiles": {
       "abc-123": { "naam": "Jan Jansen", "avatar_url": "https://profiel.rijks.nl/avatars/abc-123", "email": "j.jansen@minbzk.nl" },
       "def-456": { "naam": "Piet Pietersen", "avatar_url": "...", "email": null },
       "ghi-789": null
     }
   }

4. Avatar-URL verwijst naar de profielservice zelf:
   GET https://profiel.rijks.nl/avatars/abc-123
   → Cache-Control: max-age=86400 (24 uur)
   → De browser cachet dit, geen extra logica nodig in Wies
```

### Waarom dit werkt

- **Versheid**: max 5 minuten oud, en profielen veranderen zelden
- **Performance**: één HTTP call voor 20 profielen, ~50-100ms
- **Geen kopie**: Wies slaat niks op, haalt elke keer op (met HTTP cache)
- **Avatar**: apart gecachet door de browser (24 uur), kleine afbeelding (~10-50KB)
- **Consent**: als ambtenaar B geen toestemming geeft aan Wies → `null` in de response, Wies toont een fallback
- **GDPR**: geen profieldata in de database van Wies, alleen in de browser-cache (korte TTL)

---

## Authenticatie bij het batch endpoint

### Client-credentials, niet per-gebruiker tokens

Het authenticatiemodel is **client-credentials grant**. De *app* authenticeert zich bij de profielservice, niet de individuele *gebruiker*.

```
Wies (de app) heeft één set credentials bij Keycloak:
  - client_id: "wies"
  - client_secret: "geheim"

Wies vraagt daarmee een access token aan bij Keycloak.
Dat token zegt: "dit is Wies, een geregistreerde afnemer."

Met dat ene token kan Wies profielen ophalen van alle ambtenaren
die toestemming hebben gegeven aan Wies.
```

Er is **één token per app**, niet per gebruiker.

### Waarom dit werkt

Het kernmodel is: **toestemming is gekoppeld aan de app, niet aan de opvrager.**

Als ambtenaar B toestemming heeft gegeven aan Wies, dan mag *elke gebruiker van Wies* het profiel van B zien — dat is het hele punt van collega-profielen. Het maakt niet uit of ambtenaar A of ambtenaar C het profiel opvraagt. De vraag is alleen: "heeft B gezegd dat Wies zijn profiel mag tonen?"

Daarom is client-credentials (app-niveau) het juiste grant type, en niet authorization-code (gebruiker-niveau).

### Vergelijking van de twee modellen

```
Model 1: Client-credentials (het huidige concept) ✅
──────────────────────────────────────────────────
Wies backend heeft één token → kan alle profielen ophalen waarvoor toestemming is
Simpel, efficient, past bij batch-operaties

  Wies backend ──[app-token]──> Profielservice
                                  "Wies vraagt profiel van B"
                                  → Heeft B toestemming gegeven aan Wies? Ja → retourneer
                                  → Heeft C toestemming gegeven aan Wies? Nee → null


Model 2: Per-gebruiker tokens (niet nodig) ❌
──────────────────────────────────────────────────
Elke ambtenaar zou een token moeten hebben bij de profielservice
Wies zou 20 tokens moeten beheren voor een teamoverzicht
Niet werkbaar voor batch, en conceptueel verkeerd:
  de toestemming is aan de *app* gegeven, niet aan de collega die opvraagt
```

### Per-gebruiker authenticatie: alleen voor profielbeheer

Er is één situatie waar per-gebruiker authenticatie nodig is: **het beheren van je eigen profiel.** Dit gaat via de normale SSO authorization-code flow:

```
Ambtenaar A ──[SSO login]──> Profielservice UI
                               → A is geauthenticeerd via Rijks-SSO
                               → A kan zijn eigen profiel bewerken
                               → A kan toestemmingen per app beheren
```

### Twee auth-flows

| Flow | Grant type | Wie authenticeert | Waarvoor |
|---|---|---|---|
| App haalt profielen op | Client-credentials | De app (Wies) | Collega-profielen lezen |
| Ambtenaar beheert profiel | Authorization-code (SSO) | De ambtenaar | Eigen profiel bewerken, toestemmingen beheren |

### Hoe het batch endpoint de toestemmingscheck doet

```python
# Pseudo-code profielservice
def batch_profiles(request):
    app = authenticate_client(request)  # → "wies"
    subject_ids = request.data["subject_ids"]

    result = {}
    for sid in subject_ids:
        if heeft_toestemming(ambtenaar=sid, app=app.client_id):
            result[sid] = get_profiel(sid)
        else:
            result[sid] = None

    return result
```

In de praktijk is dit één SQL query:

```sql
SELECT subject_id, naam, email, avatar_url
FROM profielen p
JOIN toestemmingen t ON p.subject_id = t.subject_id
WHERE t.app_id = 'wies'
  AND p.subject_id IN ('abc-123', 'def-456', ...)
```

Eén query, ongeacht het aantal profielen.

---

## Integratie met server-side rendering (Django + HTMX)

### Het probleem

Bij server-side rendering moet de server de volledige HTML genereren voordat de pagina naar de browser gaat. Als Wies bij het renderen van een teamoverzicht eerst 20 profielen moet ophalen bij de profielservice, blokkeert dat de hele pageload:

```
Gebruiker klikt ──> Wies server ──> wacht op 20 profielen (200ms) ──> rendert HTML ──> browser
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    dit blokkeert de hele pagina
```

### Oplossing: lazy loading met HTMX

HTMX heeft hier een perfect patroon voor: **`hx-get` met `hx-trigger="load"`**. De pagina rendert direct met placeholders, en HTMX verrijkt de profielen asynchroon:

```
Stap 1: Wies rendert de pagina direct (geen wachten op profielservice)
        → Elke profielplaats is een placeholder met hx-get

Stap 2: Browser laadt de pagina, HTMX vuurt automatisch requests af
        → Wies backend haalt profielen op bij de profielservice
        → Stuurt HTML-fragmenten terug die de placeholders vervangen
```

### Concrete implementatie

**Wies template (teamoverzicht):**

```html
<!-- Pagina rendert direct, geen profielservice-calls nodig -->
<div class="team-overzicht">
  {% for subject_id in team_subject_ids %}
    <div hx-get="{% url 'profiel-card' subject_id %}"
         hx-trigger="load"
         hx-swap="outerHTML">
      <!-- Placeholder: toont direct, wordt vervangen door HTMX -->
      <div class="profiel-card placeholder">
        <div class="avatar-placeholder">{{ subject_id|initialen }}</div>
        <span class="naam-placeholder">Laden...</span>
      </div>
    </div>
  {% endfor %}
</div>
```

**Wies view (profiel-card endpoint):**

```python
# views.py
def profiel_card(request, subject_id):
    """Haalt profiel op bij de profielservice en retourneert een HTML-fragment."""
    profiel = profielservice_client.get_profiel(subject_id)

    if profiel is None:
        # Geen toestemming — toon fallback
        return render(request, "partials/profiel_card_fallback.html",
                      {"subject_id": subject_id})

    return render(request, "partials/profiel_card.html",
                  {"profiel": profiel})
```

**Profiel-card fragment:**

```html
<!-- partials/profiel_card.html -->
<div class="profiel-card">
  <img src="{{ profiel.avatar_url }}" alt="" class="avatar" loading="lazy">
  <span class="naam">{{ profiel.naam }}</span>
  <span class="functie">{{ profiel.functie }}</span>
</div>
```

### Optimalisatie: batch via HTMX

Individuele requests per profiel-card zijn eenvoudig, maar bij 20 teamleden zijn dat 20 requests naar de eigen Wies backend. Dit kan slimmer:

**Optie 1: Eén batch-call, meerdere fragmenten**

```html
<!-- Eén HTMX request voor het hele team -->
<div hx-get="{% url 'team-profielen' team_id %}"
     hx-trigger="load"
     hx-swap="innerHTML">
  <!-- Placeholders -->
  {% for sid in team_subject_ids %}
    <div id="profiel-{{ sid }}" class="profiel-card placeholder">...</div>
  {% endfor %}
</div>
```

```python
def team_profielen(request, team_id):
    """Batch-call naar profielservice, retourneert alle profiel-cards in één response."""
    subject_ids = Team.objects.get(id=team_id).leden_subject_ids()
    profielen = profielservice_client.get_profielen_batch(subject_ids)

    return render(request, "partials/team_profielen.html",
                  {"profielen": profielen})
```

**Optie 2: Individuele cards, maar Wies backend batcht naar profielservice**

De Wies backend kan een interne cache houden (in-memory, 5 min TTL) en bij de eerste profiel-card-request een batch-call doen naar de profielservice voor alle team-subject-IDs. De overige 19 requests worden dan uit de cache beantwoord.

### Hoe de flow eruitziet voor de gebruiker

```
t=0ms     Browser ontvangt HTML van Wies
          → Pagina is direct zichtbaar met placeholders (initialen-avatars, "Laden...")

t=50ms    HTMX vuurt requests af voor profiel-cards
          → Wies backend doet batch-call naar profielservice

t=150ms   Profielservice retourneert 20 profielen
          → Wies backend rendert HTML-fragmenten

t=200ms   HTMX swapt de placeholders voor echte profiel-cards
          → Naam, foto, functie verschijnen

t=200ms+  Browser laadt avatar-afbeeldingen (loading="lazy")
          → Foto's verschijnen als ze in de viewport komen
```

**Totaal**: de pagina is in ~0ms zichtbaar (placeholders), volledig verrijkt in ~200ms. Geen spinner, geen wachten.

### Caching op de app-backend

De app-backend kan Django's cache framework gebruiken als optionele versnelling:

```python
from django.core.cache import cache

def get_profiel_cached(subject_id):
    key = f"profiel:{subject_id}"
    profiel = cache.get(key)
    if profiel is None:
        profiel = profielservice_client.get_profiel(subject_id)
        cache.set(key, profiel, timeout=300)  # 5 min
    return profiel
```

Dit is een **korte in-memory cache**, geen kopie in de database. Het verschil is belangrijk:
- In-memory cache (Redis/memcached, 5 min TTL) = acceptabel, vergelijkbaar met HTTP browser cache
- Kopie in de eigen database = problematisch (sync, GDPR, stale data)

---

## Open vragen

1. **Wat is de fallback bij geen toestemming?** Opties:
   - Helemaal niks tonen (strikt)
   - Alleen voornaam (minimale set die altijd beschikbaar is)
   - "Profiel niet beschikbaar" placeholder
