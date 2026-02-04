/**
 * Simple Citation Processor Test
 * Tests the citation rendering functionality
 */

// Mock window and document objects for testing
global.window = {
    globalState: {
        currentWorkflow: 'test-workflow'
    }
};

global.document = {
    createElement: (tag) => {
        const element = {};
        Object.defineProperty(element, 'textContent', {
            get: function() { return this._textContent || ''; },
            set: function(value) { this._textContent = value; this.innerHTML = value; }
        });
        Object.defineProperty(element, 'innerHTML', {
            get: function() { return this._innerHTML || ''; },
            set: function(value) { this._innerHTML = value; }
        });
        return element;
    }
};

// Load the citation processor
const CitationProcessor = require('../frontend/static/modules/citation-processor.js');

// Test data
const testCitations = [
    '[citation:fd1c6cdd-c96c-4235-b184-b3d203b0cfdc]',
    '[citation:5e3b6064-dbc2-433b-8e8c-58969ec41a29]'
];

const testEnhancedMetadata = {
    citations_metadata: [
        {
            uuid: 'fd1c6cdd-c96c-4235-b184-b3d203b0cfdc',
            metadata: {
                file_path: '/home/bernard/workspace/prajna_AI/prajna-stadium/llama_index/BERNARD_SPACE/Super-RAG.Default/data.RAG/101.pdf',
                file_name: '101.pdf',
                file_type: 'application/pdf',
                file_size: 47931,
                creation_date: '2025-07-09',
                last_modified_date: '2025-07-07',
                page_num: 3,
                source: '/home/bernard/workspace/prajna_AI/prajna-stadium/llama_index/BERNARD_SPACE/Super-RAG.Default/data.RAG/101.pdf'
            },
            title: '101.pdf',
            content_preview: 'Sample content from PDF...'
        },
        {
            uuid: '5e3b6064-dbc2-433b-8e8c-58969ec41a29',
            metadata: {
                file_path: '/home/bernard/workspace/prajna_AI/prajna-stadium/llama_index/BERNARD_SPACE/Super-RAG.Default/data.RAG/102.pdf',
                file_name: '102.pdf',
                file_type: 'application/pdf',
                file_size: 35241,
                creation_date: '2025-07-10',
                last_modified_date: '2025-07-08',
                page_num: 1,
                source: '/home/bernard/workspace/prajna_AI/prajna-stadium/llama_index/BERNARD_SPACE/Super-RAG.Default/data.RAG/102.pdf'
            },
            title: '102.pdf',
            content_preview: 'Another sample content...'
        }
    ]
};

async function runTests() {
    console.log('🧪 Running Citation Processor Tests...\n');

    try {
        // Test 1: Normalize citations with metadata
        console.log('Test 1: Normalizing citations with metadata');
        const normalized = CitationProcessor.normalizeCitations(testCitations, testEnhancedMetadata);
        console.log('✅ Normalized citations:', normalized);

        // Verify titles are correct
        const expectedTitles = ['101.pdf', '102.pdf'];
        const actualTitles = normalized.map(c => c.title);
        const titlesMatch = JSON.stringify(actualTitles) === JSON.stringify(expectedTitles);

        console.log('Expected titles:', expectedTitles);
        console.log('Actual titles:', actualTitles);
        console.log('Titles match:', titlesMatch ? '✅' : '❌');

        // Test 2: Render short mode
        console.log('\nTest 2: Rendering short mode');
        const shortHtml = CitationProcessor.renderShortMode(normalized);
        console.log('✅ Short mode HTML:', shortHtml);

        // Check if HTML contains proper filenames
        const hasCorrectFilenames = shortHtml.includes('101.pdf') && shortHtml.includes('102.pdf');
        console.log('Contains correct filenames:', hasCorrectFilenames ? '✅' : '❌');

        // Test 3: Render full mode
        console.log('\nTest 3: Rendering full mode');
        const fullHtml = CitationProcessor.renderFullMode(normalized);
        console.log('✅ Full mode HTML:', fullHtml);

        // Test 4: Unified rendering
        console.log('\nTest 4: Unified rendering');
        const unifiedHtml = await CitationProcessor.renderCitationsUnified(testCitations, 'Short', { enhancedMetadata: testEnhancedMetadata });
        console.log('✅ Unified HTML:', unifiedHtml);

        // Final results
        console.log('\n🎯 Test Results:');
        console.log('✅ Citation normalization:', titlesMatch ? 'PASS' : 'FAIL');
        console.log('✅ Short mode rendering:', hasCorrectFilenames ? 'PASS' : 'FAIL');
        console.log('✅ Full mode rendering:', fullHtml.includes('101.pdf') ? 'PASS' : 'FAIL');
        console.log('✅ Unified rendering:', unifiedHtml.includes('101.pdf') ? 'PASS' : 'FAIL');

        const allTestsPass = titlesMatch && hasCorrectFilenames &&
                           fullHtml.includes('101.pdf') && unifiedHtml.includes('101.pdf');

        console.log('\n🏆 Overall Result:', allTestsPass ? 'ALL TESTS PASSED ✅' : 'SOME TESTS FAILED ❌');

    } catch (error) {
        console.error('❌ Test failed with error:', error);
    }
}

// Run the tests
runTests();
