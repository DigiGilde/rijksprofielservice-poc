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
]


def get_doc(slug: str):
    for doc in DOCS:
        if doc["slug"] == slug:
            return doc
    return None
