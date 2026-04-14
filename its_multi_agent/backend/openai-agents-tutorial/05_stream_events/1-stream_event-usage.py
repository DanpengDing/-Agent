import asyncio

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent, ResponseReasoningSummaryTextDeltaEvent

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
    set_tracing_disabled,
)

from agents.items import ToolCallItem, ToolCallOutputItem, MessageOutputItem, ReasoningItem, HandoffOutputItem


#（分别演示）
BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY =  "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
# MODEL_NAME = "Qwen/Qwen3-32B"
MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"

# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
# MODEL_NAME = "qwen3-max"


# BASE_URL = "https://api.openai-proxy.org/v1"
# API_KEY =  "sk-3fNNVrOHy9YbLm87IQZdCe9VZDI9rA5CcCRfe9Nw2w9yyEAT"
# # MODEL_NAME = "gpt-5.2-pro"
# MODEL_NAME = "gpt-5"


client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


@function_tool
def get_weather(city: str) -> str:
    return f"天气信息: {city} 是晴天"


async def main():
    agent = Agent(
        name="天气助手",
        instructions="你是一个天气助手，用户问天气必须调用 get_weather，禁止编造。",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather]
    )

    #  关键：使用 run_streamed 才会有三类 StreamEvent
    result = Runner.run_streamed(agent, "武汉的天气怎么样？")

    async for event in result.stream_events():
        # ---------------------------------------------------------------------
        # 1) RawResponsesStreamEvent：模型“原始流”事件（token/片段增量）
        # ---------------------------------------------------------------------
        if event.type == "raw_response_event":
            # 1.1 文本增量（最常见）
            if isinstance(event.data, ResponseTextDeltaEvent):
                print("\n[text_delta]",event.data.delta, end="", flush=True)  # end="" 不要换行  flush=True 立刻清空缓冲区

            # 1.2 推理摘要增量
            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                # 你也可以选择打印到单独区域
                print("\n[reasoning_summary_delta]", event.data.delta, end="", flush=True)

        # ---------------------------------------------------------------------
        # 2) RunItemStreamEvent：执行过程结构化节点（工具/消息/推理/交接等）
        # ---------------------------------------------------------------------
        elif event.type == "run_item_stream_event":

            name = getattr(event, "name")

            # 2.1 工具调用
            if name == "tool_called" and isinstance(event.item, ToolCallItem):
                tool_name = event.item.raw_item.name
                tool_args = event.item.raw_item.arguments
                print(f"\n\n 调用工具: {tool_name} args={tool_args}")

            # 2.2 工具输出
            elif name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
                print(f"\n 工具输出: {event.item.output}")

            # 2.3 生成了一条对话消息（最终给用户看的那种）
            elif name == "message_output_created" and isinstance(event.item, MessageOutputItem):
                try:
                    msg = event.item.raw_item
                    print(f"\n message_output_created: {msg}")
                except Exception as e:
                    print("\n message_output_created")

            # 2.4 生成了一条推理项（Execution Plane 的“事实记录”）
            elif name == "reasoning_item_created" and isinstance(event.item, ReasoningItem):
                try:
                    summary = event.item.raw_item.summary
                    if summary:
                        print("\n reasoning_item_created:", summary[0].text[:200], "...")
                    else:
                        print("\n reasoning_item_created (no summary)")
                except Exception as  e:
                    print("\n reasoning_item_created")

            # 2.5 多 Agent 交接（如果你只有单 Agent，通常不会触发）
            elif name in ("handoff_occured", "handoff_requested") and isinstance(event.item, HandoffOutputItem):
                try:
                    src = event.item.raw_item.source_agent.name
                    tgt = event.item.raw_item.target_agent.name
                    print(f"\n {name}: {src} -> {tgt}")
                except Exception:
                    print(f"\n {name}")

            else:
                pass

        # ---------------------------------------------------------------------
        # 3) AgentUpdatedStreamEvent：当前运行 Agent 更新（多 Agent 编排更明显）
        # ---------------------------------------------------------------------
        elif event.type == "agent_updated_stream_event":
            print(f"\n\n👤 agent_updated_stream_event: {event.new_agent.name}")

    print("\n\nfinal_output:", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
