from agents import Agent
from agents.model_settings import ModelSettings

from infrastructure.ai.openai_client import sub_model
from infrastructure.ai.prompt_loader import load_prompt
from infrastructure.tools.local.bailian_web_search import bailian_web_search
from infrastructure.tools.local.knowledge_base import query_knowledge
from infrastructure.tools.mcp.mcp_servers import knowledge_mcp_client


technical_agent = Agent(
    name="技术专家咨询智能体",
    instructions=load_prompt("technical_agent"),
    model=sub_model,
    model_settings=ModelSettings(
        temperature=0,
    ),
    tools=[query_knowledge, bailian_web_search],
    mcp_servers=[knowledge_mcp_client],
)
