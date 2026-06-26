import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_privacy_html_in_sync_with_markdown():
    """Faalt als docs/privacy.md is gewijzigd zonder de generator opnieuw te draaien."""
    try:
        call_command("generate_privacy_html", check=True)
    except CommandError as exc:
        pytest.fail(str(exc))


@pytest.mark.django_db
def test_privacy_page_accessible_anonymous(client):
    response = client.get("/privacy/")
    assert response.status_code == 200
    assert b"Privacyverklaring" in response.content


@pytest.mark.django_db
def test_footer_contains_privacy_link_when_anonymous(client):
    """De footer in base.html bevat de privacy-link en is bereikbaar voor uitgelogde bezoekers."""
    response = client.get("/privacy/")
    assert response.status_code == 200
    assert b'<footer>' in response.content
    assert b'href="/privacy/"' in response.content
