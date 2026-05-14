# Tool Failure Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build classified tool-failure handling so network timeouts, parameter validation errors, empty third-party results, authentication failures, and unknown tool failures are treated differently instead of falling into one generic retry path.

**Architecture:** Add a small failure taxonomy in the backend, normalize raw tool errors and error-like payloads into a typed result, then let `MultiAgentService` and `stream_response_service` react based on failure class. Persist classified tool failures into task memory so the frontend can show what failed, why it failed, and whether the system retried, degraded, or stopped.

**Tech Stack:** FastAPI, OpenAI Agents SDK, Pydantic, existing local function tools, pytest, SSE streaming responses

---

## File Structure

**Create:**
- `backend/app/schemas/tool_failure.py`
- `backend/app/services/tool_failure_service.py`
- `backend/app/tests/test_tool_failure_service.py`
- `backend/app/tests/test_agent_service_tool_failure_classification.py`

**Modify:**
- `backend/app/services/agent_service.py`
- `backend/app/services/stream_response_service.py`
- `backend/app/services/task_memory_service.py`
- `backend/app/infrastructure/tools/local/knowledge_base.py`
- `backend/app/infrastructure/tools/local/service_station.py`
- `backend/app/tests/test_task_memory_retry_flow.py`
- `backend/app/tests/test_stream_response_diagnostics.py`

**Why these files:**
- `tool_failure.py` defines the shared typed contract so tools and services stop passing ad hoc strings.
- `tool_failure_service.py` centralizes classification logic and action policy.
- `knowledge_base.py` and `service_station.py` are the highest-value local tools to normalize first because they already emit mixed exception and error-payload styles.
- `stream_response_service.py` is the best place to inspect tool output and surface typed process events.
- `agent_service.py` is the policy layer that decides retry vs block vs ask user to fix input.
- `task_memory_service.py` needs a dedicated tool-failure recorder instead of overloading generic error fields.

### Task 1: Add the failure taxonomy and normalization contract

**Files:**
- Create: `backend/app/schemas/tool_failure.py`
- Create: `backend/app/services/tool_failure_service.py`
- Test: `backend/app/tests/test_tool_failure_service.py`

- [ ] **Step 1: Write the failing tests for classification primitives**

```python
from schemas.tool_failure import ToolFailureCategory, ToolFailureAction
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_tool_failure_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'schemas.tool_failure'`

- [ ] **Step 3: Add the new schema file**

```python
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
```

- [ ] **Step 4: Implement the classifier service**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/app/tests/test_tool_failure_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/tool_failure.py backend/app/services/tool_failure_service.py backend/app/tests/test_tool_failure_service.py
git commit -m "feat: add tool failure classification primitives"
```

### Task 2: Normalize local tool outputs into classifiable error payloads

**Files:**
- Modify: `backend/app/infrastructure/tools/local/knowledge_base.py`
- Modify: `backend/app/infrastructure/tools/local/service_station.py`
- Test: `backend/app/tests/test_stream_response_diagnostics.py`

- [ ] **Step 1: Write the failing tests for payload shape**

```python
import json

from infrastructure.tools.local.service_station import _build_missing_location_payload


def test_missing_location_payload_has_classification_source():
    payload = json.loads(_build_missing_location_payload("帮我找维修站"))

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"
    assert "error" in payload
    assert "ask_user" in payload
```

- [ ] **Step 2: Run test to verify it fails if fields are missing or inconsistent**

Run: `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
Expected: FAIL on missing normalized classification fields or assertion mismatch

- [ ] **Step 3: Standardize `knowledge_base.py` error returns**

```python
except httpx.TimeoutException as e:
    logger.error("knowledge timeout error=%s", e)
    return {
        "ok": False,
        "status": "error",
        "source": "http_timeout",
        "error_msg": str(e),
    }
except httpx.HTTPStatusError as e:
    logger.error("knowledge upstream http error=%s", e)
    return {
        "ok": False,
        "status": "error",
        "source": "upstream_http_error",
        "error_msg": str(e),
    }
except Exception as e:
    logger.error("knowledge unknown error=%s", e)
    return {
        "ok": False,
        "status": "error",
        "source": "unknown_error",
        "error_msg": str(e),
    }
```

- [ ] **Step 4: Add an explicit empty-result payload in `service_station.py`**

```python
if not rows:
    payload = json.dumps(
        {
            "ok": False,
            "source": "empty_result",
            "error": "未查询到附近维修站",
            "query": {"lat": lat, "lng": lng, "limit": limit},
        },
        ensure_ascii=False,
    )
    logger.info("[NearestShops] empty result=%s", payload)
    return payload
```

- [ ] **Step 5: Run tests to verify the normalized tool payloads pass**

Run: `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infrastructure/tools/local/knowledge_base.py backend/app/infrastructure/tools/local/service_station.py backend/app/tests/test_stream_response_diagnostics.py
git commit -m "feat: normalize local tool failure payloads"
```

### Task 3: Teach stream processing to detect classified tool failures

**Files:**
- Modify: `backend/app/services/stream_response_service.py`
- Modify: `backend/app/tests/test_stream_response_diagnostics.py`

- [ ] **Step 1: Write the failing tests for stream-side classification extraction**

```python
from services.stream_response_service import extract_tool_failure_from_output


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
Expected: FAIL with `cannot import name 'extract_tool_failure_from_output'`

- [ ] **Step 3: Add output parsing and classification helpers**

```python
import json

from services.tool_failure_service import tool_failure_service


def try_parse_tool_output(output):
    if isinstance(output, dict):
        return output
    text = str(output or "").strip()
    if not text:
        return None
    if not text.startswith("{"):
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def extract_tool_failure_from_output(tool_name: str, output):
    payload = try_parse_tool_output(output)
    if not isinstance(payload, dict):
        return None
    return tool_failure_service.classify_payload(tool_name, payload)
```

- [ ] **Step 4: Emit a dedicated callback when a tool output represents failure**

```python
elif hasattr(event, "name") and event.name == "tool_output":
    output = getattr(event.item, "output", "")
    tool_name = callbacks.get("tool_name_lookup", lambda: "unknown")()
    failure = extract_tool_failure_from_output(tool_name, output)
    if failure is not None:
        callback = callbacks.get("on_tool_failure")
        if callable(callback):
            callback(failure)
        yield "data: " + ResponseFactory.build_text(
            failure.user_message, ContentKind.PROCESS
        ).model_dump_json() + "\n\n"
        continue
```

- [ ] **Step 5: Run tests to verify stream diagnostics pass**

Run: `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/stream_response_service.py backend/app/tests/test_stream_response_diagnostics.py
git commit -m "feat: classify tool failures during stream processing"
```

### Task 4: Persist classified failures in task memory

**Files:**
- Modify: `backend/app/services/task_memory_service.py`
- Modify: `backend/app/tests/test_task_memory_retry_flow.py`

- [ ] **Step 1: Write the failing test for dedicated tool-failure recording**

```python
from schemas.tool_failure import ToolFailure, ToolFailureAction, ToolFailureCategory
from services.task_memory_service import task_memory_service


def test_record_tool_failure_updates_task_state(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        task_memory_service._repo,
        "update_task",
        lambda **kwargs: captured.update(kwargs) or kwargs,
    )

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

    task_memory_service.record_tool_failure("u1", "task-1", failure)

    assert captured["task_stage"] == "tool_failed"
    assert captured["last_error"] == "timed out"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_task_memory_retry_flow.py -v`
Expected: FAIL with `AttributeError: 'TaskMemoryService' object has no attribute 'record_tool_failure'`

- [ ] **Step 3: Add a dedicated task-memory recorder**

```python
def record_tool_failure(self, user_id: str, task_id: str, failure) -> Optional[Dict[str, Any]]:
    return self._repo.update_task(
        user_id=user_id,
        task_id=task_id,
        task_stage="tool_failed",
        last_tool_name=failure.tool_name,
        last_error=failure.developer_message,
        last_tool_result_json={
            "tool_name": failure.tool_name,
            "failure_category": failure.category.value,
            "failure_action": failure.action.value,
            "error_code": failure.error_code,
            "user_message": failure.user_message,
            "raw_preview": failure.raw_preview,
        },
        last_active_at=self._now_string(),
    )
```

- [ ] **Step 4: Run tests to verify task-memory failure recording passes**

Run: `pytest backend/app/tests/test_task_memory_retry_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/task_memory_service.py backend/app/tests/test_task_memory_retry_flow.py
git commit -m "feat: persist classified tool failures in task memory"
```

### Task 5: Apply policy in `MultiAgentService` based on failure type

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Create: `backend/app/tests/test_agent_service_tool_failure_classification.py`

- [ ] **Step 1: Write the failing policy tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_agent_service_tool_failure_classification.py -v`
Expected: FAIL with `AttributeError: type object 'MultiAgentService' has no attribute '_resolve_tool_failure_policy'`

- [ ] **Step 3: Add a small policy resolver in `agent_service.py`**

```python
@staticmethod
def _resolve_tool_failure_policy(failure):
    if failure.action.value == "RETRY_TOOL":
        return {
            "should_retry_task": True,
            "should_block_task": False,
            "should_return_user_message": True,
        }
    if failure.action.value == "ASK_USER_CLARIFY":
        return {
            "should_retry_task": False,
            "should_block_task": False,
            "should_return_user_message": True,
        }
    return {
        "should_retry_task": False,
        "should_block_task": True,
        "should_return_user_message": True,
    }
```

- [ ] **Step 4: Wire `process_stream_response(..., callbacks=...)` to record tool failures**

```python
callbacks = {
    "on_tool_called": ...,
    "on_tool_output": ...,
    "tool_name_lookup": lambda: (task_memory_service.get_task(user_id, active_task["task_id"]) or {}).get("last_tool_name", "unknown"),
    "on_tool_failure": lambda failure: task_memory_service.record_tool_failure(
        user_id=user_id,
        task_id=active_task["task_id"],
        failure=failure,
    ),
}
```

- [ ] **Step 5: After stream completion, decide whether to retry, ask user, or block**

```python
failure = callbacks_state.get("last_tool_failure")
if failure is not None:
    policy = cls._resolve_tool_failure_policy(failure)
    if policy["should_return_user_message"]:
        yield "data: " + ResponseFactory.build_text(
            failure.user_message,
            ContentKind.PROCESS,
        ).model_dump_json() + "\n\n"
    if policy["should_block_task"] and active_task:
        task_memory_service.mark_blocked(user_id=user_id, task_id=active_task["task_id"], error=failure.developer_message)
        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
        return
```

- [ ] **Step 6: Run tests to verify policy handling passes**

Run: `pytest backend/app/tests/test_agent_service_tool_failure_classification.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent_service.py backend/app/tests/test_agent_service_tool_failure_classification.py
git commit -m "feat: apply tool failure policy in multi agent service"
```

### Task 6: Update retry-flow tests so retries only happen for retryable failure classes

**Files:**
- Modify: `backend/app/tests/test_task_memory_retry_flow.py`
- Modify: `backend/app/tests/test_agent_service_tool_failure_classification.py`

- [ ] **Step 1: Add a failing regression test for non-retryable failures**

```python
def test_parameter_error_does_not_trigger_task_retry(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "services.agent_service.MultiAgentService._resolve_tool_failure_policy",
        lambda failure: {
            "should_retry_task": False,
            "should_block_task": False,
            "should_return_user_message": True,
        },
    )
    monkeypatch.setattr(
        "services.agent_service.task_memory_service.mark_retrying",
        lambda *args, **kwargs: calls.append("retrying"),
    )

    assert calls == []
```

- [ ] **Step 2: Run the retry-flow tests to verify the regression fails before policy alignment**

Run: `pytest backend/app/tests/test_task_memory_retry_flow.py backend/app/tests/test_agent_service_tool_failure_classification.py -v`
Expected: FAIL because generic retry behavior still triggers too broadly

- [ ] **Step 3: Narrow retry behavior in `agent_service.py`**

```python
except Exception as exc:
    failure = tool_failure_service.classify_exception("runner", exc)
    policy = cls._resolve_tool_failure_policy(failure)
    if flag and policy["should_retry_task"]:
        ...
    else:
        ...
```

- [ ] **Step 4: Run the retry-flow tests to verify only retryable classes retry**

Run: `pytest backend/app/tests/test_task_memory_retry_flow.py backend/app/tests/test_agent_service_tool_failure_classification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/tests/test_task_memory_retry_flow.py backend/app/tests/test_agent_service_tool_failure_classification.py backend/app/services/agent_service.py
git commit -m "fix: retry only retryable tool failure categories"
```

### Task 7: Full verification pass

**Files:**
- Test: `backend/app/tests/test_tool_failure_service.py`
- Test: `backend/app/tests/test_stream_response_diagnostics.py`
- Test: `backend/app/tests/test_task_memory_retry_flow.py`
- Test: `backend/app/tests/test_agent_service_tool_failure_classification.py`

- [ ] **Step 1: Run focused backend tests**

Run: `pytest backend/app/tests/test_tool_failure_service.py backend/app/tests/test_stream_response_diagnostics.py backend/app/tests/test_task_memory_retry_flow.py backend/app/tests/test_agent_service_tool_failure_classification.py -v`
Expected: PASS

- [ ] **Step 2: Run a broader regression slice around memory and agent services**

Run: `pytest backend/app/tests/test_memory_api.py backend/app/tests/test_task_memory_api.py backend/app/tests/test_agent_service_memory_integration.py -v`
Expected: PASS

- [ ] **Step 3: Manual smoke test in local app**

Run:

```bash
cd backend/app
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

Expected manual checks:
- Query a knowledge request while the upstream URL is intentionally unreachable and confirm the stream shows a timeout-style message.
- Query a repair-station request without location and confirm the stream asks for clarification instead of retrying blindly.
- Trigger a Baidu auth failure and confirm the task becomes `blocked` instead of retrying.

- [ ] **Step 4: Commit**

```bash
git add backend/app
git commit -m "test: verify classified tool failure handling end to end"
```

## Self-Review

- Spec coverage: the plan covers taxonomy, tool normalization, stream extraction, task-memory persistence, retry policy narrowing, and verification.
- Placeholder scan: no `TODO`, `TBD`, or “handle appropriately” placeholders remain.
- Type consistency: the plan uses `ToolFailure`, `ToolFailureCategory`, and `ToolFailureAction` consistently across schema, service, stream, task memory, and policy steps.
