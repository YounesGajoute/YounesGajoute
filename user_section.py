# -*- coding: utf-8 -*-
"""
User Management Section for the Settings Tab in Multi-Chamber Test application.

This module provides the UserSection class that implements a section for
managing user accounts, changing passwords, and configuring login requirements.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS
from multi_chamber_test.ui.settings.base_section import BaseSection
from multi_chamber_test.core.roles import get_role_manager, get_current_role, has_access
from multi_chamber_test.ui.keypad import show_numeric_keypad


class UserSection(BaseSection):
    """
    User management section for the Settings Tab.
    
    This class implements a UI section for user management tasks like:
    - Changing own password
    - Managing user accounts (admin only)
    - Configuring login policies
    """
    
    def __init__(self, parent, role_manager=None):
        """
        Initialize the User Management section.
        """
        self.role_manager = role_manager or get_role_manager()
    
        # Session timeout must be defined before using it
        self.session_timeout = tk.IntVar(value=self.role_manager.get_session_timeout())
    
        # Now define hours/minutes based on session_timeout
        self.timeout_hours = tk.IntVar(value=self.session_timeout.get() // 3600)
        self.timeout_minutes = tk.IntVar(value=(self.session_timeout.get() % 3600) // 60)
    
        # Other user management state
        self.selected_user = tk.StringVar()
        self.selected_role = tk.StringVar()
        self.user_list = []
    
        # Login policy requirement
        self.require_login = tk.BooleanVar(value=self.role_manager.get_require_login())
    
        super().__init__(parent)
    
    def create_widgets(self):
 
        # Add cards
        self._create_user_info_card()
    
        if has_access("ADMIN"):
            self._create_user_management_section()
            self._create_permissions_section()
            self._create_login_policy_section()
            self._create_database_management_section()
        else:
            self._create_admin_placeholder()
            

    def _create_user_info_card(self):
        """Create the user information card with password management."""
        # Create a styled card
        card, content = self.create_card(
            "User Information",
            "Information about the current user and password management."
        )
        
        # Current user and role display
        info_frame = ttk.Frame(content, style='Card.TFrame')
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            info_frame,
            text="Current User:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        # Get current user and role
        current_user = self.role_manager.get_current_username() or "Not logged in"
        current_role = get_current_role()
        
        ttk.Label(
            info_frame,
            text=f"{current_user} ({current_role})",
            font=UI_FONTS.get('VALUE', ('Helvetica', 12, 'bold')),
            foreground=UI_COLORS.get('PRIMARY', 'blue')
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Change password button
        button_frame = ttk.Frame(content, style='Card.TFrame')
        button_frame.pack(fill=tk.X, pady=10)
        
        change_button = ttk.Button(
            button_frame,
            text="Change Password",
            command=self._change_own_password,
            padding=10
        )
        change_button.pack(side=tk.LEFT)
        
        # Disable button if not logged in
        if current_user == "Not logged in":
            change_button.config(state='disabled')
            ttk.Label(
                button_frame,
                text="You must be logged in to change your password",
                font=('Helvetica', 10, 'italic'),
                foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
            ).pack(side=tk.LEFT, padx=(10, 0))
    
    def _create_admin_placeholder(self):
        """Create a placeholder for admin features."""
        # Create a simple card for admin features
        card, content = self.create_card(
            "Administrator Features",
            "These features are only available to administrators."
        )
        
        # Add a simple message
        info_frame = ttk.Frame(content, style='Card.TFrame')
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            info_frame,
            text="Administrator features like user management and login policy configuration would be shown here.",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12)),
            wraplength=600
        ).pack(anchor=tk.W)
    
    def _create_user_management_section(self):
        """Create the user management section (admin only)."""
        # Create a styled card
        card, content = self.create_card(
            "User Account Management",
            "Create, edit, and delete user accounts."
        )
        
        # User list box
        list_frame = ttk.Frame(content, style='Card.TFrame')
        list_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            list_frame,
            text="User Accounts:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        # Create a frame with listbox and scrollbar
        user_list_frame = ttk.Frame(list_frame)
        user_list_frame.pack(fill=tk.BOTH, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(user_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.user_listbox = tk.Listbox(
            user_list_frame,
            height=6,
            width=40,
            font=UI_FONTS.get('LABEL', ('Helvetica', 12)),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.user_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.user_listbox.yview)
        
        # Bind selection event
        self.user_listbox.bind('<<ListboxSelect>>', self._on_user_selected)
        
        # Action buttons
        button_frame = ttk.Frame(content, style='Card.TFrame')
        button_frame.pack(fill=tk.X, pady=10)
        
        # New user button
        ttk.Button(
            button_frame,
            text="New User",
            command=self._show_new_user_dialog,
            padding=10
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Edit user button (initially disabled)
        self.edit_button = ttk.Button(
            button_frame,
            text="Edit User",
            command=self._show_edit_user_dialog,
            padding=10,
            state='disabled'
        )
        self.edit_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Delete user button (initially disabled)
        self.delete_button = ttk.Button(
            button_frame,
            text="Delete User",
            command=self._delete_user,
            padding=10,
            state='disabled'
        )
        self.delete_button.pack(side=tk.LEFT)

    def _create_database_management_section(self):
        """Create the database management section (admin only)."""
        # Create a styled card
        card, content = self.create_card(
            "Database Management",
            "Create backups and restore the user database."
        )
        
        # Backup button
        backup_frame = ttk.Frame(content, style='Card.TFrame')
        backup_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            backup_frame,
            text="Create Database Backup",
            command=self._create_backup,
            padding=10
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            backup_frame,
            text="Create a backup of the user database",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Restore button
        restore_frame = ttk.Frame(content, style='Card.TFrame')
        restore_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            restore_frame,
            text="Restore from Backup",
            command=self._show_restore_dialog,
            padding=10
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            restore_frame,
            text="Restore the user database from a backup file",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
        ).pack(side=tk.LEFT, padx=(10, 0))
    
    def _create_login_policy_section(self):
        """Create the login policy section (admin only)."""
        # Create a styled card
        card, content = self.create_card(
            "Login Policy",
            "Configure login requirements and session timeout."
        )
        
        # Require login checkbox
        login_frame = ttk.Frame(content, style='Card.TFrame')
        login_frame.pack(fill=tk.X, pady=10)
        
        require_login_cb = ttk.Checkbutton(
            login_frame,
            text="Require Login to Use Application",
            variable=self.require_login,
            command=self._on_require_login_changed
        )
        require_login_cb.pack(anchor=tk.W)
        
        # Session timeout setting in hours and minutes
        self.timeout_frame = ttk.Frame(content, style='Card.TFrame')
        self.timeout_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            self.timeout_frame,
            text="Session Timeout:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        # Create variables for hours and minutes with proper conversion
        self.timeout_hours = tk.IntVar()
        self.timeout_minutes = tk.IntVar()
        
        # Set initial values from the session_timeout (which is in seconds)
        self._update_hours_minutes_from_seconds()
        
        # Create frame for hours and minutes display
        time_display_frame = ttk.Frame(self.timeout_frame)
        time_display_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        # Hours display
        hours_frame = ttk.Frame(time_display_frame)
        hours_frame.pack(side=tk.LEFT)
        
        hours_value = ttk.Label(
            hours_frame,
            textvariable=self.timeout_hours,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12, 'bold')),
            foreground=UI_COLORS.get('PRIMARY', 'blue')
        )
        hours_value.pack(side=tk.LEFT)
        
        ttk.Label(
            hours_frame,
            text=" hours",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        # Minutes display
        minutes_frame = ttk.Frame(time_display_frame)
        minutes_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        minutes_value = ttk.Label(
            minutes_frame,
            textvariable=self.timeout_minutes,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12, 'bold')),
            foreground=UI_COLORS.get('PRIMARY', 'blue')
        )
        minutes_value.pack(side=tk.LEFT)
        
        ttk.Label(
            minutes_frame,
            text=" minutes",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        # Edit hours and minutes buttons
        edit_frame = ttk.Frame(self.timeout_frame)
        edit_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        ttk.Button(
            edit_frame,
            text="Edit Hours",
            command=self._edit_timeout_hours,
            padding=5
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            edit_frame,
            text="Edit Minutes",
            command=self._edit_timeout_minutes,
            padding=5
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # Save button for policy changes
        save_frame = ttk.Frame(content, style='Card.TFrame')
        save_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            save_frame,
            text="Save Policy Changes",
            command=self._save_login_policy,
            padding=10
        ).pack(side=tk.RIGHT)
        
        # Initially show/hide timeout based on require_login
        self._on_require_login_changed()
    
    def _update_hours_minutes_from_seconds(self):
        """Update the hours and minutes variables from session_timeout seconds."""
        total_seconds = self.session_timeout.get()
        self.timeout_hours.set(total_seconds // 3600)
        self.timeout_minutes.set((total_seconds % 3600) // 60)
    
    def _update_seconds_from_hours_minutes(self):
        """Update session_timeout seconds from hours and minutes variables."""
        hours = self.timeout_hours.get()
        minutes = self.timeout_minutes.get()
        
        total_seconds = (hours * 3600) + (minutes * 60)
        self.session_timeout.set(total_seconds)
    
    def _edit_timeout_hours(self):
        """Show keypad to edit timeout hours."""
        def on_hours_set(value):
            try:
                hours = int(value)
                if hours >= 0:
                    self.timeout_hours.set(hours)
                    self._update_seconds_from_hours_minutes()
            except (ValueError, TypeError):
                pass
        
        # Show numeric keypad for hours
        show_numeric_keypad(
            self.parent,
            self.timeout_hours,
            "Session Timeout Hours",
            min_value=0,
            max_value=24,  # Max 24 hours
            decimal_places=0,
            callback=on_hours_set
        )
    
    def _edit_timeout_minutes(self):
        """Show keypad to edit timeout minutes."""
        def on_minutes_set(value):
            try:
                minutes = int(value)
                if 0 <= minutes < 60:
                    self.timeout_minutes.set(minutes)
                    self._update_seconds_from_hours_minutes()
            except (ValueError, TypeError):
                pass
        
        # Show numeric keypad for minutes
        show_numeric_keypad(
            self.parent,
            self.timeout_minutes,
            "Session Timeout Minutes",
            min_value=0,
            max_value=59,  # 0-59 minutes
            decimal_places=0,
            callback=on_minutes_set
        )
    
    def _change_own_password(self):
        """Show dialog to change current user's password."""
        current_user = self.role_manager.get_current_username()
        
        if not current_user or current_user == "Not logged in":
            self.show_feedback("You must be logged in to change your password", is_error=True)
            return
        
        # Create password change dialog
        self._show_password_change_dialog(current_user)
    
    def _show_password_change_dialog(self, username: str):
        """Show dialog to change password for a user."""
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Change Password: {username}")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size and position
        dialog.geometry("400x300")
        
        # Style
        dialog.configure(bg=UI_COLORS.get('BACKGROUND', '#FFFFFF'))
        
        # Create content frame
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Current password field
        current_frame = ttk.Frame(content)
        current_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            current_frame,
            text="Current Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        current_var = tk.StringVar()
        current_entry = ttk.Entry(
            current_frame,
            textvariable=current_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        current_entry.pack(fill=tk.X, pady=5)
        
        # New password field
        new_frame = ttk.Frame(content)
        new_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            new_frame,
            text="New Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        new_var = tk.StringVar()
        new_entry = ttk.Entry(
            new_frame,
            textvariable=new_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        new_entry.pack(fill=tk.X, pady=5)
        
        # Confirm password field
        confirm_frame = ttk.Frame(content)
        confirm_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            confirm_frame,
            text="Confirm New Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(
            confirm_frame,
            textvariable=confirm_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        confirm_entry.pack(fill=tk.X, pady=5)
        
        # Status message
        status_var = tk.StringVar()
        status_label = ttk.Label(
            content,
            textvariable=status_var,
            font=UI_FONTS.get('LABEL', ('Helvetica', 12)),
            foreground=UI_COLORS.get('ERROR', 'red')
        )
        status_label.pack(fill=tk.X, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(content)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Change password function
        def change_password():
            current = current_var.get()
            new = new_var.get()
            confirm = confirm_var.get()
            
            # Validate
            if not current:
                status_var.set("Current password is required")
                return
                
            if not new:
                status_var.set("New password is required")
                return
                
            if len(new) < 4:
                status_var.set("New password must be at least 4 characters")
                return
                
            if new != confirm:
                status_var.set("New passwords do not match")
                return
            
            # Verify current password
            if not self.role_manager.authenticate_user(username, current):
                status_var.set("Current password is incorrect")
                return
                
            # Attempt to change password
            try:
                success = self.role_manager.reset_user_password(username, new)
                if success:
                    dialog.destroy()
                    self.show_feedback("Password changed successfully")
                else:
                    status_var.set("Failed to change password. Database error occurred.")
            except Exception as e:
                status_var.set(f"Error: {str(e)}")
        
        # Cancel button
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            padding=10
        ).pack(side=tk.LEFT)
        
        # Change button
        ttk.Button(
            button_frame,
            text="Change Password",
            command=change_password,
            padding=10
        ).pack(side=tk.RIGHT)
        
        # Focus current password field
        current_entry.focus_set()
    
    def _on_user_selected(self, event):
        """Handle user selection in listbox."""
        selection = self.user_listbox.curselection()
        if not selection:
            # Nothing selected
            self.selected_user.set("")
            self.selected_role.set("")
            self.edit_button.config(state='disabled')
            self.delete_button.config(state='disabled')
            return
        
        # Get selected user
        index = selection[0]
        if index < len(self.user_list):
            username, role = self.user_list[index]
            self.selected_user.set(username)
            self.selected_role.set(role)
            
            # Enable buttons
            self.edit_button.config(state='normal')
            self.delete_button.config(state='normal')
    
    def _show_new_user_dialog(self):
        """Show dialog to create a new user."""
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title("Create New User")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size and position
        dialog.geometry("400x350")
        
        # Style
        dialog.configure(bg=UI_COLORS.get('BACKGROUND', '#FFFFFF'))
        
        # Create content frame
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Username field
        username_frame = ttk.Frame(content)
        username_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            username_frame,
            text="Username:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        username_var = tk.StringVar()
        username_entry = ttk.Entry(
            username_frame,
            textvariable=username_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30
        )
        username_entry.pack(fill=tk.X, pady=5)
        
        # Password field
        password_frame = ttk.Frame(content)
        password_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            password_frame,
            text="Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        password_var = tk.StringVar()
        password_entry = ttk.Entry(
            password_frame,
            textvariable=password_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        password_entry.pack(fill=tk.X, pady=5)
        
        # Confirm password field
        confirm_frame = ttk.Frame(content)
        confirm_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            confirm_frame,
            text="Confirm Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(
            confirm_frame,
            textvariable=confirm_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        confirm_entry.pack(fill=tk.X, pady=5)
        
        # Role selection
        role_frame = ttk.Frame(content)
        role_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            role_frame,
            text="Role:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        role_var = tk.StringVar(value="OPERATOR")
        
        # Get available roles from role manager
        available_roles = self.role_manager.get_available_roles()
        
        role_dropdown = ttk.Combobox(
            role_frame,
            textvariable=role_var,
            values=available_roles,
            state="readonly",
            font=UI_FONTS.get('VALUE', ('Helvetica', 12))
        )
        role_dropdown.pack(fill=tk.X, pady=5)
        
        # Status message
        status_var = tk.StringVar()
        status_label = ttk.Label(
            content,
            textvariable=status_var,
            font=UI_FONTS.get('LABEL', ('Helvetica', 12)),
            foreground=UI_COLORS.get('ERROR', 'red')
        )
        status_label.pack(fill=tk.X, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(content)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Create user function
        def create_user():
            username = username_var.get().strip()
            password = password_var.get().strip()
            confirm = confirm_var.get().strip()
            role = role_var.get()
            
            # Validate
            if not username:
                status_var.set("Username is required")
                return
                
            if not password:
                status_var.set("Password is required")
                return
                
            if len(password) < 4:
                status_var.set("Password must be at least 4 characters")
                return
                
            if password != confirm:
                status_var.set("Passwords do not match")
                return
            
            # Check password strength
            strength = self.role_manager.check_password_strength(password)
            if not strength["is_strong"]:
                warning = "Warning: Password is weak. Consider using a mix of uppercase, lowercase, numbers and special characters."
                status_var.set(warning)
                
                # Ask for confirmation to continue with weak password
                if not messagebox.askyesno("Weak Password", f"{warning}\n\nContinue anyway?"):
                    return
            
            # Attempt to create user
            try:
                success = self.role_manager.create_user(username, password, role)
                if success:
                    dialog.destroy()
                    self.show_feedback(f"User '{username}' created successfully")
                    self.load_users()  # Refresh user list
                else:
                    status_var.set(f"Failed to create user: Username may already exist")
            except Exception as e:
                status_var.set(f"Error: {str(e)}")
        
        # Cancel button
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            padding=10
        ).pack(side=tk.LEFT)
        
        # Create button
        ttk.Button(
            button_frame,
            text="Create User",
            command=create_user,
            padding=10
        ).pack(side=tk.RIGHT)
        
        # Focus username field
        username_entry.focus_set()
    
    def _show_edit_user_dialog(self):
        """Show dialog to edit a user."""
        username = self.selected_user.get()
        role = self.selected_role.get()
        
        if not username:
            return
            
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Edit User: {username}")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size and position
        dialog.geometry("400x300")
        
        # Style
        dialog.configure(bg=UI_COLORS.get('BACKGROUND', '#FFFFFF'))
        
        # Create content frame
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # User info
        info_frame = ttk.Frame(content)
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            info_frame,
            text=f"Editing User: {username}",
            font=UI_FONTS.get('SUBHEADER', ('Helvetica', 14, 'bold')),
            foreground=UI_COLORS.get('PRIMARY', 'blue')
        ).pack(anchor=tk.W)
        
        ttk.Label(
            info_frame,
            text=f"Current Role: {role}",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # New role selection
        role_frame = ttk.Frame(content)
        role_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            role_frame,
            text="New Role:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        new_role_var = tk.StringVar(value=role)
        
        # Get available roles
        available_roles = self.role_manager.get_available_roles()
        
        role_dropdown = ttk.Combobox(
            role_frame,
            textvariable=new_role_var,
            values=available_roles,
            state="readonly",
            font=UI_FONTS.get('VALUE', ('Helvetica', 12))
        )
        role_dropdown.pack(fill=tk.X, pady=5)
        
        # Reset password option
        reset_frame = ttk.Frame(content)
        reset_frame.pack(fill=tk.X, pady=10)
        
        reset_var = tk.BooleanVar(value=False)
        reset_check = ttk.Checkbutton(
            reset_frame,
            text="Reset Password",
            variable=reset_var
        )
        reset_check.pack(anchor=tk.W)
        
        # New password field (initially hidden)
        password_frame = ttk.Frame(content)
        password_frame.pack(fill=tk.X, pady=10)
        password_frame.pack_forget()  # Hide initially
        
        ttk.Label(
            password_frame,
            text="New Password:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(anchor=tk.W)
        
        password_var = tk.StringVar()
        password_entry = ttk.Entry(
            password_frame,
            textvariable=password_var,
            font=UI_FONTS.get('VALUE', ('Helvetica', 12)),
            width=30,
            show="*"
        )
        password_entry.pack(fill=tk.X, pady=5)
        
        # Show/hide password field based on checkbox
        def toggle_password_field(*args):
            if reset_var.get():
                password_frame.pack(fill=tk.X, pady=10)
            else:
                password_frame.pack_forget()
                
        reset_var.trace_add("write", toggle_password_field)
        
        # Status message
        status_var = tk.StringVar()
        status_label = ttk.Label(
            content,
            textvariable=status_var,
            font=UI_FONTS.get('LABEL', ('Helvetica', 12)),
            foreground=UI_COLORS.get('ERROR', 'red')
        )
        status_label.pack(fill=tk.X, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(content)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Update user function
        def update_user():
            new_role = new_role_var.get()
            reset_password = reset_var.get()
            new_password = password_var.get().strip() if reset_password else None
            
            # Validate
            if reset_password and (not new_password or len(new_password) < 4):
                status_var.set("New password must be at least 4 characters")
                return
            
            # Update role if changed
            role_updated = False
            if new_role != role:
                try:
                    success = self.role_manager.set_user_role(username, new_role)
                    if success:
                        role_updated = True
                    else:
                        status_var.set("Failed to update role")
                        return
                except Exception as e:
                    status_var.set(f"Error updating role: {str(e)}")
                    return
            
            # Reset password if requested
            password_updated = False
            if reset_password and new_password:
                try:
                    # Check password strength
                    strength = self.role_manager.check_password_strength(new_password)
                    if not strength["is_strong"]:
                        warning = "Warning: Password is weak. Consider using a mix of uppercase, lowercase, numbers and special characters."
                        status_var.set(warning)
                        
                        # Ask for confirmation to continue with weak password
                        if not messagebox.askyesno("Weak Password", f"{warning}\n\nContinue anyway?"):
                            return
                    
                    success = self.role_manager.reset_user_password(username, new_password)
                    if success:
                        password_updated = True
                    else:
                        status_var.set("Failed to reset password")
                        return
                except Exception as e:
                    status_var.set(f"Error resetting password: {str(e)}")
                    return
            
            # If we got here, everything succeeded
            dialog.destroy()
            
            # Show appropriate feedback
            if role_updated and password_updated:
                self.show_feedback(f"User '{username}' role and password updated")
            elif role_updated:
                self.show_feedback(f"User '{username}' role updated to {new_role}")
            elif password_updated:
                self.show_feedback(f"User '{username}' password reset")
                
            # Refresh user list
            self.load_users()
        
        # Cancel button
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            padding=10
        ).pack(side=tk.LEFT)
        
        # Update button
        ttk.Button(
            button_frame,
            text="Update User",
            command=update_user,
            padding=10
        ).pack(side=tk.RIGHT)
    
    def _delete_user(self):
        """Delete the selected user."""
        username = self.selected_user.get()
        
        if not username:
            return
            
        # Confirm deletion
        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete user '{username}'?\n\nThis cannot be undone."
        ):
            return
        
        # Check if deleting current user
        current_user = self.role_manager.get_current_username()
        if username == current_user:
            messagebox.showerror(
                "Error",
                "You cannot delete your own account while logged in."
            )
            return
        
        # Attempt to delete user
        try:
            success = self.role_manager.delete_user(username)
            if success:
                self.show_feedback(f"User '{username}' deleted successfully")
                self.load_users()  # Refresh user list
                
                # Clear selection
                self.selected_user.set("")
                self.selected_role.set("")
                self.edit_button.config(state='disabled')
                self.delete_button.config(state='disabled')
            else:
                self.show_feedback(f"Failed to delete user '{username}'", is_error=True)
        except Exception as e:
            self.show_feedback(f"Error deleting user: {str(e)}", is_error=True)
    
    def _on_require_login_changed(self):
        """Handle require login checkbox change."""
        # Show/hide timeout settings based on checkbox
        if self.require_login.get():
            self.timeout_frame.pack(fill=tk.X, pady=10)
        else:
            self.timeout_frame.pack_forget()
    
    def _edit_session_timeout(self):
        """Show dialog to edit session timeout in hours and minutes."""
        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title("Edit Session Timeout")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size
        dialog.geometry("300x200")
        
        # Style
        dialog.configure(bg=UI_COLORS.get('BACKGROUND', '#FFFFFF'))
        
        # Create content frame
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Hours field
        hours_frame = ttk.Frame(content)
        hours_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            hours_frame,
            text="Hours:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        hours_var = tk.StringVar(value=str(self.timeout_hours.get()))
        hours_spinbox = ttk.Spinbox(
            hours_frame,
            from_=0,
            to=24,
            textvariable=hours_var,
            width=5
        )
        hours_spinbox.pack(side=tk.RIGHT)
        
        # Minutes field
        minutes_frame = ttk.Frame(content)
        minutes_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            minutes_frame,
            text="Minutes:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        minutes_var = tk.StringVar(value=str(self.timeout_minutes.get()))
        minutes_spinbox = ttk.Spinbox(
            minutes_frame,
            from_=0,
            to=59,
            textvariable=minutes_var,
            width=5
        )
        minutes_spinbox.pack(side=tk.RIGHT)
        
        # Range information
        info_label = ttk.Label(
            content,
            text="Note: Session timeout must be at least 1 minute.",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray'),
            wraplength=260
        )
        info_label.pack(fill=tk.X, pady=10)
        
        # Button frame
        button_frame = ttk.Frame(content)
        button_frame.pack(fill=tk.X, pady=10)
        
        def save_timeout():
            try:
                hours = int(hours_var.get())
                minutes = int(minutes_var.get())
                
                # Validate range
                if hours == 0 and minutes < 1:
                    messagebox.showwarning(
                        "Invalid Timeout",
                        "Session timeout must be at least 1 minute."
                    )
                    return
                
                # Update variables
                self.timeout_hours.set(hours)
                self.timeout_minutes.set(minutes)
                self._update_seconds_from_hours_minutes()
                
                dialog.destroy()
            except ValueError:
                messagebox.showwarning(
                    "Invalid Input",
                    "Please enter valid numbers for hours and minutes."
                )
        
        # Cancel button
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            padding=5
        ).pack(side=tk.LEFT)
        
        # Save button
        ttk.Button(
            button_frame,
            text="Save",
            command=save_timeout,
            padding=5
        ).pack(side=tk.RIGHT)
        
        # Focus the hours field
        hours_spinbox.focus_set()
    
    def _create_backup(self):
        """Create a backup of the user database."""
        try:
            backup_path = self.role_manager.create_database_backup()
            if backup_path:
                self.show_feedback(f"Backup created: {os.path.basename(backup_path)}")
            else:
                self.show_feedback("Failed to create backup", is_error=True)
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            self.show_feedback(f"Error: {str(e)}", is_error=True)
    
    def _show_restore_dialog(self):
        """Show dialog to select and restore a backup file."""
        try:
            # Show file dialog to select backup file
            backup_file = filedialog.askopenfilename(
                title="Select Backup File",
                filetypes=[("Database Backups", "*.bak"), ("All Files", "*.*")]
            )
            
            if not backup_file:
                return  # User canceled
                
            # Confirm restoration
            if not messagebox.askyesno(
                "Confirm Restore",
                f"Are you sure you want to restore from the selected backup?\n\n"
                f"File: {os.path.basename(backup_file)}\n\n"
                f"This will replace the current user database and cannot be undone."
            ):
                return
                
            # Attempt to restore from backup
            success = self.role_manager.restore_database_backup(backup_file)
            
            if success:
                self.show_feedback("Database successfully restored from backup")
                self.load_users()  # Refresh user list
            else:
                self.show_feedback("Failed to restore from backup", is_error=True)
                
        except Exception as e:
            self.logger.error(f"Error in restore dialog: {e}")
            self.show_feedback(f"Error: {str(e)}", is_error=True)
    
    def _save_login_policy(self):
        """Save login policy settings."""
        require_login = self.require_login.get()
        hours = self.timeout_hours.get()
        minutes = self.timeout_minutes.get()
        
        # Convert hours and minutes to seconds for the session timeout
        timeout_seconds = (hours * 3600) + (minutes * 60)
        
        # Validate timeout if login required
        if require_login and timeout_seconds < 60:  # At least 1 minute
            self.show_feedback("Session timeout must be at least 1 minute", is_error=True)
            return
        
        # Update settings
        try:
            self.role_manager.set_require_login(require_login)
            self.role_manager.set_session_timeout(timeout_seconds)
            
            # Show success feedback
            self.show_feedback("Login policy settings saved")
            
            # Try to save to persistent settings if possible
            try:
                from multi_chamber_test.config.settings import SettingsManager
                settings = SettingsManager()
                settings.set_setting('require_login', require_login)
                settings.set_setting('session_timeout', timeout_seconds)
                settings.save_settings()
            except Exception as settings_error:
                self.logger.warning(f"Could not save settings to file: {settings_error}")
                
        except Exception as e:
            self.show_feedback(f"Error saving settings: {str(e)}", is_error=True)
    
    def load_users(self):
        """Load user list from user database."""
        try:
            # Clear existing list
            if hasattr(self, 'user_listbox'):
                self.user_listbox.delete(0, tk.END)
            else:
                return
                
            # Get users from the role manager
            users = self.role_manager.get_all_users()
            
            # Store user list for reference
            self.user_list = users
            
            # Update listbox
            for username, role in self.user_list:
                self.user_listbox.insert(tk.END, f"{username} ({role})")
            
            self.logger.info(f"Loaded {len(self.user_list)} users")
                
        except Exception as e:
            self.logger.error(f"Error loading users: {e}")
            self.show_feedback(f"Error loading users: {str(e)}", is_error=True)
    
    def refresh_all(self):
        """Refresh all UI components."""
        # Update login policy UI from role manager settings
        self.require_login.set(self.role_manager.get_require_login())
        
        # Update session timeout and convert to hours/minutes
        self.session_timeout.set(self.role_manager.get_session_timeout())
        self._update_hours_minutes_from_seconds()
        
        # Show/hide timeout settings
        if hasattr(self, 'timeout_frame'):
            if self.require_login.get():
                self.timeout_frame.pack(fill=tk.X, pady=10)
            else:
                self.timeout_frame.pack_forget()
        
        # Load users if admin
        if has_access("ADMIN"):
            self.load_users()
    
    def on_selected(self):
        """Called when section is selected."""
        super().on_selected()
        self.refresh_all()
        
    def on_deselected(self):
        """Called when section is deselected."""
        # Remove mousewheel binding when leaving this section
        self.canvas.unbind_all("<MouseWheel>")
        return super().on_deselected()
        
    def _create_permissions_section(self):
        """Create the permissions management section (admin only)."""
        # Create a styled card
        card, content = self.create_card(
            "Role Permissions",
            "Configure what actions are permitted for each user role."
        )
    
        # Create a tabbed interface for different roles
        role_notebook = ttk.Notebook(content)
        role_notebook.pack(fill=tk.BOTH, expand=True, pady=10)
    
        # Role definitions
        roles = ["OPERATOR", "MAINTENANCE", "ADMIN"]
        self.permission_vars = {}
    
        for role in roles:
            # Tab frame
            tab_frame = ttk.Frame(role_notebook)
            role_notebook.add(tab_frame, text=role)
    
            # Canvas and scrollbar for scrollable permissions list
            canvas = tk.Canvas(tab_frame, background=UI_COLORS.get("BACKGROUND", "#FFFFFF"), highlightthickness=0)
            scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
    
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
            # Scrollable frame inside canvas
            scrollable_frame = ttk.Frame(canvas, style='Card.TFrame')
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    
            def _resize_scrollregion(event):
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfig(canvas_window, width=event.width)
    
            scrollable_frame.bind("<Configure>", _resize_scrollregion)
            canvas.bind("<Configure>", _resize_scrollregion)
    
            # Add description
            ttk.Label(
                scrollable_frame,
                text=f"Configure permissions for the {role} role:",
                font=UI_FONTS.get('LABEL', ('Helvetica', 12, 'bold')),
                wraplength=500
            ).pack(anchor=tk.W, pady=(0, 10))
    
            # Add permission checkboxes
            self._create_permission_checkboxes(scrollable_frame, role)
    
        # Save button below the notebook
        save_frame = ttk.Frame(content, style='Card.TFrame')
        save_frame.pack(fill=tk.X, pady=10)
    
        ttk.Button(
            save_frame,
            text="Save Permission Changes",
            command=self._save_permissions,
            padding=10
        ).pack(side=tk.RIGHT)
        
    def _create_permission_checkboxes(self, parent, role):
        """Create permission checkboxes for a specific role."""
        # Define available permissions
        permission_groups = {
            "System Access": [
                {"id": "access_settings", "label": "Access Settings Tab"},
                {"id": "access_history", "label": "Access Test History"},
                {"id": "access_reports", "label": "Access Reports"}
            ],
            "Test Operations": [
                {"id": "run_tests", "label": "Run Tests"},
                {"id": "stop_tests", "label": "Stop Tests"},
                {"id": "create_references", "label": "Create Reference Tests"},
                {"id": "modify_parameters", "label": "Modify Test Parameters"}
            ],
            "Hardware Control": [
                {"id": "manual_control", "label": "Manual Hardware Control"},
                {"id": "calibration", "label": "Perform Calibration"},
                {"id": "diagnostics", "label": "Access Diagnostics"}
            ],
            "User Management": [
                {"id": "create_users", "label": "Create Users"},
                {"id": "edit_users", "label": "Edit Users"},
                {"id": "delete_users", "label": "Delete Users"}
            ],
            "Data Management": [
                {"id": "export_data", "label": "Export Test Data"},
                {"id": "delete_data", "label": "Delete Test Records"},
                {"id": "backup_restore", "label": "Backup/Restore Database"}
            ]
        }
        
        # Current permissions for this role (would be loaded from role_manager)
        current_permissions = self._get_role_permissions(role)
        
        # Create permission variables dictionary
        self.permission_vars = self.permission_vars if hasattr(self, 'permission_vars') else {}
        if role not in self.permission_vars:
            self.permission_vars[role] = {}
        
        # Create UI for each permission group
        for group_name, permissions in permission_groups.items():
            # Group frame
            group_frame = ttk.LabelFrame(parent, text=group_name, padding=10)
            group_frame.pack(fill=tk.X, pady=5)
            
            # Create checkboxes for each permission
            for perm in permissions:
                perm_id = perm["id"]
                is_enabled = perm_id in current_permissions
                
                # Create variable if not exists
                if perm_id not in self.permission_vars[role]:
                    self.permission_vars[role][perm_id] = tk.BooleanVar(value=is_enabled)
                else:
                    self.permission_vars[role][perm_id].set(is_enabled)
                
                # Some permissions should be forced for certain roles
                is_forced = (role == "ADMIN" and perm_id in ["access_settings", "create_users", "edit_users"])
                
                # Create checkbox
                checkbox = ttk.Checkbutton(
                    group_frame,
                    text=perm["label"],
                    variable=self.permission_vars[role][perm_id],
                    state='disabled' if is_forced else 'normal'
                )
                checkbox.pack(anchor=tk.W, pady=2)
                
                # If forced permission, set it to True
                if is_forced:
                    self.permission_vars[role][perm_id].set(True)
    
    def _get_role_permissions(self, role):
        """Get current permissions for a role."""
        # This would be populated from your role manager or constants
        # For now, using a simple mapping of default permissions
        default_permissions = {
            "OPERATOR": [
                "access_history", "run_tests", "stop_tests"
            ],
            "MAINTENANCE": [
                "access_settings", "access_history", "run_tests", "stop_tests",
                "create_references", "modify_parameters", "manual_control", 
                "calibration", "diagnostics", "export_data"
            ],
            "ADMIN": [
                "access_settings", "access_history", "access_reports", "run_tests", 
                "stop_tests", "create_references", "modify_parameters", "manual_control", 
                "calibration", "diagnostics", "create_users", "edit_users", 
                "delete_users", "export_data", "delete_data", "backup_restore"
            ]
        }
        
        # Try to get from role_manager if available
        try:
            # This assumes your role_manager has a get_role_permissions function
            # If it doesn't, we'll use the default permissions
            if hasattr(self.role_manager, 'get_role_permissions'):
                return self.role_manager.get_role_permissions(role)
            else:
                return default_permissions.get(role, [])
        except Exception as e:
            self.logger.error(f"Error getting permissions for {role}: {e}")
            return default_permissions.get(role, [])
    
    def _save_permissions(self):
        """Save role permissions to the role manager."""
        try:
            roles_updated = []
            
            # For each role, collect enabled permissions
            for role, perms in self.permission_vars.items():
                enabled_permissions = []
                
                # Collect all enabled permissions
                for perm_id, var in perms.items():
                    if var.get():
                        enabled_permissions.append(perm_id)
                
                # Save to role manager if it has the method
                if hasattr(self.role_manager, 'set_role_permissions'):
                    if self.role_manager.set_role_permissions(role, enabled_permissions):
                        roles_updated.append(role)
            
            # Show success feedback
            if roles_updated:
                self.show_feedback(f"Updated permissions for roles: {', '.join(roles_updated)}")
            else:
                self.show_feedback("No permission changes were saved", is_error=True)
                
        except Exception as e:
            self.logger.error(f"Error saving permissions: {e}")
            self.show_feedback(f"Error saving permissions: {str(e)}", is_error=True)
    def cleanup(self):
            """Clean up resources when the section is destroyed."""
            # Remove mousewheel binding
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except:
                pass
            super().cleanup()
    

