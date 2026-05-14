import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.tool_failure import ToolFailure, ToolFailureAction, ToolFailureCategory
from services.agent_service import MultiAgentService


def test_timeout_failure_maps_to_retry():
    failure = ToolFailure(
        tool_name="query_knowledge",
        category=ToolFailureCategory.NETWORK_TIMEOUT,
        action=ToolFailureAction.RETRY_TOOL,
        error_code="http_timeout",
        developer_message="timed out",
        user_message="外部服务响应超时，系统会优先自动重试一次。",
        retryable=True,
        raw_preview="timed out",
    )

    policy = MultiAgentService._resolve_tool_failure_policy(failure)

    assert policy["should_retry_task"] is True
    assert policy["should_block_task"] is False


def test_parameter_failure_maps_to_user_clarification():
    failure = ToolFailure(
        tool_name="resolve_user_location_from_text",
        category=ToolFailureCategory.PARAMETER_ERROR,
        action=ToolFailureAction.ASK_USER_CLARIFY,
        error_code="value_error",
        developer_message="missing address",
        user_message="工具参数不完整或格式不正确，需要补充更明确的信息。",
        retryable=False,
        raw_preview="missing address",
    )

    policy = MultiAgentService._resolve_tool_failure_policy(failure)

    assert policy["should_retry_task"] is False
    assert policy["should_block_task"] is False
    assert policy["should_return_user_message"] is True


def test_blocking_failure_does_not_retry():
    failure = ToolFailure(
        tool_name="query_knowledge",
        category=ToolFailureCategory.UNKNOWN,
        action=ToolFailureAction.BLOCK_TASK,
        error_code="unknown_error",
        developer_message="bug",
        user_message="工具执行失败，暂时无法继续自动处理。",
        retryable=False,
        raw_preview="bug",
    )

    policy = MultiAgentService._resolve_tool_failure_policy(failure)

    assert policy["should_retry_task"] is False
    assert policy["should_block_task"] is True
