from __future__ import annotations

import os
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route

from mcp.server.transport_security import TransportSecuritySettings

from aicognitive_mind.api import app as portal_app
from aicognitive_mind.chatgpt_mcp import build_chatgpt_mcp
from aicognitive_mind.chatgpt_oauth import (
    AxiomAuthorizationServerProvider,
    account_signup_get,
    account_signup_post,
    hostname_from_base_url,
    oauth_login_get,
    oauth_login_post,
    oauth_signup_get,
    oauth_signup_post,
)
from aicognitive_mind.config import get_settings


def public_base_url() -> str:
    explicit = os.environ.get("AXIOM_PUBLIC_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if render_url:
        return render_url.rstrip("/")
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        return ("https://" + render_host).rstrip("/")
    return "http://127.0.0.1:8000"


BASE_URL = public_base_url()
MCP_PATH = "/axiom-mcp"
settings = get_settings()
logger = logging.getLogger("aicognitive_mind.auth_diagnostics")

if (
    BASE_URL.startswith("https://")
    and not settings.app_access_password
):
    raise RuntimeError(
        "APP_ACCESS_PASSWORD is required before exposing the Axiom MCP OAuth login."
    )

oauth_provider = AxiomAuthorizationServerProvider(
    base_url=BASE_URL,
    username=settings.app_access_username,
    password=settings.app_access_password or "",
    resource_path=MCP_PATH,
)
axiom_mcp = build_chatgpt_mcp(BASE_URL, oauth_provider)


async def _account_signup_get(request: Request):
    return await account_signup_get(request, oauth_provider)


async def _account_signup_post(request: Request):
    logger.warning("AUTH_DIAG signup request received path=%s", request.url.path)
    try:
        response = await account_signup_post(request, oauth_provider)
        logger.warning("AUTH_DIAG signup response status=%s", response.status_code)
        return response
    except Exception:
        logger.exception("AUTH_DIAG signup unhandled exception")
        raise


async def _oauth_login_get(request: Request):
    return await oauth_login_get(request, oauth_provider)


async def _oauth_login_post(request: Request):
    return await oauth_login_post(request, oauth_provider)


async def _oauth_signup_get(request: Request):
    return await oauth_signup_get(request, oauth_provider)


async def _oauth_signup_post(request: Request):
    return await oauth_signup_post(request, oauth_provider)


async def _legacy_mcp_redirect(_request: Request):
    return RedirectResponse(MCP_PATH, status_code=307)


async def _public_entry(_request: Request):
    return HTMLResponse("""<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Axiom</title></head>
<body style="font-family:system-ui;background:#111827;color:#f9fafb;display:grid;place-items:center;min-height:100vh;margin:0">
<main style="width:min(420px,calc(100vw - 40px));background:#1f2937;padding:28px;border-radius:14px">
<h1>Axiom</h1><p>Connect to an existing Axiom account or create a new Genesis mind.</p>
<a href="/signup" style="display:block;text-align:center;padding:12px;margin-top:18px;border-radius:8px;background:#2563eb;color:white;text-decoration:none">Create new account</a>
<a href="/portal" style="display:block;text-align:center;padding:12px;margin-top:12px;border-radius:8px;background:#374151;color:white;text-decoration:none">Existing Axiom</a>
</main></body></html>""")


class _AuthDiagnosticMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        method = scope.get("method", "")
        watched = path in {"/signup", "/v1/portal/login"}
        if watched:
            logger.warning("AUTH_DIAG boundary request method=%s path=%s", method, path)
        status = None

        async def diagnostic_send(message):
            nonlocal status
            if message.get("type") == "http.response.start":
                status = message.get("status")
            await send(message)

        try:
            await self.app(scope, receive, diagnostic_send)
        except Exception:
            if watched:
                logger.exception("AUTH_DIAG boundary exception method=%s path=%s", method, path)
            raise
        finally:
            if watched:
                logger.warning("AUTH_DIAG boundary complete method=%s path=%s status=%s", method, path, status)


async def _portal_login_page(_request: Request):
    return HTMLResponse("""<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Axiom Login</title></head>
<body style="font-family:system-ui;background:#111827;color:#f9fafb;display:grid;place-items:center;min-height:100vh;margin:0">
<main style="width:min(420px,calc(100vw - 40px));background:#1f2937;padding:28px;border-radius:14px">
<h1>Sign in to Axiom</h1><p id="error" style="color:#fca5a5"></p>
<form id="login"><label>Username<input id="username" autocomplete="username" required style="box-sizing:border-box;width:100%;padding:12px;margin:8px 0"></label>
<label>Password<input id="password" type="password" autocomplete="current-password" required style="box-sizing:border-box;width:100%;padding:12px;margin:8px 0"></label>
<button style="width:100%;padding:12px;margin-top:18px" type="submit">Sign in</button></form>
<p><a style="color:#93c5fd" href="/signup">Create a new Axiom account</a></p>
<script>
document.getElementById('login').addEventListener('submit', async (event) => {
  event.preventDefault();
  const response = await fetch('/v1/portal/login', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value})
  });
  if (response.ok) { location.replace('/static/index.html'); return; }
  let detail='Sign in failed.';
  try { detail=(await response.json()).detail || detail; } catch (_) {}
  document.getElementById('error').textContent=detail;
});
</script></main></body></html>""")


async def _portal_redirect(_request: Request):
    return RedirectResponse("/static/index.html", status_code=307)


hostname = hostname_from_base_url(BASE_URL)
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        hostname,
        hostname + ":*",
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
    ],
    allowed_origins=[
        BASE_URL,
        "http://127.0.0.1:*",
        "http://localhost:*",
    ],
)

app = axiom_mcp.streamable_http_app(
    streamable_http_path=MCP_PATH,
    json_response=True,
    stateless_http=True,
    transport_security=transport_security,
    host="0.0.0.0",
)

# The installed MCPServer wrapper does not accept custom routes as a transport
# argument. The returned object is an ordinary Starlette app, so append Axiom's
# login endpoints and portal after MCP/OAuth discovery routes are constructed.
# Mount("/") must remain last because it matches every remaining path.
app.router.routes.extend(
    [
        Route("/", endpoint=_public_entry, methods=["GET"]),
        Route("/portal", endpoint=_portal_login_page, methods=["GET"]),
        Route("/signup", endpoint=_account_signup_get, methods=["GET"]),
        Route("/signup", endpoint=_account_signup_post, methods=["POST"]),
        Route("/oauth/login", endpoint=_oauth_login_get, methods=["GET"]),
        Route("/oauth/login", endpoint=_oauth_login_post, methods=["POST"]),
        Route("/oauth/signup", endpoint=_oauth_signup_get, methods=["GET"]),
        Route("/oauth/signup", endpoint=_oauth_signup_post, methods=["POST"]),
        Route("/mcp", endpoint=_legacy_mcp_redirect, methods=["GET", "POST", "DELETE"]),
        Mount("/", app=portal_app),
    ]
)

_mcp_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _combined_lifespan(host_app):
    # Starlette does not automatically run a mounted sub-application's lifespan.
    # Run both the MCP session manager and the existing Axiom portal/API lifespan.
    async with AsyncExitStack() as stack:
        await oauth_provider.start()
        stack.push_async_callback(oauth_provider.close)
        await stack.enter_async_context(_mcp_lifespan(host_app))
        await stack.enter_async_context(portal_app.router.lifespan_context(portal_app))
        yield


app.router.lifespan_context = _combined_lifespan
app = _AuthDiagnosticMiddleware(app)
