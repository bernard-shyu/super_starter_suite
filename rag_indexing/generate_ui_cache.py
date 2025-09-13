"""
Generate UI Cache Manager

Manages metadata cache specifically for the Generate UI endpoint.
This cache is used only within the Generate UI and provides fast access
to metadata contents without accessing the filesystem repeatedly.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from super_starter_suite.shared.config_manager import UserConfig, config_manager
from super_starter_suite.shared.index_utils import (
    get_metadata_file_path,
    load_data_metadata,
    save_data_metadata,
    scan_data_directory,
    scan_storage_directory,
    get_data_status_simple,
    get_rag_status_summary
)

# UNIFIED LOGGING SYSTEM - Replace global logging
cache_logger = config_manager.get_logger("gen_cache")


class GenerateUICacheManager:
    """
    Manages metadata cache for the Generate UI endpoint.

    This cache stores metadata contents in memory during the lifetime
    of a Generate UI request, providing fast access and ensuring data
    consistency within the UI session.
    """

    def __init__(self, user_config: UserConfig):
        """
        Initialize the cache manager for a specific user.

        Args:
            user_config: User's configuration containing RAG paths and settings
        """
        self.user_config = user_config
        self.cache: Dict[str, Any] = {}
        self.is_loaded = False
        self.last_updated = None

        cache_logger.debug(f"GenerateUICacheManager initialized for user {user_config.user_id}")

    def load_metadata_cache(self) -> bool:
        """
        Load metadata file contents into cache on endpoint entry.

        This should be called when entering the Generate UI endpoint.
        The cache will contain all metadata for all RAG types for this user.
        If new data sources are detected, they will be automatically scanned and added.

        Returns:
            bool: True if cache was loaded successfully, False otherwise
        """
        try:
            # Get metadata file path
            metadata_file = get_metadata_file_path(self.user_config.my_rag.rag_root)

            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    self.cache = json.load(f)
                cache_logger.debug(f"Loaded existing metadata cache from {metadata_file}")
            else:
                # Initialize empty cache if no metadata file exists
                self.cache = {}
                cache_logger.debug("No existing metadata file found, initializing empty cache")

            # Discover and add any missing RAG types from configuration
            self._discover_and_add_missing_rag_types()

            self.is_loaded = True
            self.last_updated = datetime.now()

            return True

        except Exception as e:
            cache_logger.error(f"Failed to load metadata cache: {e}")
            self.cache = {}
            self.is_loaded = False
            return False

    def _discover_and_add_missing_rag_types(self) -> None:
        """
        Discover new data sources that aren't in the cache and add them.

        This method:
        1. Gets the configured RAG types from user settings
        2. Checks which ones are missing from the cache
        3. Scans the data directories for missing RAG types
        4. Adds metadata for newly discovered data sources
        5. Saves the updated metadata file
        """
        try:
            # Get configured RAG types from user settings
            configured_rag_types = self.user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
            cache_logger.debug(f"Configured RAG types: {configured_rag_types}")

            # Check for missing RAG types
            missing_rag_types = []
            for rag_type in configured_rag_types:
                if rag_type not in self.cache:
                    missing_rag_types.append(rag_type)

            if not missing_rag_types:
                cache_logger.debug("No missing RAG types found in cache")
                return

            cache_logger.info(f"Found {len(missing_rag_types)} missing RAG types: {missing_rag_types}")

            # Process each missing RAG type
            for rag_type in missing_rag_types:
                if self._add_rag_type_to_cache(rag_type):
                    cache_logger.info(f"Successfully added RAG type '{rag_type}' to cache")
                else:
                    cache_logger.warning(f"Failed to add RAG type '{rag_type}' to cache")

        except Exception as e:
            cache_logger.error(f"Error discovering missing RAG types: {e}")

    def _add_rag_type_to_cache(self, rag_type: str) -> bool:
        """
        Add a specific RAG type to the cache by scanning its data directory.

        Args:
            rag_type: The RAG type to add to the cache

        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            # Set the RAG type temporarily to scan its directory
            original_rag_type = self.user_config.my_rag.rag_type
            self.user_config.my_rag.set_rag_type(rag_type)

            # Scan the data directory for this RAG type
            data_path = self.user_config.my_rag.data_path
            cache_logger.debug(f"Scanning data directory for RAG type '{rag_type}': {data_path}")

            if not Path(data_path).exists():
                cache_logger.warning(f"Data directory does not exist for RAG type '{rag_type}': {data_path}")
                # Restore original RAG type
                self.user_config.my_rag.set_rag_type(original_rag_type)
                return False

            # Scan the data directory
            current_data = scan_data_directory(data_path)

            if current_data["total_files"] == 0:
                cache_logger.info(f"No files found in data directory for RAG type '{rag_type}'")
                # Still add empty metadata to cache to avoid repeated scans
                self.cache[rag_type] = self._create_empty_metadata(rag_type)
            else:
                # Create metadata for this RAG type
                metadata = self._create_metadata_for_rag_type(rag_type, current_data)
                self.cache[rag_type] = metadata
                cache_logger.debug(f"Added metadata for RAG type '{rag_type}' with {current_data['total_files']} files")

            # Restore original RAG type
            self.user_config.my_rag.set_rag_type(original_rag_type)

            # Save the updated cache to disk
            self._save_cache_to_disk()

            return True

        except Exception as e:
            cache_logger.error(f"Error adding RAG type '{rag_type}' to cache: {e}")
            # Restore original RAG type in case of error
            try:
                self.user_config.my_rag.set_rag_type(original_rag_type)
            except:
                pass
            return False

    def _create_metadata_for_rag_type(self, rag_type: str, data_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create metadata structure for a RAG type.

        Args:
            rag_type: The RAG type
            data_info: Data scan results from scan_data_directory()

        Returns:
            dict: Metadata structure for the RAG type
        """
        # Calculate data_file_newest from current files
        data_file_newest = None
        if data_info["current_files"]:
            newest_file = max(data_info["current_files"], key=lambda f: f["modified"])
            data_file_newest = newest_file["modified"]

        # Create metadata structure
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "data_file_newest": data_file_newest,
            "total_files": data_info["total_files"],
            "total_size": data_info["total_size"],
            "files": {},
            "rag_storage_creation": None,  # Will be set when storage is created
            "rag_storage_hash": ""
        }

        # Index files by name for quick lookup
        for file_info in data_info["current_files"]:
            metadata["files"][file_info["name"]] = {
                "size": file_info["size"],
                "modified": file_info["modified"],
                "hash": file_info.get("hash", "")
            }

        return metadata

    def _create_empty_metadata(self, rag_type: str) -> Dict[str, Any]:
        """
        Create empty metadata structure for a RAG type with no files.

        Args:
            rag_type: The RAG type

        Returns:
            dict: Empty metadata structure
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "data_file_newest": None,
            "total_files": 0,
            "total_size": 0,
            "files": {},
            "rag_storage_creation": None,
            "rag_storage_hash": ""
        }

    def _save_cache_to_disk(self) -> bool:
        """
        Save the current cache contents to the metadata file on disk.

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            metadata_file = get_metadata_file_path(self.user_config.my_rag.rag_root)

            # Ensure the directory exists
            metadata_file.parent.mkdir(parents=True, exist_ok=True)

            # Save to file
            with open(metadata_file, 'w') as f:
                json.dump(self.cache, f, indent=2)

            cache_logger.debug(f"Saved updated cache to disk: {metadata_file}")
            return True

        except Exception as e:
            cache_logger.error(f"Error saving cache to disk: {e}")
            return False

    def save_metadata_cache(self) -> bool:
        """
        Save cache contents back to metadata file on endpoint exit.

        This should be called when leaving the Generate UI endpoint.
        All cached metadata will be persisted to disk.

        Returns:
            bool: True if cache was saved successfully, False otherwise
        """
        if not self.is_loaded:
            cache_logger.warning("Cache not loaded, cannot save")
            return False

        try:
            # Save cache to metadata file
            success = save_data_metadata(
                user_rag_root=self.user_config.my_rag.rag_root,
                rag_type=self.user_config.my_rag.rag_type,
                data_info=self._get_current_data_info(),
                storage_path=self.user_config.my_rag.storage_path
            )

            if success:
                cache_logger.debug("Metadata cache saved successfully")
                return True
            else:
                cache_logger.error("Failed to save metadata cache")
                return False

        except Exception as e:
            cache_logger.error(f"Error saving metadata cache: {e}")
            return False

    def get_cached_metadata(self, rag_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached metadata for a specific RAG type.

        Args:
            rag_type: The RAG type to retrieve metadata for

        Returns:
            dict or None: Metadata dictionary if available, None otherwise
        """
        if not self.is_loaded:
            cache_logger.warning("Cache not loaded")
            return None

        return self.cache.get(rag_type)

    def update_cached_metadata(self, rag_type: str, metadata: Dict[str, Any]) -> bool:
        """
        Update cached metadata for a specific RAG type.

        Args:
            rag_type: The RAG type to update
            metadata: New metadata dictionary

        Returns:
            bool: True if update was successful
        """
        if not self.is_loaded:
            cache_logger.warning("Cache not loaded, cannot update")
            return False

        self.cache[rag_type] = metadata
        self.last_updated = datetime.now()
        cache_logger.debug(f"Updated cached metadata for RAG type {rag_type}")
        return True

    def get_detailed_file_status(self, rag_type: str) -> Dict[str, Any]:
        """
        Get detailed file status for summary/detail view switching.

        Args:
            rag_type: The RAG type to get detailed status for

        Returns:
            dict: Detailed file status information
        """
        if not self.is_loaded:
            return {"error": "Cache not loaded"}

        metadata = self.get_cached_metadata(rag_type)
        if not metadata:
            return {"error": f"No metadata found for RAG type {rag_type}"}

        # Get current data scan for comparison
        current_data = scan_data_directory(self.user_config.my_rag.data_path)

        # Build detailed file list
        detailed_files = []
        metadata_files = metadata.get("files", {})

        for file_info in current_data["current_files"]:
            file_name = file_info["name"]
            metadata_file = metadata_files.get(file_name, {})

            detailed_files.append({
                "name": file_name,
                "size": file_info["size"],
                "modified": file_info["modified"],
                "hash": file_info.get("hash", ""),
                "previous_modified": metadata_file.get("modified", ""),
                "status": self._get_file_status(file_info, metadata_file)
            })

        return {
            "rag_type": rag_type,
            "total_files": len(detailed_files),
            "files": detailed_files,
            "last_scan": datetime.now().isoformat()
        }

    def get_summary_status(self, rag_type: str) -> Dict[str, Any]:
        """
        Get summary status for the current RAG type.

        Args:
            rag_type: The RAG type to get summary for

        Returns:
            dict: Summary status information
        """
        try:
            # Get real-time status using existing functions
            data_status = get_data_status_simple(self.user_config)
            rag_status = get_rag_status_summary(self.user_config)

            return {
                "rag_type": rag_type,
                "data_status": data_status,
                "rag_status": rag_status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            cache_logger.error(f"Error getting summary status: {e}")
            return {"error": str(e)}

    def refresh_cache_for_rag_type(self, rag_type: str) -> bool:
        """
        Refresh cache for a specific RAG type with current data.

        Args:
            rag_type: The RAG type to refresh

        Returns:
            bool: True if refresh was successful
        """
        try:
            # Scan current data and storage
            current_data = scan_data_directory(self.user_config.my_rag.data_path)
            current_storage = scan_storage_directory(self.user_config.my_rag.storage_path)

            # Update metadata
            from super_starter_suite.shared.index_utils import calculate_storage_hash

            metadata = {
                "timestamp": datetime.now().isoformat(),
                "data_file_newest": self._get_newest_file_date(current_data["current_files"]),
                "rag_storage_creation": current_storage.get("last_modified"),
                "rag_storage_hash": calculate_storage_hash(self.user_config.my_rag.storage_path),
                "total_files": current_data["total_files"],
                "total_size": current_data["total_size"],
                "files": {}
            }

            # Index files
            for file_info in current_data["current_files"]:
                metadata["files"][file_info["name"]] = {
                    "size": file_info["size"],
                    "modified": file_info["modified"],
                    "hash": file_info.get("hash", "")
                }

            # Update cache
            return self.update_cached_metadata(rag_type, metadata)

        except Exception as e:
            cache_logger.error(f"Error refreshing cache for RAG type {rag_type}: {e}")
            return False

    def _get_current_data_info(self) -> Dict[str, Any]:
        """
        Get current data directory information.

        Returns:
            dict: Current data scan results
        """
        return scan_data_directory(self.user_config.my_rag.data_path)

    def _get_newest_file_date(self, files: list) -> Optional[str]:
        """
        Get the newest file modification date from a list of files.

        Args:
            files: List of file information dictionaries

        Returns:
            str or None: ISO datetime string of newest file, None if no files
        """
        if not files:
            return None

        newest_file = max(files, key=lambda f: f["modified"])
        return newest_file["modified"]

    def _get_file_status(self, current_file: Dict[str, Any], metadata_file: Dict[str, Any]) -> str:
        """
        Determine the status of a file compared to its metadata.

        Args:
            current_file: Current file information
            metadata_file: Previous file information from metadata

        Returns:
            str: Status string ("new", "modified", "unchanged")
        """
        if not metadata_file:
            return "new"

        if current_file["modified"] > metadata_file.get("modified", ""):
            return "modified"

        return "unchanged"


# Global cache manager instance (one per user session)
_cache_managers: Dict[str, GenerateUICacheManager] = {}


def get_cache_manager(user_config: UserConfig) -> GenerateUICacheManager:
    """
    Get or create a cache manager for the specified user.

    Args:
        user_config: User's configuration

    Returns:
        GenerateUICacheManager: Cache manager instance for the user
    """
    user_id = user_config.user_id
    if user_id not in _cache_managers:
        _cache_managers[user_id] = GenerateUICacheManager(user_config)

    return _cache_managers[user_id]


def cleanup_cache_manager(user_id: str):
    """
    Clean up cache manager for a user (call when user session ends).

    Args:
        user_id: User ID to clean up
    """
    if user_id in _cache_managers:
        # Optionally save cache before cleanup
        try:
            _cache_managers[user_id].save_metadata_cache()
        except Exception as e:
            cache_logger.warning(f"Failed to save cache during cleanup for user {user_id}: {e}")

        del _cache_managers[user_id]
        cache_logger.debug(f"Cleaned up cache manager for user {user_id}")
