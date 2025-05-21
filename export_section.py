#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export Settings section for the Multi-Chamber Test application.

This module provides the ExportSection class for managing data export to USB
drives, with automatic detection and real-time status monitoring.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
from typing import Callable, Optional, Dict, Any

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS
from multi_chamber_test.core.test_manager import TestManager
from multi_chamber_test.ui.settings.base_section import BaseSection


class ExportSection(BaseSection):
    """
    Data Export settings section for exporting test results.
    
    This section allows:
    - Automatic USB drive detection
    - Exporting all test results
    - Exporting last test result
    
    Implements real-time USB monitoring and thread-safe updates.
    """
    
    def __init__(self, parent, test_manager: TestManager):
        """
        Initialize the export settings section.
        
        Args:
            parent: Parent widget
            test_manager: Test manager for accessing test data
        """
        # Store manager reference
        self.test_manager = test_manager
        
        # Create file exporter utility (mock implementation)
        self.file_exporter = MockFileExporter()
        
        # State variables
        self.usb_connected = False
        self.usb_detection_active = False
        self.usb_detection_thread = None
        
        # Detection timing parameters
        self.detection_interval = 2.0  # Check USB every 2 seconds
        self.detection_last_change = 0
        
        # Call base class constructor
        super().__init__(parent)
    
    def create_widgets(self):
        """Create UI widgets for the export settings section."""
        # Section title with icon
        title_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(
            title_frame,
            text="?? Data Export",
            style='ContentTitle.TLabel'
        ).pack(anchor=tk.W)
        
        # Status message about automatic detection
        status_message = ttk.Label(
            self.content_frame,
            text="USB drives are detected automatically when connected.",
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray'),
            background=UI_COLORS.get('BACKGROUND', 'white')
        )
        status_message.pack(anchor=tk.W, pady=(0, 20))
        
        # Create export cards
        self.create_usb_status_card()
        self.create_export_options_card()
        
        # Bottom padding for aesthetics
        padding_frame = ttk.Frame(self.content_frame, height=20)
        padding_frame.pack(fill=tk.X)
    
    def create_usb_status_card(self):
        """Create the USB status card with connection monitoring."""
        # Create a styled card
        card, content = self.create_card(
            "USB Drive Status",
            "Connect a USB drive to export test results."
        )
        
        # USB status indicator
        status_frame = ttk.Frame(content, style='Card.TFrame')
        status_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            status_frame,
            text="Status:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        # USB status indicator with icon
        self.status_frame = ttk.Frame(status_frame, style='Card.TFrame')
        self.status_frame.pack(side=tk.LEFT, padx=15)
        
        self.status_icon = ttk.Label(
            self.status_frame,
            text="?",  # Default to not connected
            font=('Helvetica', 16),
            foreground=UI_COLORS.get('ERROR', 'red')
        )
        self.status_icon.pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(
            self.status_frame,
            text="Not Connected",
            font=UI_FONTS.get('VALUE', ('Helvetica', 12, 'bold')),
            foreground=UI_COLORS.get('ERROR', 'red')
        )
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Re-check button
        self.recheck_button = ttk.Button(
            status_frame,
            text="Check Again",
            command=self._check_usb_now
        )
        self.recheck_button.pack(side=tk.RIGHT)
        
        # Path display when connected
        self.path_frame = ttk.Frame(content, style='Card.TFrame')
        self.path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            self.path_frame,
            text="Mount Point:",
            font=UI_FONTS.get('LABEL', ('Helvetica', 12))
        ).pack(side=tk.LEFT)
        
        self.path_label = ttk.Label(
            self.path_frame,
            text="N/A",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
        )
        self.path_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Hide path initially
        self.path_frame.pack_forget()
    
    def create_export_options_card(self):
        """Create the export options card with export buttons."""
        # Create a styled card
        card, content = self.create_card(
            "Export Options",
            "Choose what test data to export to the USB drive."
        )
        
        # Export all results button
        export_all_frame = ttk.Frame(content, style='Card.TFrame')
        export_all_frame.pack(fill=tk.X, pady=10)
        
        self.export_all_button = ttk.Button(
            export_all_frame,
            text="Export All Test Results",
            command=self._export_all_tests,
            state='disabled'  # Disabled until USB connected
        )
        self.export_all_button.pack(side=tk.LEFT)
        
        ttk.Label(
            export_all_frame,
            text="Export complete test history to CSV file",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
        ).pack(side=tk.LEFT, padx=(15, 0))
        
        # Export last result button
        export_last_frame = ttk.Frame(content, style='Card.TFrame')
        export_last_frame.pack(fill=tk.X, pady=10)
        
        self.export_last_button = ttk.Button(
            export_last_frame,
            text="Export Last Test Result",
            command=self._export_last_test,
            state='disabled'  # Disabled until USB connected
        )
        self.export_last_button.pack(side=tk.LEFT)
        
        ttk.Label(
            export_last_frame,
            text="Export only the most recent test result",
            font=('Helvetica', 10, 'italic'),
            foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
        ).pack(side=tk.LEFT, padx=(15, 0))
    
    def _check_usb_now(self):
        """
        Perform an immediate USB check, updating the UI afterward.
        Called when the user clicks the "Check Again" button.
        """
        # Disable the button temporarily to prevent multiple clicks
        self.recheck_button.config(state='disabled')
        
        # Show checking status
        self.status_icon.config(text="?", foreground=UI_COLORS.get('PRIMARY', 'blue'))
        self.status_label.config(text="Checking...", foreground=UI_COLORS.get('PRIMARY', 'blue'))
        
        # Schedule the actual check in a separate thread
        thread = threading.Thread(
            target=self._perform_usb_check,
            daemon=True
        )
        thread.start()
    
    def _perform_usb_check(self):
        """
        Perform the actual USB check in a background thread.
        Updates the UI via the thread-safe mechanism when done.
        """
        try:
            # Check for USB connection
            is_connected = self.file_exporter.is_usb_connected()
            usb_path = self.file_exporter.find_usb_path() if is_connected else None
            
            # Schedule UI update with results
            self._schedule_ui_update(lambda: self._update_usb_status(is_connected, usb_path))
            
            # Record last detection time to avoid repeated rapid checks
            self.detection_last_change = time.time()
            
        except Exception as e:
            self.logger.error(f"Error checking USB status: {e}")
            # Update UI to show error state
            self._schedule_ui_update(lambda: self._show_usb_error())
    
    def _update_usb_status(self, is_connected: bool, usb_path: Optional[str] = None):
        """
        Update the USB status display in the UI.
        This method must only be called in the main thread.
        
        Args:
            is_connected: Whether a USB drive is connected
            usb_path: Path to the USB drive if connected
        """
        # Store current status
        old_status = self.usb_connected
        self.usb_connected = is_connected
        
        # Update UI based on connection status
        if is_connected:
            self.status_icon.config(text="?", foreground=UI_COLORS.get('SUCCESS', 'green'))
            self.status_label.config(text="Connected", foreground=UI_COLORS.get('SUCCESS', 'green'))
            
            # Show path if available
            if usb_path:
                self.path_label.config(text=usb_path)
                self.path_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Enable export buttons
            self.export_all_button.config(state='normal')
            self.export_last_button.config(state='normal')
            
        else:
            self.status_icon.config(text="?", foreground=UI_COLORS.get('ERROR', 'red'))
            self.status_label.config(text="Not Connected", foreground=UI_COLORS.get('ERROR', 'red'))
            
            # Hide path
            self.path_frame.pack_forget()
            
            # Disable export buttons
            self.export_all_button.config(state='disabled')
            self.export_last_button.config(state='disabled')
        
        # Re-enable check button
        self.recheck_button.config(state='normal')
        
        # Log status change
        if old_status != is_connected:
            if is_connected:
                self.logger.info(f"USB drive connected at {usb_path}")
            else:
                self.logger.info("USB drive disconnected")
    
    def _show_usb_error(self):
        """Show an error state in the USB status display."""
        self.status_icon.config(text="?", foreground=UI_COLORS.get('WARNING', 'orange'))
        self.status_label.config(text="Detection Error", foreground=UI_COLORS.get('WARNING', 'orange'))
        self.recheck_button.config(state='normal')
        
        # Disable export buttons
        self.export_all_button.config(state='disabled')
        self.export_last_button.config(state='disabled')
    
    def _export_all_tests(self):
        """Export all test results to the USB drive."""
        if not self.usb_connected:
            messagebox.showwarning(
                "USB Not Connected", 
                "Please connect a USB drive before exporting."
            )
            return
        
        # Show a waiting cursor
        self.frame.config(cursor="watch")
        self.parent.config(cursor="watch")
        
        try:
            # Perform export in a separate thread to avoid UI freezing
            def do_export():
                try:
                    success = self.file_exporter.export_all_tests()
                    
                    # Schedule UI update
                    self._schedule_ui_update(lambda s=success: self._show_export_result(s))
                except Exception as e:
                    self.logger.error(f"Error exporting all tests: {e}")
                    self._schedule_ui_update(
                        lambda e=str(e): messagebox.showerror(
                            "Export Error", f"Failed to export test results: {e}"
                        )
                    )
                finally:
                    # Restore cursor
                    self._schedule_ui_update(lambda: self._restore_cursor())
            
            # Start export thread
            export_thread = threading.Thread(target=do_export, daemon=True)
            export_thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting export: {e}")
            messagebox.showerror("Export Error", f"Failed to start export: {e}")
            self._restore_cursor()
    
    def _export_last_test(self):
        """Export only the last test result to the USB drive."""
        if not self.usb_connected:
            messagebox.showwarning(
                "USB Not Connected", 
                "Please connect a USB drive before exporting."
            )
            return
        
        # Show a waiting cursor
        self.frame.config(cursor="watch")
        self.parent.config(cursor="watch")
        
        try:
            # Perform export in a separate thread to avoid UI freezing
            def do_export():
                try:
                    success = self.file_exporter.export_last_test()
                    
                    # Schedule UI update
                    self._schedule_ui_update(lambda s=success: self._show_export_result(s))
                except Exception as e:
                    self.logger.error(f"Error exporting last test: {e}")
                    self._schedule_ui_update(
                        lambda e=str(e): messagebox.showerror(
                            "Export Error", f"Failed to export last test result: {e}"
                        )
                    )
                finally:
                    # Restore cursor
                    self._schedule_ui_update(lambda: self._restore_cursor())
            
            # Start export thread
            export_thread = threading.Thread(target=do_export, daemon=True)
            export_thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting export: {e}")
            messagebox.showerror("Export Error", f"Failed to start export: {e}")
            self._restore_cursor()
    
    def _show_export_result(self, success: bool):
        """Show the result of the export operation."""
        if success:
            messagebox.showinfo(
                "Export Successful", 
                "Test results were successfully exported to the USB drive."
            )
        else:
            messagebox.showerror(
                "Export Failed", 
                "Failed to export test results. Please check the USB drive and try again."
            )
    
    def _restore_cursor(self):
        """Restore the normal cursor after an operation."""
        self.frame.config(cursor="")
        self.parent.config(cursor="")
    
    def _start_usb_detection(self):
        """Start the background USB detection thread."""
        if self.usb_detection_active:
            return  # Already running
            
        self.usb_detection_active = True
        
        # Create and start the detection thread
        self.usb_detection_thread = threading.Thread(
            target=self._run_usb_detection,
            daemon=True,
            name="UsbDetectionThread"
        )
        self.usb_detection_thread.start()
        
        self.logger.debug("USB detection started")
    
    def _stop_usb_detection(self):
        """Stop the background USB detection thread."""
        self.usb_detection_active = False
        
        # Thread will terminate on its own due to the flag check
        self.usb_detection_thread = None
        
        self.logger.debug("USB detection stopped")
    
    def _run_usb_detection(self):
        """Background thread function for USB detection."""
        last_check_time = 0
        last_status = None
        
        while self.usb_detection_active:
            try:
                # Only check periodically to reduce system load
                current_time = time.time()
                if current_time - last_check_time < self.detection_interval:
                    time.sleep(0.1)
                    continue
                    
                last_check_time = current_time
                
                # Skip check if we just manually checked
                if current_time - self.detection_last_change < self.detection_interval:
                    time.sleep(0.1)
                    continue
                
                # Check USB status
                is_connected = self.file_exporter.is_usb_connected()
                
                # Only update UI if status changed
                if last_status != is_connected:
                    last_status = is_connected
                    
                    # Get path if connected
                    usb_path = self.file_exporter.find_usb_path() if is_connected else None
                    
                    # Schedule UI update with results
                    self._schedule_ui_update(
                        lambda c=is_connected, p=usb_path: self._update_usb_status(c, p)
                    )
                
                # Sleep to avoid excessive CPU usage
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error in USB detection thread: {e}")
                time.sleep(1.0)  # Sleep longer on error
    
    def refresh_all(self):
        """
        Refresh all UI components to reflect current settings.
        Called when the section is shown or needs full refresh.
        """
        # Trigger an immediate USB check
        self._check_usb_now()
    
    def update_from_monitoring(self):
        """
        Update UI based on data from monitoring thread.
        This is for real-time updates that need to happen while section is visible.
        """
        # Nothing additional needed here since we have our own dedicated
        # USB detection thread that already schedules UI updates
        pass
    
    def on_selected(self):
        """Called when this section is selected or settings tab is selected."""
        # Call base class implementation first for common handling
        super().on_selected()
        
        # Start USB detection immediately
        self._start_usb_detection()
        
        # Perform initial check
        self._check_usb_now()
    
    def on_deselected(self):
        """Called when this section is deselected or settings tab is deselected."""
        # Stop USB detection to conserve resources
        self._stop_usb_detection()
        
        return True  # Allow navigation
    
    def cleanup(self):
        """Perform any cleanup operations before app shutdown."""
        # Stop USB detection thread
        self._stop_usb_detection()
        
        # Call base class cleanup
        super().cleanup()


class MockFileExporter:
    """
    Mock implementation of a file exporter for demonstration and testing.
    
    This class provides a mock implementation of USB detection and file export
    functionality when the real file exporter is not available or for testing.
    """
    
    def __init__(self):
        """Initialize the mock file exporter."""
        self.usb_connected = False
        self.usb_path = None
        self.last_check_time = 0
        self.toggle_time = 15  # Toggle connection state every 15 seconds for demo
    
    def is_usb_connected(self) -> bool:
        """
        Check if a USB drive is connected.
        
        Returns:
            True if a USB drive is connected, False otherwise
        """
        # Toggle connection state periodically for demonstration
        current_time = time.time()
        if current_time - self.last_check_time > self.toggle_time:
            self.usb_connected = not self.usb_connected
            
            if self.usb_connected:
                self.usb_path = self._get_mock_path()
            else:
                self.usb_path = None
                
            self.last_check_time = current_time
            
        return self.usb_connected
    
    def find_usb_path(self) -> Optional[str]:
        """
        Find the path to the USB drive.
        
        Returns:
            Path to USB drive or None if not connected
        """
        return self.usb_path
    
    def export_all_tests(self) -> bool:
        """
        Export all test results to the USB drive.
        
        Returns:
            True if export was successful, False otherwise
        """
        if not self.usb_connected:
            return False
            
        # Simulate export delay
        time.sleep(1.5)
        
        # Successful export
        return True
    
    def export_last_test(self) -> bool:
        """
        Export the last test result to the USB drive.
        
        Returns:
            True if export was successful, False otherwise
        """
        if not self.usb_connected:
            return False
            
        # Simulate export delay
        time.sleep(0.8)
        
        # Successful export
        return True
    
    def _get_mock_path(self) -> str:
        """
        Get a mock USB path for the current platform.
        
        Returns:
            A platform-appropriate mock USB path
        """
        import platform
        
        system = platform.system()
        if system == 'Windows':
            return "D:\\"
        elif system == 'Darwin':  # macOS
            return "/Volumes/USB_DRIVE"
        else:  # Linux and others
            return "/media/usb"