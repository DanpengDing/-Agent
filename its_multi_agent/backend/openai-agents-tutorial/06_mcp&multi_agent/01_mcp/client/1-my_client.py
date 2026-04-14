# 文件名: client_agent.py
import asyncio
from pathlib import Path
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

from agents.mcp import MCPServerStdio

BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


async def main():
    # 获取 server.py 的绝对路径，确保 subprocess 能找到它
    server_script_path = Path(__file__).parent.parent /"server"/ "1-my_server.py"

    # 使用 async with 上下文管理器
    # 这样当 with 块结束时，Server 进程会被自动杀掉，连接会自动断开
    async with MCPServerStdio(
            name="My Local Python Server",
            # params 字典定义了如何启动这个 Server
            params={
                "command": "python",  # 执行的命令
                "args": [str(server_script_path)],  # 命令参数
            }
    ) as server_connection:
        # 此时 server_connection 已经是一个连接好的对象了
        print(f"已连接到 MCP Server: {server_connection.name}")

        # 创建 Agent，将连接对象传入 mcp_servers 列表
        agent = Agent(
            name="Weather Assistant",
            instructions="你可以使用工具查询天气或计算数字。",
            model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
            mcp_servers=[server_connection],
        )

        print("--- 第一轮：查天气 ---")
        result1 = await Runner.run(agent, "武汉天气怎么样？")
        print(f"Agent: {result1.final_output}")

        print("\n--- 第二轮：做计算 ---")
        result2 = await Runner.run(agent, "算一下 88 加 99 等于多少")
        print(f"Agent: {result2.final_output}")


if __name__ == "__main__":
    asyncio.run(main())