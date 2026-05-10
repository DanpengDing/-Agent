import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_agent.agent_factory import collect_tool_diagnostic, format_service_agent_diagnostics


def test_collect_tool_diagnostic_returns_ask_user_when_location_is_required():
    diagnostic = collect_tool_diagnostic(
        "resolve_user_location_from_text",
        '{"ok": false, "needs_user_location": true, "ask_user": "请告诉我你现在在哪个区。"}',
    )

    assert diagnostic == "ASK_USER:请告诉我你现在在哪个区。"


def test_format_service_agent_diagnostics_prefers_ask_user_prompt():
    result = format_service_agent_diagnostics(
        "已为您找到维修站。",
        ["ASK_USER:请告诉我你现在在哪个区。"],
    )

    assert result == "请告诉我你现在在哪个区。"
