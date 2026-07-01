# Afnemer-app integreren met de Rijksprofielservice

Stap-voor-stap-handleiding met code-voorbeelden tegen de lokale PoC-setup. Vervang `mijn-app` door je eigen `client_id`.

## Wat je krijgt

Twee endpoints, twee tokens:

- **`/api/v1/profiles/me`** met een **user-bound token** (Authorization Code + PKCE) — voor het profiel van de ingelogde gebruiker, plus het `subject_id` dat je opslaat om diezelfde gebruiker later via batch te kunnen ophalen.
- **`/api/v1/profiles/batch`** met een **client-credentials token** (M2M) — voor profielen van collega's, op basis van eerder opgeslagen `subject_id`s.

Zie [aansluitvoorwaarden](/docs/aansluitvoorwaarden/) voor de spelregels rond opslag, toestemming en incidentmelding.

## Architectuur op één scherm

```
Browser
   │
   ▼
Mijn-app (localhost:8080)             Rijksprofielservice (localhost:8000)
   │                                  │
   │  1. user wil eigen profiel       │
   ├─────────────────────────────────▶│  GET /o/authorize/?response_type=code
   │                                  │         &client_id=mijn-app
   │                                  │         &code_challenge=...&state=...
   │                                  │  → toont consent-scherm
   │  2. user kiest velden            │
   │◀─────────────────────────────────┤  302 → /callback?code=...&state=...
   │                                  │
   │  3. code → access_token          │
   ├─────────────────────────────────▶│  POST /o/token/ (authorization_code)
   │  ◀──────────────────────────────│  { access_token, ... }
   │                                  │
   │  4. profiel van ingelogde user   │
   ├─────────────────────────────────▶│  GET /api/v1/profiles/me  (Bearer)
   │  ◀──────────────────────────────│  { naam, email, ..., subject_id }
   │                                  │
   ────── later, voor collega's ──────
   │                                  │
   │  5. M2M token                    │
   ├─────────────────────────────────▶│  POST /o/token/ (client_credentials,
   │                                  │       client_id=mijn-app-m2m)
   │  ◀──────────────────────────────│  { access_token, ... }
   │                                  │
   │  6. batch profielen              │
   ├─────────────────────────────────▶│  POST /api/v1/profiles/batch (Bearer)
   │  ◀──────────────────────────────│  { "profiles": { "<sid>": {...}|null } }
   │                                  │
```

## Lokale poorten

| Service | Host-poort | Doel |
|---|---|---|
| Afnemer-app (Django) | `8080` | Voorbeeld-poort voor de PoC. |
| Rijksprofielservice (Django) | `8000` | Bewust uit de weg van de afnemer. |
| Postgres (rijksprofielservice) | `5433` | Naast standaard 5432 (afnemer). |

## Stap 1 — App registreren via de Applicaties-pagina

Ga in de profielservice naar [`/applicaties/nieuw/`](http://localhost:8000/applicaties/nieuw/) en vul het formulier in:

- **Naam**: `Mijn-app`
- **Client id**: `mijn-app` (zonder `-m2m`-suffix; die wordt automatisch aangemaakt)
- **Beschrijving**: bv. `Voorbeeld-applicatie voor de PoC.`
- **Redirect uri**: `http://localhost:8080/profielservice/callback/`
- **Requested fields**: vink de profielvelden aan die je app nodig heeft (bv. naam, email, functie)
- **Is approved**: ✓

Eén submit maakt drie records aan:

1. Een OAuth-client met `client_id=mijn-app`, grant type `authorization-code`, met je `redirect_uri`. Voor de user-flow.
2. Een OAuth-client met `client_id=mijn-app-m2m`, grant type `client-credentials`, zonder `redirect_uri`. Voor de batch-API.
3. Een business-`Application`-record met `requested_fields` en `is_approved`. De profielservice gebruikt dit om consent-schermen te tonen en API-antwoorden te filteren.

Beide `client_secret`s worden automatisch gegenereerd en zijn zichtbaar op de edit-pagina van de net aangemaakte app. Bewaar ze veilig — ze worden alleen daar getoond, niet opnieuw afgeleid.

De naam-conventie is bewust: client-credentials gebruikt altijd `<client_id>-m2m`. De profielservice gebruikt die suffix om de M2M-token aan de business-app te koppelen.

## Stap 2 — Authorization Code flow met PKCE

PKCE is verplicht. Genereer per request een `code_verifier` en stuur de bijbehorende `code_challenge` mee in de authorize-redirect.

```python
# mijn_app/views.py — voorbeeld
import base64
import hashlib
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect

AUTHORIZE_URL = "http://localhost:8000/o/authorize/"
CALLBACK_URL = "http://localhost:8080/profielservice/callback/"
CLIENT_ID = "mijn-app"


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def vraag_profiel_toestemming(request):
    state = secrets.token_urlsafe(16)
    verifier, challenge = _pkce_pair()
    request.session["profielservice_state"] = state
    request.session["profielservice_verifier"] = verifier
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": CALLBACK_URL,
        "scope": "read_profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")
```

De profielservice toont een consent-scherm met checkboxes per veld uit `requested_fields`. De gebruiker kan velden uitvinken — alleen aangevinkte velden komen later terug in API-responses. Alles uitvinken telt als stille deny (geen `code` in de callback).

### Callback verwerken en token ophalen

```python
# mijn_app/views.py — voorbeeld
import httpx
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect

TOKEN_URL = "http://host.docker.internal:8000/o/token/"  # back-channel
CLIENT_SECRET = settings.MIJN_APP_CLIENT_SECRET


def profielservice_callback(request):
    state = request.GET.get("state", "")
    expected = request.session.pop("profielservice_state", None)
    verifier = request.session.pop("profielservice_verifier", None)
    if not expected or expected != state:
        return HttpResponseBadRequest("State-mismatch")

    code = request.GET.get("code")
    if not code:
        return render(request, "mijn_app/toestemming_geweigerd.html")

    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CALLBACK_URL,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code_verifier": verifier,
        },
        timeout=5,
    )
    response.raise_for_status()
    access_token = response.json()["access_token"]
    # Bewaar het token in de sessie, of haal er meteen /me mee op (volgende stap).
    request.session["profielservice_token"] = access_token
    return redirect("mijn_app:dashboard")
```

## Stap 3 — `/api/v1/profiles/me` aanroepen

Het user-bound token geeft toegang tot het eigen profiel van de ingelogde gebruiker. De response bevat naast de profielvelden ook `subject_id` als metadata — sla die op aan je eigen User-model, zodat je dezelfde persoon later via de batch-API kunt opzoeken (ook in een ander request waar de user niet aanwezig is).

```python
def fetch_eigen_profiel(token: str) -> dict:
    response = httpx.get(
        "http://host.docker.internal:8000/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()
```

Voorbeeld-response:

```json
{
  "naam": "Diana Bos",
  "email": "diana.bos@rijksoverheid.nl",
  "functie": "Beleidsmedewerker",
  "subject_id": "demo-sub-diana"
}
```

Met curl:

```sh
curl -H "Authorization: Bearer <access_token>" \
     http://localhost:8000/api/v1/profiles/me
```

## Stap 4 — M2M-token en batch-API

Voor profielen van collega's gebruik je de M2M-client. Vraag een client-credentials token aan, cache het tot vlak voor expiry, en stuur er batch-requests mee.

```python
# mijn_app/profielservice_client.py — voorbeeld
import time
import httpx
from django.conf import settings

TOKEN_URL = "http://host.docker.internal:8000/o/token/"
BATCH_URL = "http://host.docker.internal:8000/api/v1/profiles/batch"
M2M_CLIENT_ID = "mijn-app-m2m"

_token_cache = {"token": None, "expires_at": 0.0}


def get_m2m_token() -> str:
    if _token_cache["expires_at"] > time.time() + 30:
        return _token_cache["token"]
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": M2M_CLIENT_ID,
            "client_secret": settings.MIJN_APP_M2M_CLIENT_SECRET,
        },
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"]
    return data["access_token"]


def haal_profielen(subject_ids: list[str]) -> dict:
    """Haal meerdere profielen in één call.

    Response shape: {"<sid>": {...velden...} | None}.
    `None` betekent: onbekend subject OF geen actieve consent voor deze app.
    """
    response = httpx.post(
        BATCH_URL,
        json={"subject_ids": subject_ids},
        headers={"Authorization": f"Bearer {get_m2m_token()}"},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()["profiles"]
```

Voorbeeld-response:

```json
{
  "profiles": {
    "demo-sub-kevin": {
      "naam": "Kevin Popov",
      "email": "kevin.popov@rijksoverheid.nl",
      "functie": "Adviseur",
      "avatar_url": "http://localhost:8000/avatars/6.jpg"
    },
    "demo-sub-onbekend": null
  }
}
```

Met curl (met seed-secret uit `seed_apps.json`):

```sh
TOKEN=$(curl -s -X POST http://localhost:8000/o/token/ \
  -d grant_type=client_credentials \
  -d client_id=wies-m2m \
  -d client_secret=local-dev-secret-wies | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -X POST http://localhost:8000/api/v1/profiles/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject_ids":["demo-sub-kevin","demo-sub-diana"]}'
```

Velden in de response zijn de doorsnijding van `Application.requested_fields` ∩ `Consent.granted_fields`. Wijzigt de gebruiker zijn consent, dan past de response zich direct aan.

## Foutgevallen

| Status | Betekenis | Wat te doen |
|---|---|---|
| 400 | Onbekende `client_id`, ongeldige `redirect_uri`, ontbrekende/onjuiste PKCE-parameters bij `/o/authorize/`. | Check de app-registratie en je PKCE-paar. |
| 400 | `subject_ids` is geen lijst bij batch-call. | Stuur een JSON-array. |
| 401 | Token ontbreekt, ongeldig, of verlopen. | Vernieuw het token. |
| 403 | App is niet goedgekeurd (`is_approved=false`), verkeerd token-type voor het endpoint (user-token op `/batch` of M2M-token op `/me`), of geen actieve consent voor de ingelogde user (`/me`). | Vraag de beheerder om goedkeuring; gebruik het juiste token-type; vraag de user opnieuw toestemming. |
| 404 | Onbekend `subject_id` bij `/api/v1/profiles/<id>`. | User bestaat niet. (Batch geeft `null` in plaats van 404.) |

## Integratiepatronen voor UI-rendering

Hieronder concrete patronen voor het renderen van schermen met profielgegevens — met Django + HTMX als voorbeeld, maar het idee werkt voor elke server-side stack.

### Server-side rendering en het blokkeringsprobleem

Bij server-side rendering moet de server de volledige HTML genereren voordat de pagina naar de browser gaat. Als een app bij het renderen van een teamoverzicht eerst 20 profielen moet ophalen, blokkeert dat de hele pageload:

```
Gebruiker klikt ──> App-server ──> wacht op 20 profielen (200ms) ──> rendert HTML ──> browser
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                   dit blokkeert de hele pagina
```

### Lazy loading met HTMX

HTMX biedt een patroon met `hx-get` en `hx-trigger="load"`. De pagina rendert direct met placeholders, en HTMX verrijkt de profielen asynchroon:

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

```python
def profiel_card(request, subject_id):
    """Haalt profiel op bij de profielservice en retourneert een HTML-fragment."""
    profielen = haal_profielen([subject_id])
    profiel = profielen.get(subject_id)
    if profiel is None:
        return render(request, "partials/profiel_card_fallback.html",
                      {"subject_id": subject_id})
    return render(request, "partials/profiel_card.html", {"profiel": profiel})
```

### Batch in plaats van N requests

Individuele requests per card zijn eenvoudig maar bij 20 teamleden zijn dat 20 backend-roundtrips. Twee betere opties:

**Optie 1 — Eén batch-call, alle fragmenten in één response:**

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
    subject_ids = Team.objects.get(id=team_id).leden_subject_ids()
    profielen = haal_profielen(subject_ids)
    return render(request, "partials/team_profielen.html",
                  {"profielen": profielen})
```

**Optie 2 — Individuele cards, maar backend batcht intern:**
Bij de eerste card-request doet de backend één batch-call voor alle team-`subject_id`s en houdt het resultaat in een korte in-memory cache (zie hieronder). De overige 19 requests worden uit de cache beantwoord.

### Korte cache aan afnemer-kant

Een korte in-memory cache (Redis/memcached, 5 min TTL) is acceptabel als versnelling. Een persistente kopie in de eigen database is dat niet — zie de [aansluitvoorwaarden](/docs/aansluitvoorwaarden/) voor de afspraken rond dataopslag.

```python
from django.core.cache import cache

def get_profiel_cached(subject_id: str):
    key = f"profiel:{subject_id}"
    profiel = cache.get(key)
    if profiel is None:
        profielen = haal_profielen([subject_id])
        profiel = profielen.get(subject_id)
        cache.set(key, profiel, timeout=300)
    return profiel
```

### Verwachte UX

```
t=0ms     Browser ontvangt HTML
          → Pagina is direct zichtbaar met placeholders (initialen, "Laden...")

t=50ms    HTMX vuurt requests af voor profiel-cards
          → Backend doet batch-call naar profielservice

t=150ms   Profielservice retourneert profielen
          → Backend rendert HTML-fragmenten

t=200ms   HTMX swapt placeholders voor echte cards
          → Naam, foto, functie verschijnen

t=200ms+  Browser laadt avatars (loading="lazy")
          → Foto's verschijnen als ze in beeld komen
```

## Implementatie-aantekeningen (valkuilen)

Een paar dingen die je tegenkomt bij het uitrollen van de integratie.

### Subject_id is geen UUID

`subject_id` is de SSO `sub`-claim — een string van wisselend formaat (bv. `demo-sub-diana`, of in productie een UUID-achtig token). Sla 'm op als `CharField`, niet `UUIDField`, anders crasht de save zodra het formaat afwijkt.

### Session-cookie clash op localhost

Draait je afnemer ook op `localhost`? Dan delen browsers de cookies tussen poorten op dezelfde host, en overschrijft de default `sessionid`-cookie van de ene Django-app die van de andere — je afnemer-user wordt "uitgelogd" zodra de profielservice op `:8000` een sessie aanmaakt.

Geef je afnemer-app unieke cookie-namen:

```python
SESSION_COOKIE_NAME = "mijn_app_sessionid"
CSRF_COOKIE_NAME = "mijn_app_csrftoken"
```

### Container ↔ host networking (twee URLs nodig)

Draait je afnemer in Docker en de profielservice op de host? Dan praat de afnemer op twee manieren met de profielservice:

- **Browser-redirect** (consent-scherm): URL moet door de **browser** bereikbaar zijn → `http://localhost:8000`.
- **Back-channel API-call** (token-exchange + `/me` + batch): URL moet vanuit de **container** bereikbaar zijn → `http://host.docker.internal:8000` op macOS/Windows. Op Linux: `extra_hosts: ["host.docker.internal:host-gateway"]` toevoegen aan `docker-compose.yml`.

Daarom twee aparte settings:

```python
PROFIELSERVICE_AUTHORIZE_URL = "http://localhost:8000/o/authorize/"        # browser
PROFIELSERVICE_TOKEN_URL     = "http://host.docker.internal:8000/o/token/" # back-channel
PROFIELSERVICE_API_URL       = "http://host.docker.internal:8000"          # back-channel
```

### ALLOWED_HOSTS-mismatch bij Host-header override

Als je via `host.docker.internal:8000` requests doet, ziet de profielservice die hostnaam in de `Host`-header. Staat hij niet in `ALLOWED_HOSTS`, dan antwoordt Django met een HTML 400-DEBUG-pagina — verraderlijk omdat `response.text` dan met `<!DOCTYPE html>` begint in plaats van een nette JSON-error.

Lokale workaround: override de Host-header expliciet zodat de TCP-connectie naar `host.docker.internal` gaat maar de profielservice `localhost` ziet:

```python
PROFIELSERVICE_API_HOST_HEADER = "localhost:8000"
# ...
headers = {"Authorization": f"Bearer {token}"}
if settings.PROFIELSERVICE_API_HOST_HEADER:
    headers["Host"] = settings.PROFIELSERVICE_API_HOST_HEADER
```

Robuuste fix: zorg dat de profielservice `host.docker.internal` (of de echte hostname) in `ALLOWED_HOSTS` heeft.

### .env-variabelen

Een minimale set:

```
MIJN_APP_CLIENT_SECRET=<secret van de auth-code OAuth-client>
MIJN_APP_M2M_CLIENT_SECRET=<secret van de -m2m OAuth-client>
PROFIELSERVICE_AUTHORIZE_URL=http://localhost:8000/o/authorize/
PROFIELSERVICE_TOKEN_URL=http://host.docker.internal:8000/o/token/
PROFIELSERVICE_API_URL=http://host.docker.internal:8000
PROFIELSERVICE_API_HOST_HEADER=localhost:8000
```

`env_file` wordt alleen geladen bij container-start, niet door autoreload. Na een `.env`-wijziging dus een herstart van je container.
