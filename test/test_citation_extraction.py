#!/usr/bin/env python3
"""
Test script to verify citation and artifact extraction logic
"""

import re
import uuid

def extract_citations_from_text(response_content):
    """Extract citations from response text (copied from workflow_utils.py)"""
    sources = []

    try:
        lines = response_content.split('\n')
        if not isinstance(lines, list):
            lines = [str(response_content)]
    except Exception as e:
        print(f"Failed to split response_content: {e}")
        lines = [str(response_content)]

    for line in lines:
        stripped = line.strip()

        # Citations: Only extract REAL UUID citations, filter out fake human-readable labels
        citation_match = re.search(r'\[citation:[^\]]+\]', stripped)
        if citation_match:
            citation = citation_match.group(0)
            citation_id = citation.replace('[citation:', '').replace(']', '')

            # FILTER OUT FAKE CITATIONS: Only accept real UUIDs with dashes and proper format
            try:
                # Try to validate as real UUID - this will raise exception for fake labels
                uuid.UUID(citation_id)
                if citation not in sources:
                    sources.append(citation)
            except ValueError:
                # This is a fake human-readable label, not a real citation UUID
                pass

    return sources

def test_citation_extraction():
    """Test citation extraction from response text"""
    print("=== Testing Citation Extraction ===")

    # Test response with valid UUID citations
    test_response = """
    Based on the analysis, here are the key findings:

    The company reported revenue of $10M [citation:f4bdb632-d171-4e38-a14b-1c7f1f3780f5].
    This represents a 15% increase from last year [citation:12345678-1234-1234-1234-123456789abc].

    Some fake citations that should be filtered:
    [citation:USPS_guidelines] and [citation:business_communication_guide].
    """

    sources = extract_citations_from_text(test_response)

    print(f"Extracted sources: {sources}")
    print(f"Expected: ['[citation:f4bdb632-d171-4e38-a14b-1c7f1f3780f5]', '[citation:12345678-1234-1234-1234-123456789abc]']")

    # Check if we got the expected citations
    expected_citations = [
        '[citation:f4bdb632-d171-4e38-a14b-1c7f1f3780f5]',
        '[citation:12345678-1234-1234-1234-123456789abc]'
    ]

    success = set(sources) == set(expected_citations)
    print(f"Citation extraction test: {'PASS' if success else 'FAIL'}")
    return success

def extract_artifact_metadata(artifact_event_data):
    """Extract artifact metadata (copied from artifact_utils.py)"""
    try:
        # Initialize with defaults
        artifact_data = {
            'type': getattr(artifact_event_data, 'type', 'unknown'),
            'language': '',
            'file_name': '',
            'code': '',
            'content': '',  # For document artifacts
            'title': '',     # For document artifacts
            'created_at': getattr(artifact_event_data, 'created_at', None)
        }

        # Handle type enum vs string conversion
        if hasattr(artifact_data['type'], 'value'):
            artifact_data['type'] = artifact_data['type'].value

        # Extract data based on artifact type and structure
        if hasattr(artifact_event_data, 'data'):
            data = artifact_event_data.data

            # Handle DocumentArtifactData (deep_research, document_generator)
            if hasattr(data, 'content'):
                artifact_data['content'] = getattr(data, 'content', '')
                artifact_data['code'] = artifact_data['content']  # Map to code field for compatibility
                artifact_data['title'] = getattr(data, 'title', '')
                artifact_data['language'] = 'markdown'  # Default for documents

                # Generate filename from title or type
                title = artifact_data['title']
                if title:
                    # Clean title for filename
                    clean_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
                    artifact_data['file_name'] = f"{clean_title}.md"
                else:
                    artifact_data['file_name'] = f"{artifact_data['type']}_{int(artifact_data['created_at'] or 0)}.md"

            # Handle CodeArtifactData or generic code artifacts
            elif hasattr(data, 'code'):
                artifact_data['code'] = getattr(data, 'code', '')
                artifact_data['language'] = getattr(data, 'language', '')
                artifact_data['file_name'] = getattr(data, 'file_name', '')

                # Auto-generate filename if missing
                if not artifact_data['file_name']:
                    lang_ext = artifact_data['language'].lower()
                    ext_map = {'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html', 'css': 'css', 'json': 'json'}
                    ext = ext_map.get(lang_ext, 'txt')
                    artifact_data['file_name'] = f"generated_{artifact_data['type']}.{ext}"

        return artifact_data

    except Exception as e:
        print(f"ERROR: Artifact extraction failed: {e}")
        # Return minimal artifact data on failure
        return {
            'type': 'error',
            'language': '',
            'file_name': f'error_{id(artifact_event_data)}.txt',
            'code': f'Artifact extraction failed: {str(e)}',
            'content': f'Artifact extraction failed: {str(e)}',
            'created_at': None
        }

def test_artifact_extraction():
    """Test artifact extraction from mock event data"""
    print("\n=== Testing Artifact Extraction ===")

    # Mock CodeArtifactData
    class MockCodeArtifactData:
        def __init__(self):
            self.type = "code"
            self.data = MockCodeData()

    class MockCodeData:
        def __init__(self):
            self.code = "print('Hello World')"
            self.language = "python"
            self.file_name = "hello.py"

    # Mock DocumentArtifactData
    class MockDocumentArtifactData:
        def __init__(self):
            self.type = "document"
            self.data = MockDocumentData()

    class MockDocumentData:
        def __init__(self):
            self.content = "# Research Report\n\nThis is a test document."
            self.title = "Test Report"

    # Test code artifact
    code_artifact = MockCodeArtifactData()
    extracted_code = extract_artifact_metadata(code_artifact)

    print(f"Code artifact extraction: {extracted_code}")
    code_success = (
        extracted_code['type'] == 'code' and
        extracted_code['language'] == 'python' and
        extracted_code['file_name'] == 'hello.py' and
        extracted_code['code'] == "print('Hello World')"
    )
    print(f"Code artifact test: {'PASS' if code_success else 'FAIL'}")

    # Test document artifact
    doc_artifact = MockDocumentArtifactData()
    extracted_doc = extract_artifact_metadata(doc_artifact)

    print(f"Document artifact extraction: {extracted_doc}")
    doc_success = (
        extracted_doc['type'] == 'document' and
        extracted_doc['language'] == 'markdown' and
        'Test Report' in extracted_doc['file_name'] and
        extracted_doc['content'] == "# Research Report\n\nThis is a test document."
    )
    print(f"Document artifact test: {'PASS' if doc_success else 'FAIL'}")

    return code_success and doc_success

if __name__ == "__main__":
    print("Testing citation and artifact extraction logic...\n")

    citation_test = test_citation_extraction()
    artifact_test = test_artifact_extraction()

    print("\n=== Test Results ===")
    print(f"Citation extraction: {'PASS' if citation_test else 'FAIL'}")
    print(f"Artifact extraction: {'PASS' if artifact_test else 'FAIL'}")
    print(f"Overall: {'PASS' if citation_test and artifact_test else 'FAIL'}")
