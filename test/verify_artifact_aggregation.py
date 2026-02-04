
import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Setup path
project_root = "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding/super_starter_suite"
parent_root = os.path.dirname(project_root)
sys.path.insert(0, parent_root)

from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_multiagent import MultiAgentCoordinator, PipelineConfig, AgentStep, AgentTransition, SharedMemoryContext
from llama_index.core.workflow import Context, StopEvent
from llama_index.core.schema import NodeWithScore, TextNode

# Configure logging for the test
logging.basicConfig(level=logging.DEBUG)
logger = config_manager.get_logger("workflow.meta")
logger.setLevel(logging.DEBUG)

def mock_workflow_run_rag(*args, **kwargs):
    # Simulate a workflow handler
    class MockHandler:
        async def stream_events(self):
            # yield an event to test streaming debug logs
            class GenericEvent: pass
            yield GenericEvent()
            
            # Yield citations (source nodes)
            # System uses SourceNodesEvent internally, orchestrator captures as citations
            class SourceNodesEvent:
                def __init__(self, nodes): self.nodes = nodes
            
            node = NodeWithScore(node=TextNode(text="Fact 1", id_="node_1"), score=0.9)
            yield SourceNodesEvent(nodes=[node])
            
            await asyncio.sleep(0.1)

        def __iter__(self): return self
        def __next__(self): raise StopIteration
        def __aiter__(self): return self
        async def __anext__(self): raise StopIteration

        def __await__(self):
            # Return a result with artifacts
            return self._run().__await__()

        async def _run(self):
            return {
                "response": "RAG result content",
                "artifacts": [{"name": "fact_1.txt", "type": "text", "content": "Fact 1"}]
            }
    return MockHandler()

def mock_workflow_run_docgen(*args, **kwargs):
    class MockHandler:
        async def stream_events(self):
            yield type('Event', (), {})()
        def __aiter__(self): return self
        async def __anext__(self): raise StopIteration
        def __await__(self):
            return self._run().__await__()
        async def _run(self):
            # Simulate a non-dict result (like an async_generator wrapper would return if awaited)
            # In our fix, we handle non-dict results gracefully by extracting content elsewhere
            return "Just a string response"
    return MockHandler()

async def test_artifact_aggregation():
    print("\n--- Testing Artifact Aggregation Logic ---")
    
    coordinator = MultiAgentCoordinator()
    ctx = MagicMock(spec=Context)
    
    # Mocking the factory function to return our mocks
    with patch('super_starter_suite.shared.workflow_multiagent.get_workflow_factory_function') as mock_get_factory:
        def factory_side_effect(name):
            if name == "A_agentic_rag":
                return lambda **kw: type('MockWF', (), {'run': mock_workflow_run_rag})()
            if name == "A_code_generator":
                return lambda **kw: type('MockWF', (), {'run': mock_workflow_run_docgen})()
            return None
        
        mock_get_factory.side_effect = factory_side_effect
        
        pipeline_config = PipelineConfig(
            pipeline_name="test_aggregate_pipeline",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="A_agentic_rag"),
                AgentStep(agent_id="step2", workflow_name="A_code_generator")
            ]
        )
        
        initial_input = {"query": "test query"}
        
        print("Executing pipeline...")
        result = await coordinator.execute_pipeline(ctx, pipeline_config, initial_input)
        
        print("\n--- Results ---")
        final_result = result.get('final_result', {})
        print(f"Final response: {final_result.get('content')}")
        
        artifacts = final_result.get('artifacts', [])
        print(f"Total artifacts: {len(artifacts)}")
        for art in artifacts:
            print(f" - Found artifact: {art.get('name')}")
            
        if len(artifacts) >= 1:
            print("\nSUCCESS: Artifacts were collected (even with non-dict response from step 2)!")
        else:
            print(f"\nFAILURE: Expected at least 1 artifact, got {len(artifacts)}.")

        citations = final_result.get('citations', [])
        print(f"Total citations (source nodes): {len(citations)}")
        if len(citations) >= 1:
            print("SUCCESS: Citations aggregated successfully!")
        else:
            print("FAILURE: No citations collected.")

if __name__ == "__main__":
    asyncio.run(test_artifact_aggregation())
