
import asyncio
import os
import sys
import logging

# Setup path
project_root = "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding/super_starter_suite"
parent_root = os.path.dirname(project_root)
sys.path.insert(0, parent_root)

from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config
from llama_index.server.api.models import ChatRequest, ChatAPIMessage
from llama_index.core.llms import MessageRole

async def test_meta_execution():
    # Configure logging to see the DEBUG messages
    config_manager.configure_logging()
    
    workflow_id = "M_rag_docgen"
    print(f"\n--- Testing execution of {workflow_id} ---")
    
    try:
        config = get_workflow_config(workflow_id)
        factory = config.workflow_factory
        
        mock_request = ChatRequest(
            id="test_user",
            messages=[ChatAPIMessage(role=MessageRole.USER, content="Explain the CUDA leak fix and then generate a summary report.")]
        )
        
        user_config = config_manager.get_user_config("test_user")
        
        workflow = factory(
            chat_request=mock_request, 
            timeout_seconds=600.0,
            user_config=user_config
        )
        
        print("Workflow created. Running...")
        handler = workflow.run(query="Explain the CUDA leak fix and then generate a summary report.")
        
        # We also want to see events to confirm event streaming
        async def monitor_events(h):
            async for ev in h.stream_events():
                # We don't need to print every event, but confirming they exist is good
                pass

        # Run concurrent monitoring
        event_task = asyncio.create_task(monitor_events(handler))
        
        result = await handler
        await event_task
        
        print("\n--- Execution Result ---")
        print(f"Response (first 200 chars): {result.get('response', '')[:200]}...")
        
        artifacts = result.get('artifacts', [])
        print(f"Artifacts collected: {len(artifacts)}")
        for i, art in enumerate(artifacts):
            print(f"  [{i}] Name: {art.get('name')}, Type: {art.get('type')}")
        
        if len(artifacts) > 0:
            print("\nSUCCESS: Artifacts were successfully aggregated from sub-agents!")
        else:
            print("\nFAILURE: No artifacts collected from sub-agents.")
            
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_meta_execution())
