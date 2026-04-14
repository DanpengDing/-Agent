#!/usr/bin/env python3
"""Agent-to-Agent conversation simulation using the LangGraph A2A endpoint."""

import asyncio
import os
import uuid

import aiohttp
from aiohttp import ClientConnectorError


def extract_text(result: dict) -> str:
    """Best-effort extraction of response text from an A2A result."""
    for art in result.get("result", {}).get("artifacts", []) or []:
        for part in art.get("parts", []) or []:
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]

    msg = (result.get("result", {}).get("status", {}) or {}).get("message", {}) or {}
    for part in msg.get("parts", []) or []:
        if part.get("kind") == "text" and part.get("text"):
            return part["text"]

    return "(no text found)"


async def send_message(session, port, assistant_id, text, context_id=None, task_id=None):
    """Send an A2A message. Returns (response_text, returned_context_id, returned_task_id)."""
    url = f"http://127.0.0.1:{port}/a2a/{assistant_id}"

    message = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
        "messageId": str(uuid.uuid4()),
    }

    # A2A multi-turn continuity: reuse contextId and taskId across turns/agents
    if context_id:
        message["contextId"] = context_id
    if task_id:
        message["taskId"] = task_id

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {"message": message},
    }

    headers = {"Accept": "application/json"}
    async with session.post(url, json=payload, headers=headers) as response:
        result = await response.json()

    returned_context_id = result.get("result", {}).get("contextId") or context_id
    returned_task_id = result.get("result", {}).get("id")
    return extract_text(result), returned_context_id, returned_task_id


async def check_endpoint(session, port, assistant_id):
    """Preflight the A2A endpoint and fail with a readable error if it is unavailable."""
    url = f"http://127.0.0.1:{port}/a2a/{assistant_id}"
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "ping"}],
                "messageId": str(uuid.uuid4()),
            }
        },
    }
    try:
        async with session.post(url, json=payload, headers={"Accept": "application/json"}) as response:
            return response.status < 500
    except ClientConnectorError as exc:
        raise RuntimeError(
            f"A2A endpoint unavailable: {url}\n"
            f"Please start the agent service bound to port {port} before running this script."
        ) from exc


async def simulate_conversation():
    """Simulate a conversation between two agents."""

    agent_a_id = int(os.getenv("AGENT_A_ID", "1"))
    agent_b_id = int(os.getenv("AGENT_B_ID", "2"))
    port_a = int(os.getenv("AGENT_A_PORT", "2024"))
    port_b = int(os.getenv("AGENT_B_PORT", "2025"))

    if not agent_a_id or not agent_b_id:
        print("Set AGENT_A_ID and AGENT_B_ID environment variables")
        return

    message = "Hello! Let's have a conversation."
    context_id = None
    task_id = None

    async with aiohttp.ClientSession() as session:
        await check_endpoint(session, port_a, agent_a_id)
        await check_endpoint(session, port_b, agent_b_id)

        for i in range(3):
            print(f"--- Round {i + 1} ---")

            message, context_id, task_id = await send_message(
                session,
                port_a,
                agent_a_id,
                message,
                context_id=context_id,
                task_id=task_id,
            )
            print(f"Agent A: {message}")

            message, context_id, task_id = await send_message(
                session,
                port_b,
                agent_b_id,
                message,
                context_id=context_id,
                task_id=task_id,
            )
            print(f"Agent B: {message}\n")


if __name__ == "__main__":
    asyncio.run(simulate_conversation())
