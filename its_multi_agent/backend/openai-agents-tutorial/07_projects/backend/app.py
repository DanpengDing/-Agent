"""
完整的智能客服后端实现
文件：backend/app.py
"""
import json
from typing import Optional, AsyncGenerator

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

# 1. 创建FastAPI应用
app = FastAPI(title="智能客服系统", version="1.0.0")

# 2. 配置CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware, # CORSMiddleware 会自动拦截后端的响应 并贴上这些标签 Access-Control-Allow-Origin Access-Control-Allow-Methods Access-Control-Allow-Headers
    allow_origins=["*"],  # 生产环境应限制为特定域名
    allow_credentials=True,  # cookie(自定义的key value)(user_id)
    allow_methods=["*"],     # 任意的请求都可以（POST）
    allow_headers=["*"],     #  请求头中带上自己的信息（token）
)



# 3. 配置模型客户端
BASE_URL = "https://api.siliconflow.cn/v1"  # 可替换为其他兼容OpenAI的接口
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"  # 使用的模型名称

# 创建异步客户端（必须使用AsyncOpenAI）
client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)  # 禁用tracing，避免401错误


# 4. 定义工具函数
@function_tool
def get_weather(city: str) -> str:
    """
    获取城市天气信息（模拟工具）

    在实际应用中，这里应该：
    1. 调用真实的天气API（如和风天气、OpenWeatherMap）
    2. 处理API响应
    3. 返回格式化的天气信息

    Args:
        city: 城市名称

    Returns:
        格式化的天气信息字符串
    """
    # 模拟天气数据 - 实际应调用真实API
    weather_data = {
        "北京": "北京：晴，24℃，风力2级，空气质量良",
        "上海": "上海：多云，26℃，风力3级，空气质量优",
        "武汉": "武汉：阴，22℃，风力1级，空气质量良",
        "广州": "广州：阵雨，28℃，风力2级，空气质量优"
    }
    # 返回对应城市的天气，或默认信息
    return weather_data.get(city, f"{city}：天气信息暂时无法获取")

# 5. 创建Agent实例
agent = Agent(
    name="天气助手",
    instructions=(
        "你是专业的天气助手，专门回答天气相关问题。"
    ),
    # 模型配置
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    # 可用工具列表
    tools=[get_weather],
    # 模型设置：auto表示让模型自主决定是否调用工具(required:强制任务一定要模型调用（找）工具)--->工具不能解决该问题，自己给你解决。
    model_settings=ModelSettings(tool_choice="required"),
)


# 6. SSE事件生成器函数
def sse(event: str, data: dict) -> str:
    """
    将事件和数据格式化为SSE格式

    SSE格式规范：
    event: {event_name}
    data: {json_data}

    注意：每个事件必须以两个换行符结束
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 7. Agent执行与SSE转换的核心函数
async def run_agent_to_sse(
        user_text: str
) -> AsyncGenerator[str, None]:
    """
    运行Agent并将执行过程转换为SSE事件流

    这个函数是系统的核心，它：
    1. 使用run_streamed方法运行Agent（获取流式结果）
    2. 监听不同类型的StreamEvent
    3. 将StreamEvent转换为SSE格式
    4. 通过生成器逐段发送给客户端

    Args:
        user_text: 用户输入的问题

    Yields:
        SSE格式的事件字符串
    """
    # 记录工具调用ID到工具名称的映射
    tool_name_by_call_id: dict[str, str] = {}

    # 使用run_streamed运行Agent（这是关键！）
    # run_streamed返回的是RunResultStreaming对象，支持异步迭代
    result = Runner.run_streamed(agent, user_text)

    try:
        # 异步迭代处理所有事件
        async for event in result.stream_events():

            # 1. 处理RunItemStreamEvent类型的事件
            if event.type == "run_item_stream_event":
                event_name = event.name

                # 1.1 工具开始调用
                if event_name == "tool_called":
                    print(f"工具调用: {event.item}")

                    # 提取工具信息
                    tool_name = event.item.raw_item.name
                    call_id = getattr(event.item.raw_item, "call_id", None)

                    # 保存工具调用ID到名称的映射（用于后续匹配）
                    if call_id:
                        tool_name_by_call_id[call_id] = tool_name

                    # 生成工具开始事件
                    yield sse("tool_started", {
                        "tool_name": tool_name,
                        "call_id": call_id
                    })

                # 1.2 工具执行完成
                elif event_name == "tool_output":
                    print(f"工具输出: {event.item}")

                    # 提取工具输出信息
                    output_item = event.item
                    raw_item = output_item.raw_item # 一个字典
                    call_id = raw_item.get("call_id")

                    # 通过call_id找到对应的工具名称
                    if call_id and call_id in tool_name_by_call_id:
                        tool_name = tool_name_by_call_id[call_id]
                        yield sse("tool_completed", {
                            "tool_name": tool_name,
                            "tool_result": output_item.output
                        })

            # 2. 处理RawResponsesStreamEvent类型的事件
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                # 文本增量事件 - 这是实现打字机效果的关键
                yield sse("text_delta", {"text": event.data.delta})

            # 3. 处理AgentUpdatedStreamEvent类型的事件(只要任务被Agent接收到)
            if event.type == "agent_updated_stream_event":

                yield sse("agent_updated", {
                    "agent_name": event.new_agent.name
                })

        # 4. 所有事件处理完成后，发送运行完成事件
        yield sse("run_completed", {
            "final_output": result.final_output
        })

    except Exception as e:
        # 异常处理：生成错误事件
        error_msg = str(e)
        print(f"[ERROR] Agent执行出错: {error_msg}")
        yield sse("error", {"message": error_msg})


# 8. FastAPI路由定义
@app.get("/api/chat/sse")
async def chat_sse_get(
        query: str
):
    """
    流式聊天API接口

    这个接口：
    1. 接收用户查询和可选的对话ID
    2. 返回SSE格式的流式响应
    3. 实现实时聊天功能

    Args:
        query: 用户查询文本

    Returns:
        StreamingResponse对象
    """

    async def generate_sse():
        """
        生成SSE响应的异步生成器

        这个内部函数：
        1. 调用run_agent_to_sse函数处理用户查询
        2. 逐段生成SSE事件
        3. 将事件发送给客户端
        """
        async for chunk in run_agent_to_sse(query):
            yield chunk

    # 返回流式响应
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive",  # 保持连接
            "X-Accel-Buffering": "no"  # 禁用nginx缓存
        }
    )


# 9. 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "智能客服系统",
        "version": "1.0.0"
    }


# 10. 启动应用
if __name__ == "__main__":
    import uvicorn

    # 启动服务器
    # host="0.0.0.0" 表示监听所有网络接口
    # port=8200 指定端口号
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8200,
    )