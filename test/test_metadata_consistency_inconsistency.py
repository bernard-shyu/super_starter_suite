#!/usr/bin/env python3
"""
Test script to verify metadata consistency validation detects inconsistencies.
This tests the implementation plan for metadata consistency fixes.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding/super_starter_suite")

from super_starter_suite.shared.config_manager import ConfigManager
from super_starter_suite.shared.index_utils import _check_filesystem_consistency

def test_inconsistency_detection():
    """Test that consistency validation correctly detects metadata/filesystem mismatches"""
    print("🧪 Testing Metadata Inconsistency Detection")
    print("=" * 50)

    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create actual test data directories
        test_data_dir = temp_path / "data" / "RAG"
        test_data_dir.mkdir(parents=True, exist_ok=True)

        # Create only 1 actual file
        actual_file = test_data_dir / "actual_file.txt"
        actual_file.write_text("This is the only real file")

        print(f"📁 Created test data directory: {test_data_dir}")
        print(f"📄 Created 1 actual file: {actual_file}")

        # Create inconsistent metadata (claims 3 files but only 1 exists)
        metadata_file = temp_path / ".data_metadata.json"
        inconsistent_metadata = {
            "RAG": {
                "meta_last_update": "2025-09-20T09:30:00.000000",
                "data_newest_time": "2025-09-20T09:30:00.000000",
                "total_files": 3,  # INCORRECT - only 1 file actually exists
                "total_size": 1000,
                "data_files": {
                    "fake_file1.txt": {"size": 100, "modified": "2025-09-20T09:30:00.000000", "hash": "fake"},
                    "fake_file2.txt": {"size": 200, "modified": "2025-09-20T09:30:00.000000", "hash": "fake"},
                    "actual_file.txt": {"size": 25, "modified": "2025-09-20T09:30:00.000000", "hash": "fake"}
                },
                "rag_type": "RAG"
            }
        }

        print("   📝 Created inconsistent metadata claiming 3 files")

        # Create a mock user config object
        class MockUserRAG:
            def __init__(self, data_path):
                self.data_path = data_path
                self.rag_type = "RAG"

            def set_rag_type(self, rag_type):
                self.rag_type = rag_type
                self.data_path = str(Path(temp_path) / "data" / rag_type)

        mock_rag = MockUserRAG(str(test_data_dir))

        # Test consistency checking
        print("\n🔍 Testing consistency validation...")
        consistency_result = _check_filesystem_consistency(inconsistent_metadata, mock_rag, "balanced")

        print(f"   🔍 Consistency check result:")
        print(f"      needs_regeneration: {consistency_result['needs_regeneration']}")
        print(f"      inconsistent_types: {consistency_result['inconsistent_types']}")

        # Verify it detected inconsistency
        if consistency_result["needs_regeneration"] and "RAG" in consistency_result["inconsistent_types"]:
            print("   ✅ SUCCESS: Inconsistency correctly detected!")
            print("   📋 Metadata consistency validation is working properly")
            return True
        else:
            print("   ❌ FAILURE: Inconsistency not detected")
            print("   📋 Metadata consistency validation is NOT working properly")
            return False

if __name__ == "__main__":
    try:
        success = test_inconsistency_detection()
        if success:
            print("\n🎉 Inconsistency detection test PASSED!")
            print("📋 The metadata consistency system correctly identifies when metadata doesn't match the filesystem.")
        else:
            print("\n❌ Inconsistency detection test FAILED!")
            print("📋 The metadata consistency system is NOT working properly.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
