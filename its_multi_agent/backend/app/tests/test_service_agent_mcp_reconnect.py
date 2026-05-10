import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_agent import agent_factory


class _FakeStreamingResult:
    def __init__(self, final_output="服务站结果"):
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None


def test_run_service_agent_reconnects_baidu_mcp_before_query(monkeypatch):
    calls = []

    async def fake_cleanup():
        calls.append("cleanup")

    async def fake_connect():
        calls.append("connect")

    def fake_run_streamed(*args, **kwargs):
        calls.append("run_streamed")
        return _FakeStreamingResult()

    monkeypatch.setattr(agent_factory.baidu_mcp_client, "cleanup", fake_cleanup)
    monkeypatch.setattr(agent_factory.baidu_mcp_client, "connect", fake_connect)
    monkeypatch.setattr(agent_factory.Runner, "run_streamed", fake_run_streamed)

    result = asyncio.run(agent_factory._run_service_agent_with_logging("最近的电脑维修站"))

    assert result == "服务站结果"
    assert calls == ["cleanup", "connect", "run_streamed"]
