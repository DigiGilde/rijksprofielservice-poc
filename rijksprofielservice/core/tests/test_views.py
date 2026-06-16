import pytest

from rijksprofielservice.core.models import Consent

pytestmark = pytest.mark.django_db


def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/inloggen/" in response.url


def test_home_redirects_to_profile_edit(client, alice):
    client.force_login(alice)
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/profiel/"


def test_profile_edit_get_renders_form(client, alice):
    client.force_login(alice)
    response = client.get("/profiel/")
    assert response.status_code == 200
    assert b"alice@minbzk.nl" in response.content
    assert b"Voornaam" in response.content
    assert b"telefoon" in response.content.lower()


def test_profile_edit_save_button_initially_disabled(client, alice):
    client.force_login(alice)
    response = client.get("/profiel/")
    assert b'id="save-btn" disabled' in response.content


def test_profile_edit_post_updates_name_and_fields(client, alice):
    client.force_login(alice)
    response = client.post(
        "/profiel/",
        data={
            "first_name": "Alicia",
            "last_name": "Aap",
            "telefoon": "06-9999",
            "functie": "Nieuwe functie",
            "organisatie": "BZK",
        },
    )
    assert response.status_code == 302
    alice.refresh_from_db()
    alice.profile.refresh_from_db()
    assert alice.first_name == "Alicia"
    assert alice.profile.telefoon == "06-9999"
    assert alice.profile.functie == "Nieuwe functie"


def test_avatar_delete_removes_avatar(client, alice):
    from django.core.files.uploadedfile import SimpleUploadedFile

    img_bytes = _make_real_jpeg()
    alice.profile.avatar.save("test.jpg", SimpleUploadedFile("test.jpg", img_bytes, "image/jpeg"))
    assert alice.profile.avatar

    client.force_login(alice)
    response = client.post("/profiel/foto/verwijderen/")
    assert response.status_code == 302
    alice.profile.refresh_from_db()
    assert not alice.profile.avatar


def _make_real_jpeg() -> bytes:
    """Maak een valide minimale JPEG (Pillow's ImageField validator accepteert dit)."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(120, 200, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def test_avatar_update_uploads_new_avatar(client, alice):
    """Eerste upload via /profiel/foto/ slaat de foto op."""
    import os

    from django.core.files.uploadedfile import SimpleUploadedFile

    img_bytes = _make_real_jpeg()
    client.force_login(alice)
    response = client.post(
        "/profiel/foto/",
        data={"avatar": SimpleUploadedFile("first.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 302
    alice.profile.refresh_from_db()
    assert alice.profile.avatar
    assert os.path.exists(alice.profile.avatar.path)


def test_avatar_update_replaces_and_removes_old_file(client, alice):
    """Bij vervangen moet het oude bestand op disk weg zijn."""
    import os

    from django.core.files.uploadedfile import SimpleUploadedFile

    img_bytes = _make_real_jpeg()
    alice.profile.avatar.save("first.jpg", SimpleUploadedFile("first.jpg", img_bytes, "image/jpeg"))
    old_path = alice.profile.avatar.path
    assert os.path.exists(old_path)

    client.force_login(alice)
    response = client.post(
        "/profiel/foto/",
        data={"avatar": SimpleUploadedFile("second.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 302
    alice.profile.refresh_from_db()
    new_path = alice.profile.avatar.path
    assert new_path != old_path
    assert not os.path.exists(old_path), f"oud bestand {old_path} bestaat nog"
    assert os.path.exists(new_path)


def test_profile_edit_avatar_url_has_cache_busting_query(client, alice):
    """Img-src moet ?v=<timestamp> bevatten zodat browser de nieuwe foto pakt."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    img_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00" + b"\x08" * 64 + b"\xff\xd9"
    )
    alice.profile.avatar.save("a.jpg", SimpleUploadedFile("a.jpg", img_bytes, "image/jpeg"))
    client.force_login(alice)
    response = client.get("/profiel/")
    assert b"/avatars/" in response.content
    assert b".jpg?v=" in response.content


def test_consent_list_shows_only_active_consents(client, alice, mock_wies, mock_amt, alice_consents_wies):
    """Pagina toont alleen apps waar de gebruiker een actieve toestemming voor heeft."""
    client.force_login(alice)
    response = client.get("/toestemmingen/")
    assert response.status_code == 200
    assert b"Mock Wies" in response.content
    assert b"Mock AMT" not in response.content


def test_consent_list_empty_state(client, alice, mock_wies, mock_amt):
    """Zonder actieve toestemmingen zien we de empty-state, geen tabel."""
    client.force_login(alice)
    response = client.get("/toestemmingen/")
    assert response.status_code == 200
    assert b"Geen actieve toestemmingen" in response.content
    assert b"Mock Wies" not in response.content
    assert b"Mock AMT" not in response.content


def test_consent_revoke_sets_revoked_at(client, alice, mock_wies, alice_consents_wies):
    client.force_login(alice)
    response = client.post(f"/toestemmingen/{mock_wies.id}/intrekken/")
    assert response.status_code == 302
    alice_consents_wies.refresh_from_db()
    assert alice_consents_wies.revoked_at is not None


def test_consent_revoke_keeps_row_for_audit(client, alice, mock_wies, alice_consents_wies):
    """Soft revoke: rij blijft staan, alleen revoked_at wordt gezet."""
    client.force_login(alice)
    client.post(f"/toestemmingen/{mock_wies.id}/intrekken/")
    assert Consent.objects.filter(user=alice, application=mock_wies).count() == 1


def test_avatar_returns_404_when_no_avatar(client, alice):
    response = client.get(f"/avatars/{alice.id}.jpg")
    assert response.status_code == 404
