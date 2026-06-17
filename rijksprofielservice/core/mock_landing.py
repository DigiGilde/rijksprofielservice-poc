"""Demo-landing voor mock consuming-apps.

Implementeert een volwaardige OAuth 2.0 Authorization Code (+ PKCE) client die
binnen dezelfde Django-instantie tegen de profielservice OAuth-server praat. De
HTTP-calls (`/o/token/`, `/api/v1/profiles/me`, `/api/v1/profiles/batch`) gaan
via `requests` over een echte loopback-call — geen DjangoTestClient.
"""

import base64
import hashlib
import secrets

import requests
from django.conf import settings
from django.shortcuts import render


def _pkce_pair() -> tuple[str, str]:
    """PKCE verifier + S256 challenge."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _client_secret(client_id: str) -> str:
    return settings.MOCK_CLIENT_SECRETS.get(client_id, "")


def _exchange_code(*, token_url: str, code: str, redirect_uri: str, client_id: str, code_verifier: str) -> dict:
    resp = requests.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": _client_secret(client_id),
            "code_verifier": code_verifier,
        },
        timeout=5,
    )
    return {"status": resp.status_code, "body": _try_json(resp)}


def _client_credentials(*, token_url: str, m2m_client_id: str) -> dict:
    resp = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "scope": "read_profile",
            "client_id": m2m_client_id,
            "client_secret": _client_secret(m2m_client_id),
        },
        timeout=5,
    )
    return {"status": resp.status_code, "body": _try_json(resp)}


def _call_api(*, url: str, access_token: str, method: str = "GET", json: dict | None = None) -> dict:
    resp = requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json=json,
        timeout=5,
    )
    return {"status": resp.status_code, "body": _try_json(resp)}


def _try_json(resp):
    try:
        return resp.json()
    except ValueError:
        return resp.text


def mock_landing(request, *, client_id: str, app_label: str):
    """Eindstation voor mock-wies / mock-amt.

    GET zonder query-params: toont 'Vraag profielgegevens aan'-knop.
    GET met `?code=&state=`: ruilt code in voor token en roept /me aan.
    GET met `?error=`: toont denial-pad.
    POST action=batch: client-credentials grant + /batch call (demo M2M).
    """
    landing_url = request.build_absolute_uri(request.path)
    token_url = request.build_absolute_uri("/o/token/")
    incoming = dict(request.GET.items())

    auth_result = None
    api_result = None

    # OAuth callback verwerken
    state = incoming.get("state")
    code = incoming.get("code")
    if code and state:
        pkce_verifier = request.session.pop(f"pkce_verifier_{state}", None)
        if pkce_verifier is None:
            auth_result = {"status": "geen-pkce-verifier", "body": "Onbekende of verlopen state."}
        else:
            token_resp = _exchange_code(
                token_url=token_url,
                code=code,
                redirect_uri=landing_url,
                client_id=client_id,
                code_verifier=pkce_verifier,
            )
            auth_result = token_resp
            body = token_resp["body"]
            if isinstance(body, dict) and "access_token" in body:
                api_result = _call_api(
                    url=request.build_absolute_uri("/api/v1/profiles/me"),
                    access_token=body["access_token"],
                )

    # M2M client-credentials demo (server-side batch-call)
    if request.method == "POST" and request.POST.get("action") == "batch":
        m2m_client = f"{client_id}-m2m"
        cc_resp = _client_credentials(token_url=token_url, m2m_client_id=m2m_client)
        body = cc_resp["body"]
        if isinstance(body, dict) and "access_token" in body:
            subject_id = request.POST.get("subject_id", "")
            api_result = {
                "kind": "batch",
                "token": cc_resp,
                "call": _call_api(
                    url=request.build_absolute_uri("/api/v1/profiles/batch"),
                    access_token=body["access_token"],
                    method="POST",
                    json={"subject_ids": [subject_id] if subject_id else []},
                ),
            }
        else:
            api_result = {"kind": "batch", "token": cc_resp, "call": None}

    # Verse Authorize-URL met PKCE
    fresh_state = secrets.token_urlsafe(16)
    pkce_verifier, pkce_challenge = _pkce_pair()
    request.session[f"pkce_verifier_{fresh_state}"] = pkce_verifier

    from urllib.parse import urlencode

    authorize_url = request.build_absolute_uri("/o/authorize/") + "?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": landing_url,
            "scope": "read_profile",
            "state": fresh_state,
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
        }
    )

    sso_subject = (
        request.user.profile.sso_subject
        if request.user.is_authenticated and hasattr(request.user, "profile")
        else ""
    )

    return render(
        request,
        "core/mock_landing.html",
        {
            "app_label": app_label,
            "client_id": client_id,
            "incoming": incoming,
            "authorize_url": authorize_url,
            "fresh_state": fresh_state,
            "auth_result": auth_result,
            "api_result": api_result,
            "sso_subject": sso_subject,
        },
    )
