import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.mcp import mcp_manager


class _DummyClient:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    async def connect(self):
        self.events.append(f"connect:{self.name}")

    async def cleanup(self):
        self.events.append(f"cleanup:{self.name}")


def test_mcp_connect_starts_knowledge_server_before_connecting_knowledge_client(monkeypatch):
    events = []

    monkeypatch.setattr(mcp_manager, "baidu_mcp_client", _DummyClient("baidu", events))
    monkeypatch.setattr(mcp_manager, "knowledge_mcp_client", _DummyClient("knowledge", events))

    async def fake_ensure_http_started():
        events.append("knowledge-http-started")

    async def fake_ensure_started():
        events.append("knowledge-server-started")

    monkeypatch.setattr(mcp_manager, "ensure_knowledge_http_server_started", fake_ensure_http_started)
    monkeypatch.setattr(mcp_manager, "ensure_knowledge_mcp_server_started", fake_ensure_started)

    asyncio.run(mcp_manager.mcp_connect())

    assert "connect:knowledge" in events
    assert events.index("knowledge-http-started") < events.index("connect:knowledge")
    assert events.index("knowledge-server-started") < events.index("connect:knowledge")
