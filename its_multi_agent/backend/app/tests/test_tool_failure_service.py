import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.tool_failure import ToolFailureAction, ToolFailureCategory
from services.tool_failure_service import tool_failure_service


def test_classify_timeout_exception():
    result = tool_failure_service.classify_exception(
        tool_name="query_knowledge",
        exc=TimeoutError("upstream timed out"),
    )

    assert result.category == ToolFailureCategory.NETWORK_TIMEOUT
    assert result.action == ToolFailureAction.RETRY_TOOL
    assert result.user_message


def test_classify_empty_result_payload():
    result = tool_failure_service.classify_payload(
        tool_name="query_nearest_repair_shops_by_coords",
        payload={"ok": False, "source": "empty_result", "error": "no shops found"},
    )

    assert result.category == ToolFailureCategory.EMPTY_RESULT
    assert result.action == ToolFailureAction.ASK_USER_CLARIFY


def test_classify_auth_failure_payload():
    result = tool_failure_service.classify_payload(
        tool_name="resolve_user_location_from_text",
        payload={"ok": False, "source": "baidu_auth_failed", "error": "auth failed"},
    )

    assert result.category == ToolFailureCategory.AUTH_FAILURE
    assert result.action == ToolFailureAction.BLOCK_TASK


def test_classify_unknown_error_payload_does_not_retry():
    result = tool_failure_service.classify_payload(
        tool_name="query_knowledge",
        payload={"ok": False, "status": "error", "source": "unknown_error", "error_msg": "bug"},
    )

    assert result.category == ToolFailureCategory.UNKNOWN
    assert result.action == ToolFailureAction.BLOCK_TASK
