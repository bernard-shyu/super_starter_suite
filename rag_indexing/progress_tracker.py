"""
Progress Tracker for RAG Generate UI

This module handles progress tracking and GEN_OCR pattern detection
for real-time progress updates in the Generate UI.

ARCHITECTURAL NOTE: This module focuses on STATE and PROGRESS patterns only.
- GEN_OCR:STATE patterns for state transitions (ST_PARSER, ST_GENERATION, ST_COMPLETED)
- GEN_OCR:PROGRESS patterns for progress tracking
- Ignores all other logger output for architectural simplification
"""

import re
from typing import Dict, Any, Optional
from datetime import datetime

# Import DTOs for encapsulated data
from super_starter_suite.shared.dto import (
    ProgressData,
    GenerationState,
    create_progress_data
)

# Import centralized logging
from super_starter_suite.shared.config_manager import config_manager

# Get logger for progress tracker (pure logging only)
logger = config_manager.get_logger("gen_prog")

# DEBUG: Verify logger configuration
logger.info(f"🔧 PROGRESS TRACKER LOGGER INITIALIZED: name={logger.name}, level={logger.level}, effective_level={logger.getEffectiveLevel()}")
# logger.debug("🔧 DEBUG TEST: Progress tracker logger debug message")

class ProgressTracker:
    """
    Tracks progress using GEN_OCR:STATE and GEN_OCR:PROGRESS patterns only.

    Architectural simplification:
    - STATE patterns: Detect state transitions (parser/generation/completed)
    - PROGRESS patterns: Track file-based and page-based progress
    - Ignore all other logger output for clean separation of concerns
    """

    def __init__(self, status_data=None):
        """
        Initialize ProgressTracker with optional StatusData injection.

        Args:
            status_data: StatusData object for accessing total_files
        """
        self.status_data = status_data
        self.reset()

    def reset(self):
        """Reset progress tracking state."""
        self.state = 'ST_READY'
        self.progress = 0
        self.processed_files = 0
        self.current_stage = None
        self.parser_stage = 'idle'
        self.generation_stage = 'idle'
        self.last_raw_message = ""

        # Hierarchical progress tracking (file + page level)
        self.current_file_pages = 0
        self.current_file_processed_pages = 0
        self.current_filename = ""  # Track current file being processed
        self.files_processed = set()  # Track unique files to avoid double-counting
        self.page_processing_started = False  # Track when page processing begins for current file

    def parse_rag_output(self, raw_line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> Optional[ProgressData]:
        """
        Parse single line of console output and return encapsulated ProgressData.

        ARCHITECTURAL FOCUS: Only processes GEN_OCR:STATE and GEN_OCR:PROGRESS patterns.
        Ignores all other logger output for clean separation of concerns.

        Args:
            raw_line: Raw console output line to parse
            task_id: Optional task identifier for the progress data
            rag_type: RAG type for context

        Returns:
            ProgressData object with encapsulated data, or None if no relevant pattern
        """
        self.last_raw_message = raw_line

        # DEBUG: Log all incoming lines to see what we're receiving
        logger.debug(f"PARSE_RAG_OUTPUT: Processing line: '{raw_line.strip()}'")

        # CRITICAL FIX: Once completed, don't process any more patterns
        if self.state == 'ST_COMPLETED':
            logger.debug("Generation already completed, ignoring further output")
            return None

        # STATE Patterns - Primary architectural focus
        if self._is_state_pattern(raw_line):
            logger.debug("PARSE_RAG_OUTPUT: Matched STATE pattern")
            return self._handle_state_pattern(raw_line, task_id, rag_type)

        # PROGRESS Patterns - Secondary architectural focus
        elif self._is_progress_pattern(raw_line):
            logger.debug("PARSE_RAG_OUTPUT: Matched PROGRESS pattern")
            return self._handle_progress_pattern(raw_line, task_id, rag_type)

        # Generation Progress Patterns (tqdm output, not GEN_OCR)
        elif self._is_tqdm_generation_pattern(raw_line):
            logger.debug("PARSE_RAG_OUTPUT: Matched TQDM pattern")
            return self._handle_tqdm_generation_progress(raw_line, task_id, rag_type)

        # DEBUG: Log when no pattern matches
        logger.debug(f"PARSE_RAG_OUTPUT: No pattern match for line: '{raw_line.strip()}'")
        return None

    def _is_state_pattern(self, line: str) -> bool:
        """Check if line contains GEN_OCR:STATE patterns for state transitions."""
        state_patterns = [
            r'GEN_OCR:STATE:\s+Start document parsing with extractor',
            r'GEN_OCR:STATE:\s+Start RAG index generating to Storage',
            r'GEN_OCR:STATE:\s+Finished RAG index generating'
        ]

        for pattern in state_patterns:
            if re.search(pattern, line):
                return True
        return False

    def _is_progress_pattern(self, line: str) -> bool:
        """Check if line contains GEN_OCR:PROGRESS patterns for progress tracking."""
        progress_patterns = [
            r'GEN_OCR:PROGRESS:\s+(EasyOCRReader|LlamaParseReader|AI-Parser)\s+process\s+file',
            r'GEN_OCR:PROGRESS:\s+Processed page'
        ]

        for pattern in progress_patterns:
            if re.search(pattern, line):
                return True
        return False

    def _is_tqdm_generation_pattern(self, line: str) -> bool:
        """Check if line contains tqdm generation progress patterns."""
        return ('Parsing nodes:' in line and ('%| ' in line or 'it/s' in line)) or \
               ('Generating embeddings:' in line and ('%| ' in line or 'it/s' in line))

    def _handle_state_pattern(self, line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> ProgressData:
        """Handle GEN_OCR:STATE patterns for state transitions."""
        if 'Start document parsing with extractor' in line:
            return self._handle_parser_state_start(task_id, rag_type)
        elif 'Start RAG index generating to Storage' in line:
            return self._handle_generation_state_start(task_id, rag_type)
        elif 'Finished RAG index generating' in line:
            return self._handle_completion_state(task_id, rag_type)

        # This should never happen since _is_state_pattern already validates the patterns
        raise ValueError(f"Unhandled state pattern in line: {line}")

    def _handle_progress_pattern(self, line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> ProgressData:
        """Handle GEN_OCR:PROGRESS patterns for progress tracking."""
        logger.debug(f"📄 HANDLING PROGRESS PATTERN: '{line.strip()}'")

        # Extract filename for tracking unique files (avoid double-counting)
        filename_match = re.search(r'process file:\s*\(([^)]+)\)', line)
        if filename_match:
            filename = filename_match.group(1).strip()
            logger.debug(f"📄 FILE MATCH: '{filename}' (already processed: {filename in self.files_processed})")
            if filename not in self.files_processed:
                self.files_processed.add(filename)
                self.processed_files += 1
                logger.info(f"📄 NEW FILE PROCESSED: {filename}, total processed: {self.processed_files}/{self.get_total_files()}")
            else:
                logger.debug(f"📄 FILE ALREADY PROCESSED: {filename} (skipping duplicate)")

        # Handle PDF page information and document type detection
        if 'Document Type:' in line and 'Pages:' in line:
            # Extract page count from "Document Type: <class 'pymupdf.Document'>  Pages: 33"
            pages_match = re.search(r'Pages:\s*(\d+)', line)
            if pages_match:
                # CRITICAL FIX: Reset ALL page tracking state when detecting new file
                self.current_file_pages = int(pages_match.group(1))
                self.current_file_processed_pages = 0  # Reset page counter
                self.page_processing_started = False  # Reset processing flag
                logger.info(f"📄 PDF DETECTED: {self.current_file_pages} pages - RESET page tracking")

        # Handle individual page processing
        if 'Processed page' in line:
            if not self.page_processing_started:
                self.page_processing_started = True
                logger.debug("📄 PAGE PROCESSING STARTED for current file")
            self.current_file_processed_pages += 1
            logger.debug(f"📄 PAGE PROCESSED: {self.current_file_processed_pages}/{self.current_file_pages}")

        # CRITICAL FIX: Use hierarchical page-based progress calculation for accurate tracking
        # This provides fine-grained progress within multi-page files instead of file-based only
        progress = self._calculate_page_based_progress()
        message = self._get_page_based_progress_message()

        logger.info(f"📊 PROGRESS UPDATE: {progress:.1f}% ({self.processed_files}/{self.get_total_files()} files) - '{message}'")

        return create_progress_data(
            state=GenerationState.PARSER,
            progress=int(progress),
            message=message,
            task_id=task_id,
            rag_type=rag_type,
            metadata={
                'stage': 'file_processing',
                'processed_files': len(self.files_processed),
                'total_files': self.get_total_files(),
                'current_file_pages': self.current_file_pages,
                'current_file_processed_pages': self.current_file_processed_pages
            }
        )

    def _handle_tqdm_generation_progress(self, line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> Optional[ProgressData]:
        """Handle tqdm generation progress patterns."""
        progress = self._extract_tqdm_progress(line)
        if progress is not None:
            if 'Parsing nodes:' in line:
                # Scale to 0-50% for parsing phase
                scaled_progress = progress / 2
                message = f'Parsing nodes: {progress}%'
                stage = 'parsing_nodes'
            elif 'Generating embeddings:' in line:
                # Scale to 50-100% for embedding phase
                scaled_progress = 50 + (progress / 2)
                message = f'Generating embeddings: {progress}%'
                stage = 'generating_embeddings'
            else:
                return None

            logger.debug(f"Tqdm progress: {scaled_progress}%")

            return create_progress_data(
                state=GenerationState.GENERATION,
                progress=int(scaled_progress),
                message=message,
                task_id=task_id,
                rag_type=rag_type,
                metadata={
                    'stage': stage,
                    'raw_progress': progress
                }
            )

        return None

    def _handle_parser_state_start(self, task_id: Optional[str] = None, rag_type: str = "RAG") -> ProgressData:
        """Handle parser state start transition."""
        self.parser_stage = 'parsing'
        self.state = 'ST_PARSER'
        logger.debug("Transitioned to parser state via STATE pattern")

        return create_progress_data(
            state=GenerationState.PARSER,
            progress=0,
            message='Starting document parsing...',
            task_id=task_id,
            rag_type=rag_type,
            metadata={'stage': 'parser_start'}
        )

    def _handle_generation_state_start(self, task_id: Optional[str] = None, rag_type: str = "RAG") -> ProgressData:
        """Handle generation state start transition."""
        self.parser_stage = 'completed'
        self.generation_stage = 'parsing'
        self.state = 'ST_GENERATION'
        logger.debug("Transitioned to generation state via STATE pattern")

        return create_progress_data(
            state=GenerationState.GENERATION,
            progress=0,
            message='Starting RAG index generation...',
            task_id=task_id,
            rag_type=rag_type,
            metadata={'stage': 'generation_start'}
        )

    def _handle_completion_state(self, task_id: Optional[str] = None, rag_type: str = "RAG") -> ProgressData:
        """Handle completion state transition."""
        self.state = 'ST_COMPLETED'
        self.generation_stage = 'completed'
        self.progress = 100
        logger.debug("Transitioned to completed state via STATE pattern")

        return create_progress_data(
            state=GenerationState.COMPLETED,
            progress=100,
            message='RAG generation completed successfully!',
            task_id=task_id,
            rag_type=rag_type,
            metadata={'stage': 'completed'}
        )

    def _extract_tqdm_progress(self, line: str) -> Optional[float]:
        """Extract progress percentage from tqdm output."""
        # Match patterns like:
        # "Parsing nodes: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 286/286 [00:00<00:00, 363.10it/s]"
        # "Generating embeddings:   6%|███████▋                                                                                                                           | 20/339 [00:04<01:05,  4.88it/s]"

        patterns = [
            r'(\d+)%',  # Basic percentage match
            r'(\d+)/(\d+)',  # current/total format (fallback)
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 1:
                    return float(match.group(1))
                elif len(match.groups()) == 2:
                    current = float(match.group(1))
                    total = float(match.group(2))
                    return (current / total) * 100 if total > 0 else 0

        return None

    def get_total_files(self) -> int:
        """Get total files from StatusData (single source of truth)."""
        if self.status_data is None:
            logger.warning(f"StatusData not available, using fallback total_files=0")
            return 0
        total_files = self.status_data.total_files
        logger.debug(f"Retrieved total_files={total_files} from StatusData")
        return total_files

    def _calculate_parser_progress(self) -> float:
        """Calculate parser progress based on processed files."""
        total_files = self.get_total_files()

        if total_files == 0:
            logger.debug(f"No total_files in StatusData, using fallback: processed_files={self.processed_files}, arbitrary progress={min(self.processed_files * 10, 100)}%")
            return min(self.processed_files * 10, 100)  # Arbitrary progress if total unknown

        progress = min((self.processed_files / total_files) * 100, 100)
        logger.debug(f"Parser progress calculation: processed_files={self.processed_files}, total_files={total_files}, progress={progress:.1f}%")
        return progress

    def _get_parser_progress_message(self) -> str:
        """Get appropriate parser progress message."""
        if self.get_total_files() > 0:
            return f'Processing file {self.processed_files}/{self.get_total_files()}'
        else:
            return f'Processing file {self.processed_files}'

    def _calculate_page_based_progress(self) -> float:
        """
        Calculate hierarchical file + page progress for accurate tracking.

        This method implements a two-level progress calculation:
        1. FILE LEVEL: Base progress from completed files (e.g., 14/17 files = 82.35%)
        2. PAGE LEVEL: Fine-grained progress within current file (e.g., 29/132 pages = 21.97%)

        FINAL PROGRESS = file_progress + (page_progress / total_files)

        EXAMPLE: 17 files, processing file 15 (132 pages), on page 29
        - Completed files: (14/17) * 100 = 82.35%
        - Current file pages: (29/132) * 100 = 21.97%
        - Current file contribution: 21.97% / 17 = 1.29%
        - TOTAL: 82.35% + 1.29% = 83.64%

        This prevents progress drops and provides smooth, accurate tracking.
        """
        if self.current_file_pages == 0:
            # Fall back to file-based progress if no page info available
            return self._calculate_parser_progress()

        # CRITICAL FIX: If page processing hasn't started yet, don't switch to page-based calculation
        # This prevents progress from dropping to 0 when we first detect PDF page information
        if not self.page_processing_started:
            # We're processing files but haven't started pages yet - stick with file-based progress
            file_progress = self._calculate_parser_progress()
            logger.debug(f"Page processing not started yet, using file-based progress: {file_progress}%")
            return min(file_progress, 95)  # Cap at 95% until page processing starts

        # CORRECTED: Use hierarchical file + page calculation instead of cumulative page calculation
        # This prevents the bug where page counts accumulate across all files
        if self.get_total_files() == 0:
            return 0

        # Base progress from completed files (files 1 to N-1)
        completed_files_progress = ((self.processed_files - 1) / self.get_total_files()) * 100
        completed_files_progress = max(0, completed_files_progress)  # Ensure non-negative

        # Current file contribution based on page progress within that file
        if self.current_file_pages > 0 and self.page_processing_started:
            # Current file page progress as fraction of one file's worth
            current_file_page_progress = (self.current_file_processed_pages / self.current_file_pages)
            current_file_contribution = (current_file_page_progress / self.get_total_files()) * 100

            total_progress = completed_files_progress + current_file_contribution
            logger.debug(f"Hierarchical progress: completed_files={completed_files_progress:.1f}%, "
                        f"current_file={current_file_contribution:.1f}%, "
                        f"total={total_progress:.1f}% "
                        f"(file {self.processed_files}/{self.get_total_files()}, "
                        f"page {self.current_file_processed_pages}/{self.current_file_pages})")
        else:
            # No page info yet, fall back to pure file-based progress
            total_progress = (self.processed_files / self.get_total_files()) * 100
            logger.debug(f"File-based progress: {total_progress:.1f}% "
                        f"(file {self.processed_files}/{self.get_total_files()})")

        return min(total_progress, 100)

    def _get_page_based_progress_message(self) -> str:
        """Get page-based progress message (more accurate for PDFs)."""
        if self.current_file_pages == 0:
            # Fall back to file-based message if no page info available
            return self._get_parser_progress_message()

        if self.current_file_pages > 0 and self.current_file_processed_pages > 0:
            # Show page-based progress when we have page information
            return f'Processing page {self.current_file_processed_pages}/{self.current_file_pages} - file {self.processed_files}/{self.get_total_files()}'
        else:
            # Show file-based progress until page processing starts
            return self._get_parser_progress_message()

    def get_current_status(self) -> Dict[str, Any]:
        """Get current status for debugging/logging."""
        return {
            'state': self.state,
            'progress': self.progress,
            'processed_files': self.processed_files,
            'total_files': self.get_total_files(),  # Use StatusData
            'parser_stage': self.parser_stage,
            'generation_stage': self.generation_stage,
            'last_message': self.last_raw_message,
            # Hierarchical progress tracking information
            'current_file_pages': self.current_file_pages,
            'current_file_processed_pages': self.current_file_processed_pages,
            'files_processed_count': len(self.files_processed),
            'files_processed_list': list(self.files_processed),
            'page_processing_started': self.page_processing_started
        }


# Global singletons removed - use session-based architecture instead
# All progress tracking should be done through RAGGenerationSession
