"""Whitelist van docs die via de UI ontsloten worden.

Bron van waarheid voor zowel `generate_docs_html` als de docs-views. Nieuwe doc
toevoegen: entry hieronder, `uv run python manage.py generate_docs_html`, commit.
"""

DOCS = [
    {
        "slug": "business-case",
        "title": "Business case",
        "source": "docs/business_case.md",
        "target": "rijksprofielservice/core/jinja2/core/docs/business_case.html",
        "template": "core/docs/business_case.html",
    },
    {
        "slug": "uit-dienst-treding",
        "title": "Uit-dienst-treding",
        "source": "docs/uit_dienst_treding.md",
        "target": "rijksprofielservice/core/jinja2/core/docs/uit_dienst_treding.html",
        "template": "core/docs/uit_dienst_treding.html",
    },
    {
        "slug": "aansluitvoorwaarden",
        "title": "Aansluitvoorwaarden",
        "source": "docs/aansluitvoorwaarden.md",
        "target": "rijksprofielservice/core/jinja2/core/docs/aansluitvoorwaarden.html",
        "template": "core/docs/aansluitvoorwaarden.html",
    },
    {
        "slug": "integratie",
        "title": "Integratiehandleiding",
        "source": "docs/integratie.md",
        "target": "rijksprofielservice/core/jinja2/core/docs/integratie.html",
        "template": "core/docs/integratie.html",
    },
]


def get_doc(slug: str):
    for doc in DOCS:
        if doc["slug"] == slug:
            return doc
    return None
