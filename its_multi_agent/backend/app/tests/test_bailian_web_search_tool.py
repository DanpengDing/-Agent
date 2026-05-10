import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local import bailian_web_search as web_search_module


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeStream:
    def __init__(self, contents):
        self._contents = contents

    def __aiter__(self):
        self._iter = iter(self._contents)
        return self

    async def __anext__(self):
        try:
            return _FakeChunk(next(self._iter))
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def test_run_bailian_web_search_aggregates_stream(monkeypatch):
    calls = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return _FakeStream(["蓝屏通常和驱动", "或硬件异常有关"])

    monkeypatch.setattr(web_search_module.sub_model_client.chat.completions, "create", fake_create)
    monkeypatch.setattr(web_search_module.settings, "SUB_MODEL_NAME", "qwen-test")

    result = asyncio.run(web_search_module._run_bailian_web_search("电脑蓝屏了怎么办"))

    assert result == "蓝屏通常和驱动或硬件异常有关"
    assert calls[0]["extra_body"] == {"enable_search": True}
    assert calls[0]["stream"] is True
