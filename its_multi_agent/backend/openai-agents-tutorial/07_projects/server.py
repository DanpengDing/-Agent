import json
from typing import Optional, AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
    set_tracing_disabled,
    ModelSettings,
)

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)

@function_tool
def get_weather(city: str) -> str:
    return f"{city}：晴，24℃，风力2级"

agent = Agent(
    name="天气助手",
    instructions=(
        "你是天气助手。\n"
        "用户问天气时必须调用 get_weather 工具获取结果，禁止编造。\n"
        "如果用户没说城市，请追问城市。\n"
        "如果用户只是打招呼或闲聊，不要调用工具，直接礼貌回应。\n"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_weather],
    # 关键：不要 required，否则用户说“你好”也会被迫工具调用
    model_settings=ModelSettings(tool_choice="auto"),
)

def sse(event: str, data: dict) -> str:
    return f"event: {event}\n" f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

async def run_agent_to_sse(user_text: str, conversation_id: Optional[str]) -> AsyncGenerator[str, None]:
    result = Runner.run_streamed(agent, user_text)

    tool_name_by_call_id: dict[str, str] = {}

    try:
        async for ev in result.stream_events():

            if ev.type == "run_item_stream_event":
                name = getattr(ev, "name", None)

                if name == "tool_called":
                    print("工具调用:", ev.item)
                    tool_name = ev.item.raw_item.name
                    call_id = getattr(ev.item.raw_item, "call_id", None)
                    if call_id:
                        tool_name_by_call_id[call_id] = tool_name
                    yield sse("tool_started", {"tool_name": tool_name, "call_id": call_id})

                elif name == "tool_output":
                    print("工具输出:", ev.item)
                    # ToolCallOutputItem 通常是 dict：{'call_id': 'xxx', 'output': '...', 'type': ...}
                    out = ev.item
                    raw_item=out.raw_item
                    call_id=raw_item.get("call_id")
                    if call_id:
                        tool_name=tool_name_by_call_id[call_id]
                        yield sse("tool_completed", {"tool_name": tool_name, "tool_result": out.output})

            if ev.type == "raw_response_event" and isinstance(ev.data, ResponseTextDeltaEvent):
                yield sse("text_delta", {"text": ev.data.delta})

            if ev.type == "agent_updated_stream_event":
                yield sse("agent_updated", {"agent_name": ev.new_agent.name})

        yield sse("run_completed", {"final_output": result.final_output})

    except Exception as e:
        yield sse("error", {"message": str(e)})


@app.get("/api/chat/sse")
async def chat_sse_get(query: str, conversation_id: Optional[str] = None):

    async def gen():
        async for chunk in run_agent_to_sse(query, conversation_id):
            yield chunk
    return StreamingResponse(gen(), media_type="text/event-stream")


if  __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
