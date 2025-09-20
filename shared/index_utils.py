from typing import Dict, Any, Optional, List
from pathlib import Path
import os
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Document,
    Settings  #, SimpleVectorStore
)
from llama_index.core.indices import load_index_from_storage
from llama_index.server.api.models import ChatRequest
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.server.tools.index.utils import get_storage_context
from super_starter_suite.shared.config_manager import ConfigManager, UserConfig
from super_starter_suite.shared.llama_utils import init_llm
from fastapi import BackgroundTasks

# UNIFIED LOGGING SYSTEM - Replace global logging
from super_starter_suite.shared.config_manager import config_manager

# Get logger for index utilities
utils_logger = config_manager.get_logger("gen_index")

def load_index(user_config: UserConfig):
    """
    Load a LlamaIndex index from the specified storage directory.
    Returns None if the directory does not exist.
    """
    STORAGE_DIR = user_config.my_rag.storage_path
    utils_logger.debug(f"load_index::  RAG_TYPE={user_config.my_rag.rag_type}  GEN-METHOD={user_config.my_rag.generate_method}  STORAGE=...{STORAGE_DIR[-60:]}")

    # check if storage already exists
    if not os.path.exists(STORAGE_DIR):
        raise ValueError(
            "Index is not found. Try run generation script to create the index first."
        )

    # load the existing index
    utils_logger.info(f"Loading index from {STORAGE_DIR}...")
    storage_context = get_storage_context(STORAGE_DIR)
    index = load_index_from_storage(storage_context)
    utils_logger.info(f"Finished loading index from {STORAGE_DIR}")
    return index

def get_index(chat_request: Optional[ChatRequest] = None) -> VectorStoreIndex:
    """
    Get or create the LlamaIndex for the specified user and RAG type.

    Args:
        chat_request: The request to the chat API.

    Returns:
        The LlamaIndex instance
    """
    user_id      = chat_request.id
    user_config  = ConfigManager().get_user_config(user_id)
    Settings.llm = init_llm(user_config)
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")     # English: "BAAI/bge-base-en-v1.5" / "BAAI/bge-large-en-v1.5",  multi-lingual: "BAAI/bge-m3" / "BAAI/bge-m3-retromae"
    return load_index(user_config)

def get_rag_index(user_config: UserConfig):
    """
    Convenience wrapper to load an index for a given RAG type using the globally loaded settings.
    """
    Settings.llm = init_llm(user_config)
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")     # English: "BAAI/bge-base-en-v1.5" / "BAAI/bge-large-en-v1.5",  multi-lingual: "BAAI/bge-m3" / "BAAI/bge-m3-retromae"
    return load_index(user_config)

# ============================================================================
# RAG Metadata Management System
# ============================================================================
# This system tracks data source changes to enable smart RAG regeneration.
# It uses a single metadata file (.data_metadata.json) with RAG types as keys.
#
# Metadata File Structure:  (NEW FORMAT - 2025-0920)
# {
#     "rag_type_1": {
#         "meta_last_update": "ISO datetime string",
#         "data_newest_time": "ISO datetime string",     # modified time of the Newest file of all data_files for this rag_type.
#         "data_newest_file": "string",                  # NEW: filename of the Newest file of all data_files for this rag_type.
#         "total_files": 10,
#         "total_size": 1024000,
#         "data_files": {                                # RENAMED from "files" to "data_files"
#             "file1.txt": {"size": 1000, "modified": "ISO datetime", "hash": "md5..."},
#             "file2.pdf": {"size": 2000, "modified": "ISO datetime", "hash": "md5..."}
#         },
#         "rag_storage_creation": "ISO datetime string",
#         "rag_storage_hash": "md5..."
#     },
#     "rag_type_2": { ...
#     }
# }
# ============================================================================

import json
import hashlib
from datetime import datetime

def get_metadata_file_path(user_rag_root: str) -> Path:
    """
    Get the path for the metadata file for this user's data sources.

    The metadata file is stored as a hidden file (.data_metadata.json) in the
    user's RAG root directory. This single file contains metadata for all
    RAG types used by this user, with each RAG type as a top-level key.

    Args:
        user_rag_root: Path to the user's RAG root directory

    Returns:
        Path: Full path to the metadata file
    """
    rag_root = Path(user_rag_root)
    metadata_file = rag_root / ".data_metadata.json"
    return metadata_file

def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate MD5 hash of a file for content verification with optimized performance.

    Enhanced version with:
    - Size-based optimization for small files (< 1MB)
    - Memory-mapped I/O for medium files (1MB - 10MB)
    - Chunked reading for large files (> 10MB)
    - Only calculates hash for files smaller than 10MB to avoid performance issues

    Args:
        file_path: Path to the file to hash

    Returns:
        str: MD5 hash as hex string, or empty string for large files or errors
    """
    try:
        # Get file size first to determine optimal hashing strategy
        file_size = file_path.stat().st_size

        # Skip files larger than 10MB for performance
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return ""

        hash_md5 = hashlib.md5()

        # OPTIMIZATION 1: Small files (< 1MB) - read entirely into memory
        if file_size < 1024 * 1024:  # 1MB threshold
            try:
                with open(file_path, "rb") as f:
                    hash_md5.update(f.read())
                return hash_md5.hexdigest()
            except (IOError, OSError, MemoryError):
                # Fallback to chunked reading if memory read fails
                pass

        # OPTIMIZATION 2: Medium files (1MB - 10MB) - use memory mapping when possible
        if file_size <= 10 * 1024 * 1024:  # 10MB limit
            try:
                # Try memory mapping for better performance on medium files
                import mmap
                with open(file_path, "rb") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        hash_md5.update(mm)
                return hash_md5.hexdigest()
            except (ImportError, OSError):
                # Fallback to chunked reading if memory mapping fails
                pass

        # OPTIMIZATION 3: Large files or fallback - use optimized chunked reading
        with open(file_path, "rb") as f:
            # Use larger chunks for better I/O performance (64KB instead of 4KB)
            chunk_size = 64 * 1024  # 64KB chunks for better throughput
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)

        return hash_md5.hexdigest()

    except (IOError, OSError, PermissionError) as e:
        utils_logger.warning(f"Could not calculate hash for {file_path}: {e}")
        return ""
    except Exception as e:
        utils_logger.error(f"Unexpected error calculating hash for {file_path}: {e}")
        return ""

def calculate_batch_file_hashes(file_paths: List[Path], max_workers: int = 4) -> Dict[str, str]:
    """
    Calculate MD5 hashes for multiple files in parallel for improved performance.

    This function optimizes hash calculation for repositories with many small files
    by processing them concurrently using a thread pool.

    Args:
        file_paths: List of file paths to hash
        max_workers: Maximum number of worker threads (default: 4)

    Returns:
        dict: Mapping of file path strings to their MD5 hashes
    """
    try:
        import concurrent.futures
        import threading

        # Thread-safe result storage
        results = {}
        results_lock = threading.Lock()

        def hash_single_file(file_path: Path) -> tuple[str, str]:
            """Hash a single file and return (path, hash) tuple."""
            file_hash = calculate_file_hash(file_path)
            return (str(file_path), file_hash)

        # Use ThreadPoolExecutor for CPU-bound hash calculations
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all hash jobs
            future_to_path = {
                executor.submit(hash_single_file, file_path): file_path
                for file_path in file_paths
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_path):
                try:
                    file_path_str, file_hash = future.result()
                    with results_lock:
                        results[file_path_str] = file_hash
                except Exception as e:
                    file_path = future_to_path[future]
                    utils_logger.warning(f"Failed to hash {file_path}: {e}")
                    with results_lock:
                        results[str(file_path)] = ""

        # utils_logger.debug(f"calculate_batch_file_hashes:: Processed {len(file_paths)} files with {max_workers} workers")
        return results

    except ImportError:
        # Fallback to sequential processing if concurrent.futures not available
        utils_logger.warning("calculate_batch_file_hashes:: concurrent.futures not available, falling back to sequential processing")
        results = {}
        for file_path in file_paths:
            results[str(file_path)] = calculate_file_hash(file_path)
        return results
    except Exception as e:
        utils_logger.error(f"calculate_batch_file_hashes:: Unexpected error in batch processing: {e}")
        # Fallback to sequential processing on any error
        results = {}
        for file_path in file_paths:
            results[str(file_path)] = calculate_file_hash(file_path)
        return results

def calculate_storage_hash(storage_path: str) -> str:
    """
    Calculate MD5 hash of all files in the RAG storage directory.

    This creates a combined hash of all index files to detect if the
    RAG storage has been modified or recreated.

    Args:
        storage_path: Path to the RAG storage directory

    Returns:
        str: MD5 hash as hex string representing all storage files
    """
    storage_dir = Path(storage_path)
    if not storage_dir.exists():
        return ""

    hash_md5 = hashlib.md5()

    try:
        # Sort files to ensure consistent hash regardless of filesystem order
        storage_files = []
        for file_path in storage_dir.rglob("*"):
            if file_path.is_file() and not str(file_path.name).startswith('.'):  # Skip hidden files
                try:
                    stat = file_path.stat()
                    if stat.st_size < 50 * 1024 * 1024:  # Only hash files < 50MB for storage
                        storage_files.append((str(file_path.relative_to(storage_dir)), file_path))
                except (OSError, PermissionError) as e:
                    utils_logger.warning(f"Could not access storage file {file_path}: {e}")

        # Sort by relative path for consistent ordering
        storage_files.sort(key=lambda x: x[0])

        # Hash each file's content
        for relative_path, file_path in storage_files:
            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                # Also include the filename in the hash for completeness
                hash_md5.update(relative_path.encode('utf-8'))
            except (IOError, OSError) as e:
                utils_logger.warning(f"Could not hash storage file {file_path}: {e}")

        return hash_md5.hexdigest()

    except Exception as e:
        utils_logger.error(f"Error calculating storage hash for {storage_path}: {e}")
        return ""

def _scan_data_directory(data_path: str, scan_depth: str = "balanced") -> Dict[str, Any]:
    """
    Scan data directory with configurable depth for performance optimization.

    This function provides different scanning strategies to balance between
    accuracy and performance based on use case. Now includes parallel hashing
    for improved performance with many small files.

    Args:
        data_path: Path to the data directory to scan
        scan_depth: Scanning strategy for performance optimization
            - "full": Hash all files <10MB (most accurate, slowest)
            - "balanced": Hash files <5MB (recommended balance) - DEFAULT
            - "fast": No hashing, metadata only (fast for quick checks)
            - "minimal": Count only, no detailed file info (ultra-fast for bulk)

    Returns:
        dict: Contains total_files, total_size, and data_files list
              (data_files may be empty for "minimal" scan_depth)
    """
    data_dir = Path(data_path)
    if not data_dir.exists():
        return {"total_files": 0, "total_size": 0, "data_files": []}

    files_info = []
    total_size = 0
    total_files = 0
    files_to_hash = []  # Collect files that need hashing for batch processing

    try:
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    total_files += 1
                    total_size += stat.st_size

                    # For minimal scanning, skip detailed file processing
                    if scan_depth == "minimal":
                        continue

                    # Create base file info
                    file_info = {
                        "name": str(file_path.relative_to(data_dir)),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "hash": ""  # Default empty hash
                    }

                    # Determine if file needs hashing based on scan_depth
                    needs_hash = False
                    if scan_depth == "full" and stat.st_size < 10 * 1024 * 1024:
                        # Full: Hash all files < 10MB (most accurate)
                        needs_hash = True
                    elif scan_depth == "balanced" and stat.st_size < 5 * 1024 * 1024:
                        # Balanced: Hash files < 5MB (good balance of speed/accuracy)
                        needs_hash = True
                    # For "fast" scan_depth, hash remains empty (no hashing needed)

                    if needs_hash:
                        files_to_hash.append(file_path)
                        file_info["_hash_pending"] = True  # Mark for batch processing
                    else:
                        file_info["hash"] = ""  # No hash needed

                    files_info.append(file_info)

                except (OSError, PermissionError) as e:
                    utils_logger.warning(f"Could not access file {file_path}: {e}")
    except (OSError, PermissionError) as e:
        utils_logger.error(f"Could not scan data directory {data_path}: {e}")

    # For minimal scanning, return just counts
    if scan_depth == "minimal":
        return {
            "total_files": total_files,
            "total_size": total_size,
            "data_files": []  # Empty for minimal scans
        }

    # Batch process hashing for improved performance
    if files_to_hash:
        try:
            # utils_logger.debug(f"_scan_data_directory:: Batch hashing {len(files_to_hash)} files with scan_depth '{scan_depth}'")
            hash_results = calculate_batch_file_hashes(files_to_hash)

            # Merge hash results back into file_info structures
            for file_info in files_info:
                if file_info.get("_hash_pending"):
                    file_path_str = str(data_dir / file_info["name"])
                    file_info["hash"] = hash_results.get(file_path_str, "")
                    del file_info["_hash_pending"]  # Clean up temporary marker

            # utils_logger.debug(f"_scan_data_directory:: Successfully batched hashed {len(files_to_hash)} files")
        except Exception as e:
            utils_logger.warning(f"_scan_data_directory:: Batch hashing failed, falling back to sequential: {e}")
            # Fallback: hash files sequentially if batch processing fails
            for file_info in files_info:
                if file_info.get("_hash_pending"):
                    try:
                        file_path = data_dir / file_info["name"]
                        file_info["hash"] = calculate_file_hash(file_path)
                    except Exception as hash_error:
                        utils_logger.warning(f"_scan_data_directory:: Failed to hash {file_info['name']}: {hash_error}")
                        file_info["hash"] = ""
                    del file_info["_hash_pending"]

    # Calculate data_newest_time and data_newest_file from the files found
    data_newest_time = None
    data_newest_file = None
    if files_info:
        try:
            newest_file = max(files_info, key=lambda f: f["modified"])
            data_newest_time = newest_file["modified"]
            data_newest_file = newest_file["name"]
        except (ValueError, TypeError) as e:
            utils_logger.warning(f"_scan_data_directory:: Error calculating data_newest_time and data_newest_file: {e}")

    return {
        "total_files": len(files_info),  # Use actual files_info length for accuracy
        "total_size": total_size,
        "data_files": files_info,  # Standardized to data_files
        "data_newest_time": data_newest_time,
        "data_newest_file": data_newest_file
    }

def _scan_storage_directory(storage_path: str) -> Dict[str, Any]:
    """
    Scan RAG storage directory and return file information.

    Scans the storage directory where RAG indexes are saved to determine
    the current state of generated indexes and when they were last updated.

    Args:
        storage_path: Path to the RAG storage directory

    Returns:
        dict: Contains storage_files list and last_modified timestamp
    """
    storage_dir = Path(storage_path)
    if not storage_dir.exists():
        return {"storage_files": [], "last_modified": None}

    storage_files = []
    latest_modified = None

    try:
        for file_path in storage_dir.rglob("*"):
            if file_path.is_file() and not str(file_path.name).startswith('.'):  # Skip hidden files
                try:
                    stat = file_path.stat()
                    modified_time = datetime.fromtimestamp(stat.st_mtime)

                    if latest_modified is None or modified_time > latest_modified:
                        latest_modified = modified_time

                    file_info = {
                        "name": str(file_path.relative_to(storage_dir)),
                        "size": stat.st_size,
                        "modified": modified_time.isoformat()
                    }
                    storage_files.append(file_info)
                except (OSError, PermissionError) as e:
                    utils_logger.warning(f"Could not access file {file_path}: {e}")
    except (OSError, PermissionError) as e:
        utils_logger.error(f"Could not scan storage directory {storage_path}: {e}")

    return {
        "storage_files": storage_files,
        "last_modified": latest_modified.isoformat() if latest_modified else None
    }

def save_data_metadata(user_config, rag_type: str, data_info: Dict[str, Any], force_overwrite: bool = False) -> bool:
    """
    Save current data status as metadata for a specific RAG type with enhanced error handling.

    Creates or updates the metadata file with current data source information
    for the specified RAG type. Includes atomic writes, backup creation, and
    overwrite protection for corrupted files.

    Now ensures ALL configured RAG types are initialized in fresh metadata files
    to prevent incomplete metadata state.

    Args:
        user_config: UserConfig object containing user-specific settings and paths
        rag_type: The RAG type (e.g., "vector", "graph", "keyword")
        data_info: Current data directory scan results
        force_overwrite: If True, overwrite corrupted metadata files without backup

    Returns:
        bool: True if metadata was saved successfully, False otherwise
    """
    try:
        user_rag_root = user_config.my_rag.rag_root
        metadata_file = get_metadata_file_path(user_rag_root)
        _, storage_path = user_config.my_rag.get_path(rag_type)

        # Ensure the directory exists
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing metadata with enhanced error handling
        metadata = {}
        backup_created = False

        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Validate existing metadata structure
                if not isinstance(metadata, dict):
                    utils_logger.warning(f"save_data_metadata:: Invalid metadata structure, resetting to empty dict")
                    metadata = {}

            except (json.JSONDecodeError, IOError, PermissionError) as e:
                utils_logger.warning(f"save_data_metadata:: Existing metadata file corrupted ({e}), handling gracefully")

                if not force_overwrite:
                    # Create backup of corrupted file
                    backup_file = metadata_file.with_suffix('.bak')
                    try:
                        import shutil
                        shutil.copy2(metadata_file, backup_file)
                        backup_created = True
                        utils_logger.info(f"save_data_metadata:: Created backup of corrupted metadata: {backup_file}")
                    except Exception as backup_error:
                        utils_logger.warning(f"save_data_metadata:: Could not create backup: {backup_error}")

                # Start fresh with corrupted file
                metadata = {}
                utils_logger.info(f"save_data_metadata:: Starting fresh with empty metadata due to corruption")

        # Calculate data_newest_time and data_newest_file from current files
        data_newest_time = None
        data_newest_file = None
        if data_info.get("data_files"):
            try:
                newest_file = max(data_info["data_files"], key=lambda f: f["modified"])
                data_newest_time = newest_file["modified"]
                data_newest_file = newest_file["name"]
            except (ValueError, TypeError) as e:
                utils_logger.warning(f"save_data_metadata:: Error calculating data_newest_time and data_newest_file: {e}")

        # Calculate storage information if storage_path is provided
        rag_storage_creation = None
        rag_storage_hash = ""
        if storage_path:
            try:
                storage_info = _scan_storage_directory(storage_path)
                rag_storage_creation = storage_info.get("last_modified")
                rag_storage_hash = calculate_storage_hash(storage_path)
            except Exception as e:
                utils_logger.warning(f"save_data_metadata:: Error calculating storage info: {e}")

        # Create metadata structure for this RAG type with validation
        # Change "files" to "data_files" in JSON format for versioning and clarity
        rag_metadata = {
            "meta_last_update": datetime.now().isoformat(),
            "data_newest_time": data_newest_time,
            "data_newest_file": data_newest_file,
            "total_files": data_info.get("total_files", 0),
            "total_size": data_info.get("total_size", 0),
            "data_files": {},  # RENAMED from "files" to "data_files"
            "rag_type": rag_type,  # CRITICAL: Include rag_type field for StatusData validation
            "rag_storage_creation": rag_storage_creation,
            "rag_storage_hash": rag_storage_hash
        }

        # Index files by name for quick lookup during comparison (existing format)
        files_list = data_info.get("data_files", [])
        for file_info in files_list:
            if isinstance(file_info, dict) and "name" in file_info:
                try:
                    rag_metadata["data_files"][file_info["name"]] = {  # Save to data_files
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", ""),
                        "hash": file_info.get("hash", "")
                    }
                except Exception as e:
                    utils_logger.warning(f"save_data_metadata:: Error processing file info for {file_info.get('name', 'unknown')}: {e}")



        # Update the metadata with this RAG type's information
        metadata[rag_type] = rag_metadata

        # ISSUE 5 FIX: Ensure ALL configured RAG types are initialized with SAME DATA
        # This prevents incomplete metadata state when only some RAG types have been used
        try:
            # Try to get configured RAG types from the config manager
            # We need to import here to avoid circular imports
            from super_starter_suite.shared.config_manager import ConfigManager

            # Get configured RAG types - this will work if we have a valid user config
            # For now, we'll use the default RAG types as fallback
            configured_rag_types = ["RAG", "CODE_GEN", "FINANCE", "TINA_DOC"]  # Default from settings

            # Try to get actual configured types if possible from the passed user_config
            try:
                # Use the passed user_config instead of hardcoded "Default"
                actual_rag_types = user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
                if actual_rag_types:
                    configured_rag_types = actual_rag_types
                    # utils_logger.debug(f"save_data_metadata:: Using configured RAG types: {configured_rag_types}")
            except Exception as config_error:
                utils_logger.warning(f"save_data_metadata:: Using default RAG types (config access failed): {config_error}")

            # Initialize missing RAG types with EMPTY metadata (proper approach)
            for configured_rag_type in configured_rag_types:
                if configured_rag_type not in metadata:
                    empty_metadata = {
                        "meta_last_update": datetime.now().isoformat(),
                        "data_newest_time": None,  # No data yet for this RAG type
                        "data_newest_file": None,  # No data yet for this RAG type
                        "total_files": 0,          # No files yet
                        "total_size": 0,           # No data yet
                        "data_files": {},               # Empty data_files dict
                        "rag_type": configured_rag_type,  # Include rag_type for validation
                        "rag_storage_creation": None,      # No storage created yet
                        "rag_storage_hash": ""             # No storage hash yet
                    }
                    metadata[configured_rag_type] = empty_metadata
                    # utils_logger.debug(f"save_data_metadata:: Successfully initialized empty RAG type '{configured_rag_type}'")

        except Exception as init_error:
            utils_logger.warning(f"save_data_metadata:: Failed to initialize missing RAG types: {init_error}")
            # Continue without initialization - don't fail the entire operation

        # ATOMIC WRITE: Write to temporary file first, then rename
        temp_file = metadata_file.with_suffix('.tmp')
        try:
            # Write to temporary file first
            with open(temp_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Atomic rename (this is atomic on POSIX systems)
            temp_file.replace(metadata_file)

            success_msg = f"Metadata saved for RAG type '{rag_type}' to {metadata_file}"
            if backup_created:
                success_msg += f" (backup created: {metadata_file.with_suffix('.bak')})"

            utils_logger.debug(success_msg)
            return True

        except Exception as write_error:
            # Clean up temporary file if write failed
            try:
                temp_file.unlink(missing_ok=True)
            except:
                pass

            utils_logger.error(f"save_data_metadata:: Atomic write failed: {write_error}")
            return False

    except Exception as e:
        utils_logger.error(f"save_data_metadata:: Unexpected error saving metadata for RAG type '{rag_type}': {e}")
        return False

def _load_metadata_file(user_rag_root: str) -> Optional[Dict[str, Any]]:
    """
    Load and parse the metadata file safely.

    Args:
        user_rag_root: Path to user's RAG root directory

    Returns:
        dict or None: Parsed metadata dictionary or None if file doesn't exist or corrupted
    """
    metadata_file = get_metadata_file_path(user_rag_root)

    if not metadata_file.exists():
        utils_logger.info(f"_load_metadata_file:: Metadata file does not exist: {metadata_file}")
        return None

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        # utils_logger.debug(f"_load_metadata_file:: Successfully loaded metadata file with {len(metadata)} RAG types")
        return metadata
    except (json.JSONDecodeError, IOError, KeyError) as e:
        utils_logger.warning(f"_load_metadata_file:: Could not load/parse metadata file {metadata_file}: {e}")
        return None
    except Exception as e:
        utils_logger.error(f"_load_metadata_file:: Unexpected error loading metadata file: {e}")
        return None


def _validate_metadata_structure(metadata: Dict[str, Any], rag_type: str) -> bool:
    """
    Validate metadata format and required fields for a specific RAG type.

    Args:
        metadata: Full metadata dictionary
        rag_type: The RAG type to validate

    Returns:
        bool: True if metadata structure is valid, False otherwise
    """
    if rag_type not in metadata:
        utils_logger.info(f"_validate_metadata_structure:: RAG type '{rag_type}' not found in metadata")
        return False

    rag_metadata = metadata[rag_type]

    # Check 1: Required fields exist (no legacy support)
    required_fields = ['meta_last_update', 'data_newest_time', 'total_files', 'total_size', 'data_files']
    missing_fields = [field for field in required_fields if field not in rag_metadata]

    if missing_fields:
        utils_logger.warning(f"_validate_metadata_structure:: Missing required fields {missing_fields} for RAG type '{rag_type}'")
        return False

    # Check 2: Timestamp format validation (strict ISO format)
    try:
        metadata_timestamp = rag_metadata.get('meta_last_update')
        if metadata_timestamp:
            datetime.fromisoformat(metadata_timestamp)  # Validate ISO format
    except (ValueError, TypeError) as e:
        utils_logger.warning(f"_validate_metadata_structure:: Invalid meta_last_update format for RAG type '{rag_type}': {e}")
        return False

    # Check 3: Basic data consistency (total_files should be reasonable)
    total_files = rag_metadata.get('total_files', 0)
    if total_files < 0 or total_files > 100000:  # Sanity check
        utils_logger.warning(f"_validate_metadata_structure:: Invalid total_files {total_files} for RAG type '{rag_type}'")
        return False

    # Check 4: Files structure validation (must be dict with filename keys)
    data_files = rag_metadata.get('data_files', {})
    if not isinstance(data_files, dict):
        utils_logger.warning(f"_validate_metadata_structure:: Invalid data_files structure for RAG type '{rag_type}' - must be dict")
        return False

    # Check 5: Files structure content validation
    if data_files:  # Only validate if data_files exist
        for filename, file_info in data_files.items():
            if not isinstance(file_info, dict):
                utils_logger.warning(f"_validate_metadata_structure:: Invalid file info structure for '{filename}' in RAG type '{rag_type}'")
                return False
            required_file_fields = ['size', 'modified', 'hash']
            missing_file_fields = [field for field in required_file_fields if field not in file_info]
            if missing_file_fields:
                utils_logger.warning(f"_validate_metadata_structure:: Missing file fields {missing_file_fields} for '{filename}' in RAG type '{rag_type}'")
                return False

    utils_logger.debug(f"_validate_metadata_structure:: Metadata structure validation PASSED for RAG type '{rag_type}'")
    return True


def _check_filesystem_consistency(user_config, metadata: Dict[str, Any], scan_depth: str) -> Dict[str, Any]:
    """
    Compare metadata against actual filesystem state for each RAG type individually.

    Args:
        metadata: Full metadata dictionary
        user_config: UserConfig object containing user-specific settings and paths
        scan_depth: Scanning strategy for consistency validation

    Returns:
        dict: {"needs_regeneration": bool, "inconsistent_types": [list]}
    """
    try:
        # utils_logger.debug(f"_check_filesystem_consistency:: Checking filesystem consistency with scan_depth '{scan_depth}'")

        # Get all configured RAG types to check consistency for all of them
        configured_rag_types = user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])

        # Check consistency for EACH RAG type with ITS OWN data directory
        inconsistent_types = []
        for check_rag_type in configured_rag_types:
            if check_rag_type not in metadata:
                utils_logger.info(f"_check_filesystem_consistency:: RAG type '{check_rag_type}' missing from metadata")
                inconsistent_types.append(check_rag_type)
                continue

            # Get THIS RAG type's specific data path using get_path method
            rag_data_path, _ = user_config.my_rag.get_path(check_rag_type)

            # Scan THIS RAG type's data directory
            current_scan = _scan_fresh_data(rag_data_path, scan_depth)
            current_files_count = current_scan.get("total_files", 0)
            current_files_by_name = {f["name"]: f for f in current_scan.get("data_files", [])}

            # utils_logger.debug(f"_check_filesystem_consistency:: RAG type '{check_rag_type}' scan complete - found {current_files_count} files, in data path: {rag_data_path}")

            check_metadata = metadata[check_rag_type]
            check_files = check_metadata.get('data_files', {})
            check_files_count = len(check_files)

            # Skip if this RAG type has no files in metadata (already initialized as empty)
            if check_files_count == 0:
                utils_logger.info(f"_check_filesystem_consistency:: RAG type '{check_rag_type}' has empty metadata")
                inconsistent_types.append(check_rag_type)
                continue

            # CONSISTENCY CHECK 1: File count mismatch
            if check_files_count != current_files_count:
                utils_logger.warning(f"_check_filesystem_consistency:: FILE COUNT MISMATCH for '{check_rag_type}': metadata={check_files_count}, filesystem={current_files_count}")
                inconsistent_types.append(check_rag_type)
                continue

            # CONSISTENCY CHECK 2: Sample file validation for existing files
            if check_files and current_files_by_name:
                sample_size = min(10, len(check_files)) if scan_depth == "full" else min(5, len(check_files)) if scan_depth == "balanced" else min(2, len(check_files))
                sample_files = list(check_files.keys())[:sample_size]

                inconsistent_files = []
                for sample_file in sample_files:
                    if sample_file not in current_files_by_name:
                        inconsistent_files.append(f"{sample_file}(missing)")
                    else:
                        # Check file size consistency
                        metadata_size = check_files[sample_file].get("size", 0)
                        current_size = current_files_by_name[sample_file].get("size", 0)
                        if metadata_size != current_size:
                            inconsistent_files.append(f"{sample_file}(size_mismatch)")

                if inconsistent_files:
                    utils_logger.warning(f"_check_filesystem_consistency:: FILE INCONSISTENCIES for '{check_rag_type}': {inconsistent_files}")
                    inconsistent_types.append(check_rag_type)

        needs_regeneration = len(inconsistent_types) > 0
        result = {
            "needs_regeneration": needs_regeneration,
            "inconsistent_types": inconsistent_types
        }

        if needs_regeneration:
            utils_logger.info(f"_check_filesystem_consistency:: Found {len(inconsistent_types)} inconsistent RAG types: {inconsistent_types}")
        else:
            utils_logger.debug("_check_filesystem_consistency:: All RAG types are consistent with filesystem")

        return result

    except Exception as consistency_error:
        utils_logger.warning(f"_check_filesystem_consistency:: Filesystem consistency check failed: {consistency_error}")
        return {"needs_regeneration": False, "inconsistent_types": []}  # Fail-safe


def _scan_fresh_data(data_path: str, scan_depth: str) -> Dict[str, Any]:
    """
    Scan filesystem to get fresh data info with configurable depth.

    Args:
        data_path: Path to data directory to scan
        scan_depth: Scanning strategy for performance optimization

    Returns:
        dict: Contains total_files, total_size, and data_files list
    """
    return _scan_data_directory(data_path, scan_depth=scan_depth)


def _save_metadata_internally(user_rag_root: str, metadata: Dict[str, Any]) -> bool:
    """
    Save metadata file internally with atomic writes and error recovery.

    Args:
        user_rag_root: Path to user's RAG root directory
        metadata: Metadata dictionary to save

    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        metadata_file = get_metadata_file_path(user_rag_root)

        # Ensure the directory exists
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        # ATOMIC WRITE: Write to temporary file first, then rename
        temp_file = metadata_file.with_suffix('.tmp')
        try:
            # Write to temporary file first
            with open(temp_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Atomic rename (this is atomic on POSIX systems)
            temp_file.replace(metadata_file)

            # utils_logger.debug(f"_save_metadata_internally:: Successfully saved metadata with {len(metadata)} RAG types")
            return True

        except Exception as write_error:
            # Clean up temporary file if write failed
            try:
                temp_file.unlink(missing_ok=True)
            except:
                pass

            utils_logger.error(f"_save_metadata_internally:: Atomic write failed: {write_error}")
            return False

    except Exception as e:
        utils_logger.error(f"_save_metadata_internally:: Unexpected error saving metadata: {e}")
        return False

def _handle_empty_metadata(user_config, scan_depth: str) -> Optional[Dict[str, Any]]:
    """
    Handle complete metadata file creation for all configured RAG types.

    CRITICAL FIX: Each RAG type now gets its own data directory scanned:
    - RAG type scans: data.RAG
    - CODE_GEN type scans: data.CODE_GEN
    - FINANCE type scans: data.FINANCE
    - TINA_DOC type scans: data.TINA_DOC

    Args:
        user_config: UserConfig object containing user-specific settings
        scan_depth: Scanning strategy

    Returns:
        dict or None: Metadata for requested RAG type or None if creation failed
    """
    try:
        my_rag = user_config.my_rag
        rag_type = my_rag.rag_type

        # Get all configured RAG types
        configured_rag_types = user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
        utils_logger.info(f"_handle_empty_metadata:: Will create metadata for RAG types: {configured_rag_types}")

        # Create metadata for EACH configured RAG type with ITS OWN data directory
        metadata = {}
        for config_rag_type in configured_rag_types:
            # CRITICAL: Set the RAG type to get the correct data_path for THIS type
            rag_data_path, _ = my_rag.get_path(config_rag_type)

            # Scan THIS RAG type's specific data directory
            fresh_data = _scan_fresh_data(rag_data_path, scan_depth)
            # utils_logger.debug(f"_handle_empty_metadata:: RAG type '{config_rag_type}' scan {rag_data_path} - {fresh_data.get('total_files', 0)} files found")

            # Calculate storage information for THIS RAG type
            storage_creation = None
            storage_hash = ""
            try:
                storage_info = _scan_storage_directory(my_rag.storage_path)
                storage_creation = storage_info.get("last_modified")
                storage_hash = calculate_storage_hash(my_rag.storage_path)
            except Exception as storage_error:
                utils_logger.warning(f"_handle_empty_metadata:: Error calculating storage info for '{config_rag_type}': {storage_error}")

            # Create metadata structure for this RAG type
            rag_metadata = {
                "meta_last_update": datetime.now().isoformat(),
                "data_newest_time": fresh_data.get("data_newest_time"),
                "data_newest_file": fresh_data.get("data_newest_file"),
                "total_files": fresh_data.get("total_files", 0),
                "total_size": fresh_data.get("total_size", 0),
                "data_files": {},  # Will be populated below
                "rag_type": config_rag_type,
                "rag_storage_creation": storage_creation,
                "rag_storage_hash": storage_hash
            }

            # Index files by name for quick lookup (existing format)
            for file_info in fresh_data.get("data_files", []):
                if isinstance(file_info, dict) and "name" in file_info:
                    rag_metadata["data_files"][file_info["name"]] = {
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", ""),
                        "hash": file_info.get("hash", "")
                    }

            metadata[config_rag_type] = rag_metadata
            # utils_logger.debug(f"_handle_empty_metadata:: Successfully created metadata for '{config_rag_type}' with {len(rag_metadata['data_files'])} files from {rag_data_path}")

        # Save complete metadata file internally
        if _save_metadata_internally(my_rag.rag_root, metadata):
            total_files_all_types = sum(meta.get('total_files', 0) for meta in metadata.values())  # Log summary of what was created
            utils_logger.info(f"_handle_empty_metadata:: Successfully created metadata file with {len(metadata)} RAG types. All total files: {total_files_all_types}")
            return metadata.get(rag_type)  # Return requested RAG type data
        else:
            utils_logger.error("_handle_empty_metadata:: Failed to save metadata file")
            return None

    except Exception as e:
        utils_logger.error(f"_handle_empty_metadata:: Unexpected error creating metadata: {e}")
        return None


def _handle_inconsistent_metadata(user_config, existing_metadata: Dict[str, Any], scan_depth: str) -> Optional[Dict[str, Any]]:
    """
    Handle partial metadata regeneration for inconsistent RAG types only.

    Args:
        user_config: UserConfig object containing user-specific settings
        existing_metadata: Current metadata dictionary
        scan_depth: Scanning strategy

    Returns:
        dict or None: Metadata for requested RAG type or None if regeneration failed
    """
    try:
        my_rag = user_config.my_rag
        rag_type = my_rag.rag_type
        user_rag_root = my_rag.rag_root

        # Check which RAG types need regeneration
        consistency_result = _check_filesystem_consistency(user_config, existing_metadata, scan_depth)
        inconsistent_types = consistency_result.get("inconsistent_types", [])

        if not inconsistent_types:
            # utils_logger.debug("_handle_inconsistent_metadata:: No inconsistent types found, returning existing metadata")
            return existing_metadata.get(rag_type)

        utils_logger.info(f"_handle_inconsistent_metadata:: Will recreate {len(inconsistent_types)} RAG types: {inconsistent_types}")

        # Update metadata for inconsistent types only
        updated_metadata = existing_metadata.copy()
        for inconsistent_rag_type in inconsistent_types:
            # Get THIS RAG type's specific data path
            rag_data_path, _ = my_rag.get_path(inconsistent_rag_type)

            # Scan THIS RAG type's specific data directory
            fresh_data = _scan_fresh_data(rag_data_path, scan_depth)
            utils_logger.debug(f"_handle_inconsistent_metadata:: Recreating '{inconsistent_rag_type}' with {fresh_data.get('total_files', 0)} files from {rag_data_path}")

            # Calculate storage information for this specific RAG type
            storage_creation = None
            storage_hash = ""
            try:
                storage_info = _scan_storage_directory(my_rag.storage_path)
                storage_creation = storage_info.get("last_modified")
                storage_hash = calculate_storage_hash(my_rag.storage_path)
            except Exception as storage_error:
                utils_logger.warning(f"_handle_inconsistent_metadata:: Error calculating storage info for '{inconsistent_rag_type}': {storage_error}")

            # Create updated metadata structure for this RAG type
            rag_metadata = {
                "meta_last_update": datetime.now().isoformat(),
                "data_newest_time": fresh_data.get("data_newest_time"),
                "total_files": fresh_data.get("total_files", 0),
                "total_size": fresh_data.get("total_size", 0),
                "data_files": {},  # Will be populated below
                "rag_type": inconsistent_rag_type,
                "rag_storage_creation": storage_creation,
                "rag_storage_hash": storage_hash
            }

            # Index files by name for quick lookup (existing format)
            for file_info in fresh_data.get("data_files", []):
                if isinstance(file_info, dict) and "name" in file_info:
                    rag_metadata["data_files"][file_info["name"]] = {
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", ""),
                        "hash": file_info.get("hash", "")
                    }

            updated_metadata[inconsistent_rag_type] = rag_metadata
            # utils_logger.debug(f"_handle_inconsistent_metadata:: Successfully updated metadata for '{inconsistent_rag_type}' with {len(rag_metadata['data_files'])} files")

        # Save updated metadata file internally
        if _save_metadata_internally(user_rag_root, updated_metadata):
            utils_logger.debug(f"_handle_inconsistent_metadata:: Successfully updated and saved metadata file")
            return updated_metadata.get(rag_type)  # Return requested RAG type data
        else:
            utils_logger.error("_handle_inconsistent_metadata:: Failed to save updated metadata file")
            return existing_metadata.get(rag_type)  # Return original data as fallback

    except Exception as e:
        utils_logger.error(f"_handle_inconsistent_metadata:: Unexpected error regenerating metadata: {e}")
        return existing_metadata.get(rag_type)  # Return original data as fallback


def load_data_metadata(user_config, rag_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    EXTERNAL API: Clean orchestration - handles empty vs inconsistent cases internally.

    When EMPTY: Scans ALL RAG types, creates fresh metadata, saves internally
    When INCONSISTENT: Scans only inconsistent RAG types, updates selectively, saves internally
    When CONSISTENT: Returns cached data directly

    External callers don't know/care about internal details.

    ---
    Load previously saved data metadata for a specific RAG type with robust error handling
    and CRITICAL FILESYSTEM CONSISTENCY VALIDATION.

    During server downtime, various changes can occur:
    1. New DATA files added (e.g., new quarterly 10-q files)
    2. New RAG types added (e.g., CODE1, CODE2 for different repos)
    3. Old RAG types removed (DATA and/or STORAGE)

    Args:
        user_config: UserConfig object containing RAG type and paths
        rag_type: Optional RAG type to load (defaults to current user_config.my_rag.rag_type)

    Returns:
        dict or None: Metadata dictionary if valid and consistent, None if rescan needed
    """
    # Set the RAG type if provided, otherwise use current
    if rag_type:
        user_config.my_rag.set_rag_type(rag_type)

    # scan_depth: Scanning strategy for consistency validation ("balanced" default)
    scan_depth = user_config.get_user_setting("GENERATE.SCAN_DEPTH", "balanced")
 
    # 1. Try to load existing metadata file
    metadata = _load_metadata_file(user_config.my_rag.rag_root)

    if metadata is None:
        # EMPTY: File doesn't exist - fresh creation for ALL RAG types
        return _handle_empty_metadata(user_config, "balanced")    # force scan_depth = "balanced" when empty

    # 2. Validate metadata structure for requested RAG type
    if not _validate_metadata_structure(metadata, user_config.my_rag.rag_type):
        # INCONSISTENT: Structure invalid - selective regeneration
        return _handle_inconsistent_metadata(user_config, metadata, scan_depth)

    # 3. Check filesystem consistency
    consistency_result = _check_filesystem_consistency(user_config, metadata, scan_depth)
    if consistency_result["needs_regeneration"]:
        # INCONSISTENT: Filesystem mismatch - selective regeneration
        return _handle_inconsistent_metadata(user_config, metadata, scan_depth)

    # 4. CONSISTENT: Return cached data directly (no scanning, no saving)
    return metadata.get(user_config.my_rag.rag_type)

def compare_data_with_metadata(data_info: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare current data status with saved metadata to detect changes.

    This is the core change detection logic that determines if RAG regeneration
    is needed. It checks for:
    1. Modified files (timestamp changed)
    2. New files (not in metadata)
    3. Deleted files (in metadata but not in current scan)

    Args:
        data_info: Current data directory scan results
        metadata: Previously saved metadata dictionary for this RAG type

    Returns:
        dict: Contains is_up_to_date boolean and changes list
    """
    if not metadata or 'data_files' not in metadata:
        return {
            "is_up_to_date": False,
            "changes": ["No previous metadata found for this RAG type"]
        }

    changes = []
    is_up_to_date = True

    # Check for modified files
    for current_file in data_info['data_files']:
        file_name = current_file['name']
        if file_name in metadata['data_files']:
            metadata_file_info = metadata['data_files'][file_name]
            if current_file['modified'] > metadata_file_info['modified']:
                changes.append(f"Modified: {file_name}")
                is_up_to_date = False
        else:
            # New file found
            changes.append(f"New: {file_name}")
            is_up_to_date = False

    # Check for deleted files
    current_file_names = {f['name'] for f in data_info['data_files']}
    metadata_file_names = set(metadata['data_files'].keys())
    deleted_files = metadata_file_names - current_file_names

    for deleted_file in deleted_files:
        changes.append(f"Deleted: {deleted_file}")
        is_up_to_date = False

    return {
        "is_up_to_date": is_up_to_date,
        "changes": changes if changes else ["No changes detected"]
    }

def check_storage_health(storage_path: str, storage_files: List[Dict[str, Any]]) -> bool:
    """
    Check if RAG storage is healthy and functional.

    Storage is considered unhealthy if:
    - Directory doesn't exist
    - Directory exists but is empty (no files)
    - Directory has files but appears corrupted (missing critical files)

    Args:
        storage_path: Path to the RAG storage directory
        storage_files: List of files in the storage directory

    Returns:
        bool: True if storage is healthy, False otherwise
    """
    storage_dir = Path(storage_path)

    # Check if directory exists
    if not storage_dir.exists():
        utils_logger.info("check_storage_health:: Directory does not exist")
        return False

    # Check if directory has files
    if not storage_files:
        utils_logger.info("check_storage_health:: Directory exists but is empty")
        return False

    # Check for critical RAG storage files
    # LlamaIndex typically creates files like index_store.json, docstore.json, vector_store.json
    file_names = [f["name"] for f in storage_files]
    critical_files = ["index_store.json", "docstore.json"]

    missing_critical = [f for f in critical_files if f not in file_names]
    if missing_critical:
        utils_logger.info(f"check_storage_health:: Missing critical files: {missing_critical}")
        return False

    # Additional checks could be added here for file sizes, content validation, etc.

    utils_logger.debug(f"check_storage_health:: Storage appears healthy - {storage_path[-40:]}")
    return True

def get_rag_status_summary(user_config: UserConfig) -> Dict[str, Any]:
    """
    Get comprehensive RAG status summary for API endpoints.

    This function implements the main logic to determine whether RAG regeneration
    is needed by comparing storage content hash and creation timestamps.

    Args:
        user_config: User's configuration object containing paths and RAG type

    Returns:
        dict: Comprehensive status information including:
        - storage_info: Current RAG storage status
        - comparison: Change detection results based on hash and timestamp comparison
        - is_up_to_date: Overall status for UI color coding
    """
    try:
        # Scan storage directory
        storage_info = _scan_storage_directory(user_config.my_rag.storage_path)

        # Load metadata for this specific RAG type
        metadata = load_data_metadata(user_config)

        if not metadata:
            result = {
                "storage_info": storage_info,
                "comparison": {"is_up_to_date": False, "changes": ["No previous metadata found for this RAG type"]},
                "is_up_to_date": False
            }
            utils_logger.info(f"get_rag_status_summary::  RESULT (no metadata)={result}")
            return result

        # New comparison logic based on storage hash and timestamps
        changes = []
        is_up_to_date = True

        # Check 1: Compare storage content hash
        current_storage_hash = calculate_storage_hash(user_config.my_rag.storage_path)
        saved_storage_hash = metadata.get("rag_storage_hash", "")

        # Only consider hash mismatch if we have a previously saved non-empty hash to compare against
        if saved_storage_hash and saved_storage_hash.strip() and current_storage_hash != saved_storage_hash:
            changes.append(f"Storage content changed (hash mismatch)")
            is_up_to_date = False
        elif not saved_storage_hash or not saved_storage_hash.strip():
            # No previous hash saved - this is normal for first-time checks
            if current_storage_hash:
                changes.append("Storage hash calculated for first time")
                # Don't set is_up_to_date = False for first-time hash calculation

        # Check 2: Compare data_newest_time with rag_storage_creation
        # Get scan depth from user configuration
        scan_depth = user_config.get_user_setting("GENERATE.SCAN_DEPTH", "balanced")
        #utils_logger.debug(f"get_rag_status_summary::  STORAGE_INFO={storage_info}  CURRENT_STORAGE_HASH={current_storage_hash}  SCAN_DEPTH={scan_depth}  SAVED_STORAGE_HASH={saved_storage_hash}")

        # First, calculate current data_newest_time with configured scan depth
        current_data = _scan_data_directory(user_config.my_rag.data_path, scan_depth=scan_depth)
        current_data_newest_time = None
        if current_data["data_files"]:
            newest_file = max(current_data["data_files"], key=lambda f: f["modified"])
            current_data_newest_time = newest_file["modified"]

        saved_rag_storage_creation = metadata.get("rag_storage_creation")
        saved_data_newest_time = metadata.get("data_newest_time")

        if current_data_newest_time and saved_rag_storage_creation:
            try:
                current_newest_dt = datetime.fromisoformat(current_data_newest_time)
                saved_creation_dt = datetime.fromisoformat(saved_rag_storage_creation)

                if current_newest_dt > saved_creation_dt:
                    changes.append(f"New data files detected after storage creation")
                    is_up_to_date = False
            except (ValueError, TypeError) as e:
                utils_logger.warning(f"Error comparing timestamps: {e}")
                changes.append("Could not compare timestamps")
                is_up_to_date = False
        elif current_data_newest_time and not saved_rag_storage_creation:
            changes.append("No previous storage creation timestamp found")
            # Don't set is_up_to_date = False just because metadata is missing
            # Missing metadata != storage corruption - this indicates obsolete data
            utils_logger.info(f"get_rag_status_summary::  INFO: Storage need to recreate for {user_config.my_rag.rag_type} (obsolete Index Storage - data is newer)")
        elif not current_data_newest_time and saved_rag_storage_creation:
            changes.append("No current data files found")
            is_up_to_date = False

        comparison = {
            "is_up_to_date": is_up_to_date,
            "changes": changes if changes else ["Storage is up to date"]
        }
        # utils_logger.debug(f"get_rag_status_summary::  CURRENT_DATA_FILE_NEWEST={current_data_newest_time}  SAVED_DATA_FILE_NEWEST={saved_data_newest_time}  SAVED_RAG_STORAGE_CREATION={saved_rag_storage_creation}  COMPARISON={comparison}")

        result = {
            "storage_info": storage_info,
            "comparison": comparison,
            "is_up_to_date": is_up_to_date
        }
        utils_logger.debug(f"get_rag_status_summary::  FINAL_RESULT={result}")
        return result

    except Exception as e:
        utils_logger.error(f"Error getting RAG status summary: {e}")
        result = {
            "error": str(e),
            "is_up_to_date": False
        }
        utils_logger.debug(f"get_rag_status_summary::  ERROR_RESULT={result}")
        return result
