
import os
import sys
import torch
import gc
from pathlib import Path

# Add project root to path
project_root = "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding"
sys.path.append(project_root)

from super_starter_suite.shared.index_utils import get_embed_model, Settings
from super_starter_suite.shared.workflow_utils import cleanup_workflow_cuda_resources
from llama_index.core.settings import Settings as LlamaSettings

def verify_cuda_fixes():
    if not torch.cuda.is_available():
        print("CUDA not available, skipping test.")
        return

    print("--- Phase 1: Verify Cache ---")
    for i in range(3):
        alloc_before = torch.cuda.memory_allocated() / 1024**2
        model = get_embed_model("BAAI/bge-m3")
        alloc_after = torch.cuda.memory_allocated() / 1024**2
        print(f"Run {i+1}: ID={id(model)}, Memory Use Change: {alloc_after - alloc_before:.1f}MB (Total: {alloc_after:.1f}MB)")
    
    print("\nSUCCESS: Embedding model is cached correctly if Memory Use Change is 0.0MB for Runs 2+.")

    print("\n--- Phase 2: Verify Cleanup ---")
    # Put something on CUDA if not already there (approx 400MB)
    x = torch.randn(10000, 10000, device="cuda")
    print(f"Allocated 100M floats on CUDA. Allocated: {torch.cuda.memory_allocated() / 1024**2:.1f}MB")
    
    # We need to delete the reference for gc to work
    del x
    
    # Call cleanup
    cleanup_workflow_cuda_resources("test_session", {"session_type": "test", "workflow_id": "test_workflow"})
    
    # Check if memory was freed
    print(f"After cleanup: {torch.cuda.memory_allocated() / 1024**2:.1f}MB")

if __name__ == "__main__":
    verify_cuda_fixes()
