import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local.service_station import _build_missing_location_payload
from schemas.response import ContentKind
from services.stream_response_service import (
    extract_backend_error_details,
    extract_backend_error_details_from_result,
    extract_tool_failure_from_output,
    process_stream_response,
)
from utils.response_util import ResponseFactory


def test_missing_location_payload_has_classification_source():
    payload = json.loads(_build_missing_location_payload("帮我找维修站"))

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"
    assert "error" in payload
    assert "ask_user" in payload


def test_extract_backend_error_details_from_tool_output():
    output = (
        "服务站查询失败\n\n"
        "后端错误详情：\n"
        "- query_service_station_and_navigate: list_tools() takes 1 positional argument"
    )

    details = extract_backend_error_details(output)

    assert details == (
        "后端错误详情：\n"
        "- query_service_station_and_navigate: list_tools() takes 1 positional argument"
    )


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


def test_build_text_packet_includes_optional_review_metadata():
    packet = ResponseFactory.build_text(
        "Need a bit more caution here.",
        ContentKind.ANSWER,
        review_verdict={
            "status": "conflicting",
            "summary": "The retrieved evidence conflicts with the draft answer.",
            "should_downgrade": True,
            "reviewed": True,
        },
        evidence_cards=[
            {
                "title": "Troubleshooting Guide",
                "snippet": "The guide recommends checking software before replacing hardware.",
                "source": "knowledge_base",
                "uri": "https://example.com/guide",
            }
        ],
        references=["knowledge_base"],
        next_action="Ask the user to run diagnostics first.",
        intent="technical_consult",
    )

    payload = packet.model_dump()

    assert payload["content"]["kind"] == "ANSWER"
    assert payload["content"]["review_verdict"]["status"] == "conflicting"
    assert payload["content"]["evidence_cards"][0]["title"] == "Troubleshooting Guide"
    assert payload["content"]["references"] == ["knowledge_base"]
    assert payload["content"]["next_action"] == "Ask the user to run diagnostics first."
    assert payload["content"]["intent"] == "technical_consult"


def test_process_stream_response_emits_structured_answer_metadata_packet():
    class _FakeStreamingResult:
        def __init__(self):
            self.final_output = {
                "answer": "Please start with software checks.",
                "intent": "technical_consult",
                "references": ["knowledge_base"],
                "review_verdict": {
                    "status": "unsupported",
                    "summary": "The original answer was not supported by retrieved evidence.",
                    "should_downgrade": True,
                    "reviewed": True,
                },
                "evidence_cards": [
                    {
                        "title": "KB Evidence",
                        "snippet": "The KB recommends software checks first.",
                        "source": "knowledge_base",
                    }
                ],
            }

        async def stream_events(self):
            if False:
                yield None

    async def _collect():
        chunks = []
        async for chunk in process_stream_response(_FakeStreamingResult()):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())

    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["content"]["kind"] == "ANSWER"
    assert payload["content"]["text"] == "Please start with software checks."
    assert payload["content"]["review_verdict"]["status"] == "unsupported"
    assert payload["content"]["evidence_cards"][0]["title"] == "KB Evidence"


def test_process_stream_response_uses_empty_text_when_answer_deltas_already_streamed():
    class _TextDelta:
        def __init__(self, delta):
            self.delta = delta

    class _FakeStreamingResult:
        def __init__(self):
            self.final_output = {
                "answer": "Please start with software checks.",
                "review_verdict": {
                    "status": "supported",
                    "summary": "Evidence supports the answer.",
                    "should_downgrade": False,
                    "reviewed": True,
                },
                "evidence_cards": [
                    {
                        "title": "KB Evidence",
                        "snippet": "The KB recommends software checks first.",
                        "source": "knowledge_base",
                    }
                ],
            }

        async def stream_events(self):
            yield SimpleNamespace(
                type="raw_response_event",
                data=_TextDelta("Please start with software checks."),
            )

    async def _collect():
        chunks = []
        with patch("services.stream_response_service.ResponseTextDeltaEvent", _TextDelta):
            async for chunk in process_stream_response(_FakeStreamingResult()):
                chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())

    assert len(chunks) == 2
    streamed_answer = json.loads(chunks[0].removeprefix("data: ").strip())
    metadata_packet = json.loads(chunks[1].removeprefix("data: ").strip())

    assert streamed_answer["content"]["text"] == "Please start with software checks."
    assert metadata_packet["content"]["text"] == ""
    assert metadata_packet["content"]["review_verdict"]["status"] == "supported"
