"""
智能点餐助手主程序
LangChain中Agent组件的作用:根据自然语言选择工具，调用工具。
该程序构建了一个包含工具选择功能的LLM系统(相当于LangChain中的Agent角色)，能够：
1. 自动选择合适的工具（常规咨询、菜品推荐、配送范围检查）
2. 调用相应工具并返回结果
3. 提供自然、友好的对话体验
手动实现Agent的机制（找工具 调用工具）

"""
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
from json import JSONDecodeError
from  typing import Dict, List,Any
from  smart_diancan.tools.llm_tool import  call_llm
from  smart_diancan.agent.mcp import general_inquiry,menu_inquiry,delivery_check_tool
import  json
import  time



class SmartRestaurantAssistant:
    """小助手类【Agent】"""
    def __init__(self):
        # 给Agent封装工具进去  tools未来需要封装工具的名字（函数的名字）和工具的对象（函数对象）
        self.tools={
           "general_inquiry":general_inquiry,
            "menu_inquiry":menu_inquiry,
            "delivery_check_tool":delivery_check_tool
        }

        self.instruction="""你是一个智能餐厅助手的意图分析器。
        请分析用户问题意图，并且选择最合适的工具来处理：

        工具说明：
        1. general_inquiry: 处理餐厅常规咨询（营业时间、地址、电话、优惠活动、预约等）
        2. menu_inquiry: 处理智能菜品推荐和咨询（推荐菜品、介绍菜品、询问菜品信息、点餐等）
        3. delivery_check_tool: 处理配送范围检查（查询某个地址是否在配送范围内、能否送达等）

        你必须严格按照以下JSON格式返回，不要包含任何其他文字：
        {
            "tool_name": "工具名称",
             "format_query": "处理后的用户问题"
        }

        正确示例：
        用户："你们几点营业？" -> {"tool_name": "general_inquiry", "format_query": "营业时间"}
        用户："推荐川菜系列的菜品" -> {"tool_name": "menu_inquiry", "format_query": "推荐川菜"}
        用户："能送到武汉大学吗？" -> {"tool_name": "delivery_check_tool", "format_query": "武汉大学"}

        重要规则：
        - 只返回纯JSON，不要有任何额外字符和解释
        - 确保JSON格式完全正确
        - tool_name必须是以下之一：general_inquiry, menu_inquiry, delivery_check_tool
        - format_query要简洁明了地概括用户问题

        记住：如果你错误的选择工具，你会受到惩罚，系统将面临崩溃。"""


        self.max_retries=3 # 最大重试次数  (包括第一次)
        self.backoff=1     # 重试的间隔

    def  _clean_llm_response(self,llm_response_content:str)->str:

        """清洗LLM的字符串内容"""
        # 切片操作 [start:end] 左边闭右开
        # 1.处理markdown格式的json    '```json {"tool_name": "general_inquiry", "format_query": "营业时间"}```'
        if llm_response_content.startswith("```json"):
            llm_response_content=llm_response_content[7:]
        if  llm_response_content.endswith("```"):
            llm_response_content=llm_response_content[:-3]

        # 2.处理json的嵌套(有效的json)的位置  ‘{"tool_name": {"name":"tom"}, "format_query": "营业时间"}’
        star_index=llm_response_content.find("{")  # 左边找打第一个
        end_index=llm_response_content.rfind("}")  # 右边找到第一个


        # 3.获取有效的json
        if star_index!=-1 and end_index!=-1 and end_index>star_index:
            clean_response=llm_response_content[star_index:end_index+1]
            return clean_response

        raise ValueError(f"{llm_response_content}不是有效的json格式字符串")


    def  _analyse_intention_fallback(self,user_query:str)->Dict[str,Any]:
        """
        基于关键词列表的规则进行降级处理【手动封装工具结构信息】
        TODO: 简单（性能高）---复杂（性能低）
        1.列表匹配
        2.正则匹配
        3.语义相似性匹配（嵌入模型：语义在空间的距离 夹角）
        4.LLM相似性匹配（文本模型）
        5.经典的机器学习算法（BF-IDF...）--->泛化能力弱、提前标注数据
        """

        logger.info("使用兜底意图分析")
        # 1.配送相关关键词列表
        delivery_keywords = ["配送", "送达", "送到", "送货", "外卖", "地址", "区域", "范围"]

        # 2.菜品推荐关键词列表
        menu_keywords = ["菜单", "菜品", "推荐", "点餐", "招牌", "特色", "什么好吃", "有什么菜"]

        # 检查配送意图
        if any(keyword in user_query for keyword in delivery_keywords):

            return {"tool_name": "delivery_check_tool", "format_query":user_query }
        # 检查菜单意图
        elif any(keyword in user_query for keyword in menu_keywords):
            return {"tool_name": "menu_inquiry", "format_query": user_query}

        # 默认常规咨询
        else:
            return {"tool_name": "general_inquiry", "format_query": user_query}



    def  _analyse_intention(self,user_query:str,last_error:str)->Dict[str,Any]:
        """意图分析"""

        instruction=self.instruction
        # 1.是否有错误
        if  last_error:
            instruction+=f"\n\n上次解析失败，错误信息：{last_error}\n请根据错误信息修正JSON格式，确保返回正确的JSON。"

        # 2.调用模型
        llm_response=call_llm(user_query,instruction)

        # 3.清洗模型的结果
        clean_response=self._clean_llm_response(llm_response)


        # 4.解析模型的结果(反序列化)
        llm_response_dict=json.loads(clean_response)
        # {'name':"xxx","age":18}  {"tool_name": "general_inquiry", "format_query": "营业时间"}

        # 5.校验字典的key是否有效
        if not all(key in  llm_response_dict for key in ["tool_name","format_query"]):
            raise ValueError(f"无效的工具结构信息：{llm_response_dict}")

        # 6.校验工具名是否在工具集中
        if  llm_response_dict['tool_name'] not in self.tools:
            raise ValueError(f"无效的工具结构信息：{llm_response_dict}")

        # 7.返回模型的结果(工具结构信息)
        return  llm_response_dict

    def analyse_intention_with_retry(self, user_query: str) -> Dict[str, Any]:
        """
        带重试的意图分析以及手动降级（金标准:重试和降级搭配使用）
        :param user_query:
        :return:
        """

        logger.info("带重试的意图分析")

        last_error=None
        # 1.重试
        for i  in range(self.max_retries):  # 0 1 2
            try:
                llm_response_dict=self._analyse_intention(user_query,last_error)
                logger.info("意图分析成功")
                return llm_response_dict
            except(ValueError,JSONDecodeError) as e:
                last_error=str(e)
                logger.warning(f"意图分析失败,开始第{i+1}次重试")  # 异常吃掉

                if i<self.max_retries-1:
                    time.sleep(self.backoff)



        logger.error(f"重试次数已经达到了最大{self.max_retries}")
        # 2.走降级处理
        return self._analyse_intention_fallback(user_query)



    def  execute_tool(self,tool_name:str,tool_param:str)->Dict[str,Any] | str:

       """执行工具"""
       try:
           # 1.判断工具是否在工具集中
           tool_obj=self.tools[tool_name]
           if tool_obj is None:
               raise ValueError(f"工具：{tool_name}不可用")
           # 2.调用工具
           # 2.1 常规问题咨询工具
           if tool_name=="general_inquiry":
               tool_result=tool_obj.invoke({"query":tool_param})# (str)
           # 2.2 菜品推荐问题工具
           elif tool_name=="menu_inquiry":
               tool_result=tool_obj.invoke({"query": tool_param}) # (str)
           # 2.3 配送距离范围查询工具
           else:
               tool_result=tool_obj.invoke({"address":tool_param,"travel_mode":"2"}) # 默认使用骑电动路线规划(dict)
           return tool_result
       except Exception as e:
           raise Exception(f"查询功能不可用,{str(e)}")



    def  invoke(self,user_query:str):
         """和小助手（Agent）聊天"""

         # 1.分析用户的意图（找工具）
         structured_tool=self.analyse_intention_with_retry(user_query)

         # 1.1 获取工具的名字
         tool_name=structured_tool['tool_name']
         # 1.2 获取工具的参数
         tool_param = structured_tool['format_query']
         print(f"工具信息->名字:{tool_name}:参数:{tool_param}")

         # 2.调用工具
         tool_result=self.execute_tool(tool_name,tool_param)

         # 3.返回工具结果
         return tool_result



# 全局方法（给service调用）【成员：方法 变量】
def chat_with_assistant(user_query:str):
    """和智能小助手对话"""
    try:
        # 1.实例化小助手
        assistant = SmartRestaurantAssistant()

        # 2.调用小助手的聊天方法
        assistant_response=assistant.invoke(user_query or  "介绍您们餐厅的基本信息")

        print(f"小助手的回复:\n{assistant_response}")
        # 3.返回小助手的结果
        return assistant_response
    except Exception as e:
        raise Exception(f"服务内部出现故障，暂不可用：{str(e)}")




if __name__ == '__main__':

    pass

    # 1.常规问题的对话
   # chat_with_assistant(user_query="你们餐厅的联系方式是多少?")

    # 2.菜品推荐问题的对话
    # chat_with_assistant(user_query="推荐鲁菜系列的菜品?")

    # 3.配送范围查询的对话
    # chat_with_assistant(user_query="清华大学能否配送到?")













