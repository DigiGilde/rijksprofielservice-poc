from django.conf import settings
from django.contrib.messages import get_messages
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from jinja2 import Environment


def get_csrf_hidden_input(request):
    token = get_token(request)
    return format_html('<input type="hidden" name="csrfmiddlewaretoken" value="{}">', token)


def environment(**options):
    env = Environment(**options)  # noqa: S701 — autoescape via Django
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "get_csrf_token": get_token,
            "get_csrf_hidden_input": get_csrf_hidden_input,
            "get_messages": get_messages,
            "DEBUG": settings.DEBUG,
        }
    )
    return env
