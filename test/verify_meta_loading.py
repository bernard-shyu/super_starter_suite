
import sys
import os
import asyncio

# Setup path
project_root = "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding/super_starter_suite"
parent_root = os.path.dirname(project_root)
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

# Mock some things if needed
from unittest.mock import MagicMock

# Attempt to load the workflow config
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.dto import WorkflowConfig

async def test_load_meta_workflow():
    all_success = True
    for workflow_id in ["M_rag_codegen", "M_rag_docgen"]:
        print(f"\n--- Testing load of {workflow_id} ---")
        try:
            config = get_workflow_config(workflow_id)
            print(f"Workflow ID: {config.workflow_ID}")
            print(f"Integrate Type: {config.integrate_type}")
            
            # This will trigger the dynamic import and factory retrieval
            factory = config.workflow_factory
            print("Successfully retrieved workflow factory!")
            
            # Test creating the workflow
            mock_request = MagicMock()
            mock_request.messages = []
            
            # Mock user_config
            mock_user_config = MagicMock()
            
            workflow = factory(
                chat_request=mock_request, 
                timeout_seconds=300.0,
                user_config=mock_user_config
            )
            print(f"Successfully created workflow instance: {type(workflow)}")
            
        except Exception as e:
            print(f"Failed to load or create workflow {workflow_id}: {e}")
            import traceback
            traceback.print_exc()
            all_success = False
            
    return all_success

if __name__ == "__main__":
    success = asyncio.run(test_load_meta_workflow())
    sys.exit(0 if success else 1)
