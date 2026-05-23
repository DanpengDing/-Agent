import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.retrieval_evidence_service import retrieval_evidence_service


def test_normalize_knowledge_items_into_evidence():
    payload = {
        "items": [
            {
                "title": "Windows Driver Recovery",
                "snippet": "Enter safe mode and roll back the most recent driver.",
                "source": "knowledge_base",
                "uri": "kb://driver-recovery",
            }
        ]
    }

    evidence = retrieval_evidence_service.normalize(payload)

    assert len(evidence) == 1
    assert evidence[0].title == "Windows Driver Recovery"
    assert evidence[0].snippet == "Enter safe mode and roll back the most recent driver."
    assert evidence[0].source == "knowledge_base"


def test_normalize_service_station_rows_into_evidence():
    payload = {
        "data": [
            {
                "service_station_name": "Quanzhou Jinjiang Laptop Service Station",
                "address": "Near Century Avenue, Qingyang Street, Jinjiang",
                "phone": "0595-22010003",
                "distance_km": 7.6,
            }
        ]
    }

    evidence = retrieval_evidence_service.normalize(payload)

    assert len(evidence) == 1
    assert evidence[0].title == "Quanzhou Jinjiang Laptop Service Station"
    assert "Century Avenue" in evidence[0].snippet
    assert evidence[0].source == "retrieval"


def test_normalize_task_payload_prefers_normalized_evidence_items():
    task = {
        "last_tool_result_json": {
            "tool_name": "query_knowledge",
            "evidence_items": [
                {
                    "title": "KB Evidence",
                    "snippet": "Normalized knowledge-base evidence.",
                    "source": "knowledge_base",
                    "uri": "kb://evidence",
                }
            ],
            "output_preview": '{"items":[{"title":"ignored","snippet":"ignored","source":"knowledge_base"}]}',
        }
    }

    evidence = retrieval_evidence_service.normalize_task_payload(task)

    assert len(evidence) == 1
    assert evidence[0].title == "KB Evidence"
    assert evidence[0].snippet == "Normalized knowledge-base evidence."
