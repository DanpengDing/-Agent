from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.knowledge_mcp_bootstrap import (
    cleanup_knowledge_mcp_server,
    ensure_knowledge_mcp_server_started,
)
from infrastructure.tools.mcp.mcp_servers import (
    baidu_mcp_client,
    knowledge_mcp_client,
)


async def mcp_connect():
    # 应用启动时只初始化仍在使用的 MCP。
    try:
        await ensure_knowledge_mcp_server_started()
        logger.info("知识库 MCP 服务已就绪")
    except Exception as e:
        logger.error("知识库 MCP 服务启动失败: %s", str(e))

    try:
        await knowledge_mcp_client.connect()
        logger.info("知识库 MCP 连接成功")
    except Exception as e:
        logger.error("知识库 MCP 连接失败: %s", str(e))

    try:
        await baidu_mcp_client.connect()
        logger.info("百度地图 MCP 连接成功")
    except Exception as e:
        logger.error("百度地图 MCP 连接失败: %s", str(e))


async def mcp_cleanup():
    try:
        await baidu_mcp_client.cleanup()
    except Exception as e:
        logger.warning("百度地图 MCP 清理时出现非致命错误: %s", e)

    try:
        await knowledge_mcp_client.cleanup()
    except Exception as e:
        logger.warning("知识库 MCP 清理时出现非致命错误: %s", e)

    try:
        await cleanup_knowledge_mcp_server()
    except Exception as e:
        logger.warning("知识库 MCP 服务清理失败: %s", e)
