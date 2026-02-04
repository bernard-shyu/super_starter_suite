"""
Multi-Agent Workflow: RAG + Document Generation

This meta-workflow orchestrates a pipeline between Ported Agentic RAG and Ported Document Generator.
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

class RAGDocGenWorkflow(BaseMultiAgentWorkflow):
    """
    Orchestrates: P_agentic_rag -> P_document_generator
    """
    
    @step
    async def run_pipeline(self, ctx: Context, ev: StartEvent) -> StopEvent:
        """Main execution step for RAG + DocGen pipeline"""
        query = self.get_query(ev)
        
        # Configure pipeline with P_agentic_rag & P_document_generator
        pipeline_config = PipelineConfig(
            pipeline_name="rag_docgen_pipeline",
            agent_steps=[
                AgentStep(agent_id="ported_rag", workflow_name="P_agentic_rag"),
                AgentStep(agent_id="ported_docgen", workflow_name="P_document_generator")
            ],
            transition_type=AgentTransition.SEQUENTIAL
        )

        initial_input = {"query": query}
        
        result = await self.coordinator.execute_pipeline(ctx, pipeline_config, initial_input)
        
        return self.format_stop_event(pipeline_config, result)


def create_workflow(chat_request: ChatRequest = None, timeout_seconds: float = 600.0, **kwargs) -> RAGDocGenWorkflow:
    """Factory function for M_rag_docgen workflow"""
    user_config = kwargs.get('user_config')
    return RAGDocGenWorkflow(
        chat_request=chat_request, 
        user_config=user_config,
        timeout=timeout_seconds
    )
