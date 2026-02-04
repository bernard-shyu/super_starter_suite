from typing import Optional

try:
    from app.index import get_index
except ImportError:
    from super_starter_suite.shared.index_utils import get_index

from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.settings import Settings
from llama_index.server.api.models import ChatRequest
from llama_index.server.tools.index import get_query_engine_tool
from llama_index.server.tools.index.citation import (
    CITATION_SYSTEM_PROMPT,
    enable_citation,
)


def create_workflow(chat_request: Optional[ChatRequest] = None, timeout_seconds: float = 90.0) -> AgentWorkflow:
    index = get_index(chat_request=chat_request)
    if index is None:
        raise RuntimeError(
            "Index not found! Please run `uv run generate` to index the data first."
        )

    try:
        # Create a query tool with citations enabled
        query_tool = enable_citation(get_query_engine_tool(index=index))

        # Define the system prompt for the agent
        # Append the citation system prompt to the system prompt
        system_prompt = """You are a helpful assistant. When using tools, ensure you handle empty or missing results gracefully."""
        system_prompt += CITATION_SYSTEM_PROMPT

        # DEBUG: Log LLM availability
        # print(f"[DEBUG] About to create AgentWorkflow with Settings.llm: {Settings.llm}")

        workflow = AgentWorkflow.from_tools_or_functions(
            tools_or_functions=[query_tool],
            llm=Settings.llm,
            system_prompt=system_prompt,
            timeout=timeout_seconds  # Use configurable timeout instead of hardcoded
        )

        # print(f"[DEBUG] AgentWorkflow created: {workflow}")
        return workflow

    except Exception as e:
        error_msg = f"Failed to create Agentic RAG workflow: {str(e)}"
        print(f"[ERROR] {error_msg}")
        # Provide a more specific error about potential data issues
        if "index" in str(e).lower():
            raise RuntimeError("Failed to create workflow due to index issues. Please ensure data is properly indexed.")
        elif "tool" in str(e).lower():
            raise RuntimeError("Failed to create workflow due to tool configuration issues.")
        else:
            raise RuntimeError(f"Workflow creation failed: {str(e)}")
