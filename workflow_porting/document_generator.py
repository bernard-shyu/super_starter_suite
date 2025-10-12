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

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, Literal
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_utils import execute_adapter_workflow
from super_starter_suite.shared.dto import MessageRole, create_chat_message

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full workflow reimplementation
from llama_index.core.workflow import Workflow, Context, Event, StartEvent, StopEvent, step
from llama_index.server.api.models import (
    ChatAPIMessage, ChatRequest, Artifact, ArtifactEvent, ArtifactType,
    DocumentArtifactData, UIEvent
)
from llama_index.core.base.llms.types import ChatMessage as LlamaChatMessage
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.prompts import PromptTemplate
from llama_index.core.settings import Settings
from super_starter_suite.shared.artifact_utils import extract_artifact_metadata
from pydantic import BaseModel, Field

import time
import re
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("workflow.ported.document_generator")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "P_document_generator"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

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
            logger.debug(f"Pattern C: Could not retrieve last artifact: {e}")
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

        logger.info(f"Pattern C: Preparing chat history for: {user_msg[:50]}...")

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
        logger.info("Pattern C: Planning document requirements...")

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

        logger.info(f"Pattern C: Planning result - {requirement.type} document: '{requirement.title}'")

        return GenerateArtifactEvent(requirement=requirement)

    @step
    async def generate_artifact(self, ctx: Context, event: GenerateArtifactEvent) -> SynthesizeAnswerEvent:
        """
        PHASE 3: Generate document artifact

        Create or update document based on planning requirements
        """
        logger.info(f"Pattern C: Generating {event.requirement.type} document: '{event.requirement.title}'")

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
        logger.info("Pattern C: Synthesizing final answer...")

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
            logger.warning("Pattern C: No JSON block found in planning response, defaulting to markdown")
            return DocumentRequirement(
                type="markdown",
                title="Document",
                requirement="Create a basic document based on the user's request."
            )

        try:
            return DocumentRequirement.model_validate_json(json_block.group(1).strip())
        except Exception as e:
            logger.error(f"Pattern C: Failed to parse requirement JSON: {e}")
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
            logger.debug("Pattern C: No document block found in response")
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
def create_workflow(chat_request: ChatRequest) -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Create document generation workflow instance
    - Handle initialization and configuration
    """
    try:
        logger.debug("Pattern C: Creating DocumentArtifactWorkflow instance")

        # Use global workflow_config timeout (240.0 seconds for document generator)
        timeout_seconds = workflow_config.timeout if workflow_config else 240.0

        logger.info(f"Pattern C: Using configured workflow timeout of {timeout_seconds}s")
        workflow = DocumentArtifactWorkflow(
            chat_request=chat_request,
            timeout=timeout_seconds
        )

        return workflow

    except Exception as e:
        logger.error(f"Pattern C: Workflow creation failed: {e}")
        raise ValueError(f"Failed to create document generator workflow: {str(e)}")

# ====================================================================================
# STEP 4-5-6: COMPLETE SERVER ENDPOINT WITH APPROACH E ARTIFACT EXTRACTION (PATTERN C)
# ====================================================================================
# ====================================================================================
# STEP 4: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# Thin factory function (belongs in this file with workflow logic)
def create_document_generator_workflow_factory(chat_request: Optional[ChatRequest] = None):
    """Thin factory that returns workflow instance using local implementation"""
    if chat_request is None:
        raise ValueError("ChatRequest must be provided for ported workflow factory")
    return create_workflow(chat_request)

@router.post("/chat")
@bind_workflow_session(workflow_config)
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    THIN ENDPOINT WRAPPER - delegates to shared infrastructure

    This endpoint now uses shared execute_ported_workflow() instead of
    containing 150+ lines of duplicate infrastructure code.
    """
    # Extract request parameters
    user_message = payload["question"]
    session = request.state.chat_session
    chat_memory = request.state.chat_memory
    user_config = request.state.user_config
    chat_manager = request.state.chat_manager

    # Use PROVEN execute_adapter_workflow instead of buggy execute_ported_workflow
    response_data = await execute_adapter_workflow(
        workflow_factory=create_document_generator_workflow_factory,  # Ported factory
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
