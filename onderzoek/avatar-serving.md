# Ontwerp: Avatar-serving en authenticatie

*April 2026*

## Context

De Rijksprofielservice slaat profielfoto's op van ambtenaren. Foto's zijn
biometrische persoonsgegevens — DPIA-vereist (zie `docs/main.md`). Tegelijk
willen we dat ze snel en cachebaar zijn: het is het leeuwendeel van het
bytes-volume (10–50 KB per foto) en wordt op elke team-pagina opnieuw geladen.

Het vertrekpunt vanuit het stack-/caching-ontwerp:

- Afnemer-apps slaan **geen** profieldata op in eigen DB of in-memory cache.
- HTTP-caching (Cache-Control/ETag) via CDN/nginx is expliciet toegestaan.
- De hot-path voor avatars hoort niet in Django te zitten — dan verliezen we
  de schaal-winst van het cache-model.

De kernvraag: hoe geef je nginx/CDN toegang tot de bytes zónder de
DPIA-gevoeligheid van foto's te negeren?

## Spanningsveld

1. **Performance**: ideaal serveert nginx direct van disk/object-store,
   zonder auth-roundtrip.
2. **Privacy**: foto's zijn geen publieke data — de URL mag niet als permanent
   toegangsbewijs rondslingeren in logs of browser-history.
3. **Consent-coupling**: als een ambtenaar consent intrekt voor app X, moet
   app X de foto niet meer kunnen zien — ook niet via een URL die eerder
   verkregen is.

## Drie patronen

### Patroon 1 — Ondoorzichtige URL als capability

De URL zelf is het toegangsbewijs. Hoge-entropie identifier, nginx serveert
zonder verdere check.

```
GET /avatars/7f3a2b9c8e1d4f6a.jpg
```

```nginx
location /avatars/ {
    alias /var/avatars/;
    expires 24h;
    add_header Cache-Control "public, max-age=86400, immutable";
}
```

De URL komt alleen in omloop binnen een batch-response die wél
consent-gecheckt is. Roteert bij elke profielwijziging (nieuwe upload →
nieuwe hash-naam, oude wordt verwijderd).

**Voordelen**: maximaal cachebaar, geen Django op hot path, standaardpatroon
(Slack, Google, Mattermost).

**Risico's**:
- URL-leaks (access-logs bij afnemer, analytics, browser history) blijven
  geldig tot de foto roteert.
- Consent-intrekking verwijdert de consent-record, niet de URL-kennis bij de
  afnemer-app.

**Mitigatie consent-intrekking**: bij intrekking → genereer nieuwe avatar-URL
voor die ambtenaar → oude URL wordt 404. Dit moet bewust ontworpen.

### Patroon 2 — Signed URLs met korte TTL

De URL bevat een handtekening én een expiry. nginx valideert lokaal met
`ngx_http_secure_link_module` (standaard onderdeel).

```
https://profiel.rijks.nl/avatars/abc-123.jpg?exp=1745344800&sig=9f3e...
```

```nginx
location /avatars/ {
    secure_link $arg_sig,$arg_exp;
    secure_link_md5 "$secure_link_expires$uri SECRET_KEY";

    if ($secure_link = "") { return 403; }
    if ($secure_link = "0") { return 410; }  # verlopen

    alias /var/avatars/;
    expires 5m;
}
```

Django genereert URLs in de batch-response:

```python
import hashlib, time

def signed_avatar_url(subject_id):
    expires = int(time.time()) + 300  # 5 min
    path = f"/avatars/{subject_id}.jpg"
    sig = hashlib.md5(f"{expires}{path}{SECRET_KEY}".encode()).hexdigest()
    return f"https://profiel.rijks.nl{path}?exp={expires}&sig={sig}"
```

**Voordelen**:
- URLs verlopen automatisch — leaks zijn tijdgebonden.
- Consent-intrekking is intrinsiek afgevangen: geen nieuwe signed URLs na
  intrekking, bestaande verlopen vanzelf.
- Geen Django in het serve-pad.

**Nadelen**:
- Per-request unieke URLs breken CDN-caching.
- **Mitigatie**: expiry afronden op cache-windows (bv. hele 5-minuten-grenzen).
  Alle requests binnen één window krijgen dezelfde URL → weer cachebaar.
  Subtiel maar belangrijk.

**Standaardpatroon** bij AWS S3 presigned URLs, CloudFront signed URLs etc.

### Patroon 3 — nginx `auth_request` naar Django

nginx doet per avatar-request een subrequest naar Django voor een
consent-check. Pas bij 200 serveert nginx de bytes.

```nginx
location /avatars/ {
    auth_request /internal/check-avatar-access;
    alias /var/avatars/;
}

location = /internal/check-avatar-access {
    internal;
    proxy_pass http://django/internal/avatar-auth;
    proxy_set_header Authorization $http_authorization;
}
```

**Voordelen**: echte auth per request, geen URL-lek-probleem.

**Nadelen**: elke foto-request raakt Django. CDN-caching wordt grotendeels
nutteloos. Precies het tegenovergestelde van wat we wilden met het
cache-ontwerp.

## Vergelijking

| Aspect | Patroon 1 (opaque) | Patroon 2 (signed) | Patroon 3 (auth_request) |
|---|---|---|---|
| Django op hot-path | Nee | Nee | Ja |
| CDN-cachebaar | ✅ uitstekend | ✅ met afgeronde expiry | ❌ effectief nee |
| URL-leaks | Blijven geldig tot rotatie | Verlopen automatisch | Niet relevant |
| Consent-intrekking | Vereist expliciete rotatie | Automatisch binnen TTL | Direct effect |
| Implementatie-complexiteit | Laag | Laag–midden | Midden |
| DPIA-verdedigbaarheid | Acceptabel met rotatie | Sterk | Sterkst |

## Voorkeur (ter bespreking met FG)

**Patroon 2 (signed URLs, 5 min TTL, afgeronde expiry)** lijkt de beste
balans: DPIA-vriendelijk, goed cachebaar, geen Django op het hot-path,
consent-intrekking werkt natuurlijk.

Patroon 1 is operationeel simpeler maar minder goed te verdedigen richting FG
vanwege de leak-gevoeligheid en de noodzaak voor expliciete rotatie bij
consent-intrekking. Patroon 3 gooit het performance-voordeel weg en is alleen
gepast als de FG per-request auth als harde eis stelt.

## Open vragen

1. **DPIA-niveau voor avatars**: welke van deze drie patronen voldoet aan de
   DPIA-eisen? Afstemmen met FG/CPO in de lopende DPIA.
2. **Rotatiebeleid bij profielwijziging/consent-intrekking**: bij patroon 1
   hard vereist, bij patroon 2 optioneel. Wat is de werkwijze?
3. **Storage-backend**: lokale disk (nginx `alias`) of object-store
   (S3-compatible, nginx als proxy)? Onafhankelijk van de drie patronen,
   maar relevant voor opslag-architectuur.
4. **Rijks-CDN vs. eigen nginx-tier**: hangt af van wat er beschikbaar is in
   de hostingcontext (SSC-ICT?). Alle drie patronen werken met beide.
5. **Token-lifetime bij Keycloak**: bij patroon 3 direct relevant; bij 1 en 2
   niet. Korte tokens (≤5 min) versterken de consent-intrekking-coupling.

## Bronnen

- [nginx secure_link module](http://nginx.org/en/docs/http/ngx_http_secure_link_module.html)
- [nginx auth_request module](http://nginx.org/en/docs/http/ngx_http_auth_request_module.html)
- [AWS S3 presigned URLs (referentie voor patroon 2)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
- `docs/main.md` — DPIA-vereiste voor avatars, opt-in consent-model
- `onderzoek/collega-profielen.md` — gelaagd cache-model, batch-endpoint context
- `docs/keycloak-integratie.md` — client-credentials flow, stateless JWT
