"""
Multi-Agent Orchestration API Endpoint

Provides REST endpoints for multi-agent pipeline orchestration,
enabling frontend and other systems to execute coordinated multi-agent workflows.

Endpoints:
- POST /multi_agent/pipeline/execute - Execute a multi-agent pipeline
- GET /multi_agent/pipelines - List available pipeline configurations
- POST /multi_agent/pipeline/create - Create a new pipeline configuration
"""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import json
import time
import asyncio
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.multi_agent_coordinator import (
    MultiAgentCoordinator, PipelineConfig, AgentStep, AgentTransition, WorkflowAdapterFactory
)

# UNIFIED LOGGING SYSTEM
logger = config_manager.get_logger("workflow.bzlogic")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "AM_multi_agent"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

# In-memory pipeline storage (could be extended to use a database)
_pipeline_configs: Dict[str, PipelineConfig] = {}

def _initialize_default_pipelines():
    """Initialize some default pipeline configurations for demonstration"""
    # Research and Code Generation Pipeline
    research_code_pipe = PipelineConfig(
        pipeline_name="research_and_code",
        agent_steps=[
            AgentStep(
                agent_id="deep_research",
                workflow_name="deep_research",
                timeout_seconds=600.0  # 10 minutes for research
            ),
            AgentStep(
                agent_id="code_generator",
                workflow_name="code_generator",
                timeout_seconds=300.0  # 5 minutes for code generation
            )
        ],
        transition_type=AgentTransition.SEQUENTIAL,
        failure_policy="fail_fast",
        output_aggregation="all_steps"
    )

    # Parallel Analysis Pipeline
    parallel_analysis_pipe = PipelineConfig(
        pipeline_name="parallel_analysis",
        agent_steps=[
            AgentStep(
                agent_id="agentic_rag_analysis",
                workflow_name="agentic_rag"
            ),
            AgentStep(
                agent_id="document_analysis",
                workflow_name="document_generator"
            ),
            AgentStep(
                agent_id="financial_analysis",
                workflow_name="financial_report"
            )
        ],
        transition_type=AgentTransition.PARALLEL,
        output_aggregation="all_steps"
    )

    _pipeline_configs["research_and_code"] = research_code_pipe
    _pipeline_configs["parallel_analysis"] = parallel_analysis_pipe

# Initialize default pipelines
_initialize_default_pipelines()


@router.post("/pipeline/execute")
@bind_workflow_session(workflow_config)  # Single param decorator # CRITICAL: Must come AFTER @router.post()
async def execute_multi_agent_pipeline(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    Execute a multi-agent pipeline with specified configuration.

    The @bind_workflow_session("multi_agent") decorator provides:
    - User context initialization for multi-agent orchestration session
    - Persistent logging and history for pipeline executions
    - Shared memory context preparation

    Expected payload:
    {
        "pipeline_name": "research_and_code",  # or pipeline_config for custom pipelines
        "pipeline_config": {...},  # Optional: full PipelineConfig dict
        "input_data": {
            "question": "User's question or task description",
            "context": "Additional context (optional)",
            "parameters": {...}  # Any additional parameters
        },
        "options": {
            "timeout_override": 900,  # Optional timeout override
            "debug_logging": false
        }
    }

    Returns:
        dict: Pipeline execution results with success/failure status
    """
    start_time = time.time()

    try:
        # Validate payload structure
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a dictionary")

        pipeline_name = payload.get("pipeline_name")
        pipeline_config_dict = payload.get("pipeline_config")
        input_data = payload.get("input_data", {})
        options = payload.get("options", {})

        # Get or create pipeline configuration
        if pipeline_config_dict:
            # Use provided pipeline configuration
            try:
                pipeline_config = _create_pipeline_config_from_dict(pipeline_config_dict)
            except Exception as e:
                logger.error(f"Failed to parse pipeline config: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid pipeline configuration: {e}")
        elif pipeline_name:
            # Use stored pipeline configuration
            pipeline_config = _pipeline_configs.get(pipeline_name)
            if not pipeline_config:
                raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_name}' not found")
        else:
            raise HTTPException(status_code=400, detail="Either pipeline_name or pipeline_config must be provided")

        # Get user config and set up coordinator
        user_config = request.state.user_config
        coordinator = MultiAgentCoordinator(user_config)

        # Apply timeout override if specified
        if options.get("timeout_override"):
            pipeline_config.max_execution_time = float(options["timeout_override"])

        logger.info(f"Starting pipeline execution: {pipeline_config.pipeline_name}")

        # Execute the pipeline
        result = await coordinator.execute_pipeline(pipeline_config, input_data)

        # Log the execution result
        execution_time = time.time() - start_time
        log_workflow_execution(
            "multi_agent_pipeline",
            f"Pipeline: {pipeline_config.pipeline_name}",
            result['status'] == 'success',
            execution_time
        )

        # Format response for frontend
        response_data = {
            "pipeline_id": result['pipeline_id'],
            "pipeline_name": pipeline_config.pipeline_name,
            "status": result['status'],
            "execution_time": execution_time,
            "agent_count": len(pipeline_config.agent_steps),
            "execution_results": result['execution_results'],
            "final_output": result.get('final_result', {}),
            "session_id": request.state.chat_session.session_id if hasattr(request.state, 'chat_session') else None
        }

        # Add error information if pipeline failed
        if result['status'] == 'failure':
            response_data["error"] = result.get('error', 'Unknown error occurred')

        # Log pipeline completion to chat history
        _log_pipeline_to_session(
            request.state,
            pipeline_config.pipeline_name,
            result,
            execution_time
        )


        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        execution_time = time.time() - start_time
        log_workflow_execution("multi_agent_pipeline", pipeline_name or "unknown", False, execution_time)
        raise HTTPException(status_code=408, detail="Pipeline execution timed out")
    except Exception as e:
        execution_time = time.time() - start_time
        pipeline_name = payload.get("pipeline_name", "unknown") if payload else "unknown"
        log_workflow_execution("multi_agent_pipeline", pipeline_name, False, execution_time)
        logger.error(f"Multi-agent pipeline error: {e}", exc_info=True)

        error_data = {"error": str(e), "status": "failed", "execution_time": execution_time}
        return JSONResponse(content=error_data, status_code=500)


@router.get("/pipelines")
async def list_available_pipelines(request: Request) -> Dict[str, Any]:
    """
    Get list of available pipeline configurations.

    Returns:
        dict: Available pipeline configurations with metadata
    """
    try:
        pipelines_info = []
        for name, config in _pipeline_configs.items():
            pipelines_info.append({
                "name": name,
                "display_name": config.pipeline_name.replace("_", " ").title(),
                "agent_count": len(config.agent_steps),
                "transition_type": config.transition_type.value,
                "description": _get_pipeline_description(name),
                "agents": [
                    {
                        "id": step.agent_id,
                        "workflow": step.workflow_name,
                        "timeout": step.timeout_seconds
                    }
                    for step in config.agent_steps
                ]
            })

        return {
            "pipelines": pipelines_info,
            "total_count": len(pipelines_info)
        }

    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pipeline list")


@router.post("/pipeline/create")
async def create_pipeline_configuration(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new pipeline configuration and store it for later use.

    Expected payload:
    {
        "pipeline_name": "custom_pipeline_name",
        "pipeline_config": {
            "agent_steps": [...],
            "transition_type": "sequential",
            "failure_policy": "fail_fast",
            "output_aggregation": "last_step",
            "max_execution_time": 900
        }
    }

    Returns:
        dict: Success confirmation with pipeline details
    """
    try:
        pipeline_name = payload.get("pipeline_name")
        pipeline_config_dict = payload.get("pipeline_config")

        if not pipeline_name or not pipeline_config_dict:
            raise HTTPException(status_code=400, detail="pipeline_name and pipeline_config are required")

        if pipeline_name in _pipeline_configs:
            raise HTTPException(status_code=409, detail=f"Pipeline '{pipeline_name}' already exists")

        # Validate and create pipeline config
        pipeline_config = _create_pipeline_config_from_dict(pipeline_config_dict)
        pipeline_config.pipeline_name = pipeline_name  # Override with provided name

        # Validate the configuration
        if not pipeline_config.validate():
            raise HTTPException(status_code=400, detail="Invalid pipeline configuration")

        # Store the configuration
        _pipeline_configs[pipeline_name] = pipeline_config

        logger.info(f"Created new pipeline configuration: {pipeline_name}")

        return {
            "success": True,
            "pipeline_name": pipeline_name,
            "agent_count": len(pipeline_config.agent_steps),
            "transition_type": pipeline_config.transition_type.value
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pipeline: {str(e)}")


def _create_pipeline_config_from_dict(config_dict: Dict[str, Any]) -> PipelineConfig:
    """Create a PipelineConfig instance from a dictionary"""
    agent_steps = []
    for step_dict in config_dict.get("agent_steps", []):
        step = AgentStep(
            agent_id=step_dict["agent_id"],
            workflow_name=step_dict["workflow_name"],
            input_transform=step_dict.get("input_transform"),
            output_transform=step_dict.get("output_transform"),
            timeout_seconds=step_dict.get("timeout_seconds", 300.0),
            retry_count=step_dict.get("retry_count", 0),
            conditional_next=step_dict.get("conditional_next")
        )
        agent_steps.append(step)

    transition_type_str = config_dict.get("transition_type", "sequential")
    transition_type = AgentTransition.SEQUENTIAL
    if transition_type_str == "parallel":
        transition_type = AgentTransition.PARALLEL
    elif transition_type_str == "conditional":
        transition_type = AgentTransition.CONDITIONAL

    return PipelineConfig(
        pipeline_name=config_dict.get("pipeline_name", "custom_pipeline"),
        agent_steps=agent_steps,
        transition_type=transition_type,
        max_execution_time=config_dict.get("max_execution_time", 900.0),
        failure_policy=config_dict.get("failure_policy", "fail_fast"),
        output_aggregation=config_dict.get("output_aggregation", "last_step")
    )


def _get_pipeline_description(pipeline_name: str) -> str:
    """Get description for predefined pipelines"""
    descriptions = {
        "research_and_code": "Conduct research then generate implementation code",
        "parallel_analysis": "Run multiple analysis agents in parallel"
    }
    return descriptions.get(pipeline_name, "Custom multi-agent pipeline")


def _log_pipeline_to_session(request_state, pipeline_name: str, result: Dict[str, Any], execution_time: float):
    """Log pipeline execution to the chat session"""
    try:
        # Create a summary of the pipeline execution
        status = result['status']
        agent_count = len(result.get('execution_results', []))
        pipeline_id = result.get('pipeline_id', 'unknown')

        # Create summary message
        if status == 'success':
            summary = f"✅ Multi-agent pipeline '{pipeline_name}' completed successfully in {execution_time:.1f}s " \
                     f"({agent_count} agents executed, pipeline ID: {pipeline_id[:8]})"
        else:
            error_msg = result.get('error', 'Unknown error')
            summary = f"❌ Multi-agent pipeline '{pipeline_name}' failed after {execution_time:.1f}s: {error_msg}"

        # Log to workflow session
        from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge
        from super_starter_suite.shared.dto import MessageRole, create_chat_message

        user_config = request_state.user_config
        session = request_state.chat_session

        # Add summary to session
        summary_msg = create_chat_message(role=MessageRole.ASSISTANT, content=summary)
        chat_manager = request_state.chat_manager
        chat_manager.add_message_to_session(session, summary_msg)

        logger.debug(f"Logged pipeline execution summary to session {session.session_id}")

    except Exception as e:
        logger.warning(f"Failed to log pipeline to session: {e}")
