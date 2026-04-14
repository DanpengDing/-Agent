from knowledge_mcp.knowledge_mcp_server import mcp


if __name__ == "__main__":
    print("Knowledge MCP Server 正在启动，默认 SSE 地址为 http://127.0.0.1:9000/sse")
    mcp.run(transport="sse")
