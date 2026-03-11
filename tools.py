import asyncio
import logging
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


async def _load_tools():
    """
    Start the MCP server subprocess and load all registered tools.
    """
    client = MultiServerMCPClient(
        {
            "travel": {
                "command": "python",
                "args": ["mcp_server.py"],
                "transport": "stdio",
            }
        }
    )

    #Wrap in try/except so a missing mcp_server.py or port conflict gives a clear message
    try:
        tools = await client.get_tools()
        logger.info("Loaded %d MCP tools", len(tools))
        return tools
    except Exception as e:
        logger.error("Failed to load MCP tools: %s", e)
        raise RuntimeError(
            f"Could not connect to MCP travel server. "
            f"Make sure mcp_server.py is present and dependencies are installed.\nOriginal error: {e}"
        ) from e


def load_tools():
    """Synchronous wrapper for use in LangGraph nodes."""
    return asyncio.run(_load_tools())