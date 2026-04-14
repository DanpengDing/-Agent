from mcp.server.fastmcp import FastMCP
from agents import function_tool
mcp = FastMCP("demo-server")

@mcp.tool()
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    print(f"Server Log: 正在查询 {city} 的天气...")
    return f"{city}的天气是晴天，39℃"

@mcp.tool()
def calculate_sum(a: int, b: int) -> int:
    """计算两个数的和"""
    return a + b

if __name__ == "__main__":
    mcp.run()