import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local import service_station


def test_missing_location_payload_requests_user_location():
    result = service_station._build_missing_location_payload("我要修电脑")
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["source"] == "missing_location"
    assert payload["needs_user_location"] is True
    assert "具体地址" in payload["ask_user"]
    assert "lat" not in payload
    assert "lng" not in payload


def test_normalize_location_query_strips_repair_station_noise():
    normalized = service_station._normalize_location_query("晋江市陈埭镇 电脑维修站")

    assert normalized == "晋江市陈埭镇"


def test_baidu_auth_failed_payload_does_not_ask_for_more_location():
    result = service_station._build_baidu_auth_failed_payload("晋江市陈埭镇 电脑维修站")
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["source"] == "baidu_auth_failed"
    assert "IP校验失败" in payload["error"]
    assert "needs_user_location" not in payload
