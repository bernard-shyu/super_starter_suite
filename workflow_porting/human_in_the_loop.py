"""
COMPLETE Pattern C: Human-In-The-Loop Workflow Porting

STEP-wise Implementation:
1. Reimplement complete business logic from STARTER_TOOLS
2. Integrate with FastAPI server framework
3. Implement APPROACH E artifact extraction
4. Add session persistence and error handling
5. Complete testing and validation

Pattern C means FORBIDDEN to import from STARTER_TOOLS directory.
All business logic must be reimplemented locally in this file.
"""

import platform
import subprocess
from typing import Any, Type, Optional, Dict
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_utils import execute_adapter_workflow
from super_starter_suite.shared.dto import MessageRole, create_chat_message

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full workflow reimplementation
from llama_index.core.workflow import Workflow, Context, StartEvent, StopEvent, Event, step
from llama_index.server.api.models import HumanInputEvent, HumanResponseEvent, ChatAPIMessage, ChatRequest
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
from llama_index.core.prompts import PromptTemplate
from llama_index.core.settings import Settings
from super_starter_suite.shared.artifact_utils import extract_artifact_metadata
from pydantic import BaseModel, Field

import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("workflow.ported.human_in_the_loop")
router = None  # Pattern C: Human-in-the-loop workflows typically don't use direct HTTP endpoints

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "P_human_in_the_loop"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

# ====================================================================================
# STEP 1-2: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C)
# ====================================================================================

class CLICommand(BaseModel):
    """Pattern C: Reimplemented CLI command data model"""
    command: str = Field(description="The command to execute.")

class CLIHumanResponseEvent(HumanResponseEvent):
    """Pattern C: Reimplemented human response event for CLI execution"""
    execute: bool = Field(
        description="True if the human wants to execute the command, False otherwise."
    )
    command: str = Field(description="The command to execute.")

class CLIHumanInputEvent(HumanInputEvent):
    """
    Pattern C: Reimplemented human input event for CLI confirmation

    This event extends from HumanInputEvent for HITL (Human-In-The-Loop) feature.
    Used when the agent needs permission from the user to execute a CLI command.
    """
    event_type: str = "cli_human_input"  # Used by UI to render with appropriate component
    response_event_type: Type = CLIHumanResponseEvent  # Used by workflow to resume with correct event
    data: CLICommand = Field(description="The command to execute.")

class CLIWorkflow(Workflow):
    """
    COMPLETE Pattern C: Human-In-The-Loop CLI Workflow Reimplementation

    Workflow that executes command line tools with human confirmation.
    Follows the pattern: Generate Command → Human Confirmation → Execute/Skip
    NO STARTER_TOOLS dependencies - complete business logic ownership
    """

    # Pattern C: Reimplement default CLI generation prompt (inspired by STARTER_TOOLS)
    default_prompt = PromptTemplate(
        template="""
        You are a helpful assistant who can write CLI commands to execute using {cli_language}.
        Your task is to analyze the user's request and write a CLI command to execute.

        ## User Request
        {user_request}

        Don't be verbose, only respond with the CLI command without any other text.
        """
    )

    def __init__(self, **kwargs: Any) -> None:
        # Pattern C: Reimplement timeout handling for HITL workflows
        # HITL Workflow should disable timeout to avoid timeout errors during human interaction
        kwargs["timeout"] = None
        super().__init__(**kwargs)

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> CLIHumanInputEvent:
        """
        PHASE 1: Generate CLI command from user request

        Analyze user request and generate appropriate CLI command for their operating system
        """
        user_msg = ev.user_msg
        if user_msg is None:
            raise ValueError("Pattern C: Missing user_msg in StartEvent")

        logger.info(f"Pattern C: Processing human-in-the-loop CLI request: {user_msg[:50]}...")

        await ctx.set("user_msg", user_msg)

        # Pattern C: Reimplement OS detection and CLI language selection
        os_name = platform.system()
        if os_name in ["Linux", "Darwin"]:
            cli_language = "bash"
        else:
            cli_language = "cmd"

        # Pattern C: Reimplement prompt formatting and LLM command generation
        prompt = self.default_prompt.format(
            user_request=user_msg,
            cli_language=cli_language
        )

        llm = Settings.llm
        if llm is None:
            raise ValueError("Pattern C: Missing LLM in Settings")

        response = await llm.acomplete(prompt, formatted=True)
        command = response.text.strip()

        if not command or command == "":
            raise ValueError("Pattern C: Couldn't generate a CLI command from the request")

        logger.info(f"Pattern C: Generated CLI command: {command[:50]}...")
        await ctx.set("command", command)

        # Pattern C: Reimplement human input request for command confirmation
        return CLIHumanInputEvent(
            data=CLICommand(command=command),
            response_event_type=CLIHumanResponseEvent,
        )

    @step
    async def handle_human_response(
        self,
        ctx: Context,
        ev: CLIHumanResponseEvent,
    ) -> StopEvent:
        """
        PHASE 2: Execute command based on human response

        Handle human confirmation/rejection and execute CLI command securely
        """
        if ev.execute:
            command = ev.command or ""
            if not command or command == "":
                raise ValueError("Pattern C: Missing command in human response event")

            logger.info(f"Pattern C: Executing approved CLI command: {command[:50]}...")

            # Pattern C: Reimplement secure command execution (inspired by STARTER_TOOLS)
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5-minute timeout for safety
                )

                output = result.stdout or result.stderr
                logger.info("Pattern C: CLI command execution completed")

                success = True if result.returncode == 0 else False
                logger.debug(f"Pattern C: Command succeeded: {success}")

                # Return either stdout or stderr depending on what was captured
                return StopEvent(result=output or f"Command completed with return code: {result.returncode}")

            except subprocess.TimeoutExpired:
                logger.error(f"Pattern C: CLI command timed out: {command}")
                return StopEvent(result="Command execution timed out after 5 minutes")
            except Exception as e:
                logger.error(f"Pattern C: CLI command execution failed: {e}")
                return StopEvent(result=f"Command execution failed: {str(e)}")

        else:
            logger.info("Pattern C: Human declined command execution")
            return StopEvent(result=None)  # Return empty result for declined execution

# ====================================================================================
# STEP 3: COMPLETE FACTORY FUNCTION REIMPLEMENTATION (PATTERN C)
# ====================================================================================
def create_workflow() -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    Creates and returns a CLI workflow instance with human-in-the-loop capabilities
    """
    try:
        logger.debug("Pattern C: Creating Human-In-The-Loop CLI Workflow instance")
        return CLIWorkflow()

    except Exception as e:
        logger.error(f"Pattern C: Workflow creation failed: {e}")
        raise ValueError(f"Failed to create human-in-the-loop workflow: {str(e)}")

# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

# Thin factory function (belongs in this file with workflow logic)
def create_human_in_the_loop_workflow_factory(chat_request: Optional[ChatRequest] = None):
    """Thin factory that returns workflow instance using local implementation"""
    return create_workflow()

@router.post("/chat")
@bind_workflow_session(workflow_config)
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    THIN ENDPOINT WRAPPER - uses execute_adapter_workflow for consistent artifact handling

    Ported workflows use the same proven infrastructure as adapted workflows.

    Note: Human-in-the-loop workflows are designed to work with the integrated
    LlamaIndex server framework for proper human interaction handling.
    """
    # Extract request parameters
    user_message = payload["question"]
    session = request.state.chat_session
    chat_memory = request.state.chat_memory
    user_config = request.state.user_config
    chat_manager = request.state.chat_manager

    # Use PROVEN execute_adapter_workflow instead of buggy execute_ported_workflow
    response_data = await execute_adapter_workflow(
        workflow_factory=create_human_in_the_loop_workflow_factory,  # Ported factory
        workflow_config=workflow_config,
        user_message=user_message,
        user_config=user_config,
        chat_manager=chat_manager,
        session=session,
        chat_memory=chat_memory,
        logger=logger
    )

    # Return JSON response (ported workflows use JSON, adapted use HTML)
    return JSONResponse(content=response_data)
