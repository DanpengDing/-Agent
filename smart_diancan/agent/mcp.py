"""
实现LangChain中各个工具的定义（定义三个工具、工具一：实现常规问题的对话回答 工具二：实现菜品查询问题对话 工具三：实现距离范围配送问题对话）
"""
import logging
import os
from langchain_core.tools import tool, ToolException
from smart_diancan.tools.llm_tool import call_llm
from smart_diancan.tools.pinecone_tool import search_menu_items_with_ids
from smart_diancan.tools.amap_tool import  check_delivery_range,PathInputModel
from typing import Dict, Any


def load_prompt_template(prompt_file_name) -> str:
    """加载指定目录下的提示词文件"""
    try:
        # 1.定位到当前文件的路径
        current_file_path = os.path.abspath(
            __file__)  # D:\\develop\\develop\\workspace\\pycharm\\bj250716\\smart_diancan\\agent\\mcp.py
        current_file_dir = os.path.dirname(
            current_file_path)  # D:\\develop\\develop\\workspace\\pycharm\\bj250716\\smart_diancan\\agent
        project_dir = os.path.dirname(
            current_file_dir)  # D:\\develop\\develop\\workspace\\pycharm\\bj250716\\smart_diancan

        # 2.拼接提示词完整路径
        prompt_path = os.path.join(project_dir, "prompt",
                                   f"{prompt_file_name}.txt")  # D:\\develop\\develop\\workspace\\pycharm\\bj250716\\smart_diancan\\prompt\\general_inquiry.txt

        # 3.读取指定路径文件下的文件
        with  open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logging.error(f"无法加载指定文件{prompt_file_name}的提示词内容")
        return "无法加载到指定的提示词内容，请根据用户的问题，直接提供帮助"


@tool
def general_inquiry(query: str) -> str:
    """
        常规问询工具

        处理用户的一般性问题，包括但不限于：
        - 餐厅介绍和服务信息
        - 营业时间和联系方式
        - 优惠活动和会员服务
        - 其他非菜品相关的咨询

        Args:
            query: 用户的问询内容
            context: 可选的上下文信息，用于提供更精准的回复

        Returns:
            str: 针对用户问询的智能回复

        Raises:
            ToolException: 当处理查询时发生错误
        """
    try:
        # 1.加载常规问题的提示词
        prompt_template = load_prompt_template("general_inquiry")

        # 从记忆组件读取QA TODO(可扩展)
        context = ""
        full_query = f"当前历史对话的内容:\n{context}\n\n当前用户问题:\n{query}\n\n,请基于以上的上下文信息来回答用户问题" if context else f"当前没有历史对话，当前用户问题:\n{query}\n\n,请基于一般信息来回答用户问题"

        # 2.调用LLM
        llm_response = call_llm(full_query, prompt_template)

        # 将QA写入到记忆组件（TODO 可扩展）
        # 3.直接返回
        return llm_response
    except Exception as e:
        raise ToolException(f"常规问询失败{e}")


@tool
def menu_inquiry(query: str) -> Dict[str, Any]:
    """
    智能菜品咨询工具

    专门处理与菜品相关的所有查询，包括：
    - 菜品介绍和详细信息
    - 价格和营养信息
    - 菜品推荐和搭配建议
    - 过敏原和饮食限制相关问题
    - 菜品可用性和特色介绍

    该工具会自动通过语义搜索找到最相关的菜品信息，然后基于这些信息回答用户问题。

    Args:
        query: 用户关于菜品的具体问题

    Returns:
        Dict[str, Any]: 包含推荐建议和菜品ID的字典
        {
            "recommendation": "基于菜品信息的推荐建议",
            "menu_ids": ["菜品ID1", "菜品ID2"]
        }

    Raises:
        ToolException: 当处理菜品查询时发生错误
    """


    try:
        # 1.加载菜品推荐问题的提示词
        prompt_template = load_prompt_template("menu_inquiry")

        # 2.上下文（向量数据库）
        # 2.1 利用文本嵌入模型（作用:利用语义从向量数据库找相似性菜品）
        similar_result = search_menu_items_with_ids(query)

        if similar_result and similar_result['contents']:
            menu_contents_context = "\n".join([f" -{item}" for item in similar_result['contents']])
            full_query = f"当前从向量数据库中检索到的菜品信息:\n{menu_contents_context}\n\n当前用户问题:\n{query}\n\n,请基于以上检索到的菜品信息，回答来用户提出的相关问题"

        else:
            full_query = f"暂无相关菜品信息:\n\n当前用户问题:\n{query}\n\n,请基于一般的菜品知识信息，回答来用户提出的相关问题"

        # 3.调用模型(分析总结：menu_contents_context：宫爆鸡丁 麻婆豆腐 query：推荐宫爆鸡丁  prompt_template：“”)
        # 3.1 利用文本模型（作用：对向量数据库中检索到的菜品以及当前问题在做一次总结、提取、过滤 最终推荐和你问题最相似的菜品）
        llm_response=call_llm(full_query,prompt_template) # 推荐

        # 4.封装字典结构返回
        return {
            "recommendation": llm_response,
            "menu_ids":similar_result['ids'] # 简单用similar_result的ids充当 实际用正则解析llm_response 提取模型返回的菜品id 作为真正的推荐出来的菜品id(TODO)
        }
    except Exception as e:
        raise ToolException(f"菜品咨询处理失败:{e}")


@tool
def delivery_check_tool(address: str, travel_mode: PathInputModel) -> str:
    """
    配送范围检查工具

    检查指定地址是否在配送范围内，并提供距离信息。

    Args:
        address: 配送地址
        travel_mode: 距离计算方式 (1=步行距离, 2=骑行距离, 3=驾车距离)

    Returns:
        str: 配送检查结果的格式化信息

    Raises:
        ToolException: 当配送检查失败时
    """

    # 说明：不需要调用任何模型（靠模型算距离，不靠谱） 调用自己封装的配送范围查询的函数
    try:
        # 1.调用配送范围查询函数
        check_delivery_range_result=check_delivery_range(address,travel_mode)

        # 2.处理数据直接返回
        if check_delivery_range_result["status"] == "success":
            status_text = "✅ 可以配送" if check_delivery_range_result["in_range"] else "❌ 超出配送范围"

            response = f"""
                配送信息查询结果：
                配送地址：{check_delivery_range_result['formatted_address']}
                配送距离：{check_delivery_range_result['distance']}公里 (骑电车)
                配送状态：{status_text}
                            """.strip()

        else:
            response = f"❌ 配送查询失败：{check_delivery_range_result['message']}"

        return    response
    except Exception as e :
        raise ToolException(f"配送范围检查失败:{e}")


if __name__ == '__main__':

    print("\n1.常规问题工具的测试")

    # 1.1 参数用字符串(工具参数只有一个)
    # general_inquiry_result=general_inquiry.invoke(input="请问您们餐厅的营业时间是什么时候?")
    # 1.2 参数用字符串(工具参数只有一个)
    # general_inquiry_result=general_inquiry.invoke("请问您们餐厅的营业时间是什么时候?")
    # 1.3 参数用字典(工具参数只有一个)
    general_inquiry_result = general_inquiry.invoke({"query":"请问您们餐厅的营业时间是什么时候"})

    print(f"常规问题工具的结果:{general_inquiry_result}") # str

    print("\n2.菜品推荐问题工具的测试")

    # menu_inquiry_result = menu_inquiry.invoke({"query":"请给我推荐一些素食的菜品"})
    menu_inquiry_result = menu_inquiry.invoke({"query":"请给我推荐蒜蓉西兰花菜品"})
    print(f"菜品推荐问题工具的结果:{menu_inquiry_result}") # dict
    # 菜品推荐问题工具的结果:
    # {
    #   'recommendation': '您好！根据您的需求，我为您推荐以下两款美味的素食菜品：\n\n1. 清炒时蔬（¥15.00）\n这款菜品选用当季新鲜时令蔬菜，搭配蒜蓉清炒而成。它的特点在于保留了蔬菜本身的鲜嫩口感，清淡爽口，非常适合追求健康饮食的人群。清炒的方式最大限度地锁住了蔬菜中的营养成分，让您既能享受美味又能保持身材。而且它没有任何过敏原，您可以放心食用。\n\n2. 蒜蓉西兰花（¥12.00）\n这道菜采用新鲜的西兰花为主料，配以蒜蓉蒸炒而成。西兰花富含维生素C、胡萝卜素等营养成分，对身体非常有益。这道菜口感清新，带有浓郁的蒜香，既保留了西兰花的脆嫩又不失其原汁原味。同样，这道菜也是素食，且没有过敏原，非常适合您选择。\n\n如果您想要更加清淡健康的菜肴，我会更倾向于推荐清炒时蔬；如果您喜欢浓郁的蒜香味，则可以尝试蒜蓉西兰花。这两款菜品都是素食，且均不含过敏原，您可以根据自己的口味喜好进行选择。希望我的推荐能够帮助到您！',
    #   'menu_ids': ['3', '5'] # 向量数据库id
    # }
    # 菜品推荐问题工具的结果:
    # {
    #   'recommendation': '您好！很高兴为您推荐蒜蓉西兰花这道美味又健康的菜品。\n\n**蒜蓉西兰花**\n- **价格**: ¥12.00\n- **特色**: 这道菜选用新鲜的西兰花，搭配蒜蓉调味，简单却充满浓郁的蒜香。采用蒸炒的烹饪方式，最大程度地保留了西兰花的营养成分，口感鲜嫩脆爽。\n- **营养亮点**: 西兰花富含维生素C、膳食纤维以及多种抗氧化物质，非常适合作为减肥期间的健康选择。\n- **特别之处**: 不仅味道鲜美，而且完全不含任何过敏原，是一款非常安全的素食选择。\n- **搭配建议**: 可以作为主菜搭配米饭或面条一起食用；也可以与豆腐、鸡蛋等其他食材搭配，增加菜肴的层次感。\n- **性价比**: 价格实惠，每份仅需12元，让您以亲民的价格享受高品质的健康美食。\n\n如果您对这道菜感兴趣的话，可以放心点餐，相信它一定会给您带来美妙的味觉体验！如果您还有其他特殊需求或者想要了解更多信息，我很乐意为您提供帮助。',
    #   'menu_ids': ['5', '3']   # 向量数据库id
    #  }


    print("\n3.菜品配送范围查询工具的测试")
    delivery_check_tool_result=delivery_check_tool.invoke({"address":"请问海淀区清华大学能配送到嘛?","travel_mode":"2"})
    # 注意：
    # delivery_check_tool_result=delivery_check_tool.invoke({"address":"请问昌平区温都水城能配送到嘛?","travel_mode":"2"})
    # delivery_check_tool_result=delivery_check_tool(address="请问昌平区温都水城能配送到嘛?",travel_mode=2)
    # data={"address": "请问昌平区温都水城能配送到嘛?", "travel_mode": 2}
    # delivery_check_tool_result=delivery_check_tool(**data)


    print(f"配送范围查询工具的结果:{delivery_check_tool_result}") # str















