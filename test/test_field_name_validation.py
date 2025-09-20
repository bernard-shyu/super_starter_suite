#!/usr/bin/env python3
"""
Simple validation script to verify the data_newest_time and data_newest_file field names
are consistently used across the backend and frontend code.
"""

import os
import sys
sys.path.append('.')

def check_backend_field_usage():
    """Check if backend code uses new field names consistently."""
    print("🔍 Checking backend field usage...")

    # Check index_utils.py
    with open('shared/index_utils.py', 'r') as f:
        content = f.read()

    # Remove comments from content for cleaner checking (look for '#' which starts comments)
    lines = content.split('\n')
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            code_lines.append(line)

    # Reconstruct content without comments
    import re
    # Remove inline comments (e.g., "...code # comment")
    code_only = '\n'.join(code_lines)
    code_only = re.sub(r'#.*', '', code_only)

    backend_checks = {
        "data_newest_time in code": '"data_newest_time"' in code_only,
        "data_newest_file in code": '"data_newest_file"' in code_only,
        "data_files field in code": '"data_files"' in code_only,
        "no active data_file_newest in code": '"data_file_newest"' not in code_only
    }

    success = all(backend_checks.values())
    print("  ✅ Backend field usage:", "PASS" if success else "FAIL")
    for check_name, passed in backend_checks.items():
        print(f"    {'✅' if passed else '❌'} {check_name}")

    return success

def check_endpoint_field_usage():
    """Check if endpoint sends new field names."""
    print("🔍 Checking endpoint field usage...")

    with open('rag_indexing/generate_endpoint.py', 'r') as f:
        content = f.read()

    endpoint_checks = {
        "sends data_newest_time": '"data_newest_time"' in content,
        "sends data_newest_file": '"data_newest_file"' in content,
        "sends data_files": '"data_files"' in content,
        "no first_filename": '"first_filename"' not in content
    }

    success = all(endpoint_checks.values())
    print("  ✅ Endpoint field usage:", "PASS" if success else "FAIL")
    for check_name, passed in endpoint_checks.items():
        print(f"    {'✅' if passed else '❌'} {check_name}")

    return success

def check_frontend_field_usage():
    """Check if frontend uses new field names."""
    print("🔍 Checking frontend field usage...")

    with open('frontend/static/generate_ui.js', 'r') as f:
        content = f.read()

    frontend_checks = {
        "uses data.data_newest_file": 'data.data_newest_file' in content,
        "no data.first_filename": 'data.first_filename' not in content,
        "no first_filename": 'first_filename' not in content
    }

    success = all(frontend_checks.values())
    print("  ✅ Frontend field usage:", "PASS" if success else "FAIL")
    for check_name, passed in frontend_checks.items():
        print(f"    {'✅' if passed else '❌'} {check_name}")

    return success

def main():
    """Main validation function."""
    print("🚀 Starting field name validation...")
    print("=" * 60)

    results = []
    results.append(check_backend_field_usage())
    print()
    results.append(check_endpoint_field_usage())
    print()
    results.append(check_frontend_field_usage())

    print()
    print("=" * 60)

    if all(results):
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ Field name consistency: data_file_newest → data_newest_time + data_newest_file")
        print("✅ Field name consistency: files → data_files")
        print("✅ All backend/frontend code updated consistently")
        return True
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("❌ Check the output above for specific failures")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
