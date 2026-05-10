import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.mcp import knowledge_http_bootstrap


class _DummyProcess:
    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


def test_ensure_knowledge_http_server_started_starts_process_when_port_closed(monkeypatch):
    process = _DummyProcess()
    calls = []
    open_states = iter([False, False, True])

    monkeypatch.setattr(knowledge_http_bootstrap, "_knowledge_http_process", None)
    monkeypatch.setattr(knowledge_http_bootstrap, "_knowledge_http_host_port", lambda: ("127.0.0.1", 8001))
    monkeypatch.setattr(
        knowledge_http_bootstrap,
        "_is_port_open",
        lambda host, port, timeout=1.0: next(open_states),
    )
    monkeypatch.setattr(
        knowledge_http_bootstrap.subprocess,
        "Popen",
        lambda *args, **kwargs: calls.append({"args": args, "kwargs": kwargs}) or process,
    )

    asyncio.run(knowledge_http_bootstrap.ensure_knowledge_http_server_started())

    assert len(calls) == 1
    command = calls[0]["args"][0]
    assert command[:2] == [sys.executable, "-c"]
    assert "uvicorn.run" in command[2]
    assert "8001" in command[2]


def test_cleanup_knowledge_http_server_terminates_owned_process(monkeypatch):
    process = _DummyProcess()
    monkeypatch.setattr(knowledge_http_bootstrap, "_knowledge_http_process", process)

    asyncio.run(knowledge_http_bootstrap.cleanup_knowledge_http_server())

    assert process.terminated is True
    assert knowledge_http_bootstrap._knowledge_http_process is None
