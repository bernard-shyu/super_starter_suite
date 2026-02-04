"""
5. Fixed Nvidia LLM 400 Bad Request
   Resolved critical 400 Bad Request errors ("Unexpected role 'user' after role 'tool'") by removing manual intermediate messages that broke strict role sequencing.

   * Role Sequencing: Removed manual "handover" messages in financial_report.py and the Adapted workflow to ensure a valid Tool -> Assistant flow.
   * System Prompt Enhancement: Improved base system prompts to guide the LLM through phase transitions (Research → Analysis → Reporting) implicitly.
   * Unified Fix: Both Ported and Adapted workflows are now compliant with strict completion APIs like Nvidia/Qwen.
"""
import os
from typing import List, Optional

try:
    from app.index import get_index
except ImportError:
    from super_starter_suite.shared.index_utils import get_index

from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.llms.function_calling import FunctionCallingLLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolSelection
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.server.api.models import AgentRunEvent, ChatRequest
from llama_index.server.settings import server_settings
from llama_index.server.tools.index import get_query_engine_tool

# Import local utilities instead of site-packages
from super_starter_suite.shared.tools.interpreter import E2BCodeInterpreter
from super_starter_suite.shared.tools.document_generator import DocumentGenerator
from super_starter_suite.shared.agent_utils import (
    call_tools,
    chat_with_tools,
)

from super_starter_suite.shared.config_manager import config_manager


def create_workflow(chat_request: Optional[ChatRequest] = None, timeout_seconds: float = 300.0) -> Workflow:
    index = get_index(chat_request=chat_request)
    if index is None:
        raise ValueError(
            "Index is not found. Try run generation script to create the index first."
        )
    query_engine_tool = get_query_engine_tool(index=index)
    e2b_api_key = os.getenv("E2B_API_KEY")
    if e2b_api_key is None:
        raise ValueError(
            "E2B_API_KEY is required to use the code interpreter tool. Please check README.md to know how to get the key."
        )
    # Calculate RAG-ROOT output directory for tool artifacts
    user_id = chat_request.id if chat_request else "anonymous"
    user_config = config_manager.get_user_config(user_id)
    rag_root = user_config.my_rag_root
    target_output_dir = os.path.join(rag_root, "chat_history", "A_financial_report", "output")
    os.makedirs(target_output_dir, exist_ok=True)

    code_interpreter_tool = E2BCodeInterpreter(
        api_key=e2b_api_key,
        output_dir=target_output_dir
    ).to_tool()
    
    document_generator_tool = DocumentGenerator(
        file_server_url_prefix=server_settings.file_server_url_prefix,
        output_dir=target_output_dir
    ).to_tool()

    return FinancialReportWorkflow(
        query_engine_tool=query_engine_tool,
        code_interpreter_tool=code_interpreter_tool,
        document_generator_tool=document_generator_tool,
        timeout=timeout_seconds  # Use configurable timeout instead of hardcoded
    )


class InputEvent(Event):
    input: List[ChatMessage]
    response: bool = False


class ResearchEvent(Event):
    input: list[ToolSelection]


class AnalyzeEvent(Event):
    input: list[ToolSelection] | ChatMessage


class ReportEvent(Event):
    input: list[ToolSelection]


class FinancialReportWorkflow(Workflow):
    """
    A workflow to generate a financial report using indexed documents.

    Requirements:
    - Indexed documents containing financial data and a query engine tool to search them
    - A code interpreter tool to analyze data and generate reports
    - A document generator tool to create report files

    Steps:
    1. LLM Input: The LLM determines the next step based on function calling.
       For example, if the model requests the query engine tool, it returns a ResearchEvent;
       if it requests document generation, it returns a ReportEvent.
    2. Research: Uses the query engine to find relevant chunks from indexed documents.
       After gathering information, it requests analysis (step 3).
    3. Analyze: Uses a custom prompt to analyze research results and can call the code
       interpreter tool for visualization or calculation. Returns results to the LLM.
    4. Report: Uses the document generator tool to create a report. Returns results to the LLM.
    """

    _default_system_prompt = """
    You are a professional financial analyst. Your goal is to provide deep research, accurate analysis, and high-quality reports.
    
    Your Workflow:
    1. RESEARCH Phase: Use 'query_engine_tool' to gather specific financial data from provided documents.
    2. ANALYSIS Phase: Critically examine gathered data. Use 'code_interpreter' for calculations or data visualizations.
    3. REPORTING Phase: Use 'document_generator' to create the final deliverable.
    
    Strict Guidelines:
    - Never invent data; use only information gathered from tools.
    - If research information is insufficient, continue researching before attempting analysis.
    - After tools return results, proceed immediately to the next logical phase in your analysis.
    """
    stream: bool = True

    def __init__(
        self,
        query_engine_tool: QueryEngineTool,
        code_interpreter_tool: FunctionTool,
        document_generator_tool: FunctionTool,
        llm: Optional[FunctionCallingLLM] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.system_prompt = system_prompt or self._default_system_prompt
        self.query_engine_tool = query_engine_tool
        self.code_interpreter_tool = code_interpreter_tool
        self.document_generator_tool = document_generator_tool
        assert query_engine_tool is not None, (
            "Query engine tool is not found. Try run generation script or upload a document file first."
        )
        assert code_interpreter_tool is not None, "Code interpreter tool is required"
        assert document_generator_tool is not None, (
            "Document generator tool is required"
        )
        self.tools = [
            self.query_engine_tool,
            self.code_interpreter_tool,
            self.document_generator_tool,
        ]
        self.llm: FunctionCallingLLM = llm or Settings.llm  # type: ignore
        assert isinstance(self.llm, FunctionCallingLLM)
        self.memory = ChatMemoryBuffer.from_defaults(llm=self.llm)

    @step()
    async def prepare_chat_history(self, ctx: Context, ev: StartEvent) -> InputEvent:
        self.stream = ev.get("stream", True)
        user_msg = ev.get("user_msg")
        chat_history = ev.get("chat_history")

        # 1. Add system prompt FIRST
        if self.system_prompt:
            self.memory.put(ChatMessage(
                role=MessageRole.SYSTEM, content=self.system_prompt
            ))

        # 2. Add history
        if chat_history is not None:
            self.memory.put_messages(chat_history)

        # 3. Add latest user query
        self.memory.put(ChatMessage(role=MessageRole.USER, content=user_msg))

        return InputEvent(input=self.memory.get())

    @step()
    async def handle_llm_input(  # type: ignore
        self,
        ctx: Context,
        ev: InputEvent,
    ) -> ResearchEvent | AnalyzeEvent | ReportEvent | StopEvent:
        """
        Handle an LLM input and decide the next step.
        """
        # Always use the latest chat history from the input
        chat_history: list[ChatMessage] = ev.input
        # Get tool calls
        response = await chat_with_tools(
            self.llm,
            self.tools,  # type: ignore
            chat_history,
        )
        if not response.has_tool_calls():
            if self.stream:
                return StopEvent(result=response.generator)
            else:
                return StopEvent(result=await response.full_response())
        # calling different tools at the same time is not supported at the moment
        # add an error message to tell the AI to process step by step
        if response.is_calling_different_tools():
            self.memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="Cannot call different tools at the same time. Try calling one tool at a time.",
                )
            )
            return InputEvent(input=self.memory.get())  # type: ignore
        self.memory.put(response.tool_call_message)
        match response.tool_name():
            case self.code_interpreter_tool.metadata.name:
                return AnalyzeEvent(input=response.tool_calls)
            case self.document_generator_tool.metadata.name:
                return ReportEvent(input=response.tool_calls)
            case self.query_engine_tool.metadata.name:
                return ResearchEvent(input=response.tool_calls)
            case _:
                raise ValueError(f"Unknown tool: {response.tool_name()}")

    @step()
    async def research(self, ctx: Context, ev: ResearchEvent) -> AnalyzeEvent:
        """
        Do a research to gather information for the user's request.
        A researcher should have these tools: query engine, search engine, etc.
        """
        ctx.write_event_to_stream(
            AgentRunEvent(
                name="Researcher",
                msg="Starting research",
            )
        )
        tool_calls = ev.input

        tool_call_outputs = await call_tools(
            ctx=ctx,
            agent_name="Researcher",
            tools=[self.query_engine_tool],
            tool_calls=tool_calls,
        )
        for tool_call_output in tool_call_outputs:
            self.memory.put(
                ChatMessage(
                    role=MessageRole.TOOL,
                    content=tool_call_output.tool_output.content,
                    additional_kwargs={
                        "name": tool_call_output.tool_output.tool_name,
                        "tool_call_id": tool_call_output.tool_call_id,
                    },
                )
            )
        # Hand off to analyze phase without breaking role sequence
        return AnalyzeEvent(input=[])

    @step()
    async def analyze(self, ctx: Context, ev: AnalyzeEvent) -> InputEvent:
        """
        Analyze the research result.
        """
        ctx.write_event_to_stream(
            AgentRunEvent(
                name="Analyst",
                msg="Starting analysis",
            )
        )
        event_requested_by_workflow_llm = isinstance(ev.input, list)
        # Requested by the workflow LLM Input step, it's a tool call
        if event_requested_by_workflow_llm:
            # Set the tool calls
            tool_calls = ev.input
        else:
            # Otherwise, it's triggered by the research step
            # Clone the shared memory to avoid conflicting with the workflow.
            chat_history = self.memory.get()
            # NO MANUAL PROMPT INJECTION HERE: Maintain Tool -> Assistant sequence
            # Check if the analyst agent needs to call tools
            response = await chat_with_tools(
                self.llm,
                [self.code_interpreter_tool],
                chat_history,
            )
            if not response.has_tool_calls():
                # If no tool call, fallback analyst message to the workflow
                msg_content = await response.full_response()
                analyst_msg = ChatMessage(
                    role=MessageRole.USER,
                    content=f"Analyst: "
                    f"\nHere is the analysis result: {msg_content}"
                    "\nUse it for other steps or response the content to the user.",
                )
                self.memory.put(analyst_msg)
                return InputEvent(input=self.memory.get())
            else:
                tool_calls = response.tool_calls
                self.memory.put(response.tool_call_message)

        # Call tools
        tool_call_outputs = await call_tools(
            ctx=ctx,
            agent_name="Analyst",
            tools=[self.code_interpreter_tool],
            tool_calls=tool_calls,  # type: ignore
        )
        for tool_call_output in tool_call_outputs:
            self.memory.put(
                ChatMessage(
                    role=MessageRole.TOOL,
                    content=tool_call_output.tool_output.content,
                    additional_kwargs={
                        "name": tool_call_output.tool_output.tool_name,
                        "tool_call_id": tool_call_output.tool_call_id,
                    },
                )
            )

        # Fallback to the input with the latest chat history
        return InputEvent(input=self.memory.get())

    @step()
    async def report(self, ctx: Context, ev: ReportEvent) -> InputEvent:
        """
        Generate a report based on the analysis result.
        """
        ctx.write_event_to_stream(
            AgentRunEvent(
                name="Reporter",
                msg="Starting report generation",
            )
        )
        tool_calls = ev.input
        tool_call_outputs = await call_tools(
            ctx=ctx,
            agent_name="Reporter",
            tools=[self.document_generator_tool],
            tool_calls=tool_calls,
        )
        for tool_call_output in tool_call_outputs:
            self.memory.put(
                ChatMessage(
                    role=MessageRole.TOOL,
                    content=tool_call_output.tool_output.content,
                    additional_kwargs={
                        "name": tool_call_output.tool_output.tool_name,
                        "tool_call_id": tool_call_output.tool_call_id,
                    },
                )
            )
        # After the tool calls, fallback to the input with the latest chat history
        return InputEvent(input=self.memory.get())
