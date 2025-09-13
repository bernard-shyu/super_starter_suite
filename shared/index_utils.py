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
utils_logger = config_manager.get_logger("gen_utils")

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
# Metadata File Structure:
# {
#     "rag_type_1": {
#         "timestamp": "ISO datetime string",
#         "data_file_newest": "ISO datetime string",  # Renamed from rag_data_newest
#         "total_files": 10,
#         "total_size": 1024000,
#         "files": {
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
    Calculate MD5 hash of a file for content verification.

    Only calculates hash for files smaller than 10MB to avoid performance
    issues with large files. For larger files, returns empty string.

    Args:
        file_path: Path to the file to hash

    Returns:
        str: MD5 hash as hex string, or empty string for large files
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except (IOError, OSError) as e:
        utils_logger.warning(f"Could not calculate hash for {file_path}: {e}")
        return ""

def calculate_storage_hash(storage_path: str) -> str:
    """
    Calculate MD5 hash of all files in the RAG storage directory.

    This creates a combined hash of all index files to detect if the
    RAG storage has been modified or regenerated.

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

def scan_data_directory(data_path: str) -> Dict[str, Any]:
    """
    Scan data directory and return comprehensive file information.

    Recursively scans the data directory to gather information about all files.
    This information is used to detect changes and determine if RAG regeneration
    is needed.

    Args:
        data_path: Path to the data directory to scan

    Returns:
        dict: Contains total_files, total_size, and current_files list with
              name, size, modified timestamp, and hash for each file
    """
    data_dir = Path(data_path)
    if not data_dir.exists():
        return {"total_files": 0, "total_size": 0, "current_files": []}

    files_info = []
    total_size = 0

    try:
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    file_info = {
                        "name": str(file_path.relative_to(data_dir)),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "hash": calculate_file_hash(file_path) if stat.st_size < 10 * 1024 * 1024 else ""  # Only hash files < 10MB
                    }
                    files_info.append(file_info)
                    total_size += stat.st_size
                except (OSError, PermissionError) as e:
                    utils_logger.warning(f"Could not access file {file_path}: {e}")
    except (OSError, PermissionError) as e:
        utils_logger.error(f"Could not scan data directory {data_path}: {e}")

    return {
        "total_files": len(files_info),
        "total_size": total_size,
        "current_files": files_info
    }

def scan_storage_directory(storage_path: str) -> Dict[str, Any]:
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

def save_data_metadata(user_rag_root: str, rag_type: str, data_info: Dict[str, Any], storage_path: Optional[str] = None) -> bool:
    """
    Save current data status as metadata for a specific RAG type.

    Creates or updates the metadata file with current data source information
    for the specified RAG type. The metadata file contains a section for each
    RAG type, allowing independent change tracking per type.

    Args:
        user_rag_root: Path to user's RAG root directory
        rag_type: The RAG type (e.g., "vector", "graph", "keyword")
        data_info: Current data directory scan results
        storage_path: Optional path to RAG storage directory to calculate hash

    Returns:
        bool: True if metadata was saved successfully, False otherwise
    """
    try:
        metadata_file = get_metadata_file_path(user_rag_root)

        # Load existing metadata if file exists
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                metadata = {}  # Start fresh if corrupted

        # Ensure the directory exists
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        # Calculate data_file_newest from current files
        data_file_newest = None
        if data_info["current_files"]:
            newest_file = max(data_info["current_files"], key=lambda f: f["modified"])
            data_file_newest = newest_file["modified"]

        # Calculate storage information if storage_path is provided
        rag_storage_creation = None
        rag_storage_hash = ""
        if storage_path:
            storage_info = scan_storage_directory(storage_path)
            rag_storage_creation = storage_info.get("last_modified")
            rag_storage_hash = calculate_storage_hash(storage_path)

        # Create metadata structure for this RAG type
        rag_metadata = {
            "timestamp": datetime.now().isoformat(),
            "data_file_newest": data_file_newest,  # Renamed from rag_data_newest
            "total_files": data_info["total_files"],
            "total_size": data_info["total_size"],
            "files": {},
            "rag_storage_creation": rag_storage_creation,
            "rag_storage_hash": rag_storage_hash
        }

        # Index files by name for quick lookup during comparison
        for file_info in data_info["current_files"]:
            rag_metadata["files"][file_info["name"]] = {
                "size": file_info["size"],
                "modified": file_info["modified"],
                "hash": file_info.get("hash", "")
            }

        # Update the metadata with this RAG type's information
        metadata[rag_type] = rag_metadata

        # Save to file
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        utils_logger.info(f"Metadata saved for RAG type '{rag_type}' to {metadata_file}")
        return True

    except Exception as e:
        utils_logger.error(f"Error saving metadata for RAG type '{rag_type}': {e}")
        return False

def load_data_metadata(user_rag_root: str, rag_type: str) -> Optional[Dict[str, Any]]:
    """
    Load previously saved data metadata for a specific RAG type.

    Reads the metadata file and returns the section for the specified RAG type.
    If the file doesn't exist or the RAG type section is missing, returns None.

    Args:
        user_rag_root: Path to user's RAG root directory
        rag_type: The RAG type to load metadata for

    Returns:
        dict or None: Metadata dictionary for the RAG type if it exists, None otherwise
    """
    metadata_file = get_metadata_file_path(user_rag_root)

    if not metadata_file.exists():
        return None

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Return the specific RAG type metadata
        return metadata.get(rag_type)
    except (json.JSONDecodeError, IOError) as e:
        utils_logger.warning(f"Could not load metadata file: {e}")
        return None

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
    if not metadata or 'files' not in metadata:
        return {
            "is_up_to_date": False,
            "changes": ["No previous metadata found for this RAG type"]
        }

    changes = []
    is_up_to_date = True

    # Check for modified files
    for current_file in data_info['current_files']:
        file_name = current_file['name']
        if file_name in metadata['files']:
            metadata_file_info = metadata['files'][file_name]
            if current_file['modified'] > metadata_file_info['modified']:
                changes.append(f"Modified: {file_name}")
                is_up_to_date = False
        else:
            # New file found
            changes.append(f"New: {file_name}")
            is_up_to_date = False

    # Check for deleted files
    current_file_names = {f['name'] for f in data_info['current_files']}
    metadata_file_names = set(metadata['files'].keys())
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
        utils_logger.debug("check_storage_health:: Directory does not exist")
        return False

    # Check if directory has files
    if not storage_files:
        utils_logger.debug("check_storage_health:: Directory exists but is empty")
        return False

    # Check for critical RAG storage files
    # LlamaIndex typically creates files like index_store.json, docstore.json, vector_store.json
    file_names = [f["name"] for f in storage_files]
    critical_files = ["index_store.json", "docstore.json"]

    missing_critical = [f for f in critical_files if f not in file_names]
    if missing_critical:
        utils_logger.debug(f"check_storage_health:: Missing critical files: {missing_critical}")
        return False

    # Additional checks could be added here for file sizes, content validation, etc.

    utils_logger.debug("check_storage_health:: Storage appears healthy")
    return True


def get_data_status_simple(user_config: UserConfig) -> Dict[str, Any]:
    """
    Get simplified data status focused on change detection with enhanced status logic.

    This provides a simplified view of data status that focuses on whether
    there are newer files that would warrant RAG regeneration, rather than
    detailed file listings.

    Enhanced Status Logic:
    - "Uptodate" (GREEN): Data is current and storage is healthy
    - "Need Generate" (RED): Storage is NOT healthy (missing, corrupted, etc.)
    - "Obsolete data" (ORANGE): Storage is healthy but data files are newer than storage creation

    Args:
        user_config: User's configuration object containing paths and RAG type

    Returns:
        dict: Simplified data status including:
        - data_file_newest: ISO datetime string of the newest file in data directory
        - has_newer_files: Boolean indicating if there are newer files than metadata
        - change_count: Number of files that have changed
        - last_scan: When the data was last scanned
        - summary: Human-readable summary of the status
        - status_color: "red", "orange", or "green" based on status logic
        - status_type: "uptodate", "need_generate", or "obsolete_data"
    """
    try:
        # Scan current data
        current_data = scan_data_directory(user_config.my_rag.data_path)
        utils_logger.debug(f"get_data_status_simple::  CURRENT_DATA={current_data}")

        # Calculate data_file_newest from current files
        data_file_newest = None
        if current_data["current_files"]:
            newest_file = max(current_data["current_files"], key=lambda f: f["modified"])
            data_file_newest = newest_file["modified"]
        utils_logger.debug(f"get_data_status_simple::  DATA_FILE_NEWEST={data_file_newest}")

        # Load metadata for this specific RAG type
        metadata = load_data_metadata(user_config.my_rag.rag_root, user_config.my_rag.rag_type)
        utils_logger.debug(f"get_data_status_simple::  METADATA={metadata}")

        # Get storage status to determine overall health
        storage_info = scan_storage_directory(user_config.my_rag.storage_path)
        storage_files = storage_info.get("storage_files", [])
        storage_exists = len(storage_files) > 0
        storage_creation_time = storage_info.get("last_modified")

        # Determine storage health status
        storage_healthy = check_storage_health(user_config.my_rag.storage_path, storage_files)

        # Get RAG status to check for storage corruption/inconsistency
        rag_status = get_rag_status_summary(user_config)
        storage_corrupted = False  # Default to not corrupted

        # Only check for corruption if storage exists and is healthy
        if storage_exists and storage_healthy:
            rag_up_to_date = rag_status.get("is_up_to_date", True)
            changes = rag_status.get("comparison", {}).get("changes", [])

            # Only consider corrupted if there are actual corruption indicators
            # Hash mismatch or missing timestamps don't mean corruption
            corruption_indicators = ["missing critical files", "corrupted", "inconsistent", "file corruption", "index corruption"]
            storage_corrupted = not rag_up_to_date and any(
                any(indicator in change.lower() for indicator in corruption_indicators)
                for change in changes
            )

            # Log abnormal cases at INFO level - but these are NOT corruption
            if not rag_up_to_date and not storage_corrupted:
                abnormal_reasons = [change for change in changes if not any(indicator in change.lower() for indicator in corruption_indicators)]
                if abnormal_reasons:
                    utils_logger.info(f"get_data_status_simple::  INFO: Storage exists and healthy, but hash/metadata mismatch detected: {abnormal_reasons}")
        # If storage doesn't exist, it's "empty", not "corrupted"

        utils_logger.debug(f"get_data_status_simple::  STORAGE_EXISTS={storage_exists}, HEALTHY={storage_healthy}, CORRUPTED={storage_corrupted}, CREATION_TIME={storage_creation_time}")
        utils_logger.debug(f"get_data_status_simple::  RAG_STATUS_UP_TO_DATE={rag_status.get('is_up_to_date', 'N/A')}, CHANGES={rag_status.get('comparison', {}).get('changes', [])}")

        if not metadata:
            result = {
                "data_file_newest": data_file_newest,
                "has_newer_files": True,
                "change_count": 0,
                "last_scan": datetime.now().isoformat(),
                "summary": "No previous metadata found - generation required",
                "status_color": "red",
                "status_type": "need_generate"
            }
            utils_logger.debug(f"get_data_status_simple::  RESULT (no metadata)={result}")
            return result

        # Enhanced status determination logic
        status_type = "uptodate"  # Default
        status_color = "green"    # Default
        summary = "Data is up to date with current RAG indexes"

        # Compare with metadata for basic data changes
        comparison = compare_data_with_metadata(current_data, metadata)
        has_data_changes = not comparison["is_up_to_date"]
        change_count = len(comparison["changes"])
        utils_logger.debug(f"get_data_status_simple::  HAS_DATA_CHANGES={has_data_changes}, CHANGE_COUNT={change_count}")

        # Determine status based on storage health and data freshness
        # CORRECTED PRIORITY ORDER: Obsolete check BEFORE general data changes
        if not storage_exists:
            # Storage doesn't exist - need generation
            status_type = "need_generate"
            status_color = "red"
            summary = "RAG storage not found - generation required"
            utils_logger.debug("get_data_status_simple::  STATUS: Storage missing")
        elif storage_corrupted:
            # Storage exists but is corrupted/inconsistent - need generation
            status_type = "need_generate"
            status_color = "red"
            summary = "RAG storage corrupted or inconsistent - regeneration required"
            utils_logger.debug("get_data_status_simple::  STATUS: Storage corrupted")
        elif data_file_newest and storage_creation_time:
            # PRIORITY: First check if data files are newer than storage creation (obsolete data)
            try:
                data_newest_dt = datetime.fromisoformat(data_file_newest)
                storage_creation_dt = datetime.fromisoformat(storage_creation_time)

                if data_newest_dt > storage_creation_dt:
                    # Data files are NEWER than storage - obsolete data (ORANGE)
                    status_type = "obsolete_data"
                    status_color = "orange"
                    summary = "Data files are newer than RAG storage - consider regeneration"
                    utils_logger.debug("get_data_status_simple::  STATUS: Obsolete data detected")
                elif has_data_changes:
                    # Data changed but storage is still newer - need generation (RED)
                    status_type = "need_generate"
                    status_color = "red"
                    summary = f"Found {change_count} change(s) - regeneration recommended"
                    utils_logger.debug("get_data_status_simple::  STATUS: Data changes detected")
                else:
                    # Everything up to date - no changes and storage is current (GREEN)
                    status_type = "uptodate"
                    status_color = "green"
                    summary = "Data is up to date with current RAG indexes"
                    utils_logger.debug("get_data_status_simple::  STATUS: Up to date")
            except (ValueError, TypeError) as e:
                utils_logger.warning(f"Error comparing timestamps: {e}")
                status_type = "need_generate"
                status_color = "red"
                summary = "Could not compare data and storage timestamps"
        elif has_data_changes:
            # Fallback: Data has changes but we can't compare timestamps
            status_type = "need_generate"
            status_color = "red"
            summary = f"Found {change_count} change(s) - regeneration recommended"
            utils_logger.debug("get_data_status_simple::  STATUS: Data changes detected (fallback)")
        else:
            # Fallback - assume up to date if we can't determine
            status_type = "uptodate"
            status_color = "green"
            summary = "Data status could not be fully determined"
            utils_logger.debug("get_data_status_simple::  STATUS: Could not determine")

        # Get additional fields for frontend display
        first_filename = None
        if current_data["current_files"]:
            first_filename = current_data["current_files"][0]["name"]

        result = {
            "data_file_newest": data_file_newest,
            "total_files": current_data["total_files"],
            "total_size": current_data["total_size"],
            "first_filename": first_filename,
            "has_newer_files": has_data_changes,
            "change_count": change_count,
            "last_scan": datetime.now().isoformat(),
            "summary": summary,
            "status_color": status_color,
            "status_type": status_type,
            "changes": comparison["changes"],
            "storage_exists": storage_exists,
            "storage_creation_time": storage_creation_time
        }
        utils_logger.debug(f"get_data_status_simple::  FINAL_RESULT={result}")
        return result

    except Exception as e:
        utils_logger.error(f"Error getting simplified data status: {e}")
        result = {
            "data_file_newest": None,
            "has_newer_files": True,
            "change_count": 0,
            "last_scan": datetime.now().isoformat(),
            "summary": f"Error scanning data: {str(e)}",
            "status_color": "red",
            "status_type": "need_generate",
            "error": str(e)
        }
        utils_logger.debug(f"get_data_status_simple::  ERROR_RESULT={result}")
        return result


def get_detailed_data_status(user_config: UserConfig) -> Dict[str, Any]:
    """
    Get detailed data status with file-by-file information for detail view.

    This provides comprehensive file information including modification dates,
    file sizes, and change status for each file in the data directory.

    Args:
        user_config: User's configuration object containing paths and RAG type

    Returns:
        dict: Detailed data status including:
        - rag_type: Current RAG type
        - total_files: Total number of files
        - files: List of detailed file information
        - last_scan: When the data was last scanned
    """
    try:
        # Scan current data
        current_data = scan_data_directory(user_config.my_rag.data_path)

        # Load metadata for comparison
        metadata = load_data_metadata(user_config.my_rag.rag_root, user_config.my_rag.rag_type)

        # Build detailed file list
        detailed_files = []
        metadata_files = metadata.get("files", {}) if metadata else {}

        for file_info in current_data["current_files"]:
            file_name = file_info["name"]
            metadata_file = metadata_files.get(file_name, {})

            # Determine file status
            if not metadata_file:
                status = "new"
            elif file_info["modified"] > metadata_file.get("modified", ""):
                status = "modified"
            else:
                status = "unchanged"

            detailed_files.append({
                "name": file_name,
                "size": file_info["size"],
                "modified": file_info["modified"],
                "hash": file_info.get("hash", ""),
                "previous_modified": metadata_file.get("modified", ""),
                "status": status
            })

        # Sort files by name for consistent display
        detailed_files.sort(key=lambda x: x["name"])

        result = {
            "rag_type": user_config.my_rag.rag_type,
            "total_files": len(detailed_files),
            "total_size": current_data["total_size"],
            "files": detailed_files,
            "last_scan": datetime.now().isoformat()
        }

        utils_logger.debug(f"get_detailed_data_status:: Generated detailed status for {len(detailed_files)} files")
        return result

    except Exception as e:
        utils_logger.error(f"Error getting detailed data status: {e}")
        result = {
            "rag_type": user_config.my_rag.rag_type,
            "total_files": 0,
            "files": [],
            "last_scan": datetime.now().isoformat(),
            "error": str(e)
        }
        return result




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
        storage_info = scan_storage_directory(user_config.my_rag.storage_path)
        utils_logger.debug(f"get_rag_status_summary::  STORAGE_INFO={storage_info}")

        # Load metadata for this specific RAG type
        metadata = load_data_metadata(user_config.my_rag.rag_root, user_config.my_rag.rag_type)

        if not metadata:
            result = {
                "storage_info": storage_info,
                "comparison": {"is_up_to_date": False, "changes": ["No previous metadata found for this RAG type"]},
                "is_up_to_date": False
            }
            utils_logger.debug(f"get_rag_status_summary::  RESULT (no metadata)={result}")
            return result

        # New comparison logic based on storage hash and timestamps
        changes = []
        is_up_to_date = True

        # Check 1: Compare storage content hash
        current_storage_hash = calculate_storage_hash(user_config.my_rag.storage_path)
        saved_storage_hash = metadata.get("rag_storage_hash", "")
        utils_logger.debug(f"get_rag_status_summary::  CURRENT_STORAGE_HASH={current_storage_hash}")
        utils_logger.debug(f"get_rag_status_summary::  SAVED_STORAGE_HASH={saved_storage_hash}")

        # Only consider hash mismatch if we have a previously saved non-empty hash to compare against
        if saved_storage_hash and saved_storage_hash.strip() and current_storage_hash != saved_storage_hash:
            changes.append(f"Storage content changed (hash mismatch)")
            is_up_to_date = False
        elif not saved_storage_hash or not saved_storage_hash.strip():
            # No previous hash saved - this is normal for first-time checks
            if current_storage_hash:
                changes.append("Storage hash calculated for first time")
                # Don't set is_up_to_date = False for first-time hash calculation

        # Check 2: Compare data_file_newest with rag_storage_creation
        # First, calculate current data_file_newest
        current_data = scan_data_directory(user_config.my_rag.data_path)
        current_data_file_newest = None
        if current_data["current_files"]:
            newest_file = max(current_data["current_files"], key=lambda f: f["modified"])
            current_data_file_newest = newest_file["modified"]

        saved_rag_storage_creation = metadata.get("rag_storage_creation")
        saved_data_file_newest = metadata.get("data_file_newest")
        utils_logger.debug(f"get_rag_status_summary::  CURRENT_DATA_FILE_NEWEST={current_data_file_newest}")
        utils_logger.debug(f"get_rag_status_summary::  SAVED_DATA_FILE_NEWEST={saved_data_file_newest}")
        utils_logger.debug(f"get_rag_status_summary::  SAVED_RAG_STORAGE_CREATION={saved_rag_storage_creation}")

        if current_data_file_newest and saved_rag_storage_creation:
            try:
                current_newest_dt = datetime.fromisoformat(current_data_file_newest)
                saved_creation_dt = datetime.fromisoformat(saved_rag_storage_creation)

                if current_newest_dt > saved_creation_dt:
                    changes.append(f"New data files detected after storage creation")
                    is_up_to_date = False
            except (ValueError, TypeError) as e:
                utils_logger.warning(f"Error comparing timestamps: {e}")
                changes.append("Could not compare timestamps")
                is_up_to_date = False
        elif current_data_file_newest and not saved_rag_storage_creation:
            changes.append("No previous storage creation timestamp found")
            # Don't set is_up_to_date = False just because metadata is missing
            # Missing metadata != storage corruption - this indicates obsolete data
            utils_logger.info(f"get_rag_status_summary::  INFO: Storage exists but creation timestamp missing for {user_config.my_rag.rag_type} (indicates obsolete data - data newer than storage)")
        elif not current_data_file_newest and saved_rag_storage_creation:
            changes.append("No current data files found")
            is_up_to_date = False

        comparison = {
            "is_up_to_date": is_up_to_date,
            "changes": changes if changes else ["Storage is up to date"]
        }
        utils_logger.debug(f"get_rag_status_summary::  COMPARISON={comparison}")

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
