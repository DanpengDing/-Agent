"""
智能点餐助手 服务类封装

封装三个核心功能：
- smart_chat: 调用 assistant.py 中的 chat_with_assistant 函数
- delivery_check: 调用 check_delivery_range 函数 获取配送范围展示
- get_menu: 调用 get_menu_items_list 函数 获取菜品区域数据的展示
"""

from  smart_diancan.tools.amap_tool import  PathInputModel

def  get_menu():
    """获取菜品区域数据的展示"""
    from  smart_diancan.tools.db_tool import  get_menu_items
    return get_menu_items()


def  check_delivery_range(address:str,model:PathInputModel):
    """获取配送范围展示"""
    from  smart_diancan.tools.amap_tool import check_delivery_range
    return check_delivery_range(address,model)



def  smart_chat(user_query:str):
    """对话接口"""
    from  smart_diancan.agent.assistant import chat_with_assistant

    return chat_with_assistant(user_query)



