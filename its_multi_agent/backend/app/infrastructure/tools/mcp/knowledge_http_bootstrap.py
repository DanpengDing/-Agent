import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from config.settings import settings
from infrastructure.logging.logger import logger

from .knowledge_mcp_bootstrap import _is_port_open

_knowledge_http_process: subprocess.Popen | None = None


def _knowledge_http_workdir() -> Path:
    return Path(__file__).resolve().parents[4] / "knowledge"


def _knowledge_http_pythonpath() -> str:
    workdir = _knowledge_http_workdir()
    package_dir = workdir / ".python-packages"
    entries = [str(workdir)]
    if package_dir.exists():
        entries.insert(0, str(package_dir))
    return os.pathsep.join(entries)


def _knowledge_http_launcher_code(host: str, port: int) -> str:
    workdir = _knowledge_http_workdir()
    package_dir = workdir / ".python-packages"
    return (
        "import os, site, uvicorn; "
        f"os.chdir({workdir.as_posix()!r}); "
        f"site.addsitedir({str(package_dir)!r}); "
        f"uvicorn.run('api.main:create_fast_api', factory=True, host={host!r}, port={port!r})"
    )


def _knowledge_http_host_port() -> tuple[str, int]:
    parsed = urlparse(settings.KNOWLEDGE_BASE_URL or "http://127.0.0.1:8001")
    return parsed.hostname or "127.0.0.1", parsed.port or 8001


async def ensure_knowledge_http_server_started() -> None:
    global _knowledge_http_process

    host, port = _knowledge_http_host_port()
    if _is_port_open(host, port):
        return

    if _knowledge_http_process is None or _knowledge_http_process.poll() is not None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        _knowledge_http_process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _knowledge_http_launcher_code(host, port),
            ],
            cwd=str(_knowledge_http_workdir()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=creationflags,
        )
        logger.info("知识库 HTTP 服务已尝试后台启动: %s:%s", host, port)

    for _ in range(60):
        if _is_port_open(host, port):
            return
        if _knowledge_http_process is not None and _knowledge_http_process.poll() is not None:
            raise RuntimeError("知识库 HTTP 服务启动失败，进程已退出")
        await asyncio.sleep(0.25)

    raise RuntimeError(f"知识库 HTTP 服务未在预期时间内就绪: {host}:{port}")


async def cleanup_knowledge_http_server() -> None:
    global _knowledge_http_process

    if _knowledge_http_process is None:
        return

    if _knowledge_http_process.poll() is None:
        _knowledge_http_process.terminate()
        try:
            await asyncio.to_thread(_knowledge_http_process.wait, 5)
        except subprocess.TimeoutExpired:
            _knowledge_http_process.kill()
            await asyncio.to_thread(_knowledge_http_process.wait, 5)

    _knowledge_http_process = None
