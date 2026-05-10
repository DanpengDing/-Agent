import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multi_agent.agent_factory import collect_tool_diagnostic, format_service_agent_diagnostics


def test_collect_tool_diagnostic_extracts_json_error():
    diagnostic = collect_tool_diagnostic(
        "query_nearest_repair_shops_by_coords",
        '{"ok": false, "error": "DB connection refused"}',
    )

    assert diagnostic == "query_nearest_repair_shops_by_coords: DB connection refused"


def test_format_service_agent_diagnostics_appends_backend_details():
    result = format_service_agent_diagnostics(
        "很抱歉，暂时无法提供服务站信息。",
        ["query_nearest_repair_shops_by_coords: DB connection refused"],
    )

    assert "很抱歉，暂时无法提供服务站信息。" in result
    assert "后端错误详情：" in result
    assert "DB connection refused" in result
