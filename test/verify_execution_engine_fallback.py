
import asyncio
import logging
from unittest.mock import MagicMock, patch
from super_starter_suite.chat_bot.workflow_execution.execution_engine import process_workflow_response
from super_starter_suite.shared.dto import WorkflowConfig, ExecutionContext

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_fallback")

async def test_fallback_logic():
    print("\n--- Testing Execution Engine Fallback Logic ---")

    # 1. Setup Mock objects
    workflow_config = WorkflowConfig(
        code_path="mock.path",
        timeout=60.0,
        display_name="Test Workflow",
        workflow_ID="T_workflow",
        integrate_type="meta"
    )

    execution_context = MagicMock(spec=ExecutionContext)
    execution_context.session = MagicMock()
    execution_context.session.session_id = "test_session_id"

    # Mock handler that implements __await__ and stream_events
    class MockHandler:
        def __init__(self, result):
            self.result = result
        
        async def stream_events(self):
            # Implement an empty async iterator
            yield MagicMock() # Yield something to make it an async generator
            
        def __await__(self):
            async def _run():
                return self.result
            return _run().__await__()

    final_result_dict = {
        "response": "Final distilled answer",
        "artifacts": [{"name": "recovered_doc.md", "type": "document", "content": "Recovered content"}],
        "citations": [{"id": "node_1", "text": "Source context"}]
    }
    handler = MockHandler(final_result_dict)
    
    # We need to overcome the fact that process_workflow_events is called inside process_workflow_response
    # Let's patch process_workflow_events and Settings in execution_engine
    
    with patch('super_starter_suite.chat_bot.workflow_execution.execution_engine.process_workflow_events') as mock_pwe, \
         patch('super_starter_suite.chat_bot.workflow_execution.execution_engine.Settings') as mock_settings:
        
        # Setup mock_pwe to return empty values to force fallback
        mock_pwe.return_value = ("", [], "", None, [])
        
        # Setup mock_settings
        mock_llm = MagicMock()
        mock_llm._sss_provider = "mock_provider"
        mock_llm._sss_model_id = "mock_model"
        mock_settings.llm = mock_llm
        
        print("Executing process_workflow_response with empty stream results...")
        result = await process_workflow_response(
            workflow_config=workflow_config,
            execution_context=execution_context,
            logger=logger,
            handler=handler
        )

        print("\n--- Results ---")
        print(f"Response: {result.get('response')}")
        artifacts = result.get('artifacts', [])
        print(f"Total artifacts: {len(artifacts)}")
        for art in artifacts:
            print(f" - Found artifact: {art.get('name')}")
            
        citations = result.get('source_nodes', [])
        print(f"Total source nodes (citations): {len(citations)}")

        # Verifications
        if len(artifacts) == 1 and artifacts[0]['name'] == 'recovered_doc.md':
            print("\nSUCCESS: Artifact recovered from final_result dict!")
        else:
            print("\nFAILURE: Artifact NOT recovered correctly.")

        if len(citations) == 1 and citations[0]['id'] == 'node_1':
            print("SUCCESS: Citations recovered from final_result.citations!")
        else:
            print("FAILURE: Citations NOT recovered correctly.")

if __name__ == "__main__":
    asyncio.run(test_fallback_logic())
