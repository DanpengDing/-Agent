import json
from typing import Any

import httpx

from schemas.tool_failure import ToolFailure, ToolFailureAction, ToolFailureCategory


class ToolFailureService:
    def classify_exception(self, tool_name: str, exc: Exception) -> ToolFailure:
        if isinstance(exc, TimeoutError):
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.NETWORK_TIMEOUT,
                action=ToolFailureAction.RETRY_TOOL,
                error_code="timeout",
                developer_message=str(exc),
                user_message="工具请求超时，系统会优先自动重试一次。",
                retryable=True,
                raw_preview=str(exc)[:500],
            )

        if isinstance(exc, httpx.TimeoutException):
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.NETWORK_TIMEOUT,
                action=ToolFailureAction.RETRY_TOOL,
                error_code="http_timeout",
                developer_message=str(exc),
                user_message="外部服务响应超时，系统会优先自动重试一次。",
                retryable=True,
                raw_preview=str(exc)[:500],
            )

        if isinstance(exc, ValueError):
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.PARAMETER_ERROR,
                action=ToolFailureAction.ASK_USER_CLARIFY,
                error_code="value_error",
                developer_message=str(exc),
                user_message="工具参数不完整或格式不正确，需要补充更明确的信息。",
                retryable=False,
                raw_preview=str(exc)[:500],
            )

        return ToolFailure(
            tool_name=tool_name,
            category=ToolFailureCategory.UNKNOWN,
            action=ToolFailureAction.BLOCK_TASK,
            error_code="unknown_exception",
            developer_message=str(exc),
            user_message="工具执行失败，暂时无法继续自动处理。",
            retryable=False,
            raw_preview=str(exc)[:500],
        )

    def classify_payload(self, tool_name: str, payload: dict[str, Any]) -> ToolFailure | None:
        if payload.get("ok") is True:
            return None

        source = str(payload.get("source") or "")
        error = str(payload.get("error") or payload.get("error_msg") or "")

        if source == "baidu_auth_failed":
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.AUTH_FAILURE,
                action=ToolFailureAction.BLOCK_TASK,
                error_code="baidu_auth_failed",
                developer_message=error,
                user_message="地图服务鉴权失败，当前无法继续自动查询。",
                retryable=False,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        if source in {"missing_location", "empty_result"}:
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.EMPTY_RESULT,
                action=ToolFailureAction.ASK_USER_CLARIFY,
                error_code=source or "empty_result",
                developer_message=error,
                user_message="工具没有拿到足够结果，需要用户补充位置或更具体条件。",
                retryable=False,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        if source in {"http_timeout", "timeout"}:
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.NETWORK_TIMEOUT,
                action=ToolFailureAction.RETRY_TOOL,
                error_code=source or "http_timeout",
                developer_message=error,
                user_message="外部服务响应超时，系统会优先自动重试一次。",
                retryable=True,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        if source == "upstream_http_error":
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.UPSTREAM_HTTP_ERROR,
                action=ToolFailureAction.RETRY_TOOL,
                error_code="upstream_http_error",
                developer_message=error,
                user_message="外部服务返回错误，系统会优先自动重试一次。",
                retryable=True,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        if source in {"http_error", "unknown_error", "database_error"}:
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.UNKNOWN,
                action=ToolFailureAction.BLOCK_TASK,
                error_code=source,
                developer_message=error or source,
                user_message="工具执行失败，暂时无法继续自动处理。",
                retryable=False,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        if payload.get("status") == "error":
            return ToolFailure(
                tool_name=tool_name,
                category=ToolFailureCategory.UPSTREAM_HTTP_ERROR,
                action=ToolFailureAction.RETRY_TOOL,
                error_code="upstream_http_error",
                developer_message=error,
                user_message="外部服务返回错误，系统会优先自动重试一次。",
                retryable=True,
                raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
            )

        return ToolFailure(
            tool_name=tool_name,
            category=ToolFailureCategory.UNKNOWN,
            action=ToolFailureAction.BLOCK_TASK,
            error_code="unknown_payload_error",
            developer_message=error or "unknown payload failure",
            user_message="工具返回了异常结果，系统暂时无法继续自动处理。",
            retryable=False,
            raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
        )


tool_failure_service = ToolFailureService()
