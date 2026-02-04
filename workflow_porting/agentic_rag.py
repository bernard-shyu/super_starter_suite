"""
COMPLETE Pattern C: Agentic RAG Workflow Porting

STEP-wise Implementation:
1. Reimplement complete business logic from STARTER_TOOLS
2. Integrate with FastAPI server framework
3. Implement APPROACH E artifact extraction
4. Add session persistence and error handling
5. Complete testing and validation

Pattern C means FORBIDDEN to import from STARTER_TOOLS directory.
All business logic must be reimplemented locally in this file.
"""

from fastapi import APIRouter, Request
from typing import Dict, Any, Optional

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full AgentWorkflow reimplementation
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.api.models import ChatRequest 
from llama_index.server.tools.index import get_query_engine_tool
from llama_index.server.tools.index.citation import enable_citation, CITATION_SYSTEM_PROMPT
from llama_index.core.settings import Settings

import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("workflow.ported")
router = APIRouter()

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config("P_agentic_rag")

# ====================================================================================
# STEP 1-2: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C)
# ====================================================================================

def create_workflow(chat_request: ChatRequest, timeout_seconds: float = 300.0) -> AgentWorkflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Get pre-loaded index using get_index() (same as adapted workflows)
    - Initialize agentic RAG workflow with citation-enabled query tools
    - Handle missing dependencies gracefully
    """
    try:
        # Get pre-loaded index (same approach as adapted workflows)
        from super_starter_suite.shared.index_utils import get_index
        index = get_index(chat_request)

        if index is None:
            logger.error("Pattern C: Index not found - ensure knowledge base is properly configured")
            raise ValueError("Index is not available. Please run setup scripts or check configuration.")

        # Create a query tool with citations enabled (reimplementation of STARTER_TOOLS logic)
        query_tool = enable_citation(get_query_engine_tool(index=index))

        # Define the system prompt for the agent (reimplementation)
        # Append the citation system prompt to the system prompt
        system_prompt = """You are a helpful assistant"""
        system_prompt += CITATION_SYSTEM_PROMPT

        logger.info("[AGENTIC_RAG] FACTORY: Successfully initialized AgentWorkflow")
        # Create AgentWorkflow using the reimplemented logic with configurable timeout
        workflow = AgentWorkflow.from_tools_or_functions(
            tools_or_functions=[query_tool],
            llm=Settings.llm,
            system_prompt=system_prompt,
            timeout=timeout_seconds
        )

        return workflow

    except ImportError as e:
        logger.error(f"Pattern C: Missing required dependencies: {e}")
        raise ValueError("Index utilities not available. Check if required packages are installed.")

    except Exception as e:
        logger.error(f"[AGENTIC_RAG] ERROR: Initialization failed: {e}")
        raise ValueError(f"Failed to create agentic RAG workflow: {str(e)}")

# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
