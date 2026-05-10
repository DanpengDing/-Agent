from services.approval_details_service import build_service_station_approval_details


def test_service_station_approval_details_describes_action_not_user_query():
    details = build_service_station_approval_details("我要修电脑")

    assert details == "待执行请求：查询附近维修站"
    assert "我要修电脑" not in details
