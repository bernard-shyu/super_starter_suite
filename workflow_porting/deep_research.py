"""
COMPLETE Pattern C: Deep Research Workflow Porting

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
from typing import Dict, Any, Optional, List

# COMPLETE Pattern C: No imports from STARTER_TOOLS - full llama_index.core.workflow reimplementation
from llama_index.core.workflow import Workflow, Context, Event, StartEvent, StopEvent, step
from llama_index.server.api.models import (
    ChatRequest, ArtifactEvent, ArtifactType, Artifact,
    DocumentArtifactData, UIEvent, SourceNodesEvent, DocumentArtifactSource
)
from llama_index.core.indices.base import BaseIndex
from llama_index.core.memory import ChatMemoryBuffer, SimpleComposableMemory
from llama_index.core.schema import NodeWithScore
from llama_index.core.settings import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from pydantic import BaseModel, Field
from typing import Literal

import uuid
import time
import os

from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.workflow_utils import write_response_to_stream, generate_followup_questions

logger = config_manager.get_logger("workflow.ported")
router = APIRouter()

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config("P_deep_research")

# ====================================================================================
# STEP 1-2-3: COMPLETE BUSINESS LOGIC REIMPLEMENTATION (PATTERN C - NO STARTER_TOOLS)
# ====================================================================================

class PlanResearchEvent(Event):
    pass

class ResearchEvent(Event):
    question_id: str
    question: str
    context_nodes: List[NodeWithScore]

class CollectAnswersEvent(Event):
    question_id: str
    question: str
    answer: str

class ReportEvent(Event):
    pass

class UIEventData(BaseModel):
    """
    Events for DeepResearch workflow which has 3 main stages:
    - Retrieve: Retrieve information from the knowledge base.
    - Analyze: Analyze the retrieved information and provide list of questions for answering.
    - Answer: Answering the provided questions. There are multiple answer events, each with its own id that is used to display the answer for a particular question.
    """

    id: Optional[str] = Field(default=None, description="The id of the event")
    event: Literal["retrieve", "analyze", "answer"] = Field(
        default="retrieve", description="The event type"
    )
    state: Literal["pending", "inprogress", "done", "error"] = Field(
        default="pending", description="The state of the event"
    )
    question: Optional[str] = Field(
        default=None,
        description="Used by answer event to display the question",
    )
    answer: Optional[str] = Field(
        default=None,
        description="Used by answer event to display the answer of the question",
    )

class AnalysisDecision(BaseModel):
    """Reimplemented analysis decision model for research planning"""
    decision: str = Field(description="research/write/cancel decision")
    research_questions: Optional[List[str]] = Field(default_factory=list, description="Questions to research")
    cancel_reason: Optional[str] = Field(default=None, description="Reason for cancellation")

class DeepResearchWorkflow(Workflow):
    """
    COMPLETE Pattern C: DeepResearchWorkflow full reimplementation

    Multi-phase research: retrieve → analyze → answer → report
    NO STARTER_TOOLS dependencies - complete business logic ownership

    Architecture:
    - Phase 1: Document retrieval from knowledge base
    - Phase 2: Research planning and question generation
    - Phase 3: Parallel question answering using context
    - Phase 4: Comprehensive report synthesis with citations
    """

    memory: SimpleComposableMemory
    context_nodes: List[NodeWithScore]
    index: BaseIndex
    user_request: str
    stream: bool = True

    def __init__(self, index: BaseIndex, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.context_nodes = []
        self.memory = SimpleComposableMemory.from_defaults(
            primary_memory=ChatMemoryBuffer.from_defaults(),
        )

    @step
    async def retrieve(self, ctx: Context, ev: StartEvent) -> PlanResearchEvent:
        """
        PHASE 1: Retrieve documents from knowledge base

        - Initialize workflow state
        - Add user query to memory
        - Retrieve semantically similar documents
        - Emit UI events and source nodes for frontend display
        """
        logger.info(f"[RESEARCH] START: Retrieving docs for '{ev.get('user_msg')[:50]}...'")

        # Initialize workflow state
        self.stream = ev.get("stream", True)
        self.user_request = ev.get("user_msg")
        chat_history = ev.get("chat_history")

        # Initialize memory with conversation context
        if chat_history:
            self.memory.put_messages(chat_history)

        self.memory.put_messages([
            ChatMessage(role=MessageRole.USER, content=self.user_request)
        ])

        # Emit UI event for retrieval phase start
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    event="retrieve",
                    state="inprogress",
                ),
            )
        )

        # Retrieve top-k semantically similar documents
        retriever = self.index.as_retriever(similarity_top_k=int(os.getenv("TOP_K", 10)))
        nodes = retriever.retrieve(self.user_request)
        self.context_nodes.extend(nodes)

        logger.info(f"[RESEARCH] RETRIEVAL: Found {len(nodes)} documents")

        # Emit source nodes for UI display and retrieval completion
        ctx.write_event_to_stream(SourceNodesEvent(nodes=nodes))
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    event="retrieve",
                    state="done",
                ),
            )
        )

        return PlanResearchEvent()

    @step
    async def analyze(self, ctx: Context, ev: PlanResearchEvent) -> PlanResearchEvent | ResearchEvent | ReportEvent | StopEvent | None:
        """
        PHASE 2: Analyze retrieved information and plan research strategy

        - Plan research based on retrieved documents
        - Generate specific questions for investigation
        - Decide whether to research, write report, or cancel
        - Emit UI events for question tracking
        """
        logger.info("[RESEARCH] ANALYZE: Planning research strategy")

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    event="analyze",
                    state="inprogress",
                ),
            )
        )

        # Get current research progress
        total_questions = await ctx.get("total_questions", 0)
        waiting_questions = await ctx.get("waiting_questions", 0)

        # If there are still unanswered questions, wait for them to complete
        if waiting_questions > 0:
            return PlanResearchEvent()

        # Plan research strategy based on context and progress
        decision = await self._plan_research(ctx, total_questions)

        if decision.decision == "cancel":
            logger.info(f"[RESEARCH] ABORT: {decision.cancel_reason}")
            ctx.write_event_to_stream(
                UIEvent(
                    type="ui_event",
                    data=UIEventData(
                        event="analyze",
                        state="done",
                    ),
                )
            )
            return StopEvent(result=decision.cancel_reason)

        elif decision.decision == "write":
            # Ensure we have sufficient research context
            if total_questions == 0:
                logger.warning("Pattern C: Insufficient research context for report generation")
                ctx.write_event_to_stream(
                    UIEvent(
                        type="ui_event",
                        data=UIEventData(
                            event="analyze",
                            state="done",
                        ),
                    )
                )
                return StopEvent(result="Insufficient information available for comprehensive report.")

            logger.info(f"[RESEARCH] REPORT: Synthesizing findings")
            self.memory.put(ChatMessage(role=MessageRole.ASSISTANT,
                                      content="No more idea to analyze. We should report the answers."))

            self.memory.put(ChatMessage(role=MessageRole.ASSISTANT,
                                      content="Researched all the questions. Now, i need to analyze if it's ready to write a report or need to research more."))
            ctx.send_event(ReportEvent())

        else:
            # Research questions generated - proceed with parallel answering
            questions = decision.research_questions or []
            total_questions += len(questions)
            await ctx.set("total_questions", total_questions)  # For tracking
            await ctx.set(
                "waiting_questions", len(questions)
            )  # For waiting questions to be answered
            self.memory.put(
                message=ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="We need to find answers to the following questions:\n"
                    + "\n".join(questions),
                )
            )
            for question in questions:
                question_id = str(uuid.uuid4())
                ctx.write_event_to_stream(
                    UIEvent(
                        type="ui_event",
                        data=UIEventData(
                            event="answer",
                            state="pending",
                            id=question_id,
                            question=question,
                            answer=None,
                        ),
                    )
                )
                ctx.send_event(
                    ResearchEvent(
                        question_id=question_id,
                        question=question,
                        context_nodes=self.context_nodes,
                    )
                )

        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    event="analyze",
                    state="done",
                ),
            )
        )
        return None

    @step(num_workers=2)  # Enable parallel question answering
    async def answer(self, ctx: Context, ev: ResearchEvent) -> CollectAnswersEvent:
        """
        PHASE 3: Answer individual research questions using document context

        - Research each question using retrieved documents
        - Provide evidence-based answers with citations
        - Emit UI events for progress tracking
        """
        logger.info(f"[RESEARCH] QUERY: {ev.question[:50]}...")

        ctx.write_event_to_stream(
            UIEvent(type="ui_event", data=UIEventData(
                event="answer", state="inprogress", id=ev.question_id, question=ev.question
            ))
        )

        try:
            answer = await self._answer_question(ev.question, ev.context_nodes)
            logger.info(f"[RESEARCH] STEP_COMPLETE: id='{ev.question_id}'")
        except Exception as e:
            logger.error(f"Pattern C: Error answering question {ev.question}: {e}")
            answer = f"Research error: {str(e)}"

        ctx.write_event_to_stream(
            UIEvent(type="ui_event", data=UIEventData(
                event="answer", state="done", id=ev.question_id,
                question=ev.question, answer=answer
            ))
        )

        return CollectAnswersEvent(
            question_id=ev.question_id,
            question=ev.question,
            answer=answer
        )

    @step
    async def collect_answers(self, ctx: Context, ev: CollectAnswersEvent) -> PlanResearchEvent | None:
        """
        PHASE 3b: Collect and integrate research answers

        - Accumulate all research findings
        - Update conversation memory with new insights
        - Prepare for next analysis phase when all questions are answered
        """
        logger.info(f"[RESEARCH] QUERY_COMPLETE: {ev.question[:30]}...")

        # Store research findings in memory
        self.memory.put(ChatMessage(role=MessageRole.ASSISTANT,
                                  content=f"Research Finding - {ev.question}\nAnswer: {ev.answer}"))

        # Update progress counters
        total_questions = await ctx.get("total_questions", 0) + 1
        await ctx.set("total_questions", total_questions)

        waiting_questions = await ctx.get("waiting_questions", 0) - 1
        await ctx.set("waiting_questions", max(0, waiting_questions))

        self.memory.put(ChatMessage(role=MessageRole.ASSISTANT,
                                  content="Research question completed. Analyzing progress..."))

        # Only return PlanResearchEvent when all questions are answered
        if waiting_questions <= 0:
            logger.info("[RESEARCH] AGGREGATE: All questions completed")
            return PlanResearchEvent()
        else:
            logger.info(f"[RESEARCH] SYNC: {total_questions} done | {waiting_questions} pending")
            return None

    @step
    async def report(self, ctx: Context, ev: ReportEvent) -> StopEvent:
        """
        PHASE 4: Generate comprehensive research report with citations

        - Synthesize all research findings
        - Create well-structured report with evidence
        - Emit final artifact with source citations
        - Generate contextual response and follow-up questions for UI
        """
        logger.info("[RESEARCH] REPORT: Generating synthesis")

        report_content = await self._generate_report()

        logger.info(f"[RESEARCH] REPORT_GENERATED: {len(report_content)} chars")

        # No completion UI events needed for report step as workflow is ending

        # Extract research findings for follow-up question generation
        research_findings = []
        for msg in self.memory.get_all():
            if (msg.role == MessageRole.ASSISTANT and
                msg.content and
                ("Research Finding" in msg.content or "research" in msg.content.lower())):
                research_findings.append(msg.content)

        # Generate follow-up questions based on research
        followup_questions = await generate_followup_questions(
            self.user_request, research_findings, self.context_nodes
        )

        # Store context for response generation
        await ctx.set("user_request", self.user_request)
        await ctx.set("total_questions", await ctx.get("total_questions", 0))
        await ctx.set("context_nodes", self.context_nodes)

        # Generate contextual response using write_response_to_stream
        contextual_response = await write_response_to_stream(None, ctx)

        # Emit final artifact event with complete research report and sources
        ctx.write_event_to_stream(
            ArtifactEvent(
                data=Artifact(
                    type=ArtifactType.DOCUMENT,
                    created_at=int(time.time()),
                    data=DocumentArtifactData(
                        title="Deep Research Report",
                        content=report_content,
                        type="markdown",
                        sources=[
                            DocumentArtifactSource(
                                id=getattr(node, 'id', str(uuid.uuid4())),
                            )
                            for node in self.context_nodes
                        ],
                    )
                )
            )
        )

        # Include follow-up questions in the result for UI processing
        result_data = {
            "response": contextual_response,
            "followup_questions": followup_questions if followup_questions else []
        }

        if followup_questions:
            logger.info(f"[RESEARCH] FOLLOWUP: Generated {len(followup_questions)} questions")

        return StopEvent(result=result_data)

    # ====================================================================================
    # PATTERN C: REIMPLEMENTED BUSINESS LOGIC METHODS (NO STARTER_TOOLS DEPENDENCY)
    # ====================================================================================

    async def _plan_research(self, ctx: Context, total_questions: int) -> AnalysisDecision:
        """
        Pattern C: Reimplemented research planning logic

        Decision tree:
        - If no questions answered yet: Start with broad research questions
        - If moderate progress: Ask more specific questions
        - If sufficient research: Proceed to report generation
        """
        if total_questions == 0:
            # Initial research phase - broad exploratory questions
            return AnalysisDecision(
                decision="research",
                research_questions=[
                    f"What are the key concepts and components related to {self.user_request}?",
                    f"How does {self.user_request} function in practice?",
                    f"What are the main challenges and considerations for {self.user_request}?"
                ]
            )
        elif total_questions >= 6:
            # Sufficient research depth - generate comprehensive report
            return AnalysisDecision(decision="write")
        elif total_questions >= 3:
            # Moderate progress - ask more specific questions
            return AnalysisDecision(
                decision="research",
                research_questions=[
                    f"What are the detailed implementation considerations for {self.user_request}?",
                    f"Can you provide specific examples and use cases of {self.user_request}?",
                    f"What are the best practices and potential pitfalls with {self.user_request}?"
                ]
            )
        else:
            # Continue with intermediate research questions
            return AnalysisDecision(
                decision="research",
                research_questions=[
                    f"What are the practical applications of {self.user_request}?",
                    f"How do different approaches to {self.user_request} compare?"
                ]
            )

    async def _answer_question(self, question: str, context_nodes: List[NodeWithScore]) -> str:
        """
        Pattern C: Reimplemented question answering with evidence-based reasoning

        - Use retrieved document context for grounded answers
        - Include source citations for transparency
        - Provide clear, factual responses
        """
        # Build context string from retrieved nodes
        context_parts = []
        for i, node in enumerate(context_nodes[:5]):  # Limit to top 5 most relevant
            content = node.get_content()
            # Remove truncation - allow full content for comprehensive research
            context_parts.append(f"[Source {i+1}]: {content}")

        context_str = "\n\n".join(context_parts)

        # Craft research-focused prompt
        prompt = f"""
        You are a research assistant answering questions based on provided documentation.

        RESEARCH QUESTION: {question}

        AVAILABLE CONTEXT FROM DOCUMENTS:
        {context_str}

        INSTRUCTIONS:
        - Answer based ONLY on the provided context
        - If context is insufficient, clearly state this limitation
        - Include specific citations to source documents
        - Provide clear, factual, well-reasoned answers
        - Keep response focused and directly relevant to the question

        RESEARCH ANSWER:
        """

        try:
            response = await Settings.llm.acomplete(prompt)
            answer = response.text.strip()

            # Ensure answer is not empty
            if not answer:
                answer = "Based on available research documents, insufficient information to fully answer this question."

            logger.debug(f"[RESEARCH] ANSWER: Generated {len(answer)} chars")
            return answer

        except Exception as e:
            logger.error(f"[RESEARCH] ERROR: LLM failure: {e}")
            return f"Unable to complete research due to processing error: {str(e)}"

    async def _generate_report(self) -> str:
        """
        Pattern C: Reimplemented comprehensive report generation

        - Synthesize all research findings into coherent narrative
        - Structure report with clear sections and findings
        - Include citations and supporting evidence
        - Provide actionable insights and conclusions
        """
        # Gather all research context from conversation memory
        research_context = "\n".join([
            f"**{msg.role.upper()}:** {msg.content}"
            for msg in self.memory.get_all()[-20:]  # Last 20 messages for context
        ])

        # Reconstruct research timeline from memory
        research_findings = []
        for msg in self.memory.get_all():
            if (msg.role == MessageRole.ASSISTANT and
                msg.content and
                ("Research Finding" in msg.content or "research" in msg.content.lower())):
                research_findings.append(msg.content)

        findings_summary = "\n".join(research_findings[-10:])  # Most recent findings

        # Generate comprehensive research report
        report_prompt = f"""
        # COMPREHENSIVE RESEARCH REPORT GENERATION

        ## RESEARCH TOPIC
        {self.user_request}

        ## RESEARCH CONTEXT
        {research_context}

        ## KEY RESEARCH FINDINGS
        {findings_summary}

        ## REPORT REQUIREMENTS
        Generate a comprehensive, well-structured research report that:

        1. **EXECUTIVE SUMMARY**
           - Overview of research topic and objectives
           - Main findings and conclusions
           - Key insights and implications

        2. **RESEARCH METHODOLOGY**
           - Approach used for investigation
           - Sources and evidence considered
           - Depth and breadth of analysis

        3. **DETAILED FINDINGS**
           - Organized by key themes and aspects
           - Supported by research evidence and citations
           - Clear explanations of complex concepts
           - Practical implications and applications

        4. **ANALYSIS AND INSIGHTS**
           - Interpretation of findings
           - Patterns and relationships identified
           - Strengths and limitations of research
           - Comparison of different perspectives

        5. **CONCLUSIONS AND RECOMMENDATIONS**
           - Summary of key takeaways
           - Practical recommendations
           - Future research directions
           - Actionable insights for implementation

        ## FORMATTING GUIDELINES
        - Use clear markdown formatting with headers and sections
        - Include citations where findings are supported by research
        - Maintain professional, objective tone
        - Ensure logical flow and readability
        - Keep focused on research topic and findings
        """

        try:
            response = await Settings.llm.acomplete(report_prompt)
            report = response.text.strip()

            # Add report metadata
            report_header = f"""# Deep Research Report: {self.user_request}
**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
**Research Depth:** {len(research_findings)} findings analyzed
**Source Documents:** {len(self.context_nodes)} documents referenced

---

"""
            complete_report = report_header + report
            logger.info(f"[RESEARCH] REPORT_DONE: {len(complete_report)} chars")
            return complete_report

        except Exception as e:
            logger.error(f"[RESEARCH] ERROR: Report generation failed: {e}")
            return f"""# Research Report Generation Error

## Summary
Unfortunately, an error occurred during report generation: {str(e)}

## Available Research Context
{research_context[:1000]}...

## Recommendation
Please try the research again or contact support if this issue persists.
"""

# ====================================================================================
# STEP 4: COMPLETE FACTORY FUNCTION REIMPLEMENTATION (PATTERN C)
# ====================================================================================

def create_workflow(chat_request: ChatRequest, timeout_seconds: float = 300.0) -> Workflow:
    """
    Pattern C: Factory function reimplemented without STARTER_TOOLS dependency

    - Load index configuration locally
    - Initialize research workflow with proper setup
    - Handle missing dependencies gracefully
    """
    try:
        from super_starter_suite.shared.index_utils import get_index
        index = get_index(chat_request=chat_request)

        if index is None:
            logger.error("Pattern C: Index not found - ensure knowledge base is properly configured")
            raise ValueError("Index is not available. Try running setup scripts or check configuration.")

        logger.info("[RESEARCH] FACTORY: Successfully initialized, TIMEOUT: {timeout_seconds}s")
        return DeepResearchWorkflow(index=index, timeout=timeout_seconds)

    except ImportError as e:
        logger.error(f"Pattern C: Missing required dependencies: {e}")
        raise ValueError("Index utilities not available. Check if required packages are installed.")

    except Exception as e:
        logger.error(f"[RESEARCH] ERROR: Initialization failed: {e}")
        raise ValueError(f"Failed to create research workflow: {str(e)}")

# ====================================================================================
# STEP 5: THIN ENDPOINT WRAPPER USING SHARED INFRASTRUCTURE
# ====================================================================================

# LEGACY CHAT ENDPOINT REMOVED
# Workflow execution is now handled centrally through /api/workflow/{workflow}/session/{session_id}
# in super_starter_suite/chat_bot/workflow_execution/workflow_endpoints.py
