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
logger = config_manager.get_logger("progress_tracker")


class ProgressTracker:
    """
    Tracks progress using GEN_OCR:STATE and GEN_OCR:PROGRESS patterns only.

    Architectural simplification:
    - STATE patterns: Detect state transitions (parser/generation/completed)
    - PROGRESS patterns: Track file-based and page-based progress
    - Ignore all other logger output for clean separation of concerns
    """

    def __init__(self):
        self.reset()

    def reset(self, total_files: int = 0):
        """Reset progress tracking state."""
        self.state = 'ST_READY'
        self.progress = 0
        self.processed_files = 0
        self.total_files = total_files
        self.current_stage = None
        self.parser_stage = 'idle'
        self.generation_stage = 'idle'
        self.last_raw_message = ""

        logger.debug(f"ProgressTracker reset: total_files={total_files}")

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
            r'GEN_OCR:PROGRESS:\s+(EasyOCRReader|LlamaParseReader|AI-Parser|Google AIVision)\s+process\s+file',
            r'GEN_OCR:PROGRESS:\s+Processed page',
            r'GEN_OCR:PROGRESS:\s+AI-Parser finished PDF file process'
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
        # Track file-based progress
        if 'process file' in line:
            self.processed_files += 1

        # Calculate progress and create response
        progress = self._calculate_parser_progress()
        message = self._get_parser_progress_message()

        return create_progress_data(
            state=GenerationState.PARSER,
            progress=int(progress),
            message=message,
            task_id=task_id,
            rag_type=rag_type,
            metadata={
                'stage': 'file_processing',
                'processed_files': self.processed_files,
                'total_files': self.total_files
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

    def _calculate_parser_progress(self) -> float:
        """Calculate parser progress based on processed files."""
        if self.total_files == 0:
            return min(self.processed_files * 10, 100)  # Arbitrary progress if total unknown
        return min((self.processed_files / self.total_files) * 100, 100)

    def _get_parser_progress_message(self) -> str:
        """Get appropriate parser progress message."""
        if self.total_files > 0:
            return f'Processing file {self.processed_files}/{self.total_files}'
        else:
            return f'Processing file {self.processed_files}'

    def get_current_status(self) -> Dict[str, Any]:
        """Get current status for debugging/logging."""
        return {
            'state': self.state,
            'progress': self.progress,
            'processed_files': self.processed_files,
            'total_files': self.total_files,
            'parser_stage': self.parser_stage,
            'generation_stage': self.generation_stage,
            'last_message': self.last_raw_message
        }

    def set_total_files(self, total_files: int):
        """Update the total number of files to process."""
        self.total_files = total_files
        logger.debug(f"Total files updated to: {total_files}")


# Global instance for backward compatibility
_progress_tracker = None

def get_progress_tracker() -> ProgressTracker:
    """Get global progress tracker instance"""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker

def reset_progress_tracker(total_files: int = 0) -> ProgressTracker:
    """Reset and return the global progress tracker instance"""
    global _progress_tracker
    _progress_tracker = ProgressTracker()
    _progress_tracker.total_files = total_files
    return _progress_tracker
