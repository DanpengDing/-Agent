import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from agents.items import ReasoningItem, MessageOutputItem

# --- 配置部分 ---
BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"

# 【建议】: 如果想稳定测试 ReasoningItem，建议尝试 DeepSeek-R1 或 QwQ
# 如果坚持用 Qwen3，请确保该 API 确实支持通过 standard reasoning 字段返回思考
# MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
MODEL_NAME = "Qwen/Qwen3-32B"
# 或者保持: MODEL_NAME = "Qwen/Qwen2.5-32B-Instruct" (注意: 普通版可能只输出文本内容而非ReasoningItem)


# BASE_URL = "https://api.openai-proxy.org/v1"
# API_KEY =  "sk-3fNNVrOHy9YbLm87IQZdCe9VZDI9rA5CcCRfe9Nw2w9yyEAT"
# # MODEL_NAME = "gpt-5.2-pro"
# MODEL_NAME = "gpt-5"




client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)


@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息，包含具体的数值"""
    # 这里模拟返回一个具体的数值，方便模型做数学题
    return f"数据源返回: {city}的气温是 24 摄氏度"


async def main():
    agent = Agent(
        name="数学与天气专家",
        # 【关键修改】: 这里的指令强制模型展现思考过程
        instructions=(
            "你是一个逻辑严密的数学家，同时也是气象专家。"
        ),
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather]
    )

    # 提出一个需要 "工具 + 数学推理" 的复杂问题
    complex_task = "帮我查一下武汉的气温，然后告诉我这个数字是不是质数？如果不是，它离最近的质数相差多少？"

    print(f"--- 任务: {complex_task} ---")
    result = await Runner.run(agent, complex_task)

    for item in result.new_items:
        # 专门捕获 ReasoningItem
        if isinstance(item, ReasoningItem):
            # 注意：不同厂商返回的结构可能不同，稳妥起见直接打印 content
            print("\n模型回答【原始事件】:", item.raw_item)
            print("\n思考完整内容:",item.raw_item.summary[0].text)  # 思考

    print(f"\n--- Agent最终输出 ---\n{result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())