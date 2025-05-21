#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
User Database module for the Multi-Chamber Test application.

This module provides the UserDB class that handles database operations
for user management, including authentication, user creation, and
password management.
"""

import os
import sqlite3
import logging
import hashlib
import time
import shutil
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from multi_chamber_test.config.constants import PASSWORD_FILE, USER_ROLES


class UserDB:
    """
    User database manager for authentication and user management.
    
    This class provides methods to:
    - Create and manage users
    - Authenticate users
    - Retrieve user information
    - Manage passwords
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the UserDB with a database path.
        
        Args:
            db_path: Path to the SQLite database file (defaults to directory of PASSWORD_FILE)
        """
        self.logger = logging.getLogger('UserDB')
        self._setup_logger()
        
        # Determine database path
        if db_path is None:
            db_dir = os.path.dirname(PASSWORD_FILE)
            self.db_path = os.path.join(db_dir, "techmac_users.db")
        else:
            self.db_path = db_path
        
        # Initialize database
        self._init_database()
    
    def _setup_logger(self):
        """Configure logging for the user database."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _init_database(self):
        """Initialize the database schema if it doesn't exist."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Check if database already exists
            db_exists = os.path.exists(self.db_path)
            
            # Create database connection
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # If database exists, check if it has the proper schema
            if db_exists:
                try:
                    # Try to query the users table to check schema
                    cursor.execute("SELECT username, password_hash, role FROM users LIMIT 1")
                    cursor.fetchone()  # This will raise an exception if the schema is wrong
                except sqlite3.OperationalError as e:
                    self.logger.warning(f"Database schema issue detected: {e}")
                    
                    # Backup the existing database
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{self.db_path}.{timestamp}.bak"
                    conn.close()
                    
                    try:
                        shutil.copy2(self.db_path, backup_path)
                        self.logger.info(f"Created backup of existing database at {backup_path}")
                        
                        # Remove the problematic database
                        os.remove(self.db_path)
                        self.logger.info("Removed corrupted database file")
                        
                        # Reconnect to create a new database
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        db_exists = False
                    except Exception as backup_error:
                        self.logger.error(f"Failed to backup/remove corrupted database: {backup_error}")
                        # Continue anyway and try to recreate the tables
            
            # Create users table if it doesn't exist or had schema issues
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            
            # Create login_attempts table for security monitoring
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT
                )
            ''')
            
            conn.commit()
            
            # Check if default users exist, create if not
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                # Create default users
                default_users = [
                    ("admin", self._hash_password(USER_ROLES["ADMIN"]["default_password"]), "ADMIN"),
                    ("maintenance", self._hash_password(USER_ROLES["MAINTENANCE"]["default_password"]), "MAINTENANCE"),
                    ("operator", self._hash_password(USER_ROLES["OPERATOR"]["default_password"]), "OPERATOR")
                ]
                
                cursor.executemany(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    default_users
                )
                
                conn.commit()
                self.logger.info("Created default users (admin, maintenance, operator)")
            
            conn.close()
            self.logger.info("User database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing user database: {e}")
            raise
    
    def _hash_password(self, password: str) -> str:
        """
        Create a secure hash of the password.
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        # Use SHA-256 hash for password
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: User's username
            password: User's password
            
        Returns:
            str: User's role if authentication successful, None otherwise
        """
        if not username or not password:
            self.logger.warning("Authentication attempt with empty username or password")
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Hash the provided password
            password_hash = self._hash_password(password)
            
            # Query user with matching username and password
            try:
                cursor.execute(
                    "SELECT role FROM users WHERE username = ? AND password_hash = ?",
                    (username, password_hash)
                )
                
                result = cursor.fetchone()
            except sqlite3.OperationalError as e:
                self.logger.error(f"Database error during authentication: {e}")
                
                # If there's a schema issue, try to fix the database
                if "no such column: role" in str(e):
                    self.logger.warning("Schema issue detected. Attempting to reinitialize database.")
                    conn.close()
                    
                    # Backup the current database
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{self.db_path}.{timestamp}.bak"
                    try:
                        shutil.copy2(self.db_path, backup_path)
                        self.logger.info(f"Created backup of problematic database at {backup_path}")
                        
                        # Remove the problematic database and reinitialize
                        os.remove(self.db_path)
                        self._init_database()
                        
                        # Try the authentication again
                        return self.authenticate_user(username, password)
                    except Exception as backup_error:
                        self.logger.error(f"Failed to fix database: {backup_error}")
                
                return None
            
            # Log authentication attempt
            success = result is not None
            try:
                cursor.execute(
                    "INSERT INTO login_attempts (username, success) VALUES (?, ?)",
                    (username, success)
                )
            except sqlite3.OperationalError:
                # If login_attempts table doesn't exist, just log and continue
                self.logger.warning("Could not log login attempt - login_attempts table may be missing")
                
            # Update last login timestamp if successful
            if success:
                try:
                    cursor.execute(
                        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?",
                        (username,)
                    )
                except sqlite3.OperationalError:
                    self.logger.warning("Could not update last_login timestamp")
            
            conn.commit()
            conn.close()
            
            # Return role if authentication successful
            if result:
                self.logger.info(f"User '{username}' authenticated successfully")
                return result[0]
            else:
                self.logger.warning(f"Failed authentication attempt for user '{username}'")
                return None
                
        except Exception as e:
            self.logger.error(f"Error authenticating user: {e}")
            return None
    
    def create_user(self, username: str, password: str, role: str) -> bool:
        """
        Create a new user.
        
        Args:
            username: New user's username
            password: New user's password
            role: New user's role
            
        Returns:
            bool: True if user was created successfully, False otherwise
        """
        if not username or not password or not role:
            self.logger.error("Invalid user creation parameters")
            return False
            
        # Validate role
        if role not in USER_ROLES and role != "NONE":
            self.logger.error(f"Invalid role: {role}")
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
            user_exists = cursor.fetchone()[0] > 0
            
            if user_exists:
                # Update existing user
                cursor.execute(
                    "UPDATE users SET password_hash = ?, role = ? WHERE username = ?",
                    (self._hash_password(password), role, username)
                )
                self.logger.info(f"User '{username}' updated with role '{role}'")
            else:
                # Insert new user
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, self._hash_password(password), role)
                )
                self.logger.info(f"User '{username}' created successfully with role '{role}'")
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            return False
    
    def reset_user_password(self, username: str, new_password: str) -> bool:
        """
        Reset a user's password.
        
        Args:
            username: Username to reset password for
            new_password: New password to set
            
        Returns:
            bool: True if password was reset successfully, False otherwise
        """
        if not username or not new_password:
            self.logger.error("Invalid password reset parameters")
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
            user_exists = cursor.fetchone()[0] > 0
            
            if not user_exists:
                self.logger.warning(f"Cannot reset password: User '{username}' not found")
                conn.close()
                return False
            
            # Hash the new password
            password_hash = self._hash_password(new_password)
            
            # Update password
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username)
            )
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Password reset successfully for user '{username}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting password: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user.
        
        Args:
            username: Username to delete
            
        Returns:
            bool: True if user was deleted successfully, False otherwise
        """
        if not username:
            self.logger.error("Invalid username for deletion")
            return False
            
        # Don't allow deleting the last admin user
        if username == "admin":
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Count admin users
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN'")
                admin_count = cursor.fetchone()[0]
                
                if admin_count <= 1:
                    self.logger.warning("Cannot delete the last admin user")
                    conn.close()
                    return False
                    
                conn.close()
            except Exception as e:
                self.logger.error(f"Error checking admin users: {e}")
                return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete user
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            
            # Check if any rows were affected
            if cursor.rowcount == 0:
                self.logger.warning(f"User '{username}' not found for deletion")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"User '{username}' deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            return False
    
    def update_user_role(self, username: str, new_role: str) -> bool:
        """
        Update a user's role.
        
        Args:
            username: Username to update
            new_role: New role to assign
            
        Returns:
            bool: True if role was updated successfully, False otherwise
        """
        if not username or not new_role:
            self.logger.error("Invalid parameters for role update")
            return False
            
        # Validate role
        if new_role not in USER_ROLES and new_role != "NONE":
            self.logger.error(f"Invalid role: {new_role}")
            return False
            
        # Don't allow changing the last admin user's role
        if username == "admin":
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get current role
                cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
                current_role = cursor.fetchone()
                
                if current_role and current_role[0] == "ADMIN" and new_role != "ADMIN":
                    # Count admin users
                    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'ADMIN'")
                    admin_count = cursor.fetchone()[0]
                    
                    if admin_count <= 1:
                        self.logger.warning("Cannot change role of the last admin user")
                        conn.close()
                        return False
                
                conn.close()
            except Exception as e:
                self.logger.error(f"Error checking admin users: {e}")
                return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update role
            cursor.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (new_role, username)
            )
            
            # Check if any rows were affected
            if cursor.rowcount == 0:
                self.logger.warning(f"User '{username}' not found for role update")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Role for user '{username}' updated to '{new_role}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating user role: {e}")
            return False
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a user.
        
        Args:
            username: Username to retrieve
            
        Returns:
            Dict containing user information or None if user not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dictionary access to rows
            cursor = conn.cursor()
            
            # Query user
            cursor.execute(
                "SELECT id, username, role, created_at, last_login FROM users WHERE username = ?",
                (username,)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # Convert to dictionary
                user_info = dict(row)
                return user_info
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving user information: {e}")
            return None
    
    def get_all_users(self) -> List[Tuple[str, str]]:
        """
        Get all users in the database.
        
        Returns:
            List of tuples containing (username, role)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query all users
            try:
                cursor.execute("SELECT username, role FROM users ORDER BY username")
                users = cursor.fetchall()
            except sqlite3.OperationalError as e:
                self.logger.error(f"Database error getting users: {e}")
                # If there's a schema issue, try to fix the database
                if "no such column: role" in str(e):
                    self.logger.warning("Schema issue detected. Reinitializing database.")
                    conn.close()
                    
                    # Backup the current database
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{self.db_path}.{timestamp}.bak"
                    
                    try:
                        shutil.copy2(self.db_path, backup_path)
                        self.logger.info(f"Created backup of problematic database at {backup_path}")
                        
                        # Remove the problematic database and reinitialize
                        os.remove(self.db_path)
                        self._init_database()
                        
                        # Try getting users again
                        return self.get_all_users()
                    except Exception as backup_error:
                        self.logger.error(f"Failed to fix database: {backup_error}")
                
                # Return admin as a fallback
                return [("admin", "ADMIN")]
            
            conn.close()
            return users
            
        except Exception as e:
            self.logger.error(f"Error retrieving all users: {e}")
            # Return admin as a fallback in case of errors
            return [("admin", "ADMIN")]
    
    def get_login_history(self, username: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get login history for a user or all users.
        
        Args:
            username: Username to retrieve history for (None for all users)
            limit: Maximum number of entries to retrieve
            
        Returns:
            List of dictionaries containing login history
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dictionary access to rows
            cursor = conn.cursor()
            
            # Query login attempts
            if username:
                cursor.execute(
                    "SELECT * FROM login_attempts WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
                    (username, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM login_attempts ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            history = [dict(row) for row in rows]
            return history
            
        except Exception as e:
            self.logger.error(f"Error retrieving login history: {e}")
            return []
    
    def check_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Check the strength of a password.
        
        Args:
            password: Password to check
            
        Returns:
            Dict containing strength assessment
        """
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
    
    def backup_database(self, backup_path: Optional[str] = None) -> Optional[str]:
        """
        Create a backup of the user database.
        
        Args:
            backup_path: Path to save the backup (None for default location)
            
        Returns:
            str: Path to the backup file or None if backup failed
        """
        try:
            # Default backup path
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{self.db_path}.{timestamp}.bak"
            
            # Ensure source database exists
            if not os.path.exists(self.db_path):
                self.logger.error(f"Cannot backup: Source database not found at {self.db_path}")
                return None
            
            # Create backup using database connection (proper way to ensure consistency)
            source_conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(backup_path)
            
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            self.logger.info(f"Database backup created at {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Error creating database backup: {e}")
            return None
    
    def restore_database(self, backup_path: str) -> bool:
        """
        Restore the user database from a backup.
        
        Args:
            backup_path: Path to the backup file
            
        Returns:
            bool: True if restore was successful, False otherwise
        """
        try:
            # Ensure backup file exists
            if not os.path.exists(backup_path):
                self.logger.error(f"Cannot restore: Backup file not found at {backup_path}")
                return False
            
            # Create a backup of the current database before restoring
            self.backup_database()
            
            # Restore from backup
            backup_conn = sqlite3.connect(backup_path)
            target_conn = sqlite3.connect(self.db_path)
            
            backup_conn.backup(target_conn)
            
            backup_conn.close()
            target_conn.close()
            
            self.logger.info(f"Database restored from {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring database: {e}")
            return False
            
    # Alias methods for compatibility with older code
    def create_database_backup(self, backup_path: Optional[str] = None) -> Optional[str]:
        """Alias for backup_database for backward compatibility."""
        return self.backup_database(backup_path)
        
    def restore_database_backup(self, backup_path: str) -> bool:
        """Alias for restore_database for backward compatibility."""
        return self.restore_database(backup_path)