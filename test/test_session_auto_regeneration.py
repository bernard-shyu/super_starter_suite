#!/usr/bin/env python3
"""
Test script to verify session handles metadata auto-regeneration properly.
This tests the complete end-to-end flow from session to consistency validation.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding/super_starter_suite")

from super_starter_suite.shared.config_manager import ConfigManager

def test_session_auto_regeneration():
    """Test that session handles metadata inconsistency auto-regeneration"""
    print("🧪 Testing Session Auto-Regeneration")
    print("=" * 50)

    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create actual test data directories
        test_data_dir = temp_path / "data" / "RAG"
        test_data_dir.mkdir(parents=True, exist_ok=True)

        # Create realistic files that would be in a RAG data directory
        test_files = [
            "document1.pdf",
            "document2.txt",
            "images/image1.jpg",
            "subdir/manual.pdf",
            "reports/yearly_report.docx"
        ]

        # Create test files with realistic content
        for file_path in test_files:
            full_path = test_data_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("#" + file_path + "\nContent for " + file_path)

        print(f"📁 Created test data directory: {test_data_dir}")
        print(f"📄 Created {len(test_files)} realistic test files")

        # Create inconsistent metadata file (claims only 1 file but there are 5)
        metadata_file = temp_path / ".data_metadata.json"
        inconsistent_metadata = {
            "RAG": {
                "meta_last_update": "2025-09-20T09:37:00.000000",
                "data_newest_time": "2025-09-20T09:37:00.000000",
                "total_files": 1,  # INCORRECT - only 1 file claimed, but 5 exist
                "total_size": 1000,
                "data_files": {
                    # Only include files that don't exist - this will trigger inconsistency
                    "nonexistent1.pdf": {"size": 1000, "modified": "2025-09-20T09:37:00.000000", "hash": "fake"},
                },
                "rag_type": "RAG"
            }
        }

        # Write the inconsistent metadata
        with open(metadata_file, 'w') as f:
            json.dump(inconsistent_metadata, f, indent=2)

        print("   📝 Created inconsistent metadata file claiming 1 file")
        print("   📁 But filesystem actually has 5 files")

        # Try to load StatusData - this should trigger auto-regeneration
        print("\n🔍 Testing StatusData loading with inconsistency...")
        from super_starter_suite.shared.dto import StatusData

        # Create a proper user config that points to our test directory
        config_manager = ConfigManager()
        user_config = config_manager.get_user_config("Default")

        # Override paths to use our test directory
        user_config.my_rag.rag_root = str(temp_path)
        user_config.my_rag.data_path = str(test_data_dir)
        user_config.my_rag.storage_path = str(temp_path / "storage" / "RAG" / "test")
        user_config.my_rag.rag_type = "RAG"

        # Try to load StatusData - this should detect inconsistency and auto-regenerate
        status_data = StatusData.load_from_file(user_config, "RAG")

        if status_data is None:
            print("❌ FAILURE: StatusData.load_from_file() returned None")
            print("   This means metadata auto-regeneration failed")
            print("   The session would fail to initialize")
            return False

        print("   ✅ SUCCESS: StatusData loaded despite inconsistency")
        print(f"   📊 StatusData reports total_files: {status_data.total_files}")
        print(f"   📊 Files list length: {len(status_data.data_files)}")

        # Verify the data is correct
        expected_files = len(test_files)
        actual_files = status_data.total_files

        if actual_files == expected_files:
            print(f"   ✅ SUCCESS: Auto-regeneration corrected file count from WRONG to CORRECT ({actual_files} files)")
            print("   📋 Metadata consistency auto-regeneration is working!")
            return True
        elif actual_files == 1:
            print(f"   ❌ FAILURE: Auto-regeneration did NOT occur - still shows {actual_files} files")
            print(f"   📋 Expected {expected_files} files but still shows {actual_files}")
            return False
        else:
            print(f"   ⚠️  PARTIAL: Auto-regeneration partially worked - got {actual_files} files (expected {expected_files})")
            return False

if __name__ == "__main__":
    try:
        success = test_session_auto_regeneration()
        if success:
            print("\n🎉 Session auto-regeneration test PASSED!")
            print("📋 The metadata consistency system automatically fixes inconsistencies when StatusData is loaded.")
        else:
            print("\n❌ Session auto-regeneration test FAILED!")
            print("📋 The session does not handle metadata inconsistency auto-regeneration properly.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
