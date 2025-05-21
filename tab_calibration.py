#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Calibration Tab module for the Multi-Chamber Test application.

This module provides the CalibrationTab class that implements the calibration
interface, providing functionality to calibrate pressure sensors for accurate readings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import time
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
import math

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS, UI_DIMENSIONS, CALIBRATION_POINTS
from multi_chamber_test.core.calibration_manager import CalibrationManager
from multi_chamber_test.core.roles import has_access
from multi_chamber_test.hardware.valve_controller import ValveController
from multi_chamber_test.hardware.pressure_sensor import PressureSensor
from multi_chamber_test.ui.password_dialog import PasswordDialog


class CalibrationTab:
    """
    Calibration interface tab.
    
    This class implements the calibration screen with chamber selection,
    calibration point management, and calibration execution controls.
    It provides a user-friendly interface to calibrate the pressure sensors
    for accurate measurements.
    """
    
    def __init__(self, parent, calibration_manager: CalibrationManager, 
                 valve_controller: ValveController, pressure_sensor: PressureSensor):
        """
        Initialize the CalibrationTab with the required components.
        
        Args:
            parent: Parent widget (typically a Frame in main_window.py)
            calibration_manager: CalibrationManager for calibration control
            valve_controller: ValveController for valve operations
            pressure_sensor: PressureSensor for readings
        """
        self.logger = logging.getLogger('CalibrationTab')
        self._setup_logger()
        
        self.parent = parent
        self.calibration_manager = calibration_manager
        self.valve_controller = valve_controller
        self.pressure_sensor = pressure_sensor
        
        # Store colors for easy access
        self.colors = UI_COLORS
        
        # Calibration state variables
        self.current_chamber = tk.IntVar(value=0)  # 0-2 for chamber selection
        self.current_point_index = 0
        self.calibration_points = []
        self.calibration_ongoing = False
        self.chamber_pressure = tk.DoubleVar(value=0.0)  # Current pressure
        self.calibration_target_pressures = CALIBRATION_POINTS
        
        # Setup TTK styles
        self._setup_styles()
        
        # Main container frame
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create UI components
        self.create_header_section()
        self.create_calibration_section()
        self.create_calibration_points_section()
        self.create_calibration_history_section()
        self.create_action_buttons()
        
        # Start pressure monitoring for the selected chamber
        self._start_pressure_monitoring()
    
    def _setup_logger(self):
        """Configure logging for the calibration tab."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _setup_styles(self):
        """Setup TTK styles for the interface."""
        style = ttk.Style()
        
        # Card frame style
        style.configure(
            'Card.TFrame',
            background=UI_COLORS['BACKGROUND'],
            relief='solid',
            borderwidth=1,
            bordercolor=UI_COLORS['BORDER']
        )
        
        # Section styles
        style.configure(
            'Section.TFrame',
            background=UI_COLORS['BACKGROUND'],
            padding=15
        )
        
        # Text styles
        style.configure(
            'CardTitle.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['HEADER']
        )
        style.configure(
            'CardText.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['LABEL']
        )
        style.configure(
            'Value.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['VALUE']
        )
        style.configure(
            'Reading.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['VALUE']
        )
        style.configure(
            'Alert.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['WARNING'],
            font=UI_FONTS['LABEL']
        )
        style.configure(
            'Success.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['SUCCESS'],
            font=UI_FONTS['LABEL']
        )
        style.configure(
            'Error.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['ERROR'],
            font=UI_FONTS['LABEL']
        )
        
        # Button styles
        style.configure(
            'Action.TButton',
            font=UI_FONTS['BUTTON'],
            padding=10
        )
        style.configure(
            'Secondary.TButton',
            font=UI_FONTS['BUTTON'],
            padding=10
        )
        style.configure(
            'Warning.TButton',
            font=UI_FONTS['BUTTON'],
            padding=10
        )
    
    def create_header_section(self):
        """Create the header section with title and chamber selection."""
        header_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title and description
        title_frame = ttk.Frame(header_frame, padding=15)
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame,
            text="Pressure Sensor Calibration",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W)
        
        ttk.Label(
            title_frame,
            text="Calibrate chamber pressure sensors for accurate readings.",
            style='CardText.TLabel'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Chamber selection frame
        chamber_frame = ttk.Frame(header_frame, padding=(15, 0, 15, 15))
        chamber_frame.pack(fill=tk.X)
        
        ttk.Label(
            chamber_frame,
            text="Select Chamber:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # Chamber radio buttons
        for i in range(3):
            ttk.Radiobutton(
                chamber_frame,
                text=f"Chamber {i+1}",
                variable=self.current_chamber,
                value=i,
                command=self.on_chamber_changed
            ).pack(side=tk.LEFT, padx=(10, 0))
    
    def create_calibration_section(self):
        """Create the main calibration controls and display section."""
        calibration_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        calibration_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Title
        ttk.Label(
            calibration_frame,
            text="Calibration Control",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Main content
        content_frame = ttk.Frame(calibration_frame, padding=15)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Current pressure display
        pressure_frame = ttk.Frame(content_frame)
        pressure_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            pressure_frame,
            text="Current Pressure:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        self.pressure_display = ttk.Label(
            pressure_frame,
            textvariable=self.chamber_pressure,
            style='Reading.TLabel'
        )
        self.pressure_display.pack(side=tk.LEFT, padx=(10, 5))
        
        ttk.Label(
            pressure_frame,
            text="mbar",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # Status message
        status_frame = ttk.Frame(content_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(
            status_frame,
            text="Select a chamber and press 'Start Calibration' to begin.",
            style='CardText.TLabel',
            wraplength=600
        )
        self.status_label.pack(anchor=tk.W)
        
        # Manual control buttons (initially disabled)
        control_frame = ttk.Frame(content_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            control_frame,
            text="Manual Controls:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # Fill button
        self.fill_button = ttk.Button(
            control_frame,
            text="Fill",
            style='Secondary.TButton',
            command=lambda: self.manual_control('fill'),
            state='disabled'
        )
        self.fill_button.pack(side=tk.LEFT, padx=(10, 5))
        
        # Pulse Fill button
        self.pulse_fill_button = ttk.Button(
            control_frame,
            text="Pulse Fill",
            style='Secondary.TButton',
            command=lambda: self.manual_control('pulse_fill'),
            state='disabled'
        )
        self.pulse_fill_button.pack(side=tk.LEFT, padx=5)
        
        # Pulse Vent button
        self.pulse_vent_button = ttk.Button(
            control_frame,
            text="Pulse Vent",
            style='Secondary.TButton',
            command=lambda: self.manual_control('pulse_vent'),
            state='disabled'
        )
        self.pulse_vent_button.pack(side=tk.LEFT, padx=5)
        
        # Empty button
        self.empty_button = ttk.Button(
            control_frame,
            text="Empty",
            style='Secondary.TButton',
            command=lambda: self.manual_control('empty'),
            state='disabled'
        )
        self.empty_button.pack(side=tk.LEFT, padx=5)
        
        # Stop button
        self.stop_button = ttk.Button(
            control_frame,
            text="Stop",
            style='Secondary.TButton',
            command=lambda: self.manual_control('stop'),
            state='disabled'
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
    
    def create_calibration_points_section(self):
        """Create the calibration points list section."""
        points_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        points_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        ttk.Label(
            points_frame,
            text="Calibration Points",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Points content
        content_frame = ttk.Frame(points_frame, padding=15)
        content_frame.pack(fill=tk.X)
        
        # Headers
        headers_frame = ttk.Frame(content_frame)
        headers_frame.pack(fill=tk.X, pady=(0, 5))
        
        header_texts = ["Point", "Target (mbar)", "Voltage (V)", "Status"]
        header_widths = [80, 120, 120, 200]
        
        for i, (text, width) in enumerate(zip(header_texts, header_widths)):
            header_label = ttk.Label(
                headers_frame,
                text=text,
                style='CardText.TLabel',
                width=width // 10  # Approximate character width
            )
            header_label.grid(row=0, column=i, padx=(0 if i == 0 else 10, 0))
        
        # Points list (will be populated during calibration)
        self.points_frame = ttk.Frame(content_frame)
        self.points_frame.pack(fill=tk.X)
        
        # Create empty rows for calibration points
        self.point_labels = []
        for i, target in enumerate(self.calibration_target_pressures):
            row_frame = ttk.Frame(self.points_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            point_number = ttk.Label(
                row_frame,
                text=str(i + 1),
                style='CardText.TLabel',
                width=header_widths[0] // 10
            )
            point_number.grid(row=0, column=0)
            
            target_label = ttk.Label(
                row_frame,
                text=str(target),
                style='CardText.TLabel',
                width=header_widths[1] // 10
            )
            target_label.grid(row=0, column=1, padx=10)
            
            voltage_label = ttk.Label(
                row_frame,
                text="--",
                style='CardText.TLabel',
                width=header_widths[2] // 10
            )
            voltage_label.grid(row=0, column=2, padx=10)
            
            status_label = ttk.Label(
                row_frame,
                text="Not Started",
                style='CardText.TLabel',
                width=header_widths[3] // 10
            )
            status_label.grid(row=0, column=3, padx=10)
            
            self.point_labels.append([point_number, target_label, voltage_label, status_label])
        
        # Record Point button (initially disabled)
        self.record_point_button = ttk.Button(
            content_frame,
            text="Record Current Point",
            style='Action.TButton',
            command=self.record_calibration_point,
            state='disabled'
        )
        self.record_point_button.pack(anchor=tk.E, pady=(10, 0))
    
    def create_calibration_history_section(self):
        """Create the calibration history section."""
        history_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        history_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        ttk.Label(
            history_frame,
            text="Calibration History",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # History content
        self.history_content = ttk.Frame(history_frame, padding=15)
        self.history_content.pack(fill=tk.X)
        
        # History will be populated when a chamber is selected
        ttk.Label(
            self.history_content,
            text="Select a chamber to view calibration history.",
            style='CardText.TLabel'
        ).pack(anchor=tk.W)
    
    def create_action_buttons(self):
        """Create the action buttons at the bottom of the tab."""
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Start Calibration button
        self.start_button = ttk.Button(
            buttons_frame,
            text="Start Calibration",
            style='Action.TButton',
            command=self.start_calibration,
            width=20
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Complete Calibration button (initially disabled)
        self.complete_button = ttk.Button(
            buttons_frame,
            text="Complete Calibration",
            style='Action.TButton',
            command=self.complete_calibration,
            state='disabled',
            width=20
        )
        self.complete_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Abort Calibration button (initially disabled)
        self.abort_button = ttk.Button(
            buttons_frame,
            text="Abort Calibration",
            style='Warning.TButton',
            command=self.abort_calibration,
            state='disabled',
            width=20
        )
        self.abort_button.pack(side=tk.LEFT)
    
    def on_chamber_changed(self):
        """Handle chamber selection change."""
        chamber_index = self.current_chamber.get()
        self.logger.info(f"Selected chamber: {chamber_index + 1}")
        
        # Update history display
        self.update_calibration_history(chamber_index)
        
        # Reset calibration UI if calibration is not ongoing
        if not self.calibration_ongoing:
            self.reset_calibration_ui()
    
    def _start_pressure_monitoring(self):
        """Start a background thread to monitor pressure."""
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_pressure,
            daemon=True
        )
        self.monitoring_thread.start()
    
    def _monitor_pressure(self):
        """Background thread function to continuously monitor pressure."""
        while self.monitoring_active:
            try:
                chamber_index = self.current_chamber.get()
                
                # Read pressure from the selected chamber
                pressure = self.pressure_sensor.read_pressure(chamber_index)
                
                if pressure is not None:
                    # Update pressure variable (for display)
                    self.chamber_pressure.set(round(pressure, 1))
                
                # Don't update too rapidly - 100ms is plenty fast
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring pressure: {e}")
                time.sleep(1.0)  # Longer delay on error
    
    def update_calibration_history(self, chamber_index: int):
        """
        Update the calibration history display for a chamber.
        
        Args:
            chamber_index: Index of the chamber (0-2)
        """
        # Clear existing history content
        for widget in self.history_content.winfo_children():
            widget.destroy()
        
        # Get calibration history from the manager
        history = self.calibration_manager.get_calibration_history(chamber_index)
        
        if not history:
            # No history available
            ttk.Label(
                self.history_content,
                text=f"No calibration history available for Chamber {chamber_index + 1}.",
                style='CardText.TLabel'
            ).pack(anchor=tk.W)
            return
        
        # Display most recent calibration first
        latest = history[0]
        
        # Latest calibration section
        latest_frame = ttk.Frame(self.history_content)
        latest_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            latest_frame,
            text="Current Calibration:",
            style='CardText.TLabel',
            font=UI_FONTS['SUBHEADER']
        ).pack(anchor=tk.W)
        
        # Format date for display
        date_str = latest.calibration_date.strftime("%Y-%m-%d %H:%M:%S")
        
        ttk.Label(
            latest_frame,
            text=f"Date: {date_str}",
            style='CardText.TLabel'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        ttk.Label(
            latest_frame,
            text=f"Multiplier: {latest.multiplier:.4f}",
            style='CardText.TLabel'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        ttk.Label(
            latest_frame,
            text=f"Offset: {latest.offset:.4f}",
            style='CardText.TLabel'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        ttk.Label(
            latest_frame,
            text=f"R-squared: {latest.r_squared:.4f}",
            style='CardText.TLabel'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        # Additional calibration history if available
        if len(history) > 1:
            history_label = ttk.Label(
                self.history_content,
                text="Previous Calibrations:",
                style='CardText.TLabel',
                font=UI_FONTS['SUBHEADER']
            )
            history_label.pack(anchor=tk.W, pady=(10, 5))
            
            # Create a simple table for history
            for i, cal in enumerate(history[1:5]):  # Show up to 5 previous entries
                date_str = cal.calibration_date.strftime("%Y-%m-%d %H:%M:%S")
                ttk.Label(
                    self.history_content,
                    text=f"{date_str} - Mult: {cal.multiplier:.4f}, Offset: {cal.offset:.4f}",
                    style='CardText.TLabel'
                ).pack(anchor=tk.W, padx=(20, 0))
    
    def reset_calibration_ui(self):
        """Reset the calibration UI to its initial state."""
        # Reset calibration points display
        for i, label_row in enumerate(self.point_labels):
            label_row[2].config(text="--")  # Reset voltage
            label_row[3].config(text="Not Started")  # Reset status
            
        # Reset status message
        self.status_label.config(
            text="Select a chamber and press 'Start Calibration' to begin.",
            style='CardText.TLabel'
        )
        
        # Reset buttons
        self.record_point_button.config(state='disabled')
        self.complete_button.config(state='disabled')
        self.abort_button.config(state='disabled')
        self.fill_button.config(state='disabled')
        self.empty_button.config(state='disabled')
        self.pulse_fill_button.config(state='disabled')
        self.pulse_vent_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.start_button.config(state='normal')
    
    def show_auth_dialog(self, min_role: str, on_success: Optional[Callable] = None):
        """
        Show authentication dialog for access to protected features.
        
        Args:
            min_role: Minimum role required
            on_success: Function to call on successful authentication
        """
        def auth_success():
            # Call success callback if provided
            if on_success:
                on_success()
        
        # Show password dialog
        PasswordDialog(
            self.parent,
            min_role,
            on_success=auth_success
        )
    
    def start_calibration(self):
        """Start the calibration process for the selected chamber."""
        # Check access rights first
        if not has_access("MAINTENANCE"):
            self.show_auth_dialog("MAINTENANCE", on_success=self.start_calibration)
            return
        
        chamber_index = self.current_chamber.get()
        
        # Start calibration using the calibration manager
        success = self.calibration_manager.start_calibration(chamber_index)
        
        if not success:
            messagebox.showerror(
                "Calibration Error",
                f"Failed to start calibration for Chamber {chamber_index + 1}."
            )
            return
        
        # Update UI state
        self.calibration_ongoing = True
        self.calibration_points = []
        self.current_point_index = 0
        
        # Update status message
        self.status_label.config(
            text="Emptying chamber to prepare for calibration...",
            style='Alert.TLabel'
        )
        
        # Update buttons
        self.start_button.config(state='disabled')
        self.abort_button.config(state='normal')
        self.fill_button.config(state='disabled')
        self.empty_button.config(state='disabled')
        self.pulse_fill_button.config(state='disabled')
        self.pulse_vent_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        
        # Schedule UI update after emptying completes (approx. 10 seconds)
        self.parent.after(10000, self.prepare_first_calibration_point)
    
    def prepare_first_calibration_point(self):
        """Prepare for the first calibration point after emptying."""
        if not self.calibration_ongoing:
            return
        
        # Enable manual controls
        self.fill_button.config(state='normal')
        self.empty_button.config(state='normal')
        self.pulse_fill_button.config(state='normal')
        self.pulse_vent_button.config(state='normal')
        self.stop_button.config(state='normal')
        
        # Enable record button
        self.record_point_button.config(state='normal')
        
        # Update status for first point (zero point)
        target = self.calibration_target_pressures[0]
        self.status_label.config(
            text=f"Record the first calibration point at {target} mbar. Ensure pressure is stable before recording.",
            style='CardText.TLabel'
        )
        
        # Update calibration point status
        self.point_labels[0][3].config(text="Ready to Record")
    
    def record_calibration_point(self):
        """Record the current calibration point."""
        if not self.calibration_ongoing:
            return
        
        # Get current chamber
        chamber_index = self.current_chamber.get()
        
        # Record point using calibration manager
        success, pressure, voltage = self.calibration_manager.record_calibration_point()
        
        if not success:
            # Check if pressure is too far from target
            target = self.calibration_target_pressures[self.current_point_index]
            current_pressure = self.chamber_pressure.get()
            
            if abs(current_pressure - target) > 20:
                messagebox.showwarning(
                    "Pressure Warning",
                    f"Current pressure ({current_pressure:.1f} mbar) is too far from target ({target} mbar).\n\n"
                    f"Please adjust pressure to be closer to the target value."
                )
            else:
                messagebox.showerror(
                    "Recording Error",
                    "Failed to record calibration point. Ensure pressure is stable."
                )
            return
        
        # Update calibration point display
        point_row = self.point_labels[self.current_point_index]
        point_row[2].config(text=f"{voltage:.4f}")
        point_row[3].config(text="Recorded", foreground=self.colors['SUCCESS'])
        
        # Move to next point or complete calibration
        self.current_point_index += 1
        
        if self.current_point_index < len(self.calibration_target_pressures):
            # Prepare for next point
            target = self.calibration_target_pressures[self.current_point_index]
            self.status_label.config(
                text=f"Adjust pressure to {target} mbar for the next calibration point.",
                style='CardText.TLabel'
            )
            self.point_labels[self.current_point_index][3].config(text="Ready to Record")
        else:
            # All points recorded
            self.status_label.config(
                text="All calibration points recorded. Press 'Complete Calibration' to finish.",
                style='Success.TLabel'
            )
            self.complete_button.config(state='normal')
    
    def complete_calibration(self):
        """Complete the calibration process."""
        if not self.calibration_ongoing:
            return
        
        # Get current chamber
        chamber_index = self.current_chamber.get()
        
        # Complete calibration using manager
        success = self.calibration_manager.complete_calibration()
        
        if not success:
            messagebox.showerror(
                "Calibration Error",
                "Failed to complete calibration. Please check the calibration points and try again."
            )
            return
        
        # Update UI
        self.calibration_ongoing = False
        
        # Update status message
        self.status_label.config(
            text=f"Calibration for Chamber {chamber_index + 1} completed successfully.",
            style='Success.TLabel'
        )
        
        # Reset button states
        self.reset_calibration_ui()
        
        # Update calibration history
        self.update_calibration_history(chamber_index)
        
        # Show success message
        messagebox.showinfo(
            "Calibration Complete",
            f"Calibration for Chamber {chamber_index + 1} has been completed successfully."
        )
    
    def abort_calibration(self):
        """Abort the current calibration process."""
        if not self.calibration_ongoing:
            return
        
        # Get current chamber
        chamber_index = self.current_chamber.get()
        
        if messagebox.askyesno(
            "Confirm Abort",
            "Are you sure you want to abort the current calibration? All progress will be lost."
        ):
            # Abort calibration using manager
            success = self.calibration_manager.abort_calibration()
            
            # Update UI regardless of success
            self.calibration_ongoing = False
            
            # Update status message
            self.status_label.config(
                text="Calibration aborted.",
                style='Error.TLabel'
            )
            
            # Reset button states
            self.reset_calibration_ui()
            
            # Show message
            messagebox.showinfo(
                "Calibration Aborted",
                f"Calibration for Chamber {chamber_index + 1} has been aborted."
            )
    
    def manual_control(self, action: str):
        """
        Perform manual control actions on the current chamber.
        
        Args:
            action: Control action ('fill', 'empty', 'pulse_fill', 'pulse_vent', 'stop')
        """
        if not self.calibration_ongoing:
            return
        
        chamber_index = self.current_chamber.get()
        
        try:
            if action == 'fill':
                # Start filling the chamber
                self.valve_controller.fill_chamber(chamber_index)
                self.status_label.config(
                    text="Filling chamber...",
                    style='Alert.TLabel'
                )
                
            elif action == 'empty':
                # Start emptying the chamber
                self.valve_controller.empty_chamber(chamber_index)
                self.status_label.config(
                    text="Emptying chamber...",
                    style='Alert.TLabel'
                )
                
            elif action == 'pulse_fill':
                # Pulse the inlet valve briefly
                self.valve_controller.pulse_valve(chamber_index, 'inlet', 0.1)
                
            elif action == 'pulse_vent':
                # Pulse the outlet valve briefly
                self.valve_controller.pulse_valve(chamber_index, 'outlet', 0.1)
                
            elif action == 'stop':
                # Stop all valve actions
                self.valve_controller.stop_chamber(chamber_index)
                self.status_label.config(
                    text=f"Adjust pressure to {self.calibration_target_pressures[self.current_point_index]} mbar for calibration.",
                    style='CardText.TLabel'
                )
                
        except Exception as e:
            self.logger.error(f"Error in manual control: {e}")
            messagebox.showerror(
                "Control Error",
                f"Failed to perform {action} action: {str(e)}"
            )
            
            # Try to close all valves on error
            try:
                self.valve_controller.stop_chamber(chamber_index)
            except:
                pass
    
    def draw_pressure_gauge(self, canvas, pressure: float, target: float = None):
        """
        Draw a pressure gauge visualization on a canvas.
        
        Args:
            canvas: Canvas widget to draw on
            pressure: Current pressure reading
            target: Target pressure (optional)
        """
        # Clear canvas
        canvas.delete("all")
        
        # Get canvas dimensions
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        # Use default values if not yet packed
        if width < 50:
            width = 200
        if height < 50:
            height = 200
        
        # Define gauge dimensions
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 2 - 10
        inner_radius = radius - 20
        max_pressure = 600  # Maximum pressure for gauge
        
        # Draw background circle
        canvas.create_oval(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            fill=UI_COLORS['BACKGROUND'],
            outline=UI_COLORS['BORDER'],
            width=2
        )
        
        # Draw scale arc
        canvas.create_arc(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            start=150, extent=-300,  # Start at top left, sweep 300 degrees clockwise
            style="arc",
            outline=UI_COLORS['BORDER'],
            width=5
        )
        
        # Draw scale markings
        for i in range(0, max_pressure + 1, 100):
            angle = 150 - (i * 300 / max_pressure)
            angle_rad = math.radians(angle)
            cos_val = math.cos(angle_rad)
            sin_val = math.sin(angle_rad)
            
            # Draw tick mark
            tick_start = radius - 10
            tick_end = radius
            canvas.create_line(
                center_x + tick_start * cos_val, center_y - tick_start * sin_val,
                center_x + tick_end * cos_val, center_y - tick_end * sin_val,
                fill=UI_COLORS['TEXT_PRIMARY'],
                width=2
            )
            
            # Draw label
            label_radius = radius - 25
            canvas.create_text(
                center_x + label_radius * cos_val, center_y - label_radius * sin_val,
                text=str(i),
                fill=UI_COLORS['TEXT_PRIMARY'],
                font=("Helvetica", 8)
            )
        
        # Draw target marker if provided
        if target is not None:
            target_angle = 150 - (target * 300 / max_pressure)
            target_angle_rad = math.radians(target_angle)
            cos_val = math.cos(target_angle_rad)
            sin_val = math.sin(target_angle_rad)
            
            # Draw target line
            canvas.create_line(
                center_x + (radius - 40) * cos_val, center_y - (radius - 40) * sin_val,
                center_x + (radius + 5) * cos_val, center_y - (radius + 5) * sin_val,
                fill=UI_COLORS['SUCCESS'],
                width=3,
                arrow=tk.LAST
            )
        
        # Draw pressure needle
        if pressure > 0:
            pressure_angle = 150 - (min(pressure, max_pressure) * 300 / max_pressure)
            pressure_angle_rad = math.radians(pressure_angle)
            cos_val = math.cos(pressure_angle_rad)
            sin_val = math.sin(pressure_angle_rad)
            
            # Determine color based on proximity to target
            if target is not None and abs(pressure - target) <= 5:
                needle_color = UI_COLORS['SUCCESS']
            else:
                needle_color = UI_COLORS['PRIMARY']
            
            # Draw needle
            canvas.create_line(
                center_x, center_y,
                center_x + inner_radius * cos_val, center_y - inner_radius * sin_val,
                fill=needle_color,
                width=3
            )
        
        # Draw center circle
        canvas.create_oval(
            center_x - 10, center_y - 10,
            center_x + 10, center_y + 10,
            fill=UI_COLORS['PRIMARY'],
            outline=UI_COLORS['BORDER']
        )
        
        # Draw pressure text
        canvas.create_text(
            center_x, center_y + radius // 2,
            text=f"{pressure:.1f} mbar",
            fill=UI_COLORS['PRIMARY'],
            font=("Helvetica", 12, "bold")
        )
    
    def create_quick_calibration_section(self):
        """Create a quick calibration option for single-point offset adjustment."""
        quick_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        quick_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        ttk.Label(
            quick_frame,
            text="Quick Offset Calibration",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Content
        content_frame = ttk.Frame(quick_frame, padding=15)
        content_frame.pack(fill=tk.X)
        
        ttk.Label(
            content_frame,
            text="Quickly adjust the zero offset for a chamber without a full calibration.",
            style='CardText.TLabel'
        ).pack(anchor=tk.W)
        
        # Chamber selection and offset adjustment
        adjust_frame = ttk.Frame(content_frame)
        adjust_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            adjust_frame,
            text="Chamber Offset:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # Offset value display
        self.offset_value = ttk.Label(
            adjust_frame,
            text="0.0 mbar",
            style='Value.TLabel'
        )
        self.offset_value.pack(side=tk.LEFT, padx=10)
        
        # Adjustment buttons
        ttk.Button(
            adjust_frame,
            text="-5",
            command=lambda: self.adjust_offset(-5)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            adjust_frame,
            text="-1",
            command=lambda: self.adjust_offset(-1)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            adjust_frame,
            text="+1",
            command=lambda: self.adjust_offset(1)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            adjust_frame,
            text="+5",
            command=lambda: self.adjust_offset(5)
        ).pack(side=tk.LEFT, padx=5)
        
        # Apply button
        ttk.Button(
            content_frame,
            text="Apply Offset",
            style='Action.TButton',
            command=self.apply_offset
        ).pack(side=tk.LEFT, pady=(10, 0))
    
    def adjust_offset(self, amount: int):
        """
        Adjust the offset value by the specified amount.
        
        Args:
            amount: Amount to adjust by (mbar)
        """
        # Check for maintenance access
        if not has_access("MAINTENANCE"):
            self.show_auth_dialog("MAINTENANCE", on_success=lambda: self.adjust_offset(amount))
            return
        
        # Extract current offset value
        current_text = self.offset_value.cget("text")
        try:
            current_offset = float(current_text.split()[0])
        except ValueError:
            current_offset = 0.0
        
        # Calculate new offset
        new_offset = current_offset + amount
        
        # Update display
        self.offset_value.config(text=f"{new_offset:.1f} mbar")
    
    def apply_offset(self):
        """Apply the current offset value to the selected chamber."""
        # Check for maintenance access
        if not has_access("MAINTENANCE"):
            self.show_auth_dialog("MAINTENANCE", on_success=self.apply_offset)
            return
        
        chamber_index = self.current_chamber.get()
        
        # Extract offset value
        current_text = self.offset_value.cget("text")
        try:
            offset = float(current_text.split()[0])
        except ValueError:
            messagebox.showerror("Error", "Invalid offset value")
            return
        
        # Apply offset through pressure sensor
        try:
            self.pressure_sensor.set_chamber_offset(chamber_index, offset)
            messagebox.showinfo(
                "Offset Applied",
                f"Offset of {offset:.1f} mbar applied to Chamber {chamber_index + 1}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply offset: {str(e)}")
    
    def on_tab_selected(self):
        """Called when this tab is selected."""
        # Update the calibration history for the current chamber
        chamber_index = self.current_chamber.get()
        self.update_calibration_history(chamber_index)
        
        # Reset UI if not in calibration
        if not self.calibration_ongoing:
            self.reset_calibration_ui()
    
    def on_tab_deselected(self):
        """Called when user switches away from this tab."""
        # If calibration is in progress, ask for confirmation
        if self.calibration_ongoing:
            if messagebox.askyesno(
                "Calibration In Progress",
                "Calibration is still in progress. Leaving this tab will abort the calibration. Continue?"
            ):
                # Abort calibration
                self.abort_calibration()
            else:
                # Stay on this tab - returning False would prevent tab change
                return False
        return True
    
    def cleanup(self):
        """Clean up resources when closing the application."""
        # Stop pressure monitoring
        self.monitoring_active = False
        if hasattr(self, 'monitoring_thread') and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1.0)
        
        # Abort any ongoing calibration
        if self.calibration_ongoing:
            self.calibration_manager.abort_calibration()
