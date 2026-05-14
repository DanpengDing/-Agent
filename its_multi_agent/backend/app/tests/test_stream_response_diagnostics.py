import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local.service_station import _build_missing_location_payload
from services.stream_response_service import (
    extract_backend_error_details,
    extract_backend_error_details_from_result,
    extract_tool_failure_from_output,
)


def test_missing_location_payload_has_classification_source():
    payload = json.loads(_build_missing_location_payload("帮我找维修站"))

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"
    assert "error" in payload
    assert "ask_user" in payload


def test_extract_backend_error_details_from_tool_output():
    output = "服务站查询失败\n\n后端错误详情：\n- query_service_station_and_navigate: list_tools() takes 1 positional argument"

    details = extract_backend_error_details(output)

    assert details == "后端错误详情：\n- query_service_station_and_navigate: list_tools() takes 1 positional argument"


def test_extract_backend_error_details_ignores_normal_output():
    assert extract_backend_error_details("服务站查询成功") is None


def test_extract_backend_error_details_from_run_result_items():
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(output="服务站查询失败\n\n后端错误详情：\n- tool: backend broke"),
        ],
    )

    assert extract_backend_error_details_from_result(result) == [
        "后端错误详情：\n- tool: backend broke"
    ]


def test_extract_tool_failure_from_dict_output():
    failure = extract_tool_failure_from_output(
        tool_name="query_knowledge",
        output={"ok": False, "status": "error", "source": "http_timeout", "error_msg": "timed out"},
    )

    assert failure is not None
    assert failure.category.value == "NETWORK_TIMEOUT"


def test_extract_tool_failure_from_json_string_output():
    failure = extract_tool_failure_from_output(
        tool_name="query_nearest_repair_shops_by_coords",
        output='{"ok": false, "source": "empty_result", "error": "未查询到附近维修站"}',
    )

    assert failure is not None
    assert failure.category.value == "EMPTY_RESULT"
