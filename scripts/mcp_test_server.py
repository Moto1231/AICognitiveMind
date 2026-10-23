"""Offline transport/storage smoke harness. Production always uses the model Steward.

Agent assessment is exercised separately with scripted model responses in
test_steward_agent.py. This harness preserves provider-free transport tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aicognitive_mind import mcp_server
from aicognitive_mind.memory_steward import MemoryStewardTool

service_class = mcp_server.CognitiveMcpService


def offline_service(*args, **kwargs):
    return service_class(*args, **kwargs, steward_factory=MemoryStewardTool)


if __name__ == "__main__":
    mcp_server.CognitiveMcpService = offline_service
    mcp_server.main()
