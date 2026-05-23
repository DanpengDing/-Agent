import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local import service_station


def test_parse_json_response_raises_clear_error_for_plain_text_mcp_error():
    try:
        service_station._parse_json_response("map_geocode", "API response error: unkown error")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "non-JSON" in str(exc)
        assert "unkown error" in str(exc)


def test_resolve_user_location_returns_missing_location_for_generic_lookup_text(monkeypatch):
    monkeypatch.setattr(service_station, "get_ip_via_stun", lambda: None)

    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("baidu mcp should not be called for generic lookup text")

    monkeypatch.setattr(service_station.baidu_mcp_client, "call_tool", _fail_if_called)

    payload = json.loads(
        asyncio.run(
            service_station.resolve_user_location_from_text.on_invoke_tool(
                SimpleNamespace(tool_name="resolve_user_location_from_text"),
                '{"user_input":"查询附近维修站"}',
            )
        )
    )

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"


def test_resolve_user_location_treats_lookup_verb_only_text_as_missing_location(monkeypatch):
    monkeypatch.setattr(service_station, "get_ip_via_stun", lambda: None)

    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("baidu mcp should not be called for lookup-verb-only text")

    monkeypatch.setattr(service_station.baidu_mcp_client, "call_tool", _fail_if_called)

    payload = json.loads(
        asyncio.run(
            service_station.resolve_user_location_from_text.on_invoke_tool(
                SimpleNamespace(tool_name="resolve_user_location_from_text"),
                '{"user_input":"查询"}',
            )
        )
    )

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"
