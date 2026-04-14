import asyncio
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

# 使用官网文档中的类
from agents.mcp import MCPServerStreamableHttp

BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


async def main():
    print("正在连接 MCP Server...")


    # 1. 类名：使用 MCPServerStreamableHttp
    # 2. URL：指向 /mcp
    async with MCPServerStreamableHttp(
            name="Remote Server",
            params={
                "url": "http://localhost:8000/mcp",
                "timeout": 30,
            },
            cache_tools_list=True,
    ) as server_connection:
        print(f"已连接到: {server_connection.name}")

        agent = Agent(
            name="Remote Caller",
            instructions="请调用远程工具回答问题。",
            model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
            mcp_servers=[server_connection],
        )


        print("\n--- 发送请求 ---")
        result = await Runner.run(agent, "请帮我计算 55 加 66")
        print(f"Agent 回复: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())