# 2-http_server.py
import uvicorn
from mcp.server.fastmcp import FastMCP

# 1. 创建 Server，注意这里并没有直接 run()，而是准备挂载
mcp = FastMCP("远程计算服务")

@mcp.tool()
def add(a: int, b: int) -> int:
    """计算两个数字的和"""
    print(f"Server Log: 收到请求 add({a}, {b})")
    return a + b

@mcp.tool()
def echo_message(msg: str) -> str:
    """回显消息"""
    return f"服务端收到: {msg}"

# 2. 启动 HTTP 服务
# FastMCP 底层使用 Starlette/FastAPI，虽然 mcp.run() 默认是 stdio，
# 但我们可以显式指定 transport='sse' (Server-Sent Events) 来支持 HTTP 流式传输
if __name__ == "__main__":
    print("HTTP MCP Server 正在启动，监听 http://localhost:8000")
    mcp.run(transport="sse")