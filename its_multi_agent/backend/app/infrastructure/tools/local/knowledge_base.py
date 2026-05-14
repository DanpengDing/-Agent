import asyncio
from typing import Dict

import httpx
from agents import function_tool

from config.settings import settings
from infrastructure.logging.logger import logger


@function_tool
async def query_knowledge(question: str) -> Dict:
    """
    Query the knowledge base service for technical documents or troubleshooting results.
    """

    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            response = await client.post(
                url=f"{settings.KNOWLEDGE_BASE_URL}/query",
                json={"question": question},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            logger.error("knowledge timeout error=%s", exc)
            return {
                "ok": False,
                "status": "error",
                "source": "http_timeout",
                "error_msg": str(exc),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("knowledge upstream http error=%s", exc)
            return {
                "ok": False,
                "status": "error",
                "source": "upstream_http_error",
                "error_msg": str(exc),
            }
        except httpx.HTTPError as exc:
            logger.error("knowledge http error=%s", exc)
            return {
                "ok": False,
                "status": "error",
                "source": "http_error",
                "error_msg": str(exc),
            }
        except Exception as exc:
            logger.error("knowledge unknown error=%s", exc)
            return {
                "ok": False,
                "status": "error",
                "source": "unknown_error",
                "error_msg": str(exc),
            }


async def main():
    result = await query_knowledge(question="电脑不能开机怎么解决?")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
