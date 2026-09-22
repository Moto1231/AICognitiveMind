from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from html import escape
from urllib.parse import parse_qs, quote, urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response


@dataclass
class PendingAuthorization:
    client_id: str
    params: AuthorizationParams
    expires_at: float


class AxiomAuthorizationServerProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Small OAuth 2.1 authorization server for the personal Axiom MCP endpoint.

    Dynamic client registrations and bearer tokens are intentionally operational
    state, not cognitive memory. They may be lost on a service restart; ChatGPT
    can simply authorize again. The Mind itself remains in canonical storage.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        required_scope: str = "axiom:mind",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.resource_url = self.base_url + "/mcp"
        self.username = username
        self.password = password
        self.required_scope = required_scope
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.pending: dict[str, PendingAuthorization] = {}
        self.codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            raise ValueError("OAuth client registration requires a client_id")
        self.clients[client_info.client_id] = client_info

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        if client.client_id is None:
            raise ValueError("OAuth client has no client_id")
        self._purge_expired()
        request_id = secrets.token_urlsafe(32)
        self.pending[request_id] = PendingAuthorization(
            client_id=client.client_id,
            params=params,
            expires_at=time.time() + 600,
        )
        return self.base_url + "/oauth/login?request=" + quote(request_id)

    def pending_request(self, request_id: str) -> PendingAuthorization | None:
        self._purge_expired()
        return self.pending.get(request_id)

    def authenticate(self, username: str, password: str) -> bool:
        return hmac.compare_digest(username, self.username) and hmac.compare_digest(
            password, self.password
        )

    def approve(self, request_id: str) -> str:
        self._purge_expired()
        pending = self.pending.pop(request_id, None)
        if pending is None:
            raise ValueError("Authorization request is missing or expired")
        params = pending.params
        scopes = list(params.scopes or [self.required_scope])
        if self.required_scope not in scopes:
            scopes.append(self.required_scope)
        code = AuthorizationCode(
            code=secrets.token_urlsafe(32),
            client_id=pending.client_id,
            scopes=scopes,
            expires_at=time.time() + 300,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource or self.resource_url,
            subject=self.username,
        )
        self.codes[code.code] = code
        return construct_redirect_uri(
            str(params.redirect_uri),
            code=code.code,
            state=params.state,
        )

    def deny(self, request_id: str) -> str:
        self._purge_expired()
        pending = self.pending.pop(request_id, None)
        if pending is None:
            raise ValueError("Authorization request is missing or expired")
        return construct_redirect_uri(
            str(pending.params.redirect_uri),
            error="access_denied",
            state=pending.params.state,
        )

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        self._purge_expired()
        code = self.codes.get(authorization_code)
        if code is None or client.client_id != code.client_id:
            return None
        return code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        if client.client_id != authorization_code.client_id:
            raise ValueError("Authorization code belongs to another client")
        self.codes.pop(authorization_code.code, None)
        return self._mint_token_pair(
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
            resource=authorization_code.resource or self.resource_url,
            subject=authorization_code.subject or self.username,
        )

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        self._purge_expired()
        token = self.refresh_tokens.get(refresh_token)
        if token is None or client.client_id != token.client_id:
            return None
        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if client.client_id != refresh_token.client_id:
            raise ValueError("Refresh token belongs to another client")
        requested = scopes or refresh_token.scopes
        if not set(requested).issubset(set(refresh_token.scopes)):
            raise ValueError("Refresh request attempted to expand scope")
        self.refresh_tokens.pop(refresh_token.token, None)
        return self._mint_token_pair(
            client_id=refresh_token.client_id,
            scopes=requested,
            resource=refresh_token.resource or self.resource_url,
            subject=refresh_token.subject or self.username,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        self._purge_expired()
        return self.access_tokens.get(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)

    def _mint_token_pair(
        self,
        *,
        client_id: str,
        scopes: list[str],
        resource: str,
        subject: str,
    ) -> OAuthToken:
        now = int(time.time())
        access_value = secrets.token_urlsafe(32)
        refresh_value = secrets.token_urlsafe(40)
        self.access_tokens[access_value] = AccessToken(
            token=access_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + 3600,
            resource=resource,
            subject=subject,
            claims={"iss": self.base_url},
        )
        self.refresh_tokens[refresh_value] = RefreshToken(
            token=refresh_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + 30 * 24 * 3600,
            resource=resource,
            subject=subject,
        )
        return OAuthToken(
            access_token=access_value,
            refresh_token=refresh_value,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(scopes),
        )

    def _purge_expired(self) -> None:
        now = time.time()
        self.pending = {
            key: value for key, value in self.pending.items() if value.expires_at > now
        }
        self.codes = {
            key: value for key, value in self.codes.items() if value.expires_at > now
        }
        self.access_tokens = {
            key: value
            for key, value in self.access_tokens.items()
            if value.expires_at is None or value.expires_at > now
        }
        self.refresh_tokens = {
            key: value
            for key, value in self.refresh_tokens.items()
            if value.expires_at is None or value.expires_at > now
        }


def _login_page(request_id: str, *, error: str = "") -> HTMLResponse:
    safe_request = escape(request_id, quote=True)
    error_html = (
        '<p style="color:#b42318">' + escape(error) + "</p>" if error else ""
    )
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Authorize Axiom Mind</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#111827; color:#f9fafb;
           display:grid; place-items:center; min-height:100vh; margin:0; }}
    main {{ width:min(420px, calc(100vw - 40px)); background:#1f2937; padding:28px;
            border-radius:14px; box-shadow:0 18px 60px #0008; }}
    input, button {{ box-sizing:border-box; width:100%; padding:12px; margin-top:8px;
                     border-radius:8px; border:1px solid #4b5563; }}
    input {{ background:#111827; color:#f9fafb; }}
    button {{ cursor:pointer; margin-top:18px; background:#2563eb; color:white; border:0; }}
    .deny {{ background:#374151; }}
    p {{ color:#d1d5db; }}
  </style>
</head>
<body>
<main>
  <h1>Authorize Axiom Mind</h1>
  <p>Sign in with the same credentials used for the Axiom portal.</p>
  {error_html}
  <form method="post" action="/oauth/login">
    <input type="hidden" name="request" value="{safe_request}">
    <label>Username<input name="username" autocomplete="username" required></label>
    <label>Password<input type="password" name="password" autocomplete="current-password" required></label>
    <button type="submit" name="decision" value="approve">Connect ChatGPT to Axiom</button>
    <button class="deny" type="submit" name="decision" value="deny">Cancel</button>
  </form>
</main>
</body>
</html>"""
    return HTMLResponse(html)


async def oauth_login_get(
    request: Request,
    provider: AxiomAuthorizationServerProvider,
) -> Response:
    request_id = request.query_params.get("request", "")
    if not request_id or provider.pending_request(request_id) is None:
        return HTMLResponse("Authorization request is missing or expired.", status_code=400)
    return _login_page(request_id)


async def oauth_login_post(
    request: Request,
    provider: AxiomAuthorizationServerProvider,
) -> Response:
    raw = (await request.body()).decode("utf-8", errors="replace")
    form = {key: values[-1] for key, values in parse_qs(raw).items() if values}
    request_id = form.get("request", "")
    if not request_id or provider.pending_request(request_id) is None:
        return HTMLResponse("Authorization request is missing or expired.", status_code=400)
    if form.get("decision") == "deny":
        return RedirectResponse(provider.deny(request_id), status_code=302)
    username = form.get("username", "")
    password = form.get("password", "")
    if not provider.authenticate(username, password):
        return _login_page(request_id, error="Username or password was not accepted.")
    return RedirectResponse(provider.approve(request_id), status_code=302)


def hostname_from_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise ValueError("Public Axiom URL has no hostname")
    return parsed.hostname
