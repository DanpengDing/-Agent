import asyncio
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from config.settings import settings
from infrastructure.logging.logger import logger

_knowledge_mcp_process: subprocess.Popen | None = None


def _knowledge_mcp_script_path() -> Path:
    return Path(__file__).resolve().parents[4] / "knowledge" / "knowledge_mcp" / "knowledge_mcp_server.py"


def _knowledge_mcp_workdir() -> Path:
    return _knowledge_mcp_script_path().parent


def _knowledge_mcp_host_port() -> tuple[str, int]:
    parsed = urlparse(settings.KNOWLEDGE_MCP_URL or "http://127.0.0.1:9000/sse")
    return parsed.hostname or "127.0.0.1", parsed.port or 9000


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def ensure_knowledge_mcp_server_started() -> None:
    global _knowledge_mcp_process

    host, port = _knowledge_mcp_host_port()
    if _is_port_open(host, port):
        return

    if _knowledge_mcp_process is None or _knowledge_mcp_process.poll() is not None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _knowledge_mcp_process = subprocess.Popen(
            [sys.executable, str(_knowledge_mcp_script_path())],
            cwd=str(_knowledge_mcp_workdir()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        logger.info("已触发本地知识库 MCP 服务启动")

    for _ in range(40):
        if _is_port_open(host, port):
            return
        if _knowledge_mcp_process is not None and _knowledge_mcp_process.poll() is not None:
            raise RuntimeError("知识库 MCP 服务进程已退出，未能成功启动")
        await asyncio.sleep(0.25)

    raise RuntimeError(f"知识库 MCP 服务未在预期时间内启动: {host}:{port}")


async def cleanup_knowledge_mcp_server() -> None:
    global _knowledge_mcp_process

    if _knowledge_mcp_process is None:
        return

    if _knowledge_mcp_process.poll() is None:
        _knowledge_mcp_process.terminate()
        try:
            await asyncio.to_thread(_knowledge_mcp_process.wait, 5)
        except subprocess.TimeoutExpired:
            _knowledge_mcp_process.kill()
            await asyncio.to_thread(_knowledge_mcp_process.wait, 5)

    _knowledge_mcp_process = None
