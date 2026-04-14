import asyncio
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

# 【关键修正】使用文档中指定的 SSE 客户端类
from agents.mcp import MCPServerSse

BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


async def main():
    print("正在连接 SSE MCP Server...")

    # 【关键修正】
    # 1. 类名：MCPServerSse
    # 2. URL：指向 /sse (FastMCP 默认路径)
    async with MCPServerSse(
            name="My Remote Server",
            params={
                "url": "http://127.0.0.1:8000/sse",
                "timeout": 30,
            },
            cache_tools_list=True,
    ) as server_connection:
        print(f"已通过 SSE 连接到: {server_connection.name}")

        agent = Agent(
            name="Remote Caller",
            instructions="请调用远程工具回答问题。",
            model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
            mcp_servers=[server_connection],
        )

        print("\n--- 发送请求 ---")
        result = await Runner.run(agent, "请帮我计算 1024 加 2048 是多少")
        print(f"Agent 回复: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())