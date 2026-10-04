"""Example wiring for an existing FastAPI + FastMCP Axiom Mind host.

Rename imports to match the host application's actual MCP/FastAPI objects.
"""

from axiom_body.fastapi_bridge import install_body_websocket
from axiom_body.mcp_tools import register_body_tools
from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager


def install(app, mcp):
    body_session = BodySessionManager(command_timeout=10.0)
    body_service = AxiomBodyService(body_session)

    install_body_websocket(app, body_session, path="/body/ws")
    register_body_tools(mcp, body_service)

    return body_session, body_service
