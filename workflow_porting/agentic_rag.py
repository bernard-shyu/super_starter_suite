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

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_utils import execute_adapter_workflow
from super_starter_suite.shared.dto import MessageRole, create_chat_message

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full AgentWorkflow reimplementation
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.server.api.models import ChatAPIMessage, ChatRequest, Artifact, ArtifactEvent
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
from super_starter_suite.shared.artifact_utils import extract_artifact_metadata
from llama_index.server.tools.index import get_query_engine_tool
from llama_index.server.tools.index.citation import enable_citation, CITATION_SYSTEM_PROMPT
from llama_index.core.settings import Settings

import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("workflow.ported.agentic_rag")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "P_agentic_rag"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

# ====================================================================================
# STEP 1-2: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C)
# ====================================================================================

def create_workflow(chat_request: Optional[ChatRequest] = None, timeout_seconds: float = 90.0) -> AgentWorkflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Load index configuration locally using ChatRequest from adapter execution
    - Initialize agentic RAG workflow with citation-enabled query tools
    - Handle missing dependencies gracefully
    - Follow timeout handling pattern from STARTER_TOOLS/agentic_rag/app/workflow.py
    """
    try:
        # Adapter execution provides proper ChatRequest - no more None handling needed
        from super_starter_suite.shared.index_utils import get_index
        index = get_index(chat_request=chat_request)

        if index is None:
            logger.error("Pattern C: Index not found - ensure knowledge base is properly configured")
            raise ValueError("Index is not available. Please run setup scripts or check configuration.")

        # Create a query tool with citations enabled (reimplementation of STARTER_TOOLS logic)
        query_tool = enable_citation(get_query_engine_tool(index=index))

        # Define the system prompt for the agent (reimplementation)
        # Append the citation system prompt to the system prompt
        system_prompt = """You are a helpful assistant"""
        system_prompt += CITATION_SYSTEM_PROMPT

        logger.debug("Pattern C: Successfully initialized AgentWorkflow with citation-enabled query tools")
        # Create AgentWorkflow using the reimplemented logic with configurable timeout
        workflow = AgentWorkflow.from_tools_or_functions(
            tools_or_functions=[query_tool],
            llm=Settings.llm,
            system_prompt=system_prompt,
            timeout=timeout_seconds  # Use configurable timeout instead of hardcoded
        )

        return workflow

    except ImportError as e:
        logger.error(f"Pattern C: Missing required dependencies: {e}")
        raise ValueError("Index utilities not available. Check if required packages are installed.")

    except Exception as e:
        logger.error(f"Pattern C: AgentWorkflow initialization failed: {e}")
        raise ValueError(f"Failed to create agentic RAG workflow: {str(e)}")

# ====================================================================================
# STEP 4-5-6: COMPLETE SERVER ENDPOINT WITH APPROACH E ARTIFACT EXTRACTION (PATTERN C)
# ====================================================================================
# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# Thin factory function (belongs in this file with workflow logic)
def create_agentic_rag_workflow_factory(chat_request: Optional[ChatRequest] = None):
    """Thin factory that returns workflow instance using local implementation"""
    return create_workflow(chat_request)

@router.post("/chat")
@bind_workflow_session(workflow_config)
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    PORTED AgentWorkflow endpoint using ADAPTER pattern for consistency.

    AgentWorkflows should use execute_agentic_workflow pattern
    like A_agentic_rag adapter does.
    """
    import time
    from super_starter_suite.shared.workflow_utils import execute_agentic_workflow, validate_workflow_payload

    execution_start = time.time()

    try:
        # Validation & session setup
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            return JSONResponse({"error": error_msg, "artifacts": None}, status_code=400)

        user_message = payload["question"]
        session = request.state.chat_session
        chat_memory = request.state.chat_memory
        chat_manager = request.state.chat_manager
        user_config = request.state.user_config

        # Use ADAPTER PATTERN: execute_agentic_workflow for consistency
        response_data = await execute_agentic_workflow(
            workflow_factory=create_workflow,
            workflow_config=workflow_config,
            user_message=user_message,
            user_config=user_config,
            chat_manager=chat_manager,
            session=session,
            chat_memory=chat_memory,
            logger=logger
        )

        return JSONResponse(content=response_data)

    except Exception as e:
        error_msg = f"AgentWorkflow failed: {str(e)}"
        logger.error(error_msg)
        return JSONResponse({"error": error_msg, "artifacts": None}, status_code=500)
