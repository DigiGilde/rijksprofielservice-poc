# Integratie-patronen voor afnemer-apps

Hoe integreren afnemer-apps met de Rijksprofielservice? Dit document beschrijft concrete patronen, met Django + HTMX als voorbeeld.

## Server-side rendering en het blokkeringsprobleem

Bij server-side rendering moet de server de volledige HTML genereren voordat de pagina naar de browser gaat. Als een app bij het renderen van een teamoverzicht eerst 20 profielen moet ophalen, blokkeert dat de hele pageload:

```
Gebruiker klikt ──> App server ──> wacht op 20 profielen (200ms) ──> rendert HTML ──> browser
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                   dit blokkeert de hele pagina
```

## Oplossing: lazy loading met HTMX

HTMX biedt een patroon met `hx-get` en `hx-trigger="load"`. De pagina rendert direct met placeholders, en HTMX verrijkt de profielen asynchroon:

**Template (teamoverzicht):**

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

**View (profiel-card endpoint):**

```python
def profiel_card(request, subject_id):
    """Haalt profiel op bij de profielservice en retourneert een HTML-fragment."""
    profiel = profielservice_client.get_profiel(subject_id)

    if profiel is None:
        return render(request, "partials/profiel_card_fallback.html",
                      {"subject_id": subject_id})

    return render(request, "partials/profiel_card.html",
                  {"profiel": profiel})
```

**Profiel-card fragment:**

```html
<div class="profiel-card">
  <img src="{{ profiel.avatar_url }}" alt="" class="avatar" loading="lazy">
  <span class="naam">{{ profiel.naam }}</span>
  <span class="functie">{{ profiel.functie }}</span>
</div>
```

## Optimalisatie: batch in plaats van N requests

Individuele requests per profiel-card zijn eenvoudig maar bij 20 teamleden zijn dat 20 requests naar de eigen backend. Twee betere opties:

### Optie 1: Eén batch-call, alle fragmenten in één response

```html
<div hx-get="{% url 'team-profielen' team_id %}"
     hx-trigger="load"
     hx-swap="innerHTML">
  {% for sid in team_subject_ids %}
    <div id="profiel-{{ sid }}" class="profiel-card placeholder">...</div>
  {% endfor %}
</div>
```

```python
def team_profielen(request, team_id):
    """Batch-call naar profielservice, retourneert alle profiel-cards."""
    subject_ids = Team.objects.get(id=team_id).leden_subject_ids()
    profielen = profielservice_client.get_profielen_batch(subject_ids)
    return render(request, "partials/team_profielen.html",
                  {"profielen": profielen})
```

### Optie 2: Individuele cards, maar backend batcht intern

De app-backend doet bij de eerste profiel-card-request een batch-call naar de profielservice voor alle team-subject-IDs en houdt het resultaat in een korte in-memory cache (5 min TTL). De overige 19 requests worden dan uit de cache beantwoord.

## Verwachte gebruikerservaring

```
t=0ms     Browser ontvangt HTML
          → Pagina is direct zichtbaar met placeholders (initialen, "Laden...")

t=50ms    HTMX vuurt requests af voor profiel-cards
          → App-backend doet batch-call naar profielservice

t=150ms   Profielservice retourneert 20 profielen
          → App-backend rendert HTML-fragmenten

t=200ms   HTMX swapt placeholders voor echte profiel-cards
          → Naam, foto, functie verschijnen

t=200ms+  Browser laadt avatar-afbeeldingen (loading="lazy")
          → Foto's verschijnen als ze in de viewport komen
```

De pagina is in ~0ms zichtbaar (placeholders), volledig verrijkt in ~200ms.

## Caching op de app-backend

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

Dit is een **korte in-memory cache** (Redis/memcached, 5 min TTL), geen kopie in de database. Het verschil is belangrijk:

- In-memory cache (5 min TTL) = acceptabel, vergelijkbaar met HTTP browser-cache
- Kopie in de eigen database = problematisch (sync, GDPR, stale data)

## Toestemmingscheck in de profielservice

Bij een batch-request doet de profielservice de toestemmingscheck in één query:

```sql
SELECT subject_id, naam, email, avatar_url
FROM profielen p
JOIN toestemmingen t ON p.subject_id = t.subject_id
WHERE t.app_id = 'wies'
  AND p.subject_id IN ('abc-123', 'def-456', ...)
```

Profielen zonder toestemming komen als `null` terug in de response. De app toont dan een fallback.
