"""Genereer privacy.html uit docs/privacy.md.

Bron van waarheid is docs/privacy.md. De gegenereerde Jinja2-template wordt
gecommit zodat hij in PR's reviewbaar blijft; de test
`test_privacy_html_in_sync_with_markdown` draait deze command met --check en
faalt als beide uit sync raken.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from markdown_it import MarkdownIt

SOURCE = "docs/privacy.md"
TARGET = "rijksprofielservice/core/jinja2/core/privacy.html"

PREAMBLE = (
    '{% extends "core/base.html" %}\n'
    "{% block title %}Privacyverklaring · Rijksprofielservice{% endblock %}\n"
    "{% block content %}\n"
    '<article class="privacy">\n'
)
POSTAMBLE = "</article>\n{% endblock %}\n"


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


def render_privacy_html(markdown_text: str) -> str:
    md = _build_renderer()
    body = md.render(markdown_text)
    return PREAMBLE + body + POSTAMBLE


class Command(BaseCommand):
    help = "Genereer de privacy.html-template uit docs/privacy.md."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Faal als de gegenereerde HTML afwijkt van wat op disk staat.",
        )

    def handle(self, *args, **options):
        source_path = settings.BASE_DIR / SOURCE
        target_path = settings.BASE_DIR / TARGET

        markdown_text = source_path.read_text(encoding="utf-8")
        new_html = render_privacy_html(markdown_text)

        if options["check"]:
            current = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
            if current != new_html:
                raise CommandError(
                    f"{TARGET} loopt niet meer in pas met {SOURCE}. "
                    "Draai `uv run python manage.py generate_privacy_html` en commit het resultaat."
                )
            self.stdout.write(self.style.SUCCESS(f"{TARGET} is in sync met {SOURCE}."))
            return

        target_path.write_text(new_html, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Geschreven: {TARGET}"))
