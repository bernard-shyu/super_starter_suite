"""
Terminal Output Manager for RAG Generate UI

This module manages timestamped terminal messages for dual display
in the Generate UI - main state terminal output and live display.
"""

import logging
import asyncio
import sys
import threading
import io
from contextlib import redirect_stdout, redirect_stderr
from typing import List, Dict, Optional, Callable, Awaitable
from datetime import datetime

# Import centralized logging
from super_starter_suite.shared.config_manager import config_manager

# Get logger for terminal output (MVC internal communication)
logger = logging.getLogger("MVC_terminal")

# In-memory store for generation logs (global)
generation_logs: Dict[str, List[str]] = {}


class RealTimeLogCaptureHandler(logging.Handler):
    """Custom logging handler to capture logs and send to MVC Controller using thread-safe communication."""

    def __init__(self, task_id: str, progress_callback: Optional[Callable[[str], Awaitable[None]]] = None, loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__()
        self.task_id = task_id
        self.progress_callback = progress_callback
        try:
            self.loop = loop or asyncio.get_event_loop()
        except RuntimeError:
            # No event loop is running (e.g., in background thread)
            self.loop = None
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    def emit(self, record):
        """Capture log and send raw message to MVC Controller using thread-safe communication."""
        log_entry = self.format(record)
        if self.task_id not in generation_logs:
            generation_logs[self.task_id] = []
        generation_logs[self.task_id].append(log_entry)

        # Send raw log message to MVC Controller using thread-safe approach
        if self.progress_callback:
            try:
                # Use thread-safe approach to schedule callback on main event loop
                if self.loop and self.loop.is_running():
                    def _schedule_callback():
                        """Function to be called on the main event loop thread."""
                        try:
                            # Get the raw message (this is what gets sent to progress tracker)
                            raw_message = record.getMessage()

                            # Create task on main event loop to process the message
                            # progress_callback is async, so we need to await it or handle it properly
                            async def _process_message():
                                try:
                                    await self.progress_callback(raw_message)
                                except Exception as e:
                                    print(f"[ERROR] Failed to process message via MVC Controller: {e}")

                            # Safely create task - check if create_task is available
                            try:
                                asyncio.create_task(_process_message())
                            except (AttributeError, RuntimeError):
                                # Fallback for older Python versions or environments without create_task
                                import concurrent.futures
                                def _run_async():
                                    # Create a new event loop for this thread if needed
                                    try:
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        loop.run_until_complete(_process_message())
                                        loop.close()
                                    except Exception as e:
                                        print(f"[ERROR] Failed to run async task in fallback mode: {e}")

                                # Run in thread pool to avoid blocking
                                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                                executor.submit(_run_async)
                                executor.shutdown(wait=False)
                        except Exception as e:
                            # Use a different logger to avoid recursion
                            print(f"[ERROR] Failed to schedule MVC Controller callback: {e}")

                    # Schedule the callback on the main event loop from background thread
                    if self.loop:
                        self.loop.call_soon_threadsafe(_schedule_callback)
                else:
                    # If no event loop is available, just print to avoid recursion
                    print(f"[WARNING] No event loop available for MVC Controller callback")

            except Exception as e:
                # Use print instead of logging to avoid infinite recursion
                print(f"[ERROR] Failed to schedule MVC Controller callback: {e}")


class TerminalOutputManager:
    """
    MODEL-CENTRIC Terminal Message Manager for MVC Architecture

    MVC DESIGN PRINCIPLES:
    ======================
    This MODEL component categorizes messages by IMPORTANCE/TYPE only.
    It does NOT know about VIEW display patterns (Main vs Live panels).

    MESSAGE CATEGORIES (MODEL concern):
    - important: Critical state changes, errors, completions
    - stateful: State transitions, status updates
    - progress: Progress bars, incremental updates
    - debugging: Debug info, tracing, verbose output
    - error: Error messages and warnings
    - info: General information messages

    VIEW RESPONSIBILITY:
    ====================
    The VIEW layer decides how to display these categories:
    - Main panel: important + stateful + error
    - Live panel: progress + debugging + info
    - Or any other display pattern the VIEW chooses

    This decoupling ensures MODEL doesn't need to change when VIEW display patterns change.
    """

    # Message importance categories (MODEL-centric, not VIEW-centric)
    CATEGORY_IMPORTANT = "important"    # Critical state changes, completions
    CATEGORY_STATEFUL = "stateful"      # State transitions, status updates
    CATEGORY_PROGRESS = "progress"      # Progress bars, incremental updates
    CATEGORY_DEBUGGING = "debugging"    # Debug info, tracing
    CATEGORY_ERROR = "error"            # Errors and warnings
    CATEGORY_INFO = "info"              # General information

    def __init__(self, max_messages: int = 1000):
        self.max_messages = max_messages
        self.messages: List[Dict] = []

    def add_message(self, message: str, category: str = CATEGORY_INFO) -> Dict:
        """
        MODEL-CENTRIC: Add message with importance category.

        Args:
            message: The message text
            category: Importance category (important, stateful, progress, debugging, error, info)

        Returns:
            The created message dictionary
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        terminal_message = {
            'timestamp': timestamp,
            'message': message,
            'category': category,  # MODEL-centric categorization
        }

        # Add to messages list (MODEL stores all messages with categories)
        self.messages.append(terminal_message)

        # Maintain maximum message count
        self._trim_messages()

        return terminal_message

    def add_important_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add important message (critical state changes, completions, errors)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_IMPORTANT)

    def add_stateful_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add stateful message (state transitions, status updates)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_STATEFUL)

    def add_progress_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add progress message (progress bars, incremental updates)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_PROGRESS)

    def add_debugging_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add debugging message (debug info, tracing, verbose output)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_DEBUGGING)

    def add_error_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add error message (errors and warnings)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_ERROR)

    def add_info_message(self, message: str) -> Dict:
        """
        MODEL-CENTRIC: Add info message (general information)

        Args:
            message: The message text

        Returns:
            The created message dictionary
        """
        return self.add_message(message, self.CATEGORY_INFO)

    def get_recent_messages(self, count: int = 50) -> List[Dict]:
        """
        MODEL-CENTRIC: Get recent terminal messages (all categories)

        Args:
            count: Number of recent messages to retrieve

        Returns:
            List of recent message dictionaries
        """
        return self.messages[-count:]

    def get_messages_by_category(self, category: str, count: int = 50) -> List[Dict]:
        """
        MODEL-CENTRIC: Get messages by specific category

        Args:
            category: Category to filter by (important, stateful, progress, debugging, error, info)
            count: Number of messages to retrieve

        Returns:
            List of messages for the specified category
        """
        filtered_messages = [msg for msg in self.messages if msg['category'] == category]
        return filtered_messages[-count:]

    def get_messages_by_categories(self, categories: List[str], count: int = 50) -> List[Dict]:
        """
        MODEL-CENTRIC: Get messages by multiple categories

        Args:
            categories: List of categories to include
            count: Number of messages to retrieve per category

        Returns:
            List of messages for the specified categories
        """
        filtered_messages = [msg for msg in self.messages if msg['category'] in categories]
        return filtered_messages[-count:]

    def clear_messages(self):
        """MODEL-CENTRIC: Clear all terminal messages"""
        self.messages.clear()

    def get_message_stats(self) -> Dict:
        """
        MODEL-CENTRIC: Get statistics about terminal messages

        Returns:
            Dictionary with message statistics by category
        """
        stats = {'total_messages': len(self.messages), 'max_messages': self.max_messages}

        # Count messages by category
        for category in [self.CATEGORY_IMPORTANT, self.CATEGORY_STATEFUL, self.CATEGORY_PROGRESS,
                        self.CATEGORY_DEBUGGING, self.CATEGORY_ERROR, self.CATEGORY_INFO]:
            stats[category] = len([msg for msg in self.messages if msg['category'] == category])

        return stats

    def _trim_messages(self):
        """MODEL-CENTRIC: Trim messages to maintain maximum count"""
        if len(self.messages) > self.max_messages:
            excess = len(self.messages) - self.max_messages
            self.messages = self.messages[excess:]


# Global functions for backward compatibility
def get_generation_logs(task_id: str) -> List[str]:
    """
    Retrieve the logs for a generation task.

    Args:
        task_id: The task identifier

    Returns:
        List of log messages for the task
    """
    return generation_logs.get(task_id, [])


def clear_generation_logs(task_id: str):
    """
    Clear the logs for a generation task.

    Args:
        task_id: The task identifier
    """
    if task_id in generation_logs:
        generation_logs[task_id].clear()


# Global instance for the application
_terminal_manager = None

def get_terminal_manager() -> TerminalOutputManager:
    """Get global terminal output manager instance"""
    global _terminal_manager
    if _terminal_manager is None:
        _terminal_manager = TerminalOutputManager()
    return _terminal_manager

def reset_terminal_manager(max_messages: int = 1000) -> TerminalOutputManager:
    """Reset and return the global terminal manager instance"""
    global _terminal_manager
    _terminal_manager = TerminalOutputManager(max_messages)
    return _terminal_manager


# NOTE: StdoutCapture class removed - replaced by working wrapper functions
# The original StdoutCapture was not working and has been replaced by the
# capture_rag_generation_output() function which successfully captures TQDM progress bars


# ============================================================================
# STDOUT CAPTURE UTILITIES (TQDM Progress Bar Solution)
# ============================================================================

def capture_stdout_output(func, *args, **kwargs):
    """
    Wrap any function to capture its stdout/stderr output and send to logging system.

    This solves the issue where libraries like TQDM print directly to stdout/stderr,
    bypassing Python's logging system. The captured output is forwarded through
    the logging system so it can be captured by RealTimeLogCaptureHandler.

    Args:
        func: Any function that may produce stdout/stderr output
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the wrapped function

    Usage:
        # Direct function wrapping
        result = capture_stdout_output(some_function, arg1, arg2, kwarg=value)

        # Or use in generate_ocr_reader.py like this:
        def generate_rag_index():
            return VectorStoreIndex.from_documents(documents, show_progress=True)

        index = capture_stdout_output(generate_rag_index)
    """
    # Use the existing logger defined at module level

    def stdout_callback(captured_text: str):
        """Process captured stdout output (TQDM progress bars, etc.)."""
        clean_text = captured_text.strip()
        if clean_text:
            # Send TQDM and other stdout output to MVC Controller via logging
            # This ensures it gets captured by RealTimeLogCaptureHandler
            logger.info(f"TQDM_CAPTURE: {clean_text}")

    # Create stdout capture with callback (inline implementation)
    class StdoutRedirector:
        """Simple stdout capture implementation."""
        def __init__(self, callback):
            self.callback = callback
            self.original_stdout = None
            self.original_stderr = None

        def write(self, text):
            """Capture output and send to callback."""
            if text.strip():
                try:
                    self.callback(text.rstrip())
                except Exception as e:
                    print(f"[ERROR] Stdout capture callback failed: {e}")

        def flush(self):
            pass

        def start_capture(self):
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr
            sys.stdout = self
            sys.stderr = self

        def stop_capture(self):
            if self.original_stdout:
                sys.stdout = self.original_stdout
            if self.original_stderr:
                sys.stderr = self.original_stderr

    # Create and start stdout capture
    stdout_capture = StdoutRedirector(stdout_callback)
    stdout_capture.start_capture()

    try:
        # Execute the RAG generation function
        logger.info("Starting RAG generation with stdout capture for TQDM progress bars")
        result = func(*args, **kwargs)
        logger.info("RAG generation completed successfully with stdout capture")
        return result
    finally:
        # Always restore stdout/stderr
        stdout_capture.stop_capture()
        logger.info("Stdout capture stopped, stdout/stderr restored")


def wrap_with_stdout_capture(func):
    """
    Decorator to wrap any function with stdout capture.

    This decorator captures all stdout/stderr output from the decorated function
    and forwards it through the logging system for UI display.

    Usage:
        @wrap_with_stdout_capture
        def generate_index(...):
            # TQDM output will be captured automatically
            pass
    """
    def wrapper(*args, **kwargs):
        return capture_stdout_output(func, *args, **kwargs)
    return wrapper
