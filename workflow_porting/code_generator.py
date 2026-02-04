"""
COMPLETE Pattern C: Code Generator Workflow Porting

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
from typing import Dict, Any, Optional, Literal, Union

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full workflow reimplementation
from llama_index.core.workflow import Workflow, Context, Event, StartEvent, StopEvent, step
from llama_index.server.api.models import (
    ChatAPIMessage, ChatRequest, Artifact, ArtifactEvent, ArtifactType,
    CodeArtifactData, UIEvent
)
from llama_index.core.base.llms.types import ChatMessage as LlamaChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.settings import Settings
from pydantic import BaseModel, Field

import time
import re
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("workflow.ported")
router = APIRouter()

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config("P_code_generator")

# ====================================================================================
# STEP 1-2: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C)
# ====================================================================================

class Requirement(BaseModel):
    """Pattern C: Reimplemented requirement model for code planning"""
    next_step: Literal["answering", "coding"]
    language: Optional[str] = None
    file_name: Optional[str] = None
    requirement: str

class UIEventData(BaseModel):
    """Pattern C: Reimplemented UI event data for code generation workflow"""
    state: Literal["plan", "generate", "completed"] = Field(
        description="Current state: plan/generate/completed"
    )
    requirement: Optional[str] = Field(
        description="Requirement description",
        default=None,
    )

class PlanEvent(Event):
    """Pattern C: Planning event for code generation workflow"""
    user_msg: str
    context: Optional[str] = None

class GenerateArtifactEvent(Event):
    """Pattern C: Code artifact generation event"""
    requirement: Requirement

class SynthesizeAnswerEvent(Event):
    """Pattern C: Answer synthesis event"""
    pass

class CodeArtifactWorkflow(Workflow):
    """
    COMPLETE Pattern C: CodeArtifactWorkflow full reimplementation

    Multi-step workflow: prepare → plan → generate/answer → complete
    Handles code generation and updates with intelligent planning
    NO STARTER_TOOLS dependencies - complete business logic ownership
    """

    chat_request: ChatRequest
    last_artifact = None

    def __init__(self, chat_request: ChatRequest, **kwargs):
        super().__init__(**kwargs)
        self.chat_request = chat_request
        # Pattern C: Reimplement artifact retrieval instead of STARTER_TOOLS import
        self.last_artifact = self._get_last_artifact(chat_request)

    # Pattern C: Reimplement artifact retrieval method
    def _get_last_artifact(self, chat_request: ChatRequest) -> Optional[Artifact]:
        """Pattern C: Reimplement last artifact retrieval without STARTER_TOOLS"""
        try:
            from llama_index.server.api.utils import get_last_artifact
            return get_last_artifact(chat_request)
        except Exception as e:
            logger.debug(f"[CODE_GEN] RETRIEVE: No existing artifact found ({e})")
            return None

    @step
    async def prepare_chat_history(self, ctx: Context, ev: StartEvent) -> PlanEvent:
        """
        PHASE 1: Prepare conversation history and memory

        Initialize workflow state and create chat memory
        """
        user_msg = ev.user_msg
        if user_msg is None:
            raise ValueError("user_msg is required to run the workflow")

        logger.info(f"[CODE_GEN] START: Preparing docs for '{user_msg[:50]}...'")

        await ctx.set("user_msg", user_msg)

        # Build chat history with user message
        chat_history = ev.chat_history or []
        chat_history.append(LlamaChatMessage(role="user", content=user_msg))

        # Create memory with conversation history
        memory = ChatMemoryBuffer.from_defaults(
            chat_history=chat_history,
            llm=Settings.llm,
        )
        await ctx.set("memory", memory)

        return PlanEvent(
            user_msg=user_msg,
            context=str(self.last_artifact.model_dump_json())
            if self.last_artifact
            else "",
        )

    @step
    async def planning(self, ctx: Context, event: PlanEvent) -> Union[GenerateArtifactEvent, SynthesizeAnswerEvent]:
        """
        PHASE 2: Intelligent planning - decide whether to code or answer

        Analyzes user request to determine next step: code generation vs explanation
        """
        logger.info("[CODE_GEN] PLAN: Analyzing requirement")

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(state="plan", requirement=None),
            )
        )

        # Pattern C: Reimplement complex planning prompt (inspired by STARTER_TOOLS)
        planning_prompt = """
        You are a product analyst responsible for analyzing the user's request and providing the next step for code or document generation.
        You are helping user with their code artifact. To update the code, you need to plan a coding step.

        Follow these instructions:
        1. Carefully analyze the conversation history and the user's request to determine what has been done and what the next step should be.
        2. The next step must be one of the following two options:
           - "coding": To make the changes to the current code.
           - "answering": If you don't need to update the current code or need clarification from the user.
        Important: Avoid telling the user to update the code themselves, you are the one who will update the code (by planning a coding step).
        3. If the next step is "coding", you may specify the language ("typescript" or "python") and file_name if known, otherwise set them to null.
        4. The requirement must be provided clearly what is the user request and what need to be done for the next step in details
           as precise and specific as possible, don't be stingy with in the requirement.
        5. If the next step is "answering", set language and file_name to null, and the requirement should describe what to answer or explain to the user.
        6. Be concise; only return the requirements for the next step.
        7. The requirements must be in the following format:
           ```json
           {
               "next_step": "answering" | "coding",
               "language": "typescript" | "python" | null,
               "file_name": string | null,
               "requirement": string
           }
           ```
        """.strip()

        # Add context if available
        full_prompt = planning_prompt
        if event.context:
            full_prompt += f"\n\n## The context is: \n{event.context}\n"

        full_prompt += f"\n\nNow, plan the user's next step for this request: {event.user_msg}"

        # Execute planning analysis
        response = await Settings.llm.acomplete(prompt=full_prompt, formatted=True)

        # Pattern C: Reimplement JSON requirement parsing (inspired by STARTER_TOOLS)
        requirement = self._parse_requirement_from_response(response.text)

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(state="generate", requirement=requirement.requirement),
            )
        )

        # Store planning result in memory
        memory: ChatMemoryBuffer = await ctx.get("memory")
        memory.put(LlamaChatMessage(role="assistant", content=f"The plan for next step: \n{response.text}"))
        await ctx.set("memory", memory)

        logger.info(f"[CODE_GEN] DECISION: {requirement.next_step} | {requirement.requirement[:50]}...")

        if requirement.next_step == "coding":
            return GenerateArtifactEvent(requirement=requirement)
        else:
            return SynthesizeAnswerEvent()

    @step
    async def generate_artifact(self, ctx: Context, event: GenerateArtifactEvent) -> SynthesizeAnswerEvent:
        """
        PHASE 3: Code artifact generation

        Generate code based on planning requirements and previous artifacts
        """
        logger.info(f"[CODE_GEN] GENERATE: {event.requirement.language or 'unknown'}")

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(state="generate", requirement=event.requirement.requirement),
            )
        )

        # Pattern C: Reimplement code generation prompt (inspired by STARTER_TOOLS)
        coding_prompt = """
        You are a skilled developer who can help user with coding.
        You are given a task to generate or update a code for a given requirement.

        ## Follow these instructions:
        **1. Carefully read the user's requirements.**
           If any details are ambiguous or missing, make reasonable assumptions and clearly reflect those in your output.
        **2. For code requests:**
           - If the user does not specify a framework or language, default to a React component using the Next.js framework.
           - For Next.js, use Shadcn UI components, Typescript, @types/node, @types/react, @types/react-dom, PostCSS, and TailwindCSS.
           - Ensure the code is idiomatic, production-ready, and includes necessary imports.
           - Only generate code relevant to the user's request—do not add extra boilerplate.
        **3. Don't be verbose on response**
           - No other text or comments only return the code which wrapped by the appropriate code block.
        **4. Only the following languages are allowed: "typescript", "python".**
        **5. If there is no code to update, return the reason without any code block.**
        """.strip()

        # Add previous artifact context
        previous_artifact_text = ""
        if self.last_artifact:
            previous_artifact_text = f"\n\nThe previous code is:\n{self.last_artifact.model_dump_json()}"

        full_coding_prompt = (f"{coding_prompt}{previous_artifact_text}\n\n"
                             f"Now, generate the code for the following requirement:\n{event.requirement.model_dump()}")

        response = await Settings.llm.acomplete(prompt=full_coding_prompt, formatted=True)

        # Pattern C: Reimplement code extraction from LLM response (inspired by STARTER_TOOLS)
        code, language = self._extract_code_from_response(response.text, event.requirement.language)

        # Store generated code in memory
        memory: ChatMemoryBuffer = await ctx.get("memory")
        memory.put(LlamaChatMessage(role="assistant", content=f"Updated the code: \n{response.text}"))
        await ctx.set("memory", memory)

        # Emit code artifact event
        ctx.write_event_to_stream(
            ArtifactEvent(
                data=Artifact(
                    type=ArtifactType.CODE,
                    created_at=int(time.time()),
                    data=CodeArtifactData(
                        language=event.requirement.language or language or "",
                        file_name=event.requirement.file_name or "",
                        code=code,
                    ),
                ),
            )
        )

        return SynthesizeAnswerEvent()

    @step
    async def synthesize_answer(self, ctx: Context, event: SynthesizeAnswerEvent) -> StopEvent:
        """
        PHASE 4: Answer synthesis and final explanation

        Generate natural language explanation of what was done
        """
        logger.info("[CODE_GEN] COMPLETE: Synthesizing final answer")

        memory: ChatMemoryBuffer = await ctx.get("memory")
        chat_history = memory.get()

        # Add system context for answer synthesis
        chat_history.append(LlamaChatMessage(
            role="system",
            content="""
            You are a helpful assistant who is responsible for explaining the work to the user.
            Based on the conversation history, provide an answer to the user's question.
            The user has access to the code so avoid mentioning the whole code again in your response.
            """.strip()
        ))

        # Stream final answer
        response_stream = await Settings.llm.astream_chat(messages=chat_history)

        ctx.write_event_to_stream(
            UIEvent(type="ui_event", data=UIEventData(state="completed"))
        )

        return StopEvent(result=response_stream)

    # ====================================================================================
    # PATTERN C: REIMPLEMENTED BUSINESS LOGIC METHODS (NO STARTER_TOOLS DEPENDENCY)
    # ====================================================================================

    def _parse_requirement_from_response(self, response_text: str) -> Requirement:
        """
        Pattern C: Reimplemented requirement parsing from LLM response
        """
        # Extract JSON block using regex
        json_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text, re.IGNORECASE)
        if json_block is None:
            # Fallback to default answering
            logger.warning("[CODE_GEN] PLAN_ERROR: No JSON found, defaulting to answer")
            return Requirement(
                next_step="answering",
                language=None,
                file_name=None,
                requirement="Explain the current status and ask for clarification if needed."
            )

        try:
            return Requirement.model_validate_json(json_block.group(1).strip())
        except Exception as e:
            logger.error(f"[CODE_GEN] ERROR: JSON parse failed: {e}")
            return Requirement(
                next_step="answering",
                language=None,
                file_name=None,
                requirement="There was an issue processing the request. Please clarify what you'd like help with."
            )

    def _extract_code_from_response(self, response_text: str, requested_language: Optional[str]) -> tuple[str, Optional[str]]:
        """
        Pattern C: Reimplemented code extraction from LLM response
        """
        # Look for code blocks with language specification
        language_pattern = r"```(\w+)([\s\S]*)```"
        code_match = re.search(language_pattern, response_text)

        if code_match is None:
            logger.debug("[CODE_GEN] EXTRACT: No code block found")
            return "", requested_language

        language = code_match.group(1).strip().lower()
        code = code_match.group(2).strip()

        # Validate language
        if language not in ["typescript", "python", "javascript", "ts", "js"]:
            if requested_language:
                language = requested_language
            else:
                language = "typescript"  # Default

        return code, language

# ====================================================================================
# STEP 3: COMPLETE FACTORY FUNCTION REIMPLEMENTATION (PATTERN C)
# ====================================================================================
def create_workflow(chat_request: ChatRequest, timeout_seconds: float = 240.0) -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Create code generation workflow instance
    - Handle initialization and configuration
    """
    try:
        logger.debug("[CODE_GEN] FACTORY: Creating instance")

        workflow = CodeArtifactWorkflow(
            chat_request=chat_request,
            timeout=timeout_seconds  # Use configurable timeout
        )

        return workflow

    except Exception as e:
        logger.error(f"[CODE_GEN] ERROR: Creation failed: {e}")
        raise ValueError(f"Failed to create code generator workflow: {str(e)}")

# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
