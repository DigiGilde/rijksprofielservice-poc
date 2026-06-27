"""Genereer doc-templates uit de markdown-bestanden in `docs_registry.DOCS`.

Bron van waarheid zijn de markdown-bestanden in `/docs/`. De gegenereerde
Jinja2-templates worden gecommit zodat ze in PR's reviewbaar blijven; de test
`test_docs_html_in_sync_with_markdown` draait deze command met --check en
faalt als bron en gegenereerde template uit sync raken.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from markdown_it import MarkdownIt

from rijksprofielservice.core.docs_registry import DOCS


def _build_renderer() -> MarkdownIt:
    md = MarkdownIt("commonmark")
    default_link_open = md.renderer.rules.get(
        "link_open",
        lambda tokens, idx, options, env: md.renderer.renderToken(tokens, idx, options, env),
    )

    def link_open(tokens, idx, options, env):
        token = tokens[idx]
        href = token.attrGet("href") or ""
        if href.startswith(("http://", "https://")):
            token.attrSet("target", "_blank")
            token.attrSet("rel", "noopener")
        return default_link_open(tokens, idx, options, env)

    md.renderer.rules["link_open"] = link_open
    return md


def render_doc_html(markdown_text: str, title: str) -> str:
    md = _build_renderer()
    body = md.render(markdown_text)
    preamble = (
        '{% extends "core/docs/_layout.html" %}\n'
        f"{{% block title %}}{title} · Rijksprofielservice{{% endblock %}}\n"
        "{% block doc_body %}\n"
        '<article class="privacy">\n'
    )
    postamble = "</article>\n{% endblock %}\n"
    return preamble + body + postamble


class Command(BaseCommand):
    help = "Genereer doc-templates uit de markdown-bestanden in docs_registry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Faal als een gegenereerde HTML afwijkt van wat op disk staat.",
        )

    def handle(self, *args, **options):
        check = options["check"]
        out_of_sync = []
        for doc in DOCS:
            source_path = settings.BASE_DIR / doc["source"]
            target_path = settings.BASE_DIR / doc["target"]

            markdown_text = source_path.read_text(encoding="utf-8")
            new_html = render_doc_html(markdown_text, doc["title"])

            if check:
                current = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
                if current != new_html:
                    out_of_sync.append((doc["target"], doc["source"]))
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(new_html, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Geschreven: {doc['target']}"))

        if check:
            if out_of_sync:
                lines = "\n".join(f"- {t} (uit {s})" for t, s in out_of_sync)
                raise CommandError(
                    "De volgende doc-templates lopen niet meer in pas met hun markdown-bron:\n"
                    f"{lines}\n"
                    "Draai `uv run python manage.py generate_docs_html` en commit het resultaat."
                )
            self.stdout.write(self.style.SUCCESS("Alle docs zijn in sync met hun markdown-bron."))
