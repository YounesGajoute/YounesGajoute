#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Tab module for the Multi-Chamber Test application.

This module provides the MainTab class that implements the main testing
interface, including pressure gauges, timeline, and test controls.
"""

import tkinter as tk
from tkinter import ttk
import logging
import math
import time
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from datetime import datetime

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS, UI_DIMENSIONS, TEST_STATES, PRESSURE_DEFAULTS
from multi_chamber_test.core.test_manager import TestManager
from multi_chamber_test.config.settings import SettingsManager


class MainTab:
    """
    Main testing interface tab.
    
    This class implements the main testing screen with pressure gauges,
    timeline, and test controls for the Multi-Chamber Test application.
    It provides a user-friendly interface to monitor and control the
    testing process across multiple chambers.
    """
    
    def __init__(self, parent, test_manager: TestManager, settings_manager: SettingsManager):
        """
        Initialize the MainTab with the parent widget and TestManager.
        
        Args:
            parent: Parent widget (typically a Frame in main_window.py)
            test_manager: TestManager instance for test control
        """
        self.logger = logging.getLogger('MainTab')
        self._setup_logger()
       
        self.parent = parent
        self.test_manager = test_manager
        self.settings_manager = settings_manager
        self.settings_manager.register_observer(self.on_setting_changed)

        # Store colors for easy access
        self.colors = UI_COLORS

        # Set up internal state variables
        self.test_running = False
        self.test_state = tk.StringVar(value="IDLE")
        self.current_reference = tk.StringVar(value="")
        self.barcode_var = tk.StringVar()
        
        # Set up variable traces
        self.test_state.trace_add('write', self._handle_state_change)
        
        # Setup TTK styles
        self._setup_styles()
        
        # Main container frame
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create UI components
        self.create_status_section()
        self.create_reference_section()
        self.create_chamber_gauges()
        self.create_timeline()
        self.create_control_buttons()
        
        # Register callbacks with test manager
        self.test_manager.set_callbacks(
            status_callback=self.update_status,
            progress_callback=self.update_progress,
            result_callback=self.show_test_results
        )
        
        # Initialize the UI with current test state
        self.update_all()
        
        # Schedule regular UI updates
        self._start_ui_updates()

    
    def _setup_logger(self):
        """Configure logging for the main tab."""
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
        
        # Status background styles
        style.configure(
            'StatusBg.TFrame',
            background=UI_COLORS['STATUS_BG']
        )
        style.configure(
            'StatusRunning.TFrame',
            background=UI_COLORS['PRIMARY']
        )
        style.configure(
            'StatusWarning.TFrame',
            background=UI_COLORS['WARNING']
        )
        style.configure(
            'StatusSuccess.TFrame',
            background=UI_COLORS['SUCCESS']
        )
        style.configure(
            'StatusError.TFrame',
            background=UI_COLORS['ERROR']
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
            'Status.TLabel',
            background=UI_COLORS['STATUS_BG'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['SUBHEADER']
        )
        style.configure(
            'StatusRunning.TLabel',
            background=UI_COLORS['PRIMARY'],
            foreground=UI_COLORS['SECONDARY'],
            font=UI_FONTS['SUBHEADER']
        )
        style.configure(
            'StatusWarning.TLabel',
            background=UI_COLORS['WARNING'],
            foreground=UI_COLORS['SECONDARY'],
            font=UI_FONTS['SUBHEADER']
        )
        style.configure(
            'StatusSuccess.TLabel',
            background=UI_COLORS['SUCCESS'],
            foreground=UI_COLORS['SECONDARY'],
            font=UI_FONTS['SUBHEADER']
        )
        style.configure(
            'StatusError.TLabel',
            background=UI_COLORS['ERROR'],
            foreground=UI_COLORS['SECONDARY'],
            font=UI_FONTS['SUBHEADER']
        )
        style.configure(
            'GaugeTitle.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['SUBHEADER'],
            anchor='center'
        )
        style.configure(
            'Value.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['VALUE']
        )
        
        # Button styles
        style.configure(
            'Action.TButton',
            font=UI_FONTS['BUTTON'],
            background=UI_COLORS['PRIMARY'],
            foreground=UI_COLORS['SECONDARY']
        )
        style.map(
            'Action.TButton',
            background=[('active', UI_COLORS['PRIMARY'])],
            foreground=[('active', UI_COLORS['SECONDARY'])]
        )
        
        style.configure(
            'Warning.TButton',
            font=UI_FONTS['BUTTON'],
            background=UI_COLORS['ERROR'],
            foreground=UI_COLORS['SECONDARY']
        )
        style.map(
            'Warning.TButton',
            background=[('active', UI_COLORS['ERROR'])],
            foreground=[('active', UI_COLORS['SECONDARY'])]
        )
    
    def create_status_section(self):
        """Create the status display section."""
        status_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status title removed
        
        # Status message with colored background
        status_container = ttk.Frame(status_frame, padding=15)
        status_container.pack(fill=tk.X, pady=(0, 10))
        
        # Status message with dynamic background
        self.status_bg_frame = ttk.Frame(
            status_container,
            style='StatusBg.TFrame',
            padding=10
        )
        self.status_bg_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(
            self.status_bg_frame,
            text=TEST_STATES["IDLE"],
            style='Status.TLabel',
            anchor=tk.CENTER
        )
        self.status_label.pack(fill=tk.X)
    
    def create_reference_section(self):
        """Create the reference selection and barcode scanning section."""
        self.ref_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        self.ref_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Get the current test mode from settings
        test_mode = self.settings_manager.get_setting('test_mode', "reference")
        
        # Title removed
        
        # Description text about the current mode
        description_frame = ttk.Frame(self.ref_frame, padding=(15, 10))
        description_frame.pack(fill=tk.X)
        
        description_text = "Scan a barcode to load test parameters." if test_mode == "reference" else "Using chamber parameters from settings."
        
        ttk.Label(
            description_frame,
            text=description_text,
            style='CardText.TLabel'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Reference barcode section (only shown in reference mode)
        if test_mode == "reference":
            self.barcode_frame = ttk.Frame(self.ref_frame, padding=(15, 5, 15, 10))
            self.barcode_frame.pack(fill=tk.X)
            
            self.ref_label = ttk.Label(
                self.barcode_frame,
                text="Scan Reference Barcode:",
                style='CardText.TLabel'
            )
            self.ref_label.pack(side=tk.LEFT, padx=(0, 10))
            
            self.barcode_entry = ttk.Entry(
                self.barcode_frame,
                textvariable=self.barcode_var,
                width=30,
                font=UI_FONTS['VALUE']
            )
            self.barcode_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
            
            # Bind Return key to handle barcode scan
            self.barcode_entry.bind('<Return>', self.handle_barcode_scan)
            
            # Set focus to barcode entry for immediate scanning
            self.barcode_entry.focus_set()
        
        # Current reference display (initially hidden)
        self.ref_display_frame = ttk.Frame(self.ref_frame, padding=(15, 5, 15, 10))
        # Don't pack yet - controlled by reference value
        
        ttk.Label(
            self.ref_display_frame,
            text="Current Reference:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.ref_value_label = ttk.Label(
            self.ref_display_frame,
            textvariable=self.current_reference,
            style='Value.TLabel'
        )
        self.ref_value_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Show current reference if available
        if self.current_reference.get():
            self.ref_display_frame.pack(fill=tk.X)
    
    def create_chamber_gauges(self):
        """Create the pressure gauges for all chambers."""
        # Main container for all gauges
        gauges_container = ttk.Frame(self.main_frame, style='Card.TFrame')
        gauges_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Title
        ttk.Label(
            gauges_container,
            text="Chamber Pressure Monitoring",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Gauge content frame
        self.gauges_frame = ttk.Frame(gauges_container, padding=15)
        self.gauges_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid columns to be equal width
        self.gauges_frame.columnconfigure(0, weight=1)
        self.gauges_frame.columnconfigure(1, weight=1)
        self.gauges_frame.columnconfigure(2, weight=1)
        
        # Create gauges for each chamber
        self.chamber_frames = []
        self.pressure_gauges = []
        
        for i in range(3):
            # Gauge frame
            chamber_frame = ttk.Frame(self.gauges_frame)
            chamber_frame.grid(row=0, column=i, sticky='nsew', padx=10)
            
            # Chamber title
            ttk.Label(
                chamber_frame,
                text=f"Chamber {i+1}",
                style='GaugeTitle.TLabel'
            ).pack(pady=(0, 5))
            
            # Pressure gauge (Canvas)
            gauge_canvas = tk.Canvas(
                chamber_frame,
                width=UI_DIMENSIONS['GAUGE_SIZE'],
                height=UI_DIMENSIONS['GAUGE_SIZE'],
                bg=UI_COLORS['BACKGROUND'],
                highlightthickness=0
            )
            gauge_canvas.pack(pady=5)
            
            # Store references
            self.chamber_frames.append(chamber_frame)
            self.pressure_gauges.append(gauge_canvas)
            
            # Initial draw
            self.draw_pressure_gauge(i, 0)
    
    def create_timeline(self):
        """Create the test timeline visualization."""
        timeline_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        timeline_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        ttk.Label(
            timeline_frame,
            text="Test Progress",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Timeline content
        timeline_content = ttk.Frame(timeline_frame, padding=15)
        timeline_content.pack(fill=tk.X)
        
        # Timeline canvas
        self.timeline_canvas = tk.Canvas(
            timeline_content,
            height=UI_DIMENSIONS['TIMELINE_HEIGHT'],
            bg=UI_COLORS['BACKGROUND'],
            highlightthickness=0
        )
        self.timeline_canvas.pack(fill=tk.X, expand=True)
        
        # Initial draw
        self.draw_timeline(0, 0)
    
    def create_control_buttons(self):
        """Create the test control buttons."""
        buttons_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        buttons_frame.pack(fill=tk.X)
        
        # Button container with padding
        button_container = ttk.Frame(buttons_frame, padding=15)
        button_container.pack(fill=tk.X)
        
        # Start Test button
        self.start_button = ttk.Button(
            button_container,
            text="Start Test",
            command=self.start_test,
            style='Action.TButton',
            width=UI_DIMENSIONS['BUTTON_WIDTH']
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop Test button (initially disabled)
        self.stop_button = ttk.Button(
            button_container,
            text="Stop Test",
            command=self.stop_test,
            style='Warning.TButton',
            width=UI_DIMENSIONS['BUTTON_WIDTH'],
            state='disabled'
        )
        self.stop_button.pack(side=tk.LEFT)
    
    def _handle_state_change(self, *args):
        """
        Handle changes in test state with proper UI updates.
        
        Args:
            *args: Variable trace arguments (not used)
        """
        state = self.test_state.get()
        
        # Update status label based on state
        if state in TEST_STATES:
            self.status_label.config(text=TEST_STATES[state])
        
        # Update status colors based on state
        if state == "IDLE":
            self.status_bg_frame.configure(style='StatusBg.TFrame')
            self.status_label.configure(style='Status.TLabel')
        elif state in ["FILLING", "REGULATING", "STABILIZING", "TESTING"]:
            self.status_bg_frame.configure(style='StatusRunning.TFrame')
            self.status_label.configure(style='StatusRunning.TLabel')
        elif state == "EMPTYING":
            self.status_bg_frame.configure(style='StatusWarning.TFrame')
            self.status_label.configure(style='StatusWarning.TLabel')
        elif state == "COMPLETE":
            self.status_bg_frame.configure(style='StatusSuccess.TFrame')
            self.status_label.configure(style='StatusSuccess.TLabel')
        elif state == "ERROR":
            self.status_bg_frame.configure(style='StatusError.TFrame')
            self.status_label.configure(style='StatusError.TLabel')
        
        # Update button states based on test state
        if state in ["IDLE", "COMPLETE", "ERROR"]:
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.test_running = False
        else:
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.test_running = True
    
    def handle_barcode_scan(self, event=None):
        """
        Handle barcode scanner input.
        
        Args:
            event: Event data (not used)
        """
        barcode = self.barcode_var.get().strip()
        if not barcode:
            self.logger.warning("Empty barcode scanned")
            return
        
        # Try to load the reference
        success = self.test_manager.set_test_mode("reference", barcode)
        
        if success:
            # Update UI
            self.current_reference.set(barcode)
            self.ref_display_frame.pack(fill=tk.X)
            
            # Clear barcode field for next scan
            self.barcode_var.set("")
            
            # Show success message
            self.update_status("IDLE", f"Reference {barcode} loaded successfully")
        else:
            # Show error and clear field
            self.barcode_var.set("")
            self.update_status("ERROR", f"Reference {barcode} not found or invalid")
    
    def draw_pressure_gauge(self, chamber_index: int, pressure: float, target: float = None, threshold: float = None):
        """
        Draw an enhanced pressure gauge for a chamber with visual feedback, optimized for 1920x1080 displays.
        
        Args:
            chamber_index: Index of the chamber (0-2)
            pressure: Current pressure reading
            target: Target pressure value (optional)
            threshold: Threshold pressure value (optional)
        """
        canvas = self.pressure_gauges[chamber_index]
        canvas.delete("all")
        
        # Get chamber state from test manager
        chamber_state = self.test_manager.chamber_states[chamber_index]
        chamber_target = target if target is not None else chamber_state.pressure_target
        chamber_threshold = threshold if threshold is not None else chamber_state.pressure_threshold
        chamber_tolerance = chamber_state.pressure_tolerance
        
        # Constants for gauge dimensions - larger for HD displays
        GAUGE_SIZE = UI_DIMENSIONS['GAUGE_SIZE']  # Now larger, defined in constants.py
        CENTER_X, CENTER_Y = GAUGE_SIZE // 2, GAUGE_SIZE // 2
        RADIUS = (GAUGE_SIZE // 2) - 15  # Slightly reduced to provide more space between gauges
        INNER_RADIUS = RADIUS - 25  # Increased inner margin for larger displays
        MAX_PRESSURE = PRESSURE_DEFAULTS['MAX_PRESSURE']
        
        # 1. Draw layered background for depth effect with more subtle shadows
        for i in range(3):
            offset = i + 1
            canvas.create_oval(
                CENTER_X - RADIUS + offset,
                CENTER_Y - RADIUS + offset,
                CENTER_X + RADIUS + offset,
                CENTER_Y + RADIUS + offset,
                fill='', outline=UI_COLORS['BORDER'],
                width=1  # Thinner shadow lines for cleaner appearance
            )
        
        # 2. Draw main gauge background
        background_color = UI_COLORS['BACKGROUND'] if chamber_state.enabled else '#F5F5F5'
        canvas.create_oval(
            CENTER_X - RADIUS,
            CENTER_Y - RADIUS,
            CENTER_X + RADIUS,
            CENTER_Y + RADIUS,
            fill=background_color,
            outline=UI_COLORS['BORDER'],
            width=2
        )
        
        # Skip the rest if chamber is disabled
        if not chamber_state.enabled:
            canvas.create_text(
                CENTER_X,
                CENTER_Y - 10,
                text="Disabled",
                font=UI_FONTS['SUBHEADER'],
                fill=UI_COLORS['TEXT_SECONDARY']
            )
            return
        
        # 3. Draw tolerance zone background
        tolerance_start = chamber_target - chamber_tolerance
        tolerance_end = chamber_target + chamber_tolerance
        tolerance_start_angle = 150 - (tolerance_start * 300 / MAX_PRESSURE)
        tolerance_end_angle = 150 - (tolerance_end * 300 / MAX_PRESSURE)
        
        canvas.create_arc(
            CENTER_X - RADIUS,
            CENTER_Y - RADIUS,
            CENTER_X + RADIUS,
            CENTER_Y + RADIUS,
            start=tolerance_start_angle,
            extent=tolerance_end_angle - tolerance_start_angle,
            fill='#E8F5E9',  # Light green background for tolerance zone
            outline=''
        )
        
        # 4. Draw main scale arc
        canvas.create_arc(
            CENTER_X - RADIUS,
            CENTER_Y - RADIUS,
            CENTER_X + RADIUS,
            CENTER_Y + RADIUS,
            start=150,
            extent=-300,
            style=tk.ARC,
            outline=UI_COLORS['BORDER'],
            width=14  # Slightly thicker for HD displays
        )
        
        # 5. Draw scale markers and labels - MORE markers for better precision
        # Major ticks at 100 mbar intervals
        for i in range(0, MAX_PRESSURE + 1, 100):
            angle = 150 - (i * 300 / MAX_PRESSURE)
            radian = math.radians(angle)
            
            # Draw major tick marks
            cos_val = math.cos(radian)
            sin_val = math.sin(radian)
            
            canvas.create_line(
                CENTER_X + INNER_RADIUS * cos_val,
                CENTER_Y - INNER_RADIUS * sin_val,
                CENTER_X + RADIUS * cos_val,
                CENTER_Y - RADIUS * sin_val,
                fill=UI_COLORS['TEXT_PRIMARY'],
                width=3  # Thicker major ticks
            )
            
            # Draw label
            label_radius = INNER_RADIUS - 22  # Pushed further in for clarity
            canvas.create_text(
                CENTER_X + label_radius * cos_val,
                CENTER_Y - label_radius * sin_val,
                text=str(i),
                font=UI_FONTS['GAUGE_UNIT'],
                fill=UI_COLORS['TEXT_PRIMARY']
            )
        
        # Minor ticks at 50 mbar intervals (between major ticks)
        for i in range(50, MAX_PRESSURE, 100):
            angle = 150 - (i * 300 / MAX_PRESSURE)
            radian = math.radians(angle)
            
            # Draw minor tick marks
            cos_val = math.cos(radian)
            sin_val = math.sin(radian)
            
            tick_start_radius = INNER_RADIUS + 10  # Shorter minor ticks
            canvas.create_line(
                CENTER_X + tick_start_radius * cos_val,
                CENTER_Y - tick_start_radius * sin_val,
                CENTER_X + RADIUS * cos_val,
                CENTER_Y - RADIUS * sin_val,
                fill=UI_COLORS['TEXT_PRIMARY'],
                width=1  # Thinner minor ticks
            )
        
        # Even smaller ticks at 25 mbar intervals for high precision
        for i in range(25, MAX_PRESSURE, 50):
            if i % 100 != 0 and i % 50 != 0:  # Skip points we already drew
                angle = 150 - (i * 300 / MAX_PRESSURE)
                radian = math.radians(angle)
                
                cos_val = math.cos(radian)
                sin_val = math.sin(radian)
                
                tick_start_radius = INNER_RADIUS + 15  # Even shorter mini ticks
                canvas.create_line(
                    CENTER_X + tick_start_radius * cos_val,
                    CENTER_Y - tick_start_radius * sin_val,
                    CENTER_X + RADIUS * cos_val,
                    CENTER_Y - RADIUS * sin_val,
                    fill=UI_COLORS['TEXT_SECONDARY'],  # Lighter color for mini ticks
                    width=1
                )
        
        # 6. Draw target and threshold markers with improved visibility
        target_angle = min(300, (chamber_target * 300 / MAX_PRESSURE))
        threshold_angle = min(300, (chamber_threshold * 300 / MAX_PRESSURE))
        
        for angle, color, width, label in [
            (target_angle, UI_COLORS['SUCCESS'], 3, "Target"),
            (threshold_angle, UI_COLORS['ERROR'], 2, "Min")
        ]:
            radian = math.radians(150 - angle)
            marker_length = 25  # Longer markers
            
            # Draw the marker line
            canvas.create_line(
                CENTER_X + (RADIUS - marker_length) * math.cos(radian),
                CENTER_Y - (RADIUS - marker_length) * math.sin(radian),
                CENTER_X + (RADIUS + 8) * math.cos(radian),
                CENTER_Y - (RADIUS + 8) * math.sin(radian),
                fill=color,
                width=width,
                arrow=tk.LAST,  # Add arrowhead for better visibility
                arrowshape=(10, 12, 5)  # Customize arrow size
            )
            
            # Add small marker label
            if angle > 20 and angle < 280:  # Only show labels if they fit in visible area
                label_radius = RADIUS + 22
                canvas.create_text(
                    CENTER_X + label_radius * math.cos(radian),
                    CENTER_Y - label_radius * math.sin(radian),
                    text=label,
                    font=("Helvetica", 9),
                    fill=color
                )
        
        # 7. Draw pressure indicator arc with improved visual feedback
        current_angle = min(300, (pressure * 300 / MAX_PRESSURE))
        if current_angle > 0:
            # Determine color based on pressure state
            if pressure < chamber_threshold:
                arc_color = UI_COLORS['ERROR']
            elif abs(pressure - chamber_target) <= chamber_tolerance:
                arc_color = UI_COLORS['SUCCESS']
            else:
                arc_color = UI_COLORS['WARNING']
                
            # Draw progress arc
            canvas.create_arc(
                CENTER_X - RADIUS,
                CENTER_Y - RADIUS,
                CENTER_X + RADIUS,
                CENTER_Y + RADIUS,
                start=150,
                extent=-current_angle,
                style=tk.ARC,
                outline=arc_color,
                width=14  # Match main arc width
            )
            
            # Add a needle for precise reading
            needle_radian = math.radians(150 - current_angle)
            needle_cos = math.cos(needle_radian)
            needle_sin = math.sin(needle_radian)
            
            canvas.create_line(
                CENTER_X, CENTER_Y,
                CENTER_X + (RADIUS - 5) * needle_cos,
                CENTER_Y - (RADIUS - 5) * needle_sin,
                fill=arc_color,
                width=2,
                arrow=tk.LAST,
                arrowshape=(8, 10, 3)
            )
        
        # 8. Draw enhanced central display
        display_radius = 40  # Larger central display
        
        # Draw shadow for depth effect
        shadow_offset = 2
        canvas.create_oval(
            CENTER_X - display_radius + shadow_offset,
            CENTER_Y - display_radius + shadow_offset,
            CENTER_X + display_radius + shadow_offset,
            CENTER_Y + display_radius + shadow_offset,
            fill='#E0E0E0',
            outline=''
        )
        
        # Draw main display background
        canvas.create_oval(
            CENTER_X - display_radius,
            CENTER_Y - display_radius,
            CENTER_X + display_radius,
            CENTER_Y + display_radius,
            fill=UI_COLORS['BACKGROUND'],
            outline=UI_COLORS['BORDER'],
            width=2
        )
        
        # 9. Draw pressure value with enhanced typography
        # Use larger font for pressure value
        canvas.create_text(
            CENTER_X,
            CENTER_Y - 12,
            text=f"{pressure:.0f}",
            font=UI_FONTS['GAUGE_VALUE'],
            fill=UI_COLORS['TEXT_PRIMARY']
        )
        
        # Add unit with better spacing
        canvas.create_text(
            CENTER_X,
            CENTER_Y + 16,
            text="mbar",
            font=UI_FONTS['GAUGE_UNIT'],
            fill=UI_COLORS['TEXT_PRIMARY']
        )
        
        # 10. Add current pressure percentage indicator (optional for HD displays)
        percentage = min(100, (pressure / MAX_PRESSURE) * 100)
        
        # Only show if non-zero
        if percentage > 1:
            canvas.create_text(
                CENTER_X,
                CENTER_Y + 36,
                text=f"{percentage:.0f}%",
                font=("Helvetica", 9),
                fill=UI_COLORS['TEXT_SECONDARY']
            )
    
    def draw_timeline(self, elapsed_time: float, total_time: float):
        """
        Draw a timeline visualization showing test progress.
        
        Args:
            elapsed_time: Elapsed time in seconds
            total_time: Total test duration in seconds
        """
        canvas = self.timeline_canvas
        canvas.delete("all")
        
        # Get canvas dimensions
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        # Use default values if not yet packed
        if width < 10:  # Not yet properly sized
            width = 600
        
        # Define visual parameters
        bar_height = 20
        y_center = height / 2
        margin = 20
        usable_width = width - (2 * margin)
        
        # Draw background bar
        canvas.create_rectangle(
            margin, y_center - bar_height / 2,
            width - margin, y_center + bar_height / 2,
            fill='#E0E0E0', outline=UI_COLORS['BORDER']
        )
        
        # Calculate and draw progress
        if total_time > 0:
            progress = min(1.0, elapsed_time / total_time)
            progress_width = usable_width * progress
            
            if progress > 0:
                # Draw progress bar
                canvas.create_rectangle(
                    margin, y_center - bar_height / 2,
                    margin + progress_width, y_center + bar_height / 2,
                    fill=UI_COLORS['PRIMARY']
                )
                
                # Draw progress percentage
                percentage = progress * 100
                if progress_width > 30:  # Only show percentage if there's enough space
                    percentage_text_color = 'white' if percentage > 20 else UI_COLORS['TEXT_PRIMARY']
                    canvas.create_text(
                        margin + progress_width / 2, y_center,
                        text=f"{percentage:.0f}%",
                        fill=percentage_text_color,
                        font=UI_FONTS['LABEL']
                    )
        
        # Draw time markers
        marker_count = 5
        for i in range(marker_count):
            # Calculate marker position
            x = margin + (usable_width * i / (marker_count - 1))
            time_value = total_time * i / (marker_count - 1)
            
            # Draw marker line
            canvas.create_line(
                x, y_center - bar_height / 2 - 5,
                x, y_center + bar_height / 2 + 5,
                fill=UI_COLORS['TEXT_PRIMARY'],
                width=1
            )
            
            # Draw time label
            canvas.create_text(
                x, y_center + bar_height / 2 + 15,
                text=f"{time_value:.0f}s",
                fill=UI_COLORS['TEXT_PRIMARY'],
                font=UI_FONTS['GAUGE_UNIT']
            )
        
        # Draw remaining time if test is running
        if self.test_running and total_time > 0:
            remaining = max(0, total_time - elapsed_time)
            canvas.create_text(
                width - margin, y_center - bar_height / 2 - 15,
                text=f"Remaining: {remaining:.1f}s",
                fill=UI_COLORS['TEXT_PRIMARY'],
                font=UI_FONTS['LABEL'],
                anchor='e'
            )

    def on_setting_changed(self, key: str, value: Any):
        """
        Handle settings changes from settings manager.
        
        This method should be added to the MainTab class to respond to
        settings changes broadcast by the SettingsManager.
        
        Args:
            key: The setting key that changed
            value: The new value
        """
        # Handle specific settings that MainTab cares about
        if key == "test_mode":
            self.logger.info(f"MainTab received updated test_mode: {value}")
            self._rebuild_reference_section()
        
        # Handle test duration changes
        elif key == "test_duration":
            # Only update if different from current value
            if hasattr(self, 'test_mode_var') and hasattr(self.test_mode_var, 'duration_var'):
                current = self.duration_var.get()
                if current != value:
                    self.logger.info(f"Updating test duration display to {value}")
                    self.duration_var.set(value)
        
        # Handle chamber settings changes if main tab displays chamber info
        elif key.startswith('chamber') and '_' in key:
            # Extract chamber number and setting
            parts = key.split('_', 1)
            if len(parts) == 2:
                try:
                    chamber_str = parts[0]
                    chamber_idx = int(chamber_str[7:]) - 1  # Convert from chamber1 to index 0
                    setting_name = parts[1]
                    
                    # Only handle changes we care about for UI display
                    if setting_name in ['enabled', 'pressure_target', 'pressure_threshold', 'pressure_tolerance']:
                        self.logger.debug(f"Updating chamber display for {key}={value}")
                        # Update any UI elements showing chamber info
                        self.update_chamber_display(chamber_idx)
                except (ValueError, IndexError):
                    pass
        
        # Handle bulk chamber updates
        elif key == 'all_chambers':
            self.logger.info("Updating all chamber displays")
            self.update_all()

    def _rebuild_reference_section(self):
        """Recreate the reference section based on current test mode."""
        # Check if we have the section
        if not hasattr(self, 'ref_frame'):
            self.logger.debug("No reference frame to rebuild")
            return
            
        # Get the current mode
        test_mode = self.settings_manager.get_setting('test_mode', "reference")
        self.logger.info(f"Rebuilding reference section for mode: {test_mode}")
        
        # Store any current reference
        current_ref = self.current_reference.get() if hasattr(self, 'current_reference') else ""
        
        # Remember the position of ref_frame in parent's children list
        parent = self.ref_frame.master
        children = parent.winfo_children()
        ref_index = children.index(self.ref_frame)
        
        # Find the widgets before and after ref_frame
        before_widget = children[ref_index - 1] if ref_index > 0 else None
        after_widget = children[ref_index + 1] if ref_index < len(children) - 1 else None
        
        # Destroy existing frame
        self.ref_frame.destroy()
        
        # Create new frame
        self.ref_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        
        # Pack it in the correct position
        if before_widget:
            self.ref_frame.pack(after=before_widget, fill=tk.X, pady=(0, 10))
        elif after_widget:
            self.ref_frame.pack(before=after_widget, fill=tk.X, pady=(0, 10))
        else:
            self.ref_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        ttk.Label(
            self.ref_frame,
            text="Test Reference",
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        # Description text about the current mode
        description_frame = ttk.Frame(self.ref_frame, padding=(15, 10))
        description_frame.pack(fill=tk.X)
        
        description_text = "Scan a barcode to load test parameters." if test_mode == "reference" else "Using chamber parameters from settings."
        
        ttk.Label(
            description_frame,
            text=description_text,
            style='CardText.TLabel'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Reference barcode section (only shown in reference mode)
        if test_mode == "reference":
            self.barcode_frame = ttk.Frame(self.ref_frame, padding=(15, 5, 15, 10))
            self.barcode_frame.pack(fill=tk.X)
            
            self.ref_label = ttk.Label(
                self.barcode_frame,
                text="Scan Reference Barcode:",
                style='CardText.TLabel'
            )
            self.ref_label.pack(side=tk.LEFT, padx=(0, 10))
            
            self.barcode_entry = ttk.Entry(
                self.barcode_frame,
                textvariable=self.barcode_var if hasattr(self, 'barcode_var') else None,
                width=30,
                font=UI_FONTS['VALUE'] if 'UI_FONTS' in globals() else ('Helvetica', 12)
            )
            self.barcode_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
            
            # Bind Return key to handle barcode scan
            if hasattr(self, 'handle_barcode_scan'):
                self.barcode_entry.bind('<Return>', self.handle_barcode_scan)
            
            # Set focus to barcode entry for immediate scanning
            self.barcode_entry.focus_set()
        
        # Current reference display (initially hidden)
        self.ref_display_frame = ttk.Frame(self.ref_frame, padding=(15, 5, 15, 10))
        
        ttk.Label(
            self.ref_display_frame,
            text="Current Reference:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Restore current reference or create new variable
        if not hasattr(self, 'current_reference'):
            self.current_reference = tk.StringVar(value=current_ref)
        
        self.ref_value_label = ttk.Label(
            self.ref_display_frame,
            textvariable=self.current_reference,
            style='Value.TLabel'
        )
        self.ref_value_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Show current reference if available
        if self.current_reference.get():
            self.ref_display_frame.pack(fill=tk.X)
        
        self.logger.info("Reference section rebuilt")
       
    def update_chamber_display(self, chamber_idx):
        """
        Update the display for a specific chamber.
        
        Args:
            chamber_idx: Chamber index (0-2)
        """
        if hasattr(self, 'draw_pressure_gauge') and 0 <= chamber_idx < 3:
            # Get current chamber state from test manager or settings
            chamber_state = None
            settings = None
            
            # Try to get from test manager first
            if hasattr(self, 'test_manager') and hasattr(self.test_manager, 'chamber_states'):
                if chamber_idx < len(self.test_manager.chamber_states):
                    chamber_state = self.test_manager.chamber_states[chamber_idx]
            
            # If no chamber state from test manager, get from settings
            if chamber_state is None and hasattr(self, 'settings_manager'):
                # Settings manager uses 1-based indexing for chambers
                settings = self.settings_manager.get_chamber_settings(chamber_idx + 1)
            
            # Get current pressure (if available)
            current_pressure = 0.0
            if chamber_state and hasattr(chamber_state, 'current_pressure'):
                current_pressure = chamber_state.current_pressure
            
            # Get chamber parameters either from chamber_state or settings
            target = None
            threshold = None
            
            if chamber_state:
                if hasattr(chamber_state, 'pressure_target'):
                    target = chamber_state.pressure_target
                if hasattr(chamber_state, 'pressure_threshold'):
                    threshold = chamber_state.pressure_threshold
            elif settings:
                target = settings.get('pressure_target')
                threshold = settings.get('pressure_threshold')
            
            # Update the gauge with new values
            self.draw_pressure_gauge(chamber_idx, current_pressure, target, threshold)
            
            self.logger.debug(f"Updated chamber {chamber_idx+1} display")

    def start_test(self):
        """Start a test with the current parameters."""
        if self.test_running:
            self.logger.warning("Test already in progress")
            return
        
        # Get current test mode from settings
        test_mode = self.settings_manager.get_setting('test_mode', "reference")
        
        # If in reference mode, we need a reference to be loaded
        if test_mode == "reference" and not self.current_reference.get():
            self.update_status("ERROR", "Please scan a reference barcode before starting the test")
            return
        
        # Start the test
        success = self.test_manager.start_test()
        
        if not success:
            self.logger.error("Failed to start test")
            self.update_status("ERROR", "Failed to start test")
            return
        
        # UI updates will be handled by callbacks from test_manager
    
    def stop_test(self):
        """Stop the current test."""
        if not self.test_running:
            self.logger.warning("No test running")
            return
        
        # Stop the test
        self.test_manager.stop_test()
        
        # UI updates will be handled by callbacks from test_manager
    
    def update_status(self, state: str, message: Optional[str] = None):
        """
        Update the status display.
        
        Args:
            state: New test state
            message: Optional custom message
        """
        # Update state variable (triggers _handle_state_change)
        self.test_state.set(state)
        
        # Use custom message if provided
        if message:
            self.status_label.config(text=message)
    
    def update_progress(self, phase: str, progress: float, phase_data: Dict[str, Any] = None):
        """
        Update the progress display.
        
        Args:
            phase: Current test phase
            progress: Overall progress (0-1)
            phase_data: Phase-specific data
        """
        if not phase_data:
            phase_data = {}
        
        # Update timeline
        if 'elapsed_time' in phase_data and 'total_time' in phase_data:
            self.draw_timeline(phase_data['elapsed_time'], phase_data['total_time'])
        elif phase == 'testing' and 'elapsed_time' in phase_data:
            self.draw_timeline(phase_data['elapsed_time'], self.test_manager.test_duration.get())
    
    def show_test_results(self, overall_result: bool, chamber_results: List[Dict[str, Any]]):
        """
        Display test results after completion.
        
        Args:
            overall_result: Overall test result (pass/fail)
            chamber_results: List of per-chamber results
        """
        # Update status with result
        result_text = "PASS" if overall_result else "FAIL"
        self.update_status(
            "COMPLETE",
            f"Test Complete - {result_text}"
        )
        
        # Update chamber gauges with final values
        for result in chamber_results:
            chamber_index = result.get('chamber_id', 0)
            if 0 <= chamber_index < 3:
                final_pressure = result.get('final_pressure', 0)
                self.draw_pressure_gauge(chamber_index, final_pressure)
    
    def update_all(self):
        """Update all UI elements with current test state."""
        # Get current test status
        test_status = self.test_manager.get_test_status()
        
        # Update test state
        self.test_state.set(test_status['test_state'])
        
        # Get the current test mode from settings
        test_mode = self.settings_manager.get_setting('test_mode', "reference")
        
        # Ensure test mode in test manager matches settings (in case we just opened the app)
        if test_status['test_mode'] != test_mode:
            # Only set basic mode without reference
            self.test_manager.set_test_mode(test_mode)
        
        # Update reference
        if test_status['reference']:
            self.current_reference.set(test_status['reference'])
            self.ref_display_frame.pack(fill=tk.X)
        
        # Update chamber gauges
        for i, chamber_info in enumerate(test_status['chambers']):
            if i < len(self.pressure_gauges):
                self.draw_pressure_gauge(
                    i,
                    chamber_info['current_pressure'],
                    chamber_info['pressure_target'],
                    chamber_info['pressure_threshold']
                )
        
        # Update timeline
        self.draw_timeline(
            test_status.get('elapsed_time', 0),
            test_status.get('total_duration', self.test_manager.test_duration)
        )
        
        # Update button states
        if test_status['running']:
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.test_running = True
        else:
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.test_running = False
    
    def _start_ui_updates(self):
        """Start regular UI updates."""
        self._update_ui_elements()
    
    def _update_ui_elements(self):
        """Update UI elements with current data from test manager."""
        if self.test_running:
            # Get current test status
            test_status = self.test_manager.get_test_status()
            
            # Update chamber gauges
            for i, chamber_info in enumerate(test_status['chambers']):
                if i < len(self.pressure_gauges):
                    self.draw_pressure_gauge(
                        i,
                        chamber_info['current_pressure']
                    )
            
            # Update timeline
            self.draw_timeline(
                test_status.get('elapsed_time', 0),
                test_status.get('total_duration', self.test_manager.test_duration.get())
            )
        
        # Schedule next update after 100ms
        self.parent.after(100, self._update_ui_elements)
    
    def on_tab_selected(self):
        """Called when this tab is selected."""
        # Update the UI with current test state
        self.update_all()
        
        # If in reference mode, focus on barcode entry for quick scanning
        test_mode = self.settings_manager.get_setting('test_mode', "reference")
        if test_mode == "reference" and hasattr(self, 'barcode_entry'):
            self.barcode_entry.focus_set()
    
    def on_tab_deselected(self):
        """Called when user switches away from this tab."""
        # Any cleanup or state saving can go here
        pass
    
    def handle_parameter_change(self):
        """Handle changes to test parameters."""
        # Reset the gauges with new parameters
        self.update_all()
    
    def reset(self):
        """Reset the UI state."""
        # Reset test state
        self.test_state.set("IDLE")
        
        # Reset gauges
        for i in range(len(self.pressure_gauges)):
            self.draw_pressure_gauge(i, 0)
        
        # Reset timeline
        self.draw_timeline(0, 0)
        
        # Reset buttons
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        
        # Reset flags
        self.test_running = False