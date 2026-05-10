import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_agent import agent_factory


class _FakeStreamingResult:
    def __init__(self, final_output="技术建议"):
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None


def test_consult_technical_expert_uses_streaming_runner(monkeypatch):
    calls = []

    async def fail_if_run_called(*args, **kwargs):
        raise AssertionError("Runner.run should not be used for technical expert")

    def fake_run_streamed(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _FakeStreamingResult(final_output="蓝屏排查建议")

    monkeypatch.setattr(agent_factory.Runner, "run", fail_if_run_called)
    monkeypatch.setattr(agent_factory.Runner, "run_streamed", fake_run_streamed)

    result = asyncio.run(agent_factory._run_technical_agent_with_logging("电脑蓝屏了怎么办"))

    assert result == "蓝屏排查建议"
    assert len(calls) == 1
    assert calls[0]["kwargs"]["starting_agent"] is agent_factory.technical_agent
