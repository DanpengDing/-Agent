import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.tools.mcp.mcp_servers import knowledge_mcp_client
from multi_agent.technical_agent import technical_agent


def test_technical_agent_uses_explicit_bailian_web_search_tool():
    assert technical_agent.mcp_servers == [knowledge_mcp_client]
    assert technical_agent.model_settings.extra_body is None
    assert [tool.name for tool in technical_agent.tools] == ["query_knowledge", "bailian_web_search"]
