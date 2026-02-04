"""
Multi-Agent Workflow: RAG + Code Generation

This meta-workflow orchestrates a pipeline between Agentic RAG and Code Generation.
"""

from typing import Any, Optional
from fastapi import APIRouter
from llama_index.core.workflow import StartEvent, StopEvent, step, Context
from llama_index.server.api.models import ChatRequest
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_multiagent import (
    BaseMultiAgentWorkflow, 
    PipelineConfig, 
    AgentStep, 
    AgentTransition
)

logger = config_manager.get_logger("workflow.meta")
router = APIRouter()

class RAGCodeGenWorkflow(BaseMultiAgentWorkflow):
    """
    Orchestrates: RAG -> RAG (as requested by user for M_rag_codegen)
    NOTE: User requested A_agentic_rag & A_agentic_rag.
    """
    
    @step
    async def run_pipeline(self, ctx: Context, ev: StartEvent) -> StopEvent:
        """Main execution step for RAG + CodeGen pipeline"""
        query = self.get_query(ev)
        
        # Configure pipeline with A_agentic_rag & A_agentic_rag
        pipeline_config = PipelineConfig(
            pipeline_name="rag_codegen_pipeline",
            agent_steps=[
                AgentStep(agent_id="agentic_rag_1", workflow_name="A_agentic_rag"),
                AgentStep(agent_id="code_generator_1", workflow_name="A_code_generator")
            ],
            transition_type=AgentTransition.SEQUENTIAL
        )

        initial_input = {"query": query}
        
        result = await self.coordinator.execute_pipeline(ctx, pipeline_config, initial_input)
        
        return self.format_stop_event(pipeline_config, result)


def create_workflow(chat_request: ChatRequest = None, timeout_seconds: float = 600.0, **kwargs) -> RAGCodeGenWorkflow:
    """Factory function for M_rag_codegen workflow"""
    user_config = kwargs.get('user_config')
    return RAGCodeGenWorkflow(
        chat_request=chat_request, 
        user_config=user_config,
        timeout=timeout_seconds
    )
