#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Settings Tab main module for the Multi-Chamber Test application.

This module provides the SettingsTab class that implements the settings
interface with a modern sidebar navigation and section-based content display.
Includes advanced thread-safe monitoring, efficient UI updates, and proper
memory management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import time
import weakref
from typing import Dict, Any, List, Optional, Callable, Set, Type

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS
from multi_chamber_test.config.settings import SettingsManager
from multi_chamber_test.core.test_manager import TestManager
from multi_chamber_test.core.roles import get_role_manager, has_access
from multi_chamber_test.ui.password_dialog import PasswordDialog


class SettingsTab:
    """
    Modern settings interface tab with advanced implementation techniques.
    
    This class implements a modular settings interface with thread-safe updating,
    efficient UI refresh logic, and proper memory/lifecycle management.
    """
    
    def __init__(self, parent, test_manager: TestManager, settings_manager: SettingsManager):
        """
        Initialize the SettingsTab with the parent widget and required components.
        
        Args:
            parent: Parent widget (typically a Frame in main_window.py)
            test_manager: TestManager for applying settings
            settings_manager: SettingsManager for storing/retrieving settings
        """
        self.logger = logging.getLogger('SettingsTab')
        self._setup_logger()
        
        self.parent = parent
        self.test_manager = test_manager
        self.settings_manager = settings_manager
        self.role_manager = get_role_manager()
        
        # Store colors for easy access
        self.colors = UI_COLORS
        
        # Section configuration
        self.section_config = {
            'general': {
                'title': "General Settings",
                'icon': "",
                'class': None,  # Will be imported on demand
                'access_role': None,  # No special access needed
                'loaded': False
            },
            'chambers': {
                'title': "Chamber Settings",
                'icon': "",
                'class': None,
                'access_role': None,
                'loaded': False
            },
            'diagnostics': {
                'title': "Diagnostics",
                'icon': "",
                'class': None,
                'access_role': "MAINTENANCE",
                'loaded': False
            },
            'history': {
                'title': "Test History",
                'icon': "",
                'class': None,
                'access_role': None,
                'loaded': False
            },
            'export': {
                'title': "Data Export",
                'icon': "",
                'class': None,
                'access_role': None,
                'loaded': False
            },
            'users': {
                'title': "User Management",
                'icon': "",
                'class': None,
                'access_role': "OPERATOR",  # Everyone can change their password
                'loaded': False
            }
        }
        
        # Keep track of section instances with weak references
        # This helps avoid circular references and memory leaks
        self.sections = {}
        self.section_refs = {}
        self.current_section = None
        
        # Thread synchronization and UI update management
        self._ui_update_lock = threading.RLock()
        self._ui_update_queue = []
        self._ui_update_scheduled = False
        self._monitoring_active = False
        self._monitoring_thread = None
        
        # Setup TTK styles with modern appearance
        self._setup_styles()
        
        # Main container frame
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create UI structure
        self._create_layout()
        
        # Start monitoring thread for real-time data
        self._start_monitoring()
        
        # Initialize with the General section
        self.show_section('general')
        
        # Set up cleanup on tab destruction
        self.parent.bind("<Destroy>", self._on_destroy, add="+")
    
    def _setup_logger(self):
        """Configure logging for the settings tab."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _setup_styles(self):
        """Setup TTK styles for a modern interface."""
        style = ttk.Style()
        
        # Main container style
        style.configure(
            'SettingsContainer.TFrame',
            background=UI_COLORS['BACKGROUND']
        )
        
        # Sidebar styles
        style.configure(
            'Sidebar.TFrame',
            background='#2A3F54'  # Darker blue for sidebar
        )
        
        # Sidebar item styles (normal and selected)
        style.configure(
            'SidebarItem.TFrame',
            background='#2A3F54'
        )
        style.configure(
            'SidebarItemSelected.TFrame',
            background='#1ABB9C'  # Teal highlight for selected item
        )
        
        # Sidebar text styles
        style.configure(
            'SidebarText.TLabel',
            background='#2A3F54',
            foreground='#ECF0F1',  # Light text
            font=UI_FONTS['LABEL']
        )
        style.configure(
            'SidebarTextSelected.TLabel',
            background='#1ABB9C',
            foreground='#FFFFFF',  # White text for selected
            font=UI_FONTS['LABEL']
        )
        style.configure(
            'SidebarIcon.TLabel',
            background='#2A3F54',
            foreground='#ECF0F1',
            font=('Helvetica', 16)  # Larger font for icons
        )
        style.configure(
            'SidebarIconSelected.TLabel',
            background='#1ABB9C',
            foreground='#FFFFFF',
            font=('Helvetica', 16)
        )
        
        # Sidebar title
        style.configure(
            'SidebarTitle.TLabel',
            background='#2A3F54',
            foreground='#FFFFFF',
            font=UI_FONTS['HEADER']
        )
        
        # Content area styles
        style.configure(
            'Content.TFrame',
            background=UI_COLORS['BACKGROUND']
        )
        style.configure(
            'ContentTitle.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['HEADER']
        )
        
        # Card styles for settings panels
        style.configure(
            'Card.TFrame',
            background='#FFFFFF',
            relief='flat'
        )
        style.configure(
            'CardTitle.TLabel',
            background='#FFFFFF',
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['SUBHEADER']
        )
        
        # Button styles
        style.configure(
            'Settings.TButton',
            background=UI_COLORS['PRIMARY'],
            foreground='#FFFFFF',
            font=UI_FONTS['BUTTON'],
            padding=10
        )
        style.configure(
            'BackButton.TButton',
            background='#2A3F54',
            foreground='#FFFFFF',
            font=UI_FONTS['BUTTON'],
            padding=10
        )
    
    def _create_layout(self):
        """Create the main layout with sidebar and content area."""
        # Create sidebar first
        self._create_sidebar()
        
        # Create content area
        self._create_content_area()
        
        # Add separator between sidebar and content
        separator = ttk.Separator(self.main_frame, orient=tk.VERTICAL)
        separator.place(x=250, y=0, relheight=1)
    
    def _create_sidebar(self):
        """Create the modern sidebar with navigation buttons."""
        # Sidebar frame
        self.sidebar_frame = ttk.Frame(self.main_frame, style='Sidebar.TFrame', width=250)
        self.sidebar_frame.place(x=0, y=0, relheight=1, width=250)
        
        # App title
        title_frame = ttk.Frame(self.sidebar_frame, style='Sidebar.TFrame')
        title_frame.pack(fill=tk.X, pady=(20, 30))
        
        ttk.Label(
            title_frame,
            text="Settings",
            style='SidebarTitle.TLabel',
            anchor='center'
        ).pack(fill=tk.X)
        
        # Navigation buttons with icons
        self.nav_buttons = {}
        
        # Create navigation items dynamically from configuration
        for section_id, config in self.section_config.items():
            if not config['access_role'] or has_access(config['access_role']):
                self.create_sidebar_item(
                    section_id,
                    config['title'],
                    section_id == 'general',  # Select general by default
                    config['icon']
                )
        
    
    def create_sidebar_item(self, section_id: str, text: str, is_selected: bool = False, icon: str = ""):
        """
        Create a styled sidebar item with icon and text.
        
        Args:
            section_id: ID of the section to show when clicked
            text: Button text to display
            is_selected: Whether this button is initially selected
            icon: Icon character to display
        """
        # Styles based on selection state
        frame_style = 'SidebarItemSelected.TFrame' if is_selected else 'SidebarItem.TFrame'
        icon_style = 'SidebarIconSelected.TLabel' if is_selected else 'SidebarIcon.TLabel'
        text_style = 'SidebarTextSelected.TLabel' if is_selected else 'SidebarText.TLabel'
        
        # Create container frame for the item
        item_frame = ttk.Frame(self.sidebar_frame, style=frame_style)
        item_frame.pack(fill=tk.X, pady=2)
        
        # Icon
        icon_label = ttk.Label(
            item_frame,
            text=icon,
            style=icon_style
        )
        icon_label.pack(side=tk.LEFT, padx=(20, 10), pady=10)
        
        # Text
        text_label = ttk.Label(
            item_frame,
            text=text,
            style=text_style
        )
        text_label.pack(side=tk.LEFT, pady=10, fill=tk.X)
        
        # Make the whole item clickable
        item_frame.bind("<Button-1>", lambda e, sid=section_id: self.show_section(sid))
        icon_label.bind("<Button-1>", lambda e, sid=section_id: self.show_section(sid))
        text_label.bind("<Button-1>", lambda e, sid=section_id: self.show_section(sid))
        
        # Change cursor to hand when hovering
        item_frame.bind("<Enter>", lambda e: item_frame.configure(cursor="hand2"))
        item_frame.bind("<Leave>", lambda e: item_frame.configure(cursor=""))
        icon_label.bind("<Enter>", lambda e: icon_label.configure(cursor="hand2"))
        icon_label.bind("<Leave>", lambda e: icon_label.configure(cursor=""))
        text_label.bind("<Enter>", lambda e: text_label.configure(cursor="hand2"))
        text_label.bind("<Leave>", lambda e: text_label.configure(cursor=""))
        
        # Store references for later updates
        self.nav_buttons[section_id] = {
            'frame': item_frame,
            'icon': icon_label,
            'text': text_label
        }
    
    def _create_content_area(self):
        """Create the main content area with modern styling."""
        self.content_frame = ttk.Frame(self.main_frame, style='Content.TFrame')
        self.content_frame.place(x=251, y=0, relwidth=1, relheight=1, width=-251)
    
    def show_section(self, section_id: str):
        """
        Show a specific settings section with thread-safe handling.
        
        Args:
            section_id: ID of the section to show
        """
        # Ensure UI updates happen in the main thread
        if threading.current_thread() != threading.main_thread():
            self._schedule_ui_update(lambda: self.show_section(section_id))
            return
            
        # Check if section exists in configuration
        if section_id not in self.section_config:
            self.logger.error(f"Unknown section ID: {section_id}")
            return
            
        config = self.section_config[section_id]
        
        # Check access rights for restricted sections
        if config['access_role'] and not has_access(config['access_role']):
            PasswordDialog(
                self.parent,
                config['access_role'],
                on_success=lambda: self.show_section(section_id)
            )
            return
        
        # Update sidebar button styles
        for sid, button_data in self.nav_buttons.items():
            if sid == section_id:
                button_data['frame'].configure(style='SidebarItemSelected.TFrame')
                button_data['icon'].configure(style='SidebarIconSelected.TLabel')
                button_data['text'].configure(style='SidebarTextSelected.TLabel')
            else:
                button_data['frame'].configure(style='SidebarItem.TFrame')
                button_data['icon'].configure(style='SidebarIcon.TLabel')
                button_data['text'].configure(style='SidebarText.TLabel')
        
        # Hide current section if any
        if self.current_section:
            section = self._get_section(self.current_section)
            if section:
                section.hide()
        
        # Load and show the requested section
        section = self._get_section(section_id, create_if_needed=True)
        if section:
            section.show()
            self.current_section = section_id
            self.logger.info(f"Switched to {section_id} settings section")
    
    def _get_section(self, section_id: str, create_if_needed: bool = False):
        """
        Get a section instance with thread-safe lazy loading.
        
        Args:
            section_id: ID of the section to get
            create_if_needed: Whether to create the section if it doesn't exist
            
        Returns:
            The section instance or None if not available
        """
        # Check if we have a valid weak reference
        if section_id in self.section_refs:
            section = self.section_refs[section_id]()
            if section is not None:
                return section
                
        # If we need to create it
        if create_if_needed:
            with self._ui_update_lock:
                # Check again inside the lock to prevent race conditions
                if section_id in self.section_refs:
                    section = self.section_refs[section_id]()
                    if section is not None:
                        return section
                
                # Load section class if needed
                if not self.section_config[section_id]['class']:
                    self._load_section_class(section_id)
                
                # Create instance if class is available
                section_class = self.section_config[section_id]['class']
                if section_class:
                    try:
                        # Create section instance with appropriate parameters
                        if section_id == 'general':
                            section = section_class(
                                self.content_frame,
                                self.settings_manager,
                                self.test_manager
                            )
                        elif section_id == 'chambers':
                            section = section_class(
                                self.content_frame,
                                self.settings_manager,
                                self.test_manager
                            )
                        elif section_id == 'diagnostics':
                            section = section_class(
                                self.content_frame,
                                self.test_manager
                            )
                        elif section_id == 'history':
                            section = section_class(
                                self.content_frame,
                                self.test_manager
                            )
                        elif section_id == 'export':
                            section = section_class(
                                self.content_frame,
                                self.test_manager
                            )
                        elif section_id == 'users':
                            section = section_class(
                                self.content_frame,
                                self.role_manager
                            )
                        else:
                            self.logger.error(f"Unsupported section ID: {section_id}")
                            return None
                            
                        # Mark as loaded and store weak reference
                        self.section_config[section_id]['loaded'] = True
                        self.section_refs[section_id] = weakref.ref(section)
                        return section
                    except Exception as e:
                        self.logger.error(f"Error creating section {section_id}: {e}")
        
        return None
    
    def _load_section_class(self, section_id: str):
        """
        Dynamically import and load a section class on demand.
        
        Args:
            section_id: ID of the section to load
        """
        try:
            if section_id == 'general':
                from multi_chamber_test.ui.settings.general_section import GeneralSection
                self.section_config[section_id]['class'] = GeneralSection
            elif section_id == 'chambers':
                from multi_chamber_test.ui.settings.chamber_section import ChamberSection
                self.section_config[section_id]['class'] = ChamberSection
            elif section_id == 'diagnostics':
                from multi_chamber_test.ui.settings.diagnostics_section import DiagnosticsSection
                self.section_config[section_id]['class'] = DiagnosticsSection
            elif section_id == 'history':
                from multi_chamber_test.ui.settings.history_section import HistorySection
                self.section_config[section_id]['class'] = HistorySection
            elif section_id == 'export':
                from multi_chamber_test.ui.settings.export_section import ExportSection
                self.section_config[section_id]['class'] = ExportSection
            elif section_id == 'users':
                from multi_chamber_test.ui.settings.user_section import UserSection
                self.section_config[section_id]['class'] = UserSection
            else:
                self.logger.error(f"Unknown section ID for loading: {section_id}")
        except ImportError as e:
            self.logger.error(f"Could not import section {section_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error loading section class {section_id}: {e}")
    
    def _start_monitoring(self):
        """Start a background thread for monitoring data changes."""
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            return  # Already running
            
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitor_data_changes,
            daemon=True,
            name="SettingsMonitorThread"
        )
        self._monitoring_thread.start()
    
    def _stop_monitoring(self):
        """Stop the background monitoring thread."""
        self._monitoring_active = False
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=1.0)
            self._monitoring_thread = None
    
    def _monitor_data_changes(self):
        """Background thread for monitoring data changes."""
        last_update = time.time()
        
        while self._monitoring_active:
            try:
                # Check at most once per second
                now = time.time()
                if now - last_update < 1.0:
                    time.sleep(0.1)
                    continue
                    
                last_update = now
                
                # Handle events that require notification to active section
                active_section = self._get_section(self.current_section) if self.current_section else None
                
                if active_section and hasattr(active_section, 'update_from_monitoring'):
                    # Schedule the update in the main thread
                    self._schedule_ui_update(
                        lambda section=active_section: section.update_from_monitoring()
                    )
                
                # Sleep between checks
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
                time.sleep(1.0)  # Longer sleep on error
    
    def _schedule_ui_update(self, update_func: Callable):
        """
        Schedule a UI update to run in the main thread.
        
        Args:
            update_func: Function to run for the update
        """
        with self._ui_update_lock:
            self._ui_update_queue.append(update_func)
            
            # Schedule processing if not already scheduled
            if not self._ui_update_scheduled:
                self.parent.after(10, self._process_ui_updates)
                self._ui_update_scheduled = True
    
    def _process_ui_updates(self):
        """Process pending UI updates in the main thread."""
        with self._ui_update_lock:
            # Get all updates to process
            updates = self._ui_update_queue.copy()
            self._ui_update_queue.clear()
            self._ui_update_scheduled = False
        
        # Process updates outside the lock
        for update_func in updates:
            try:
                update_func()
            except Exception as e:
                self.logger.error(f"Error processing UI update: {e}")
        
        # If more updates were added during processing, schedule again
        with self._ui_update_lock:
            if self._ui_update_queue and not self._ui_update_scheduled:
                self.parent.after(10, self._process_ui_updates)
                self._ui_update_scheduled = True
    
    def _on_destroy(self, event):
        """Handle cleanup when the tab is destroyed."""
        # Only respond to our own destruction
        if event.widget == self.parent:
            self.logger.debug("Cleaning up SettingsTab resources")
            
            # Stop background monitoring
            self._stop_monitoring()
            
            # Clear all references
            for section_id in list(self.section_refs.keys()):
                self.section_refs[section_id] = None
                
            self.section_refs.clear()
            self.sections.clear()
    
    def on_tab_selected(self):
        """Called when this tab is selected."""
        # Wake up monitoring if it's not running
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._start_monitoring()
            
        # Update the current section if there is one
        if self.current_section:
            section = self._get_section(self.current_section)
            if section:
                self._schedule_ui_update(lambda section=section: section.on_selected())
    
    def on_tab_deselected(self):
        """Called when user switches away from this tab."""
        # Notify current section if needed
        prevent_switch = False
        
        if self.current_section:
            section = self._get_section(self.current_section)
            if section:
                result = section.on_deselected()
                if result is False:
                    # Prevent tab switching if section requests it
                    prevent_switch = True
        
        # Pause monitoring if we're actually switching
        if not prevent_switch:
            self._stop_monitoring()
            
        return not prevent_switch  # Return True to allow switching, False to prevent
    
    def cleanup(self):
        """Perform any cleanup operations before app shutdown."""
        self._stop_monitoring()
        
        # Let all sections clean up
        for section_id in list(self.section_refs.keys()):
            section = self.section_refs[section_id]()
            if section and hasattr(section, 'cleanup'):
                try:
                    section.cleanup()
                except Exception as e:
                    self.logger.error(f"Error cleaning up section {section_id}: {e}")
                    
        # Clear all references
        self.section_refs.clear()
        self.sections.clear()