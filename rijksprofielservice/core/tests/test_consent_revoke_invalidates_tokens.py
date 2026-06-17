"""End-to-end revoke: consent intrekken verwijdert AccessTokens direct."""

import pytest

from rijksprofielservice.core.tests.test_oauth_flow import _complete_flow, authorize_params  # noqa: F401

pytestmark = pytest.mark.django_db


def test_revoke_invalidates_user_bound_token(client, alice, mock_wies, authorize_params):  # noqa: F811
    token_response = _complete_flow(client, alice, mock_wies, authorize_params)
    access_token = token_response.json()["access_token"]

    me_before = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {access_token}")
    assert me_before.status_code == 200

    # Intrekken via de UI-route
    revoke = client.post(f"/toestemmingen/{mock_wies.id}/intrekken/")
    assert revoke.status_code == 302

    me_after = client.get("/api/v1/profiles/me", HTTP_AUTHORIZATION=f"Bearer {access_token}")
    assert me_after.status_code == 401
