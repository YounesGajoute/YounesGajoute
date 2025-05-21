#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Roles module for the Multi-Chamber Test application.

This module provides role-based access control functionality, including
role checking, password management, and helper functions to verify
if a user has sufficient permissions for certain operations.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import hashlib
import time

from multi_chamber_test.config.constants import USER_ROLES
from multi_chamber_test.database.user_db import UserDB  # Updated import path

class RoleManager:
    """
    Manager for role-based access control.
    
    This class manages user authentication, role permissions, and access control
    for the Multi-Chamber Test application.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('RoleManager')
        self._setup_logger()
        self.user_db = UserDB()

        self.current_role = "OPERATOR"
        self.current_username = None
        self.authenticated = False
        self.last_auth_time = 0
        self.session_timeout = 600  # seconds (10 minutes)
        
        # Settings for the "require login" feature
        self.require_login = False
        self.default_role = "OPERATOR"
        
        # Load settings
        self._load_settings()
    
    def _setup_logger(self):
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def _load_settings(self):
        """Load authentication settings from SettingsManager if available."""
        try:
            from multi_chamber_test.config.settings import SettingsManager
            settings = SettingsManager()
            
            # Load require_login setting (default to False if not found)
            self.require_login = bool(settings.get_setting('require_login', False))
            
            # Load default_role setting (default to OPERATOR if not found)
            self.default_role = settings.get_setting('default_role', "OPERATOR")
            
            # Load session timeout (default to 10 minutes if not found)
            self.session_timeout = int(settings.get_setting('session_timeout', 600))
            
            self.logger.info(f"Loaded authentication settings: require_login={self.require_login}, default_role={self.default_role}, session_timeout={self.session_timeout}s")
        except Exception as e:
            self.logger.warning(f"Failed to load authentication settings: {e}")
    
    def set_require_login(self, required: bool):
        """
        Set whether login is required to use the system.
        
        Args:
            required: Whether login is required
        """
        self.require_login = bool(required)
        self.logger.info(f"Require login set to: {self.require_login}")
    
    def get_require_login(self) -> bool:
        """
        Get whether login is required to use the system.
        
        Returns:
            bool: Whether login is required
        """
        return self.require_login
    
    def set_default_role(self, role: str):
        """
        Set the default role when no user is logged in.
        
        Args:
            role: Default role
        """
        if role in USER_ROLES:
            self.default_role = role
            self.logger.info(f"Default role set to: {role}")
        else:
            self.logger.error(f"Invalid role: {role}")
    
    def get_default_role(self) -> str:
        """
        Get the default role when no user is logged in.
        
        Returns:
            str: Default role
        """
        return self.default_role
    
    def set_session_timeout(self, timeout_seconds: int) -> None:
        """
        Set the session timeout period.
        
        Args:
            timeout_seconds: Session timeout in seconds
        """
        if timeout_seconds < 60:
            self.logger.warning(f"Session timeout too short: {timeout_seconds}s. Using 60s minimum.")
            timeout_seconds = 60
            
        self.session_timeout = timeout_seconds
        self.logger.info(f"Session timeout set to {timeout_seconds}s")
    
    def get_session_timeout(self) -> int:
        """
        Get the session timeout period in seconds.
        
        Returns:
            int: Session timeout in seconds
        """
        return self.session_timeout
    
    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            
        Returns:
            str: Role of authenticated user or None if authentication failed
        """
        role = self.user_db.authenticate_user(username, password)
        if role:
            self.current_role = role
            self.current_username = username
            self.authenticated = True
            self.last_auth_time = time.time()
            self.logger.info(f"Authenticated user '{username}' as {role}")
            return role
        return None
    
    def create_user(self, username: str, password: str, role: str) -> bool:
        """
        Create a new user or update an existing user.
        
        Args:
            username: Username for the new user
            password: Password for the new user
            role: Role for the new user
            
        Returns:
            bool: True if user was created successfully, False otherwise
        """
        return self.user_db.create_user(username, password, role)

    def reset_user_password(self, username: str, new_password: str) -> bool:
        """
        Reset a user's password.
        
        Args:
            username: Username to reset password for
            new_password: New password to set
            
        Returns:
            bool: True if password was reset successfully, False otherwise
        """
        return self.user_db.reset_user_password(username, new_password)

    def delete_user(self, username: str) -> bool:
        """
        Delete a user.
        
        Args:
            username: Username to delete
            
        Returns:
            bool: True if user was deleted successfully, False otherwise
        """
        return self.user_db.delete_user(username)
    
    def set_user_role(self, username: str, new_role: str) -> bool:
        """
        Update a user's role.
        
        Args:
            username: Username to update role for
            new_role: New role to assign
            
        Returns:
            bool: True if role was updated successfully, False otherwise
        """
        return self.user_db.update_user_role(username, new_role)

    def get_users(self) -> List[Tuple[str, str]]:
        """
        Get a list of all users and their roles.
        
        Returns:
            List of tuples with (username, role)
        """
        return self.user_db.get_all_users()

    def get_all_users(self) -> List[Tuple[str, str]]:
        """
        Get a list of all users and their roles.
        
        Returns:
            List of tuples with (username, role)
        """
        return self.user_db.get_all_users()

    def get_available_roles(self) -> List[str]:
        """
        Get list of available roles.
        
        Returns:
            List of role names
        """
        roles = list(USER_ROLES.keys())
        
        # Add NONE role when require_login is active
        if self.require_login:
            roles.append("NONE")
            
        return roles

    def is_authenticated(self) -> bool:
        """
        Check if current user is authenticated and session is still valid.
        
        Returns:
            bool: True if authenticated and session is valid, False otherwise
        """
        if not self.authenticated:
            return False
        if time.time() - self.last_auth_time > self.session_timeout:
            self.logger.info("Session expired")
            self.authenticated = False
            self.current_role = self.default_role
            self.current_username = None
            return False
        return True
    
    def refresh_session(self) -> None:
        """Refresh the authentication session timeout."""
        if self.authenticated:
            self.last_auth_time = time.time()
    
    def logout(self):
        """Log out the current user."""
        self.authenticated = False
        self.current_role = self.default_role
        self.current_username = None
        self.logger.info("User logged out")
    
    def get_current_role(self) -> str:
        """
        Get the current user role.
        
        If no user is authenticated:
        - Return "NONE" if require_login is True
        - Return default_role (usually "OPERATOR") if require_login is False
        
        Returns:
            str: Current role
        """
        if self.is_authenticated():
            return self.current_role
        
        # If authentication is required, return NONE role when not logged in
        if self.require_login:
            return "NONE"
            
        # Otherwise return the default role (usually OPERATOR)
        return self.default_role
    
    def get_current_username(self) -> Optional[str]:
        """
        Get the username of the currently authenticated user.
        
        Returns:
            str: Current username or None if not authenticated
        """
        return self.current_username if self.is_authenticated() else None
    
    def get_current_user(self) -> Optional[str]:
        """
        Get the username of the currently authenticated user.
        Alias for get_current_username for backward compatibility.
        
        Returns:
            str: Current username or None if not authenticated
        """
        return self.get_current_username()
    
    def get_role_level(self, role: Optional[str] = None) -> int:
        """
        Get the numeric level of a role.
        
        Args:
            role: Role name (or None to use current role)
            
        Returns:
            int: Role level (0 for NONE role)
        """
        role = role or self.get_current_role()
        
        # Special case for NONE role
        if role == "NONE":
            return 0
            
        return USER_ROLES.get(role, {}).get("level", 0)
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if the current role has the specified permission.
        
        Args:
            permission: Permission to check
            
        Returns:
            bool: True if role has permission, False otherwise
        """
        current_role = self.get_current_role()
        
        # NONE role has no permissions
        if current_role == "NONE":
            return False
        
        if current_role in USER_ROLES:
            role_permissions = USER_ROLES[current_role]['permissions']
            return permission in role_permissions
        
        return False
    
    def has_access(self, min_role: str) -> bool:
        """
        Check if current role has access to features requiring the specified role.
        
        Args:
            min_role: Minimum role required for access
            
        Returns:
            bool: True if current role has sufficient access, False otherwise
        """
        return self.get_role_level() >= self.get_role_level(min_role)
    
    def require_role(self, min_role: str) -> bool:
        """
        Check if user is authenticated and has the required role.
        
        Args:
            min_role: Minimum role required for access
            
        Returns:
            bool: True if authenticated and has sufficient role, False otherwise
        """
        return self.is_authenticated() and self.has_access(min_role)
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a user.
        
        Args:
            username: Username to get info for
            
        Returns:
            Dict with user information or None if user not found
        """
        if hasattr(self.user_db, 'get_user'):
            return self.user_db.get_user(username)
        return None
    
    def check_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Check the strength of a password.
        
        Args:
            password: Password to check
            
        Returns:
            Dict containing strength assessment
        """
        if hasattr(self.user_db, 'check_password_strength'):
            return self.user_db.check_password_strength(password)
        
        # Fallback if method doesn't exist
        result = {
            "length": len(password),
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(not c.isalnum() for c in password),
            "is_strong": False
        }
        
        # Calculate strength score (0-4)
        score = sum([
            result["length"] >= 8,
            result["has_uppercase"],
            result["has_lowercase"],
            result["has_digit"],
            result["has_special"]
        ])
        
        result["score"] = score
        result["is_strong"] = score >= 3
        
        return result
    
    def create_database_backup(self) -> Optional[str]:
        """
        Create a backup of the user database.
        
        Returns:
            str: Path to backup file or None if backup failed
        """
        if hasattr(self.user_db, 'backup_database'):
            return self.user_db.backup_database()
        
        # Fallback if method doesn't exist in UserDB
        if hasattr(self.user_db, 'create_database_backup'):
            return self.user_db.create_database_backup()
            
        return None
    
    def restore_database_backup(self, backup_path: str) -> bool:
        """
        Restore user database from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            bool: True if restore successful, False otherwise
        """
        if hasattr(self.user_db, 'restore_database'):
            return self.user_db.restore_database(backup_path)
        
        # Fallback if method doesn't exist in UserDB
        if hasattr(self.user_db, 'restore_database_backup'):
            return self.user_db.restore_database_backup(backup_path)
            
        return False


# Convenience functions for use throughout the application

_role_manager = None

def get_role_manager() -> RoleManager:
    """
    Get the global RoleManager instance.
    
    Returns:
        RoleManager: Global instance of RoleManager
    """
    global _role_manager
    if _role_manager is None:
        _role_manager = RoleManager()
    return _role_manager

def has_access(min_role: str) -> bool:
    """
    Check if current role has access to features requiring the specified role.
    
    Args:
        min_role: Minimum role required for access
        
    Returns:
        bool: True if current role has sufficient access, False otherwise
    """
    return get_role_manager().has_access(min_role)

def get_current_role() -> str:
    """
    Get the current user role.
    
    Returns:
        str: Current role
    """
    return get_role_manager().get_current_role()

def get_current_username() -> Optional[str]:
    """
    Get the username of the currently authenticated user.
    
    Returns:
        str: Current username or None if not authenticated
    """
    return get_role_manager().get_current_username()