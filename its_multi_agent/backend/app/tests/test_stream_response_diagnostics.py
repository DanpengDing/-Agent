from types import SimpleNamespace

from services.stream_response_service import (
    extract_backend_error_details,
    extract_backend_error_details_from_result,
)


def test_extract_backend_error_details_from_tool_output():
    output = "服务站查询失败。\n\n后端错误详情：\n- query_service_station_and_navigate: list_tools() takes 1 positional argument"

    details = extract_backend_error_details(output)

    assert details == "后端错误详情：\n- query_service_station_and_navigate: list_tools() takes 1 positional argument"


def test_extract_backend_error_details_ignores_normal_output():
    assert extract_backend_error_details("服务站查询成功") is None


def test_extract_backend_error_details_from_run_result_items():
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(output="服务站查询失败。\n\n后端错误详情：\n- tool: backend broke"),
        ],
    )

    assert extract_backend_error_details_from_result(result) == [
        "后端错误详情：\n- tool: backend broke"
    ]
