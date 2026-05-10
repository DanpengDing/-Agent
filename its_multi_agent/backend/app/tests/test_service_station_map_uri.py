import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.local.service_station import build_baidu_map_direction_uri


def test_build_baidu_map_direction_uri_contains_coordinates_and_names():
    uri = build_baidu_map_direction_uri(
        origin_lat=24.8739,
        origin_lng=118.6757,
        destination_lat=24.9012,
        destination_lng=118.6001,
        origin_name="用户位置",
        destination_name="泉州维修站",
    )

    assert uri.startswith("https://api.map.baidu.com/direction?")
    assert "origin=latlng%3A24.8739%2C118.6757%7Cname%3A%E7%94%A8%E6%88%B7%E4%BD%8D%E7%BD%AE" in uri
    assert "destination=latlng%3A24.9012%2C118.6001%7Cname%3A%E6%B3%89%E5%B7%9E%E7%BB%B4%E4%BF%AE%E7%AB%99" in uri
    assert "mode=driving" in uri
