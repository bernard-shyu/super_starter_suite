from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional
from super_starter_suite.chat_bot.workflow_execution.workflow_executor import WorkflowExecutor
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config
from llama_index.core.workflow import Event, StartEvent 

# UNIFIED LOGGING SYSTEM - Replace global logging
logger = config_manager.get_logger("workflow.adapted")
router = APIRouter()

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config("A_document_generator")

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
