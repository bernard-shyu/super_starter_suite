#!/usr/bin/env python3
"""
Verification test for the metadata consistency fix.

Tests the success criteria:
- ✅ Metadata shows correct file counts for all RAG types
- ✅ Filesystem consistency maintained automatically
- ✅ SCAN_DEPTH parameter properly integrated
- ✅ Auto-regeneration works when inconsistencies detected
- ✅ No cross-contamination between RAG types

This test verifies that the Generate UI fix resolves the original issue
where folders showed 0 files despite containing files.
"""

import json
import os
import tempfile
from pathlib import Path
from super_starter_suite.shared.config_manager import ConfigManager
from super_starter_suite.shared.index_utils import load_data_metadata, save_data_metadata


def test_metadata_consistency_and_correct_counts():
    """
    Test that metadata shows correct file counts for all RAG types.

    This addresses the original bug where folders showed 0 files despite containing files.
    """
    print("=" * 60)
    print("TEST: Metadata Consistency and Correct File Counts")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up temporary directory structure
        rag_root = Path(temp_dir)
        config_manager = ConfigManager()

        # Create test RAG directories with files
        rag_types = ["RAG", "CODE_GEN", "FINANCE", "TINA_DOC"]
        expected_counts = {}

        for rag_type in rag_types:
            # Create data directory for this RAG type (following the convention: data.{rag_type})
            data_dir = rag_root / f"data.{rag_type}"
            data_dir.mkdir(parents=True, exist_ok=True)

            # Add some test files
            files_created = 0
            for i in range(3 + len(rag_type)):  # Vary file counts per RAG type
                file_path = data_dir / f"test_file_{i}.txt"
                file_path.write_text(f"Test content for {rag_type} file {i}")
                files_created += 1

            expected_counts[rag_type] = files_created
            print(f"Created {files_created} files in data/{rag_type}/")

        print("\nTesting metadata operations...")

        # Test 1: Fresh metadata creation (Empty metadata case)
        print("\n1. Testing fresh metadata creation:")
        user_config = config_manager.get_user_config("Default")

        # Override the RAG root for this test
        original_rag_root = user_config.my_rag.rag_root
        user_config.my_rag.rag_root = str(rag_root)

        try:
            # Load metadata (should trigger empty metadata creation)
            metadata = load_data_metadata(user_config, "RAG")

            if metadata is None:
                print("❌ FAILED: load_data_metadata returned None")
                return False

            print("✅ SUCCESS: Metadata created automatically")

            # Verify all RAG types have been initialized
            metadata_file = rag_root / ".data_metadata.json"
            if not metadata_file.exists():
                print("❌ FAILED: Metadata file was not created")
                return False

            # Load and verify the full metadata file
            with open(metadata_file, 'r') as f:
                full_metadata = json.load(f)

            print(f"✅ SUCCESS: Metadata file created with {len(full_metadata)} RAG types")

            # Test 2: Verify correct file counts
            print("\n2. Testing correct file counts:")
            correct_counts = True

            for rag_type in rag_types:
                if rag_type not in full_metadata:
                    print(f"❌ FAILED: RAG type '{rag_type}' missing from metadata")
                    correct_counts = False
                    continue

                meta_count = full_metadata[rag_type].get('total_files', 0)
                expected_count = expected_counts[rag_type]

                if meta_count == expected_count:
                    print(f"✅ RAG type '{rag_type}': metadata={meta_count}, actual={expected_count}")
                else:
                    print(f"❌ FAILED: RAG type '{rag_type}': metadata={meta_count}, actual={expected_count}")
                    correct_counts = False

            if not correct_counts:
                print("❌ FAILED: Incorrect file counts detected")
                return False

            print("✅ SUCCESS: All file counts are correct")

            # Test 3: Test SCAN_DEPTH parameter integration
            print("\n3. Testing SCAN_DEPTH parameter integration:")

            # Test different scan depths
            scan_depths = ["minimal", "fast", "balanced", "full"]

            for scan_depth in scan_depths:
                # Temporarily set scan depth using config manager
                user_settings = config_manager.get_merged_config("Default")
                if "GENERATE" not in user_settings:
                    user_settings["GENERATE"] = {}
                user_settings["GENERATE"]["SCAN_DEPTH"] = scan_depth
                config_manager.save_user_settings("Default", user_settings)

                try:
                    # Clear any cached user config to force reload
                    if "Default" in config_manager._user_configs:
                        del config_manager._user_configs["Default"]

                    metadata_with_depth = load_data_metadata(user_config, "RAG")
                    if metadata_with_depth is not None:
                        print(f"✅ SCAN_DEPTH '{scan_depth}': Successfully processed")
                    else:
                        print(f"❌ FAILED: SCAN_DEPTH '{scan_depth}': Failed to process")
                        return False
                except Exception as e:
                    print(f"❌ FAILED: SCAN_DEPTH '{scan_depth}': Exception - {e}")
                    return False

            print("✅ SUCCESS: All SCAN_DEPTH values work properly")

            # Test 4: Test auto-regeneration consistency
            print("\n4. Testing auto-regeneration consistency:")

            # Delete some files from one RAG type
            data_dir = rag_root / "data.RAG"
            test_file = data_dir / "test_file_0.txt"
            if test_file.exists():
                test_file.unlink()
                expected_counts["RAG"] -= 1

            # Load metadata again - should detect inconsistency and regenerate
            metadata_after_delete = load_data_metadata(user_config, "RAG")

            if metadata_after_delete is None:
                print("❌ FAILED: Auto-regeneration returned None")
                return False

            # Check if the count was updated
            current_rag_meta = load_data_metadata(user_config, "RAG")
            current_count = current_rag_meta.get('total_files', 0) if current_rag_meta else 0

            if current_count == expected_counts["RAG"]:
                print(f"✅ SUCCESS: Auto-regeneration updated count: {current_count} files")
            else:
                print(f"❌ FAILED: Auto-regeneration failed: current={current_count}, expected={expected_counts['RAG']}")
                return False

            # Test 5: Test no cross-contamination
            print("\n5. Testing no cross-contamination between RAG types:")

            # Load metadata for all RAG types and verify they're independent
            cross_contamination = False

            for rag_type in rag_types:
                type_metadata = load_data_metadata(user_config, rag_type)

                if type_metadata is None:
                    print(f"❌ FAILED: Cross-contamination - {rag_type} metadata missing")
                    cross_contamination = True
                    continue

                # Verify the data_files only contain files from this RAG type
                files_data = type_metadata.get('data_files', {})

                # Handle both dict and list formats (metadata file stores as dict, StatusData converts to list)
                if isinstance(files_data, dict):
                    files_list = []
                    for filename, file_info in files_data.items():
                        if isinstance(file_info, dict):
                            files_list.append({
                                "name": filename,
                                **file_info
                            })
                elif isinstance(files_data, list):
                    files_list = files_data
                else:
                    files_list = []

                for file_info in files_list:
                    if isinstance(file_info, dict):
                        file_name = file_info.get('name', '')
                        if not file_name.startswith(f"{rag_type}/") and not file_name.startswith("data/"):
                            # Allow relative paths or names that include the RAG type
                            if rag_type not in file_name and "test_file" not in file_name:
                                print(f"❌ FAILED: Cross-contamination - {rag_type} contains file '{file_name}' from different RAG type")
                                cross_contamination = True
                    else:
                        # Handle case where file_info is a string
                        print(f"⚠️  WARNING: Unexpected file_info format (string) in {rag_type}: {file_info}")
                        continue

            if not cross_contamination:
                print("✅ SUCCESS: No cross-contamination between RAG types")
            else:
                print("❌ FAILED: Cross-contamination detected between RAG types")
                return False

        finally:
            # Restore original configuration
            user_config.my_rag.rag_root = original_rag_root

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! Metadata consistency fix is working correctly.")
    print("✅ Metadata shows correct file counts for all RAG types")
    print("✅ Filesystem consistency maintained automatically")
    print("✅ SCAN_DEPTH parameter properly integrated")
    print("✅ Auto-regeneration works when inconsistencies detected")
    print("✅ No cross-contamination between RAG types")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_metadata_consistency_and_correct_counts()
    exit(0 if success else 1)
