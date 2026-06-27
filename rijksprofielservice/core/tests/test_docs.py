import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_docs_html_in_sync_with_markdown():
    """Faalt als een markdown-bron is gewijzigd zonder de generator opnieuw te draaien."""
    try:
        call_command("generate_docs_html", check=True)
    except CommandError as exc:
        pytest.fail(str(exc))


@pytest.mark.django_db
def test_docs_index_accessible_anonymous(client):
    response = client.get("/docs/")
    assert response.status_code == 200
    assert b"Business case" in response.content
    assert b'href="/docs/business-case/"' in response.content


@pytest.mark.django_db
def test_docs_business_case_accessible_anonymous(client):
    response = client.get("/docs/business-case/")
    assert response.status_code == 200
    assert b"Business case" in response.content


@pytest.mark.django_db
def test_docs_unknown_slug_returns_404(client):
    response = client.get("/docs/onbekend/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_footer_contains_docs_link(client):
    response = client.get("/docs/")
    assert response.status_code == 200
    assert b"<footer>" in response.content
    assert b'href="/docs/"' in response.content
