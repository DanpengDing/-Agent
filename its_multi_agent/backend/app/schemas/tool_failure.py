from enum import Enum

from pydantic import BaseModel, Field


class ToolFailureCategory(str, Enum):
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    PARAMETER_ERROR = "PARAMETER_ERROR"
    EMPTY_RESULT = "EMPTY_RESULT"
    AUTH_FAILURE = "AUTH_FAILURE"
    UPSTREAM_HTTP_ERROR = "UPSTREAM_HTTP_ERROR"
    UNKNOWN = "UNKNOWN"


class ToolFailureAction(str, Enum):
    RETRY_TOOL = "RETRY_TOOL"
    ASK_USER_CLARIFY = "ASK_USER_CLARIFY"
    BLOCK_TASK = "BLOCK_TASK"
    RETURN_DEGRADED_RESULT = "RETURN_DEGRADED_RESULT"


class ToolFailure(BaseModel):
    tool_name: str
    category: ToolFailureCategory
    action: ToolFailureAction
    error_code: str = Field(default="")
    developer_message: str = Field(default="")
    user_message: str = Field(default="")
    retryable: bool = Field(default=False)
    raw_preview: str = Field(default="")
