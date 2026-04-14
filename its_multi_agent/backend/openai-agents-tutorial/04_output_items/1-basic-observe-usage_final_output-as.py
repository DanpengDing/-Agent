import asyncio
from openai import AsyncOpenAI
from pydantic import BaseModel
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled

# 配置保持不变
BASE_URL = "https://api.openai-proxy.org/v1"
API_KEY = "sk-3fNNVrOHy9YbLm87IQZdCe9VZDI9rA5CcCRfe9Nw2w9yyEAT"
MODEL_NAME = "gpt-5-nano"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)

# 1. 定义最终想要的结构 (保持不变)
class Person(BaseModel):
    name: str
    age: int
    source: str  # 加个字段，证明是从数据库来的

# 2. 定义一个模拟数据库查询的工具
# 注意：工具返回的是字符串，不是对象。Agent 负责把字符串变成对象。
@function_tool
def query_database(user_id: int) -> str:
    """根据用户ID查询数据库中的详细信息"""
    print(f"\n[模拟数据库] 正在查询 ID: {user_id} ...")
    if user_id == 8888:
        # 模拟数据库返回的原始脏数据
        return "DB_RESULT: Found user. Name: 王五. Age: 42. Region: CN-East."
    return "DB_RESULT: User not found."

async def main():
    agent = Agent(
        name="数据库查询助手",
        # 指令非常关键：告诉它必须先查库，再填表
        instructions="你是一个用户信息查询助手。当用户提供ID时，必须先使用工具查询数据库，然后根据查询结果提取结构化信息。",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[query_database], # 注册新工具
        output_type=Person      # 强制最终输出类型
    )

    # 输入只给 ID，强制 Agent 必须用工具才能知道名字
    input_text = "帮我查询ID为8888的用户信息"
    print(f"--- 用户输入: {input_text} ---")



    result = await Runner.run(agent, input_text)

    # 3. 使用 final_output_as 进行类型转换
    # 此时 final_output 应该是根据工具返回值生成的 Person 对象
    person_data = result.final_output_as(Person)

    print("\n--- 1. 查看中间过程 (RunItem) ---")
    # 这里会看到：ToolCall (工具调用) -> ToolOutput (工具结果) -> Response (最终回复)
    for i, item in enumerate(result.new_items):
        item_type = type(item).__name__
        # 打印一下具体内容，看看 Agent 是怎么一步步操作的
        content_preview = str(item.raw_item)[:100].replace('\n', ' ')
        print(f"步骤 {i+1} [{item_type}]: {content_preview}...")

    print("\n--- 2. 验证最终结果 (final_output_as) ---")
    print(f"对象类型: {type(person_data)}")
    print(f"姓名: {person_data.name}")
    print(f"年龄: {person_data.age}")
    print(f"来源: {person_data.source}")

if __name__ == "__main__":
    asyncio.run(main())