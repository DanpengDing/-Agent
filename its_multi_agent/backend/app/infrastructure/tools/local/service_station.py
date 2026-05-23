import json
import math
from typing import Any
from urllib.parse import urlencode
import re

import stun
from agents import function_tool
from pymysql.cursors import DictCursor

from infrastructure.database.database_pool import pool
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import baidu_mcp_client


class BaiduMcpAuthError(RuntimeError):
    """百度地图 MCP 鉴权失败。"""


LOCATION_QUERY_NOISE_PATTERNS = [
    r"查询",
    r"查一下",
    r"搜索",
    r"找一下",
    r"最近的?",
    r"离我最近",
    r"附近",
    r"我要去",
    r"我想去",
    r"帮我找",
    r"导航去",
    r"电脑维修站",
    r"维修站",
    r"电脑维修",
    r"修电脑",
]


def bd09mc_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    x = lng
    y = lat

    if abs(y) < 1e-6 or abs(x) < 1e-6:
        return 0.0, 0.0

    out_lng = x / 20037508.34 * 180
    out_lat = y / 20037508.34 * 180
    out_lat = 180 / math.pi * (2 * math.atan(math.exp(out_lat * math.pi / 180)) - math.pi / 2)
    return out_lng, out_lat


def get_ip_via_stun():
    try:
        _, external_ip, _ = stun.get_ip_info()
        return external_ip
    except Exception as exc:
        logger.warning("[Location] STUN failed error=%s", exc)
        return None


def _safe_preview(value: Any, limit: int = 500) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}...(truncated)"


def _extract_mcp_text(tool_name: str, result: Any) -> str:
    content_list = getattr(result, "content", None)
    if not content_list:
        logger.warning("[BaiduMCP] tool=%s returned empty content result=%s", tool_name, _safe_preview(result))
        return ""

    first_content = content_list[0]
    text = getattr(first_content, "text", "")
    if not text:
        logger.warning(
            "[BaiduMCP] tool=%s first content has no text content=%s",
            tool_name,
            _safe_preview(first_content),
        )
        return ""

    logger.info("[BaiduMCP] tool=%s raw_text=%s", tool_name, _safe_preview(text, 1000))
    return text


def _parse_json_response(tool_name: str, raw_text: str) -> dict:
    if not raw_text:
        raise ValueError(f"{tool_name} returned empty JSON")

    if "Authentication failed" in raw_text and "IP校验失败" in raw_text:
        logger.error("[BaiduMCP] tool=%s auth failed raw_text=%s", tool_name, _safe_preview(raw_text, 1000))
        raise BaiduMcpAuthError("百度地图服务鉴权失败（APP IP校验失败），当前服务器 IP 不在百度地图 AK 白名单中。")

    try:
        return json.loads(raw_text)
    except Exception as exc:
        logger.error(
            "[BaiduMCP] tool=%s json parse failed error=%s raw_text=%s",
            tool_name,
            exc,
            _safe_preview(raw_text, 1000),
        )
        raise ValueError(
            f"{tool_name} returned non-JSON response: {_safe_preview(raw_text, 200)}"
        ) from exc


def _build_missing_location_payload(original_input: str) -> str:
    payload = json.dumps(
        {
            "ok": False,
            "error": "无法可靠解析用户当前位置，请先提供你的城市、区县、商圈或具体地址。",
            "source": "missing_location",
            "original_input": original_input,
            "needs_user_location": True,
            "ask_user": "请告诉我你现在在哪个城市、区县、商圈，或者直接发一个具体地址，我再帮你查最近的电脑维修服务站。",
        },
        ensure_ascii=False,
    )
    logger.info("[Location] missing location result=%s", payload)
    return payload


def _build_baidu_auth_failed_payload(original_input: str) -> str:
    payload = json.dumps(
        {
            "ok": False,
            "error": "百度地图服务鉴权失败（APP IP校验失败），当前服务器 IP 不在百度地图 AK 白名单中，暂时无法查询或导航附近维修站。",
            "source": "baidu_auth_failed",
            "original_input": original_input,
        },
        ensure_ascii=False,
    )
    logger.info("[Location] baidu auth failed result=%s", payload)
    return payload


def _normalize_location_query(user_input: str) -> str:
    text = (user_input or "").strip()
    if not text:
        return ""

    normalized = text
    for pattern in LOCATION_QUERY_NOISE_PATTERNS:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)

    normalized = re.sub(r"\s+", " ", normalized).strip(" ，,。；;、")
    return normalized or text.strip()


def build_baidu_map_direction_uri(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    origin_name: str = "用户位置",
    destination_name: str = "目的地",
    mode: str = "driving",
) -> str:
    query = urlencode(
        {
            "origin": f"latlng:{origin_lat},{origin_lng}|name:{origin_name}",
            "destination": f"latlng:{destination_lat},{destination_lng}|name:{destination_name}",
            "mode": mode,
            "region": "中国",
            "output": "html",
            "src": "multi_agent_repair_station",
        }
    )
    return f"https://api.map.baidu.com/direction?{query}"


@function_tool
def map_uri(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    origin_name: str = "用户位置",
    destination_name: str = "目的地",
    mode: str = "driving",
) -> str:
    uri = build_baidu_map_direction_uri(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
        origin_name=origin_name,
        destination_name=destination_name,
        mode=mode,
    )
    return json.dumps(
        {
            "ok": True,
            "uri": uri,
            "origin": {"lat": origin_lat, "lng": origin_lng, "name": origin_name},
            "destination": {"lat": destination_lat, "lng": destination_lng, "name": destination_name},
            "mode": mode,
        },
        ensure_ascii=False,
    )


@function_tool
async def resolve_user_location_from_text(user_input: str) -> str:
    logger.info("[Location] resolve start raw_input=%s", user_input)

    relative_locations = {
        "当前位置",
        "当前",
        "这里",
        "我这里",
        "我附近",
        "离我最近",
        "附近",
        "nearby",
        "here",
    }

    original_input = user_input.strip() if user_input else ""
    normalized_input = _normalize_location_query(original_input)
    if normalized_input in relative_locations:
        logger.info("[Location] relative term detected input=%s", normalized_input)
        normalized_input = ""
    if normalized_input.lower() in {"查询", "搜索", "查一下", "找一下"}:
        logger.info("[Location] generic lookup text detected input=%s", normalized_input)
        normalized_input = ""

    if normalized_input:
        try:
            logger.info("[Location] geocode start address=%s", normalized_input)
            geo_result = await baidu_mcp_client.call_tool(
                tool_name="map_geocode",
                arguments={"address": normalized_input},
            )
            raw_text = _extract_mcp_text("map_geocode", geo_result)
            data = _parse_json_response("map_geocode", raw_text)
            result = data["result"]

            if isinstance(result, dict) and "location" in result:
                lat = float(result["location"]["lat"])
                lng = float(result["location"]["lng"])
                payload = json.dumps(
                    {
                        "ok": True,
                        "lat": lat,
                        "lng": lng,
                        "source": "geocode",
                        "original_input": normalized_input,
                    },
                    ensure_ascii=False,
                )
                logger.info("[Location] geocode success result=%s", payload)
                return payload

            logger.warning("[Location] geocode invalid result=%s", _safe_preview(data, 1000))
        except BaiduMcpAuthError:
            return _build_baidu_auth_failed_payload(original_input)
        except Exception as exc:
            logger.warning("[Location] geocode failed address=%s error=%s", normalized_input, exc, exc_info=True)

    user_ip = get_ip_via_stun()
    logger.info("[Location] detected external_ip=%s", user_ip)

    if user_ip and user_ip not in ("127.0.0.1", "localhost", "::1"):
        try:
            logger.info("[Location] ip location start ip=%s", user_ip)
            ip_result = await baidu_mcp_client.call_tool("map_ip_location", {"ip": user_ip})
            raw_text = _extract_mcp_text("map_ip_location", ip_result)
            data = _parse_json_response("map_ip_location", raw_text)
            if data.get("status") != 0:
                raise ValueError(f"ip location status={data.get('status')} message={data.get('message')}")

            point = data.get("content", {}).get("point", {})
            x_str = point.get("x")
            y_str = point.get("y")
            if not x_str or not y_str:
                raise ValueError("missing x/y coordinates")

            lng, lat = bd09mc_to_bd09(float(x_str), float(y_str))
            payload = json.dumps(
                {
                    "ok": True,
                    "lat": lat,
                    "lng": lng,
                    "source": "ip",
                    "original_input": normalized_input,
                },
                ensure_ascii=False,
            )
            logger.info("[Location] ip location success result=%s", payload)
            return payload
        except BaiduMcpAuthError:
            return _build_baidu_auth_failed_payload(original_input)
        except Exception as exc:
            logger.warning("[Location] ip location failed ip=%s error=%s", user_ip, exc, exc_info=True)

    return _build_missing_location_payload(original_input)


@function_tool
def query_nearest_repair_shops_by_coords(lat: float, lng: float, limit: int = 3) -> str:
    connection = None
    cursor = None
    try:
        logger.info("[NearestShops] query start lat=%s lng=%s limit=%s", lat, lng, limit)
        connection = pool.connection()
        cursor = connection.cursor(DictCursor)

        sql = """
        SELECT
            id,
            service_station_name,
            province,
            city,
            district,
            address,
            phone,
            manager,
            manager_phone,
            opening_hours,
            repair_types,
            repair_specialties,
            repair_services,
            supported_brands,
            rating,
            established_year,
            employee_count,
            service_station_description,
            latitude,
            longitude,
            (
                6371 * acos(
                    cos(radians(%s)) *
                    cos(radians(latitude)) *
                    cos(radians(longitude) - radians(%s)) +
                    sin(radians(%s)) *
                    sin(radians(latitude))
                )
            ) AS distance_km
        FROM repair_shops
        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND ABS(latitude) <= 90
            AND ABS(longitude) <= 180
        ORDER BY distance_km ASC
        LIMIT %s
        """

        cursor.execute(sql, (lat, lng, lat, limit))
        rows = cursor.fetchall()
        logger.info("[NearestShops] found count=%s lat=%s lng=%s", len(rows), lat, lng)
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

        logger.debug("[NearestShops] first_row=%s", rows[0])

        payload = json.dumps(
            {
                "ok": True,
                "count": len(rows),
                "data": rows,
                "query": {"lat": lat, "lng": lng, "limit": limit},
            },
            ensure_ascii=False,
            default=str,
        )
        logger.info("[NearestShops] query result=%s", payload[:1200])
        return payload

    except Exception as exc:
        logger.error("[NearestShops] DB query failed error=%s", exc, exc_info=True)
        payload = json.dumps(
            {
                "ok": False,
                "source": "database_error",
                "error": f"查询附近服务站失败: {exc}",
                "query": {"lat": lat, "lng": lng, "limit": limit},
            },
            ensure_ascii=False,
        )
        logger.info("[NearestShops] query result=%s", payload)
        return payload
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
