"""
COMPLETE Pattern C: Document Generator Workflow Porting

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
from typing import Dict, Any, Optional, Literal

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full workflow reimplementation
from llama_index.core.workflow import Workflow, Context, Event, StartEvent, StopEvent, step
from llama_index.server.api.models import (
    ChatAPIMessage, ChatRequest, Artifact, ArtifactEvent, ArtifactType,
    DocumentArtifactData, UIEvent
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
workflow_config = get_workflow_config("P_document_generator")

# ====================================================================================
# STEP 1-2: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C)
# ====================================================================================

class DocumentRequirement(BaseModel):
    """Pattern C: Reimplemented document requirement model"""
    type: Literal["markdown", "html"]
    title: str
    requirement: str

class UIEventData(BaseModel):
    """Pattern C: Reimplemented UI event data for document generation workflow"""
    state: Literal["plan", "generate", "completed"] = Field(
        description="Current state: plan/generate/completed"
    )
    requirement: Optional[str] = Field(
        description="Requirement description",
        default=None,
    )

class PlanEvent(Event):
    """Pattern C: Planning event for document generation workflow"""
    user_msg: str
    context: Optional[str] = None

class GenerateArtifactEvent(Event):
    """Pattern C: Document artifact generation event"""
    requirement: DocumentRequirement

class SynthesizeAnswerEvent(Event):
    """Pattern C: Answer synthesis event"""
    requirement: DocumentRequirement
    generated_artifact: str

class DocumentArtifactWorkflow(Workflow):
    """
    COMPLETE Pattern C: DocumentArtifactWorkflow full reimplementation

    Workflow for generating or updating document artifacts (markdown, HTML)
    Example: Create project guidelines, update documentation, generate reports
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
            logger.debug(f"[DOC_GEN] RETRIEVE: No existing artifact found ({e})")
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

        logger.info(f"[DOC_GEN] START: Preparing docs for '{user_msg[:50]}...'")

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
    async def planning(self, ctx: Context, event: PlanEvent) -> GenerateArtifactEvent:
        """
        PHASE 2: Plan document requirements

        Analyze user request to determine document type, title, and specific requirements
        """
        logger.info("[DOC_GEN] PLAN: Analyzing requirement")

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(state="plan", requirement=None),
            )
        )

        # Pattern C: Reimplement document planning prompt (inspired by STARTER_TOOLS)
        planning_prompt = """
        You are a documentation analyst responsible for analyzing the user's request and providing requirements for document generation or update.

        Follow these instructions:
        1. Carefully analyze the conversation history and the user's request to determine what has been done and what the next step should be.
        2. From the user's request, provide requirements for the next step of the document generation or update.
        3. Do not be verbose; only return the requirements for the next step of the document generation or update.
        4. Only the following document types are allowed: "markdown", "html".
        5. The requirement should be in the following format:
           ```json
           {
               "type": "markdown" | "html",
               "title": string,
               "requirement": string
           }
           ```
        """.strip()

        # Add context if available
        full_prompt = planning_prompt
        if event.context:
            full_prompt += f"\n\n## The context is: \n{event.context}\n"

        full_prompt += f"\n\nNow, please plan for the user's request: {event.user_msg}"

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
        memory.put(LlamaChatMessage(role="assistant", content=f"Planning for the document generation: \n{response.text}"))
        await ctx.set("memory", memory)

        logger.info(f"[DOC_GEN] DECISION: {requirement.type} | '{requirement.title}'")

        return GenerateArtifactEvent(requirement=requirement)

    @step
    async def generate_artifact(self, ctx: Context, event: GenerateArtifactEvent) -> SynthesizeAnswerEvent:
        """
        PHASE 3: Generate document artifact

        Create or update document based on planning requirements
        """
        logger.info(f"[DOC_GEN] GENERATE: {event.requirement.type} | '{event.requirement.title}'")

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(state="generate", requirement=event.requirement.requirement),
            )
        )

        # Pattern C: Reimplement document generation prompt (inspired by STARTER_TOOLS)
        generation_prompt = """
        You are a skilled technical writer who can help users with documentation.
        You are given a task to generate or update a document for a given requirement.

        ## Follow these instructions:
        **1. Carefully read the user's requirements.**
           If any details are ambiguous or missing, make reasonable assumptions and clearly reflect those in your output.
        **2. For document requests:**
           - If the user does not specify a type, default to Markdown.
           - Ensure the document is clear, well-structured, and grammatically correct.
           - Only generate content relevant to the user's request—do not add extra boilerplate.
        **3. Do not be verbose in your response.**
           - No other text or comments; only return the document content wrapped by the appropriate code block (```markdown or ```html).
           - If the user's request is to update the document, only return the updated document.
        **4. Only the following types are allowed: "markdown", "html".**
        **5. If there is no change to the document, return the reason without any code block.**
        """.strip()

        # Add previous artifact context
        previous_artifact_text = ""
        if self.last_artifact:
            previous_artifact_text = f"\n\n## The previous content is:\n{self.last_artifact.model_dump_json()}"

        full_prompt = (f"{generation_prompt}{previous_artifact_text}\n\n"
                      f"Now, please generate the document for the following requirement:\n{event.requirement.model_dump()}")

        response = await Settings.llm.acomplete(prompt=full_prompt, formatted=True)

        # Pattern C: Reimplement document extraction from LLM response (inspired by STARTER_TOOLS)
        content, doc_type = self._extract_document_from_response(response.text, event.requirement.type)

        # Store generated document in memory
        memory: ChatMemoryBuffer = await ctx.get("memory")
        memory.put(LlamaChatMessage(role="assistant", content=f"Generated document: \n{response.text}"))
        await ctx.set("memory", memory)

        # Emit document artifact event
        ctx.write_event_to_stream(
            ArtifactEvent(
                data=Artifact(
                    type=ArtifactType.DOCUMENT,
                    created_at=int(time.time()),
                    data=DocumentArtifactData(
                        title=event.requirement.title,
                        content=content,
                        type=doc_type,  # type: ignore
                    ),
                ),
            )
        )

        return SynthesizeAnswerEvent(
            requirement=event.requirement,
            generated_artifact=response.text,
        )

    @step
    async def synthesize_answer(self, ctx: Context, event: SynthesizeAnswerEvent) -> StopEvent:
        """
        PHASE 4: Synthesize final explanation

        Provide user explanation of what was generated/updated
        """
        logger.info("[DOC_GEN] COMPLETE: Synthesizing final answer")

        memory: ChatMemoryBuffer = await ctx.get("memory")
        chat_history = memory.get()

        # Add system context for answer synthesis
        chat_history.append(LlamaChatMessage(
            role="system",
            content="""
            Your responsibility is to explain the work to the user.
            If there is no document to update, explain the reason.
            If the document is updated, just summarize what changed. Don't need to include the whole document again in the response.
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

    def _parse_requirement_from_response(self, response_text: str) -> DocumentRequirement:
        """
        Pattern C: Reimplemented requirement parsing from LLM response
        """
        # Extract JSON block using regex
        json_block = re.search(r"```json([\s\S]*)```", response_text, re.IGNORECASE)
        if json_block is None:
            # Fallback to default requirement
            logger.warning("[DOC_GEN] PLAN_ERROR: No JSON found, defaulting to markdown")
            return DocumentRequirement(
                type="markdown",
                title="Document",
                requirement="Create a basic document based on the user's request."
            )

        try:
            return DocumentRequirement.model_validate_json(json_block.group(1).strip())
        except Exception as e:
            logger.error(f"[DOC_GEN] ERROR: JSON parse failed: {e}")
            return DocumentRequirement(
                type="markdown",
                title="Document",
                requirement="There was an issue processing the request. Please clarify what document you'd like to create."
            )

    def _extract_document_from_response(self, response_text: str, requested_type: str) -> tuple[str, str]:
        """
        Pattern C: Reimplemented document extraction from LLM response
        """
        # Look for document blocks with type specification
        doc_pattern = r"```(markdown|html)([\s\S]*)```"
        doc_match = re.search(doc_pattern, response_text, re.IGNORECASE)

        if doc_match is None:
            logger.debug("[DOC_GEN] EXTRACT: No document block found")
            return f"No document was generated. LLM Response: {response_text[:200]}...", requested_type

        doc_type = doc_match.group(1).lower()
        content = doc_match.group(2).strip()

        # Validate and fallback to requested type
        if doc_type not in ["markdown", "html"]:
            doc_type = requested_type

        return content, doc_type

# ====================================================================================
# STEP 3: COMPLETE FACTORY FUNCTION REIMPLEMENTATION (PATTERN C)
# ====================================================================================
def create_workflow(chat_request: ChatRequest, timeout_seconds: float = 240.0) -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Create document generation workflow instance
    - Handle initialization and configuration
    """
    try:
        logger.debug("[DOC_GEN] FACTORY: Creating instance, TIMEOUT: {timeout_seconds}s")
        workflow = DocumentArtifactWorkflow(
            chat_request=chat_request,
            timeout=timeout_seconds
        )

        return workflow

    except Exception as e:
        logger.error(f"[DOC_GEN] ERROR: Creation failed: {e}")
        raise ValueError(f"Failed to create document generator workflow: {str(e)}")

# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
