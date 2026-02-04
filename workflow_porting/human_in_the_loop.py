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

import os
import platform
import subprocess
from typing import Any, Type, Optional, Dict

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full workflow reimplementation
from llama_index.core.workflow import Workflow, Context, StartEvent, StopEvent, Event, step
from llama_index.server.api.models import HumanInputEvent, HumanResponseEvent, ChatRequest
from llama_index.core.prompts import PromptTemplate
from llama_index.core.settings import Settings
from pydantic import BaseModel, Field

import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

# Create an empty APIRouter for workflows that don't provide HTTP endpoints
from fastapi import APIRouter
router = APIRouter()

logger = config_manager.get_logger("workflow.ported")

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config("P_human_in_the_loop")

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

        logger.info(f"[HITL] START: Processing CLI request: {user_msg[:50]}...")

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

        logger.info(f"[HITL] PROMPT: Generated command '{command[:50]}...'")
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

            logger.info(f"[HITL] EXECUTE: Approved command '{command[:50]}...', cwd: {os.getcwd()}")

            # Pattern C: Reimplement secure command execution (inspired by STARTER_TOOLS)
            try:
                # Use workflow's predefined user_data_path for command execution
                # workflow_config.user_data_path should be initialized in workflow_loader.py with USER_RAG_ROOT/workflow_data
                workflow_data_dir = getattr(workflow_config, 'user_data_path', os.path.expanduser("~"))
                logger.debug(f"[HITL] DIR: {workflow_data_dir}")

                os.makedirs(workflow_data_dir, exist_ok=True)  # Ensure directory exists

                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5-minute timeout for safety
                    cwd=workflow_data_dir  # Execute in workflow's user data directory
                )

                output = result.stdout or result.stderr
                success = True if result.returncode == 0 else False
                logger.info("[HITL] COMPLETE: Execution finished, success: {success}")

                # Return either stdout or stderr depending on what was captured
                return StopEvent(result=output or f"Command completed with return code: {result.returncode}")

            except subprocess.TimeoutExpired:
                logger.error(f"[HITL] ERROR: Timeout for command '{command[:30]}'")
                return StopEvent(result="Command execution timed out after 5 minutes")
            except Exception as e:
                logger.error(f"[HITL] ERROR: Execution failed: {e}")
                return StopEvent(result=f"Command execution failed: {str(e)}")

        else:
            logger.info("[HITL] DECLINE: User rejected execution")
            return StopEvent(result=None)  # Return empty result for declined execution

# ====================================================================================
# STEP 3: COMPLETE FACTORY FUNCTION REIMPLEMENTATION (PATTERN C)
# ====================================================================================

def create_workflow(chat_request: ChatRequest, timeout_seconds: float = 120.0) -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    Creates and returns a CLI workflow instance with human-in-the-loop capabilities
    """
    try:
        logger.debug("[HITL] FACTORY: Creating instance, TIMEOUT: {timeout_seconds}s")
        return CLIWorkflow(timeout=timeout_seconds)

    except Exception as e:
        logger.error(f"[HITL] ERROR: Creation failed: {e}")
        raise ValueError(f"Failed to create human-in-the-loop workflow: {str(e)}")

# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
