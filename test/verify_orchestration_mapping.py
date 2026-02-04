
import asyncio
from super_starter_suite.shared.workflow_multiagent import BaseMultiAgentWorkflow, PipelineConfig, AgentStep, PipelineResult
from super_starter_suite.shared.dto import ChatRequest
from llama_index.core.workflow import StopEvent, step, StartEvent
from llama_index.server.api.models import ChatAPIMessage
from llama_index.core.llms import MessageRole

def test_format_stop_event():
    print("\n--- Testing BaseMultiAgentWorkflow.format_stop_event ---")
    
    # Mock chat request with dummy user message to satisfy validation
    chat_request = ChatRequest(id="test_user", messages=[
        ChatAPIMessage(role=MessageRole.USER, content="dummy query")
    ])
    
    # Instantiate workflow - MUST have at least one step returning StopEvent
    class TestWorkflow(BaseMultiAgentWorkflow):
        @step
        async def mock_step(self, ev: StartEvent) -> StopEvent:
            return StopEvent(result={})
    
    wf = TestWorkflow(chat_request=chat_request)
    
    # Setup mock pipeline config
    pipeline_config = PipelineConfig(
        pipeline_name="Test Pipeline",
        agent_steps=[AgentStep(agent_id="agent1", workflow_name="W1")]
    )
    
    # Setup the nested result dictionary that MultiAgentCoordinator returns
    orchestrator_result = {
        'pipeline_id': 'test-uuid',
        'status': PipelineResult.SUCCESS.value,
        'execution_results': [
            {
                'agent_id': 'agent1',
                'workflow': 'W1',
                'success': True,
                'result': {'content': 'Step 1 response'}
            }
        ],
        'final_result': {
            'content': 'Final aggregated response',
            'artifacts': [{'name': 'doc.pdf', 'type': 'document'}],
            'citations': [{'id': 'c1', 'text': 'Ref 1'}]
        }
    }
    
    print("Formatting stop event...")
    stop_event = wf.format_stop_event(pipeline_config, orchestrator_result)
    
    # Verify extraction
    result_data = stop_event.result
    print(f"Response extracted: {result_data.get('response')}")
    artifacts = result_data.get('artifacts', [])
    print(f"Artifacts count: {len(artifacts)}")
    citations = result_data.get('citations', [])
    print(f"Citations count: {len(citations)}")
    
    # Asserts
    if result_data.get('response') != 'Final aggregated response':
        raise AssertionError(f"Response mismatch: {result_data.get('response')}")
    if len(artifacts) != 1:
        raise AssertionError(f"Artifact count mismatch: {len(artifacts)}")
    if artifacts[0]['name'] != 'doc.pdf':
        raise AssertionError(f"Artifact name mismatch: {artifacts[0]['name']}")
    if len(citations) != 1:
        raise AssertionError(f"Citation count mismatch: {len(citations)}")
    if citations[0]['id'] != 'c1':
        raise AssertionError(f"Citation ID mismatch: {citations[0]['id']}")
    
    print("\nSUCCESS: format_stop_event correctly extracted nested data!")

if __name__ == "__main__":
    try:
        test_format_stop_event()
    except Exception as e:
        import traceback
        print(f"TEST FAILED with error: {e}")
        traceback.print_exc()
        exit(1)
