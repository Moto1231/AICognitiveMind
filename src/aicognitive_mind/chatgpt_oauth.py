from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from aicognitive_mind.config import get_settings
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.persistence import StorageRuntime, create_storage


@dataclass
class PendingAuthorization:
    client_id: str
    params: AuthorizationParams
    expires_at: float

    def model_dump(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "params": self.params.model_dump(mode="json"),
            "expires_at": self.expires_at,
        }

    @classmethod
    def model_validate(cls, value: dict[str, Any]) -> PendingAuthorization:
        return cls(
            client_id=str(value["client_id"]),
            params=AuthorizationParams.model_validate(value["params"]),
            expires_at=float(value["expires_at"]),
        )


class AxiomAuthorizationServerProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth 2.1 authorization server for the personal Axiom MCP endpoint.

    OAuth state is operational state, not cognitive memory. In production it is
    persisted in Axiom's runtime_records storage so Render restarts do not force
    ChatGPT to lose its client registration or refresh token.
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

        # In-memory mirrors are useful for tests and reduce repeated storage reads.
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.pending: dict[str, PendingAuthorization] = {}
        self.codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}

        self._storage: StorageRuntime | None = None
        self._records: RuntimeRecords | None = None

    async def start(self) -> None:
        """Attach durable operational storage for deployed OAuth state."""
        if self._records is not None:
            return
        storage = await create_storage(get_settings())
        self._storage = storage.runtime
        self._records = RuntimeRecords(storage.mind)

    async def close(self) -> None:
        if self._storage is not None:
            await self._storage.close()
        self._storage = None
        self._records = None

    def _key(self, kind: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"oauth_{kind}_{digest}"

    async def _load_record(self, kind: str, value: str) -> dict[str, Any] | None:
        if self._records is None:
            return None
        return await self._records.get(self._key(kind, value))

    async def _save_record(
        self,
        kind: str,
        value: str,
        payload: dict[str, Any],
        *,
        active: bool = True,
    ) -> None:
        if self._records is None:
            return
        key = self._key(kind, value)
        revised = {
            "kind": "oauth_" + kind,
            "active": active,
            "payload": payload,
            "updated_at": time.time(),
        }
        before = await self._records.get(key)
        if before is None:
            await self._records.create(key, revised)
            return
        if not await self._records.replace(key, before, revised):
            # Retry once against the current operational record.
            before = await self._records.get(key)
            if before is None:
                await self._records.create(key, revised)
            elif not await self._records.replace(key, before, revised):
                raise RuntimeError("OAuth operational state changed concurrently")

    async def _deactivate(self, kind: str, value: str) -> None:
        if self._records is None:
            return
        key = self._key(kind, value)
        before = await self._records.get(key)
        if before is None or not before.get("active", False):
            return
        revised = {**before, "active": False, "updated_at": time.time()}
        if not await self._records.replace(key, before, revised):
            raise RuntimeError("OAuth operational state changed concurrently")

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        cached = self.clients.get(client_id)
        if cached is not None:
            return cached
        record = await self._load_record("client", client_id)
        if not record or not record.get("active", False):
            return None
        client = OAuthClientInformationFull.model_validate(record["payload"])
        self.clients[client_id] = client
        return client

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            raise ValueError("OAuth client registration requires a client_id")
        client_id = client_info.client_id
        self.clients[client_id] = client_info
        await self._save_record(
            "client",
            client_id,
            client_info.model_dump(mode="json"),
        )

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        if client.client_id is None:
            raise ValueError("OAuth client has no client_id")
        scopes = list(params.scopes or [self.required_scope])
        if self.required_scope not in scopes:
            raise AuthorizeError(
                error="invalid_scope",
                error_description=f"Required scope {self.required_scope!r} was not requested",
            )

        request_id = secrets.token_urlsafe(32)
        pending = PendingAuthorization(
            client_id=client.client_id,
            params=params,
            expires_at=time.time() + 600,
        )
        self.pending[request_id] = pending
        await self._save_record("pending", request_id, pending.model_dump())
        return self.base_url + "/oauth/login?request=" + quote(request_id)

    async def pending_request(self, request_id: str) -> PendingAuthorization | None:
        cached = self.pending.get(request_id)
        if cached is not None:
            if cached.expires_at > time.time():
                return cached
            self.pending.pop(request_id, None)

        record = await self._load_record("pending", request_id)
        if not record or not record.get("active", False):
            return None
        pending = PendingAuthorization.model_validate(record["payload"])
        if pending.expires_at <= time.time():
            await self._deactivate("pending", request_id)
            return None
        self.pending[request_id] = pending
        return pending

    def authenticate(self, username: str, password: str) -> bool:
        return hmac.compare_digest(username, self.username) and hmac.compare_digest(
            password,
            self.password,
        )

    async def approve(self, request_id: str) -> str:
        pending = await self.pending_request(request_id)
        if pending is None:
            raise ValueError("Authorization request is missing or expired")
        self.pending.pop(request_id, None)
        await self._deactivate("pending", request_id)

        params = pending.params
        scopes = list(params.scopes or [self.required_scope])
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
        await self._save_record(
            "code",
            code.code,
            code.model_dump(mode="json"),
        )
        return construct_redirect_uri(
            str(params.redirect_uri),
            code=code.code,
            state=params.state,
        )

    async def deny(self, request_id: str) -> str:
        pending = await self.pending_request(request_id)
        if pending is None:
            raise ValueError("Authorization request is missing or expired")
        self.pending.pop(request_id, None)
        await self._deactivate("pending", request_id)
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
        cached = self.codes.get(authorization_code)
        if cached is not None:
            if cached.expires_at > time.time() and client.client_id == cached.client_id:
                return cached
            self.codes.pop(authorization_code, None)

        record = await self._load_record("code", authorization_code)
        if not record or not record.get("active", False):
            return None
        code = AuthorizationCode.model_validate(record["payload"])
        if code.expires_at <= time.time() or client.client_id != code.client_id:
            if code.expires_at <= time.time():
                await self._deactivate("code", authorization_code)
            return None
        self.codes[authorization_code] = code
        return code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        if client.client_id != authorization_code.client_id:
            raise ValueError("Authorization code belongs to another client")
        self.codes.pop(authorization_code.code, None)
        await self._deactivate("code", authorization_code.code)
        return await self._mint_token_pair(
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
        cached = self.refresh_tokens.get(refresh_token)
        if cached is not None:
            if (
                (cached.expires_at is None or cached.expires_at > time.time())
                and client.client_id == cached.client_id
            ):
                return cached
            self.refresh_tokens.pop(refresh_token, None)

        record = await self._load_record("refresh", refresh_token)
        if not record or not record.get("active", False):
            return None
        token = RefreshToken.model_validate(record["payload"])
        if (
            token.expires_at is not None
            and token.expires_at <= time.time()
        ) or client.client_id != token.client_id:
            if token.expires_at is not None and token.expires_at <= time.time():
                await self._deactivate("refresh", refresh_token)
            return None
        self.refresh_tokens[refresh_token] = token
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
        await self._deactivate("refresh", refresh_token.token)
        return await self._mint_token_pair(
            client_id=refresh_token.client_id,
            scopes=requested,
            resource=refresh_token.resource or self.resource_url,
            subject=refresh_token.subject or self.username,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        cached = self.access_tokens.get(token)
        if cached is not None:
            if cached.expires_at is None or cached.expires_at > time.time():
                return cached
            self.access_tokens.pop(token, None)

        record = await self._load_record("access", token)
        if not record or not record.get("active", False):
            return None
        access = AccessToken.model_validate(record["payload"])
        if access.expires_at is not None and access.expires_at <= time.time():
            await self._deactivate("access", token)
            return None
        self.access_tokens[token] = access
        return access

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)
        await self._deactivate(
            "access" if isinstance(token, AccessToken) else "refresh",
            token.token,
        )

    async def _mint_token_pair(
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
        access = AccessToken(
            token=access_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + 3600,
            resource=resource,
            subject=subject,
            claims={"iss": self.base_url},
        )
        refresh = RefreshToken(
            token=refresh_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + 30 * 24 * 3600,
            resource=resource,
            subject=subject,
        )
        self.access_tokens[access_value] = access
        self.refresh_tokens[refresh_value] = refresh
        await self._save_record("access", access_value, access.model_dump(mode="json"))
        await self._save_record("refresh", refresh_value, refresh.model_dump(mode="json"))
        return OAuthToken(
            access_token=access_value,
            refresh_token=refresh_value,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(scopes),
        )


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
  <title>Authorize Axiom</title>
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
  <h1>Authorize Axiom</h1>
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
    if not request_id or await provider.pending_request(request_id) is None:
        return HTMLResponse("Authorization request is missing or expired.", status_code=400)
    return _login_page(request_id)


async def oauth_login_post(
    request: Request,
    provider: AxiomAuthorizationServerProvider,
) -> Response:
    raw = (await request.body()).decode("utf-8", errors="replace")
    form = {key: values[-1] for key, values in parse_qs(raw).items() if values}
    request_id = form.get("request", "")
    if not request_id or await provider.pending_request(request_id) is None:
        return HTMLResponse("Authorization request is missing or expired.", status_code=400)
    if form.get("decision") == "deny":
        return RedirectResponse(await provider.deny(request_id), status_code=302)
    username = form.get("username", "")
    password = form.get("password", "")
    if not provider.authenticate(username, password):
        return _login_page(request_id, error="Username or password was not accepted.")
    return RedirectResponse(await provider.approve(request_id), status_code=302)


def hostname_from_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise ValueError("Public Axiom URL has no hostname")
    return parsed.hostname
